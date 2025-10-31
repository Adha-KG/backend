import logging
import uuid
from app.celery_app import celery
from app.services.chunker import chunk_text
from app.services.pdf_loader import extract_text_from_pdf
from embeddings import EmbeddingService  # updated service we built
from langchain_chroma import Chroma
from langchain_core.documents import Document
from chromadb.config import Settings

logger = logging.getLogger(__name__)
BATCH_SIZE = 50

# Initialize embedding service (sync for Celery)
embeddings = EmbeddingService()

def get_vectorstore(collection_name="pdf_chunks"):
    """
    Return a LangChain Chroma vectorstore connected to local Chroma DB.
    """
    return Chroma(
        collection_name=collection_name,
        persist_directory="./chroma_db",
        embedding_function=embeddings.embedding_model,
        client_settings=Settings(anonymized_telemetry=False)
    )


@celery.task(bind=True)
def process_pdf(self, file_path: str, collection_name="pdf_chunks"):
    """
    Process PDF → chunk → embed → save into Chroma (via LangChain).
    Synchronous version for Celery workers.
    """
    logger.info(f"Processing PDF: {file_path}")

    try:
        # Extract text
        documents = extract_text_from_pdf(file_path)
        if not documents:
            raise ValueError(f"No text extracted from PDF: {file_path}")

        text = " ".join(doc.page_content for doc in documents)
        if not text.strip():
            raise ValueError(f"No text extracted from PDF: {file_path}")

        logger.info(f"Extracted text length: {len(text)}")

        # Split into chunks
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("No chunks created from text")

        logger.info(f"Created {len(chunks)} chunks")

        # Initialize vectorstore
        vectorstore = get_vectorstore(collection_name)
        total_chunks = len(chunks)
        processed_chunks = 0

        logger.info(f"Total chunks to process: {total_chunks}")

        # Process in batches
        for start_idx in range(0, total_chunks, BATCH_SIZE):
            batch_chunks = chunks[start_idx:start_idx + BATCH_SIZE]
            batch_size = len(batch_chunks)

            logger.info(f"Processing batch {start_idx//BATCH_SIZE + 1}: {batch_size} chunks")

            # Wrap each chunk into a Document (LangChain format)
            batch_docs = [
                Document(
                    page_content=chunk,
                    metadata={
                        "source": file_path,
                        "chunk_id": f"{file_path}-{start_idx + i}-{uuid.uuid4()}"
                    }
                )
                for i, chunk in enumerate(batch_chunks)
            ]

            try:
                vectorstore.add_documents(batch_docs)
                processed_chunks += batch_size
                logger.info(f"Saved batch {start_idx//BATCH_SIZE + 1} to ChromaDB")
            except Exception as e:
                logger.exception(f"Failed to save batch to ChromaDB: {e}")
                raise

            # Update Celery task progress
            self.update_state(
                state="PROGRESS",
                meta={"processed": processed_chunks, "total": total_chunks}
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
