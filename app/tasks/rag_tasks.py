# app/tasks.py
import asyncio
import logging
import os
import uuid

from app.celery_app import celery
from app.services.chunker import chunk_text
from app.services.pdf_loader import extract_text_from_pdf
from app.services.vectorstore import get_collection

logger = logging.getLogger(__name__)

BATCH_SIZE = 50

@celery.task(bind=True)
def process_pdf(
    self,
    file_path: str,
    original_filename: str = None,
    unique_filename: str = None,
    user_id: str = None,           # Add this parameter
    document_id: str = None        # Add this parameter
):
    """
    Enhanced PDF processing with user context and database updates
    """
    logger.info(f"Processing PDF: {file_path} for user: {user_id}")

    # Extract original filename if not provided
    if not original_filename:
        original_filename = os.path.basename(file_path)

    if not unique_filename:
        unique_filename = file_path

    try:
        # Update document status to processing if document_id provided
        if document_id:
            try:
                # Import here to avoid circular imports
                from app.services.document_service import update_document_status
                asyncio.run(update_document_status(document_id, 'processing'))
                logger.info(f"Updated document {document_id} status to processing")
            except Exception as e:
                logger.warning(f"Could not update document status to processing: {e}")

        # Extract text from PDF
        documents = extract_text_from_pdf(file_path)
        if not documents:
            raise ValueError(f"No text extracted from PDF: {file_path}")

        text = " ".join(doc.page_content for doc in documents)
        if not text.strip():
            raise ValueError(f"No text extracted from PDF: {file_path}")
        logger.info(f"Extracted text length: {len(text)}")

        # Chunk the text
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("No chunks created from text")

        # Ensure all chunks are valid strings and clean Unicode issues
        cleaned_chunks = []
        for chunk in chunks:
            if not chunk or not str(chunk).strip():
                continue

            # Clean Unicode - remove surrogates and normalize
            try:
                # Remove surrogate pairs (common in poorly extracted PDFs)
                clean_chunk = chunk.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
                # Remove any remaining non-printable or problematic characters
                clean_chunk = ''.join(char for char in clean_chunk if char.isprintable() or char in '\n\r\t ')
                clean_chunk = clean_chunk.strip()

                if clean_chunk:
                    cleaned_chunks.append(clean_chunk)
            except Exception as e:
                logger.warning(f"Failed to clean chunk: {e}, skipping")
                continue

        if not cleaned_chunks:
            raise ValueError("No valid chunks created from text after filtering and cleaning")

        logger.info(f"Created {len(cleaned_chunks)} valid chunks (cleaned from {len(chunks)} raw chunks)")

        # Get user-specific collection if user_id provided, otherwise use default
        collection_name = f"user_{user_id}_docs" if user_id else "default_docs"
        collection = get_collection(collection_name)
        if collection is None:
            raise ValueError(f"Failed to get ChromaDB collection: {collection_name}")

        total_chunks = len(cleaned_chunks)
        processed_chunks = 0
        chunk_ids = []
        logger.info(f"Total chunks to process: {total_chunks}")

        # Process chunks in batches
        for start_idx in range(0, total_chunks, BATCH_SIZE):
            batch_chunks = cleaned_chunks[start_idx : start_idx + BATCH_SIZE]
            batch_size = len(batch_chunks)

            logger.info(
                f"Processing batch {start_idx // BATCH_SIZE + 1}: {batch_size} chunks"
            )

            # Generate unique IDs for each chunk
            batch_ids = [
                f"{unique_filename}-{start_idx + i}-{uuid.uuid4().hex[:8]}" 
                for i in range(batch_size)
            ]
            # Store chunk IDs for database update
            chunk_ids.extend(batch_ids)

            # Create metadata for each chunk
            batch_metadatas = [
                {
                    "source": file_path,
                    "original_filename": original_filename,
                    "unique_filename": unique_filename,
                    "user_id": user_id,
                    "document_id": document_id,
                    "chunk_index": start_idx + i,
                    "batch": start_idx // BATCH_SIZE + 1,
                    "total_chunks": total_chunks,
                    "chunk_length": len(batch_chunks[i]),
                }
                for i in range(batch_size)
            ]

            try:
                # Validate and ensure all batch chunks are proper strings
                validated_chunks = []
                for chunk in batch_chunks:
                    if not isinstance(chunk, str):
                        logger.warning(f"Non-string chunk detected: {type(chunk)}, converting to string")
                        chunk = str(chunk)
                    if not chunk.strip():
                        logger.warning("Empty chunk detected, skipping")
                        continue
                    validated_chunks.append(chunk.strip())

                if not validated_chunks:
                    logger.error("No valid chunks in batch after validation")
                    continue

                # Debug logging
                logger.info(f"About to add {len(validated_chunks)} chunks to ChromaDB")
                logger.info(f"Chunk types: {[type(c).__name__ for c in validated_chunks[:3]]}")
                logger.info(f"First chunk preview: {repr(validated_chunks[0][:100]) if validated_chunks else 'N/A'}")

                # Final safety check - ensure texts is a proper list of strings
                # Convert to list explicitly to avoid any iterator/generator issues
                safe_texts = list(validated_chunks)

                # Verify all are strings
                for i, chunk in enumerate(safe_texts):
                    if not isinstance(chunk, str):
                        logger.error(f"Chunk {i} is not a string: {type(chunk)}")
                        raise TypeError(f"Invalid chunk type at index {i}: {type(chunk)}")

                logger.info(f"Safe texts count: {len(safe_texts)}, type: {type(safe_texts)}")

                # Add chunks to ChromaDB - pass as standard list
                ids = collection.add_texts(
                    texts=safe_texts,
                    metadatas=list(batch_metadatas[:len(safe_texts)]),
                    ids=list(batch_ids[:len(safe_texts)])
                )
                processed_chunks += batch_size
                logger.info(
                    f"Saved batch {start_idx // BATCH_SIZE + 1} to ChromaDB with {len(ids)} documents"
                )
            except Exception as e:
                logger.exception(f"Failed to save batch to ChromaDB: {e}")
                raise

            # Update task progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "processed": processed_chunks, 
                    "total": total_chunks,
                    "status": f"Processing batch {start_idx // BATCH_SIZE + 1}"
                },
            )

        # Update document status to completed if document_id provided
        if document_id:
            try:
                from app.services.document_service import update_document_status
                asyncio.run(update_document_status(
                    document_id,
                    'completed',
                    chunk_ids=chunk_ids,
                    total_chunks=total_chunks
                ))
                logger.info(f"Updated document {document_id} status to completed")
            except Exception as e:
                logger.warning(f"Could not update document status to completed: {e}")

        logger.info(
            f"PDF {file_path} fully processed - {processed_chunks} chunks saved for user {user_id}"
        )
        return {
            "message": f"PDF {original_filename or file_path} processed successfully",
            "processed_chunks": processed_chunks,
            "total_chunks": total_chunks,
            "user_id": user_id,
            "document_id": document_id,
            "chunk_ids": chunk_ids[:10],  # Return first 10 chunk IDs for reference
            "collection_name": collection_name
        }

    except Exception as e:
        # Update document status to failed if document_id provided
        if document_id:
            try:
                from app.services.document_service import update_document_status
                asyncio.run(update_document_status(
                    document_id,
                    'failed',
                    error=str(e)
                ))
                logger.info(f"Updated document {document_id} status to failed")
            except Exception as update_e:
                logger.warning(f"Could not update document status to failed: {update_e}")
        logger.exception(f"Failed to process PDF {file_path}: {e}")
        raise
