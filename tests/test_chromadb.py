"""Test ChromaDB connection and operations."""
import logging
import sys
import time
from pathlib import Path

import chromadb
import pytest
from chromadb.config import Settings

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.embeddings import embedding_model
from app.services.vectorstore import get_chroma_client

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@pytest.fixture
def embedding_dimension():
    """Get the embedding dimension from the actual model."""
    test_embedding = embedding_model.embed_query("test")
    return len(test_embedding)


@pytest.fixture
def chroma_client():
    """Get a shared ChromaDB client for tests."""
    # Use the singleton client from vectorstore to avoid conflicts
    return get_chroma_client()


def test_chromadb_client_creation(chroma_client):
    """Test creating a ChromaDB client."""
    start = time.time()
    elapsed = time.time() - start
    logger.info(f"✓ Client created in {elapsed:.2f}s")
    assert chroma_client is not None, "Client should be created"


def test_list_collections(chroma_client):
    """Test listing ChromaDB collections."""
    collections = chroma_client.list_collections()
    logger.info(f"✓ Found {len(collections)} collections")
    assert isinstance(collections, list), "Collections should be a list"


def test_get_or_create_collection(chroma_client):
    """Test getting or creating a collection."""
    start = time.time()
    collection = chroma_client.get_or_create_collection("pdf_embeddings")
    elapsed = time.time() - start
    logger.info(f"✓ Collection accessed in {elapsed:.2f}s")
    assert collection is not None, "Collection should be created or retrieved"


def test_collection_count(chroma_client):
    """Test counting documents in a collection."""
    collection = chroma_client.get_or_create_collection("pdf_embeddings")
    count = collection.count()
    logger.info(f"✓ Collection has {count} documents")
    assert isinstance(count, int), "Count should be an integer"
    assert count >= 0, "Count should be non-negative"


def test_add_document(chroma_client, embedding_dimension):
    """Test adding a document to ChromaDB."""
    collection = chroma_client.get_or_create_collection("test_collection")
    test_id = f"test_{int(time.time())}"

    collection.add(
        documents=["test document"],
        embeddings=[[0.1] * embedding_dimension],
        ids=[test_id],
    )
    logger.info("✓ Successfully added test document")
    assert collection.count() > 0, "Collection should have at least one document"


def test_query_collection(chroma_client, embedding_dimension):
    """Test querying ChromaDB collection."""
    collection = chroma_client.get_or_create_collection("test_collection")

    # Add a test document first
    test_id = f"test_{int(time.time())}"
    collection.add(
        documents=["test query document"],
        embeddings=[[0.1] * embedding_dimension],
        ids=[test_id],
    )

    # Query
    results = collection.query(query_embeddings=[[0.1] * embedding_dimension], n_results=1)
    logger.info(f"✓ Query successful: {len(results['documents'][0])} results")
    assert "documents" in results, "Results should contain 'documents'"
    assert len(results["documents"][0]) > 0, "Should return at least one result"


def test_chromadb_basic_workflow(chroma_client, embedding_dimension):
    """Test complete ChromaDB workflow."""
    # Use unique collection name to avoid conflicts
    collection_name = f"workflow_test_{int(time.time())}"
    collection = chroma_client.get_or_create_collection(collection_name)

    # Add documents
    test_ids = [f"workflow_test_{i}_{int(time.time())}" for i in range(3)]
    collection.add(
        documents=["Document 1", "Document 2", "Document 3"],
        embeddings=[
            [0.1] * embedding_dimension,
            [0.2] * embedding_dimension,
            [0.3] * embedding_dimension,
        ],
        ids=test_ids,
    )

    # Verify count
    assert collection.count() == 3, "Should have 3 documents"

    # Query
    results = collection.query(
        query_embeddings=[[0.15] * embedding_dimension], n_results=2
    )
    assert len(results["documents"][0]) == 2, "Should return 2 results"
