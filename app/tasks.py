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
        logger.info(f"Created {len(chunks)} chunks")

        # Get user-specific collection if user_id provided, otherwise use default
        collection_name = f"user_{user_id}_docs" if user_id else "default_docs"
        collection = get_collection(collection_name)
        if collection is None:
            raise ValueError(f"Failed to get ChromaDB collection: {collection_name}")

        total_chunks = len(chunks)
        processed_chunks = 0
        chunk_ids = []
        logger.info(f"Total chunks to process: {total_chunks}")

        # Process chunks in batches
        for start_idx in range(0, total_chunks, BATCH_SIZE):
            batch_chunks = chunks[start_idx : start_idx + BATCH_SIZE]
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
                # Add chunks to ChromaDB
                ids = collection.add_texts(
                    texts=batch_chunks, 
                    metadatas=batch_metadatas, 
                    ids=batch_ids
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
