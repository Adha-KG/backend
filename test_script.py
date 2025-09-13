import logging
import uuid

from app.celery_app import celery
from app.services.chunker import chunk_text

# Use the sync embedding function
from app.services.embeddings import get_embedding_sync
from app.services.pdf_loader import extract_text_from_pdf
from app.services.vectorstore import get_collection

logger = logging.getLogger(__name__)

BATCH_SIZE = 50

@celery.task(bind=True)
def process_pdf(self, file_path: str):
    """
    Synchronous version of PDF processing - no asyncio
    """
    logger.info(f"Processing PDF: {file_path}")

    try:
        # Extract and validate text
        documents = extract_text_from_pdf(file_path)
        if not documents:
            raise ValueError(f"No text extracted from PDF: {file_path}")

        text = " ".join(doc.page_content for doc in documents)
        if  not text.strip():
            raise ValueError(f"No text extracted from PDF: {file_path}")
        logger.info(f"Extracted text length: {len(text)}")

        string = 'test'
        embedding = get_embedding_sync(string)
        logger.info("Generated test embedding of length")
        # Chunk and validate
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("No chunks created from text")
        logger.info(f"Created {len(chunks)} chunks")

        # Get collection
        collection = get_collection()
        if collection is None:
            raise ValueError("Failed to get ChromaDB collection")

        total_chunks = len(chunks)
        processed_chunks = 0
        logger.info(f"Total chunks to process: {total_chunks}")
        # Process in batches
        for start_idx in range(0, total_chunks, BATCH_SIZE):
            batch_chunks = chunks[start_idx:start_idx + BATCH_SIZE]
            batch_size = len(batch_chunks)

            logger.info(f"Processing batch {start_idx//BATCH_SIZE + 1}: {batch_size} chunks")

            # Generate embeddings synchronously
            embeddings = []
            for i, chunk in enumerate(batch_chunks):
                try:
                    embedding = get_embedding_sync(chunk)
                    embeddings.append(embedding)
                    logger.debug(f"Generated embedding {i+1}/{batch_size}")
                except Exception as e:
                    logger.exception(f"Failed to generate embedding for chunk {i}: {e}")
                    raise

            # Validate embeddings
            if len(embeddings) != len(batch_chunks):
                raise ValueError(f"Embedding count mismatch: {len(embeddings)} vs {len(batch_chunks)}")

            # Generate IDs and save
            batch_ids = [f"{file_path}-{start_idx + i}-{uuid.uuid4()}" for i in range(batch_size)]

            try:
                collection.add(
                    documents=batch_chunks,
                    embeddings=embeddings,
                    ids=batch_ids
                )
                processed_chunks += batch_size
                logger.info(f"Saved batch {start_idx//BATCH_SIZE + 1} to ChromaDB")
            except Exception as e:
                logger.exception(f"Failed to save batch to ChromaDB: {e}")
                raise

            # Update progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "processed": processed_chunks,
                    "total": total_chunks
                }
            )

        logger.info(f"PDF {file_path} fully processed - {processed_chunks} chunks saved")
        return {
            "message": f"PDF {file_path} processed successfully",
            "processed_chunks": processed_chunks,
            "total_chunks": total_chunks
        }

    except Exception as e:
        logger.exception(f"Failed to process PDF {file_path}: {e}")
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise
