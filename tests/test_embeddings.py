"""Test embedding model functionality."""
import sys
from pathlib import Path

import pytest
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

import chromadb
from chromadb.config import Settings

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.embeddings import embedding_model


def test_single_string_embedding():
    """Test embedding a single string."""
    test_text = "This is a test sentence."
    embedding = embedding_model.embed_query(test_text)
    assert isinstance(embedding, list), "Embedding should be a list"
    assert len(embedding) > 0, "Embedding should have dimensions"
    assert all(isinstance(x, (int, float)) for x in embedding), "Embedding should contain numbers"


def test_batch_embeddings():
    """Test embedding a list of strings."""
    test_texts = [
        "First test sentence.",
        "Second test sentence.",
        "Third test sentence.",
    ]
    embeddings = embedding_model.embed_documents(test_texts)
    assert len(embeddings) == len(test_texts), "Should generate embedding for each text"
    assert all(
        len(emb) == len(embeddings[0]) for emb in embeddings
    ), "All embeddings should have same dimensions"
    assert len(embeddings[0]) > 0, "Embeddings should have dimensions"


def test_chromadb_integration():
    """Test ChromaDB integration with embeddings."""
    # Create temp client
    client = chromadb.Client(
        Settings(anonymized_telemetry=False, is_persistent=False)
    )

    # Create collection
    collection = Chroma(
        client=client,
        collection_name="test_collection",
        embedding_function=embedding_model,
    )

    # Test adding texts
    test_chunks = [
        "This is chunk 1",
        "This is chunk 2",
        "This is chunk 3",
    ]

    ids = collection.add_texts(
        texts=test_chunks,
        metadatas=[{"index": i} for i in range(len(test_chunks))],
        ids=[f"test-{i}" for i in range(len(test_chunks))],
    )

    assert len(ids) == len(test_chunks), "Should add all chunks to ChromaDB"

    # Test similarity search
    results = collection.similarity_search("chunk", k=2)
    assert len(results) > 0, "Should find similar documents"
    assert all(isinstance(doc, Document) for doc in results), "Results should be Document objects"

