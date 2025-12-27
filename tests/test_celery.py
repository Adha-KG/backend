"""Test Celery task functionality."""
import asyncio
import logging
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.embeddings import get_embedding, get_embedding_sync
from app.services.vectorstore import get_chroma_client, get_collection

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@pytest.mark.celery
def test_celery_task_execution():
    """Test basic Celery task execution."""
    from app.tasks.rag_tasks import process_pdf

    # This test requires a running Celery worker
    # In CI/CD, you might want to skip this or use a test worker
    pytest.skip("Requires running Celery worker - skipping in unit tests")


@pytest.mark.celery
def test_chromadb_access_from_celery_context():
    """Test ChromaDB access from Celery context."""
    try:
        collection = get_collection()
        assert collection is not None, "Should be able to get ChromaDB collection"
        
        # Get the underlying ChromaDB client to access count
        client = get_chroma_client()
        chroma_collection = client.get_or_create_collection("pdf_chunks")
        count = chroma_collection.count()
        
        logger.info(f"ChromaDB accessed: {count} documents")
        assert isinstance(count, int), "Count should be an integer"
    except Exception as e:
        pytest.fail(f"Failed to access ChromaDB: {e}")


@pytest.mark.celery
def test_embedding_async_from_celery_context():
    """Test async embedding generation from Celery context."""
    import asyncio
    
    test_text = "Hello, world!"
    try:
        # Use async version with asyncio.run
        embedding = asyncio.run(get_embedding(test_text))
        assert embedding is not None, "Should generate embedding"
        assert isinstance(embedding, list), "Embedding should be a list"
        assert len(embedding) > 0, "Embedding should have dimensions"
    except Exception as e:
        pytest.fail(f"Failed to generate embedding: {e}")


@pytest.mark.celery
def test_embedding_sync_from_celery_context():
    """Test synchronous embedding generation from Celery context."""
    test_text = "Hello, world!"
    try:
        # Use sync version for Celery tasks
        embedding = get_embedding_sync(test_text)
        assert embedding is not None, "Should generate embedding"
        assert isinstance(embedding, list), "Embedding should be a list"
        assert len(embedding) > 0, "Embedding should have dimensions"
    except Exception as e:
        pytest.fail(f"Failed to generate embedding: {e}")
