"""Test actual PDF processing workflow."""
import os
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.chunker import chunk_text
from app.services.pdf_loader import extract_text_from_pdf
from app.services.vectorstore import get_collection


@pytest.fixture
def pdf_path():
    """Get a test PDF path."""
    test_pdf = "./uploads/5ded9e59-a0dc-4a3c-a49b-158ff98dd0cd_L_18_C_23.pdf"
    if os.path.exists(test_pdf):
        return test_pdf

    # Try to find any PDF in uploads
    uploads_dir = Path("./uploads")
    if uploads_dir.exists():
        pdfs = list(uploads_dir.glob("*.pdf"))
        if pdfs:
            return str(pdfs[0])

    pytest.skip("No PDF files found in uploads directory")


def test_pdf_text_extraction(pdf_path):
    """Test extracting text from PDF."""
    documents = extract_text_from_pdf(pdf_path)
    assert len(documents) > 0, "Should extract at least one document"
    text = " ".join(doc.page_content for doc in documents)
    assert len(text) > 0, "Extracted text should not be empty"


def test_text_chunking(pdf_path):
    """Test chunking extracted text."""
    documents = extract_text_from_pdf(pdf_path)
    text = " ".join(doc.page_content for doc in documents)
    chunks = chunk_text(text)

    assert len(chunks) > 0, "Should create at least one chunk"
    assert all(
        isinstance(chunk, str) for chunk in chunks
    ), "All chunks should be strings"
    assert all(
        chunk and chunk.strip() for chunk in chunks
    ), "All chunks should be non-empty"


def test_chunk_validation(pdf_path):
    """Test chunk validation logic."""
    documents = extract_text_from_pdf(pdf_path)
    text = " ".join(doc.page_content for doc in documents)
    chunks = chunk_text(text)

    # Validate chunks (same as in rag_tasks.py)
    validated_chunks = [str(chunk).strip() for chunk in chunks if chunk and str(chunk).strip()]

    assert len(validated_chunks) > 0, "Should have validated chunks after filtering"
    assert all(
        isinstance(chunk, str) and chunk.strip() for chunk in validated_chunks
    ), "All validated chunks should be non-empty strings"


def test_chromadb_add_chunks(pdf_path):
    """Test adding chunks to ChromaDB."""
    documents = extract_text_from_pdf(pdf_path)
    text = " ".join(doc.page_content for doc in documents)
    chunks = chunk_text(text)

    # Validate chunks
    validated_chunks = [str(chunk).strip() for chunk in chunks if chunk and str(chunk).strip()]

    if not validated_chunks:
        pytest.skip("No validated chunks to test")

    # Test with small batch
    collection = get_collection("test_workflow")
    test_batch = validated_chunks[:3]

    # Verify all chunks are strings
    assert all(isinstance(c, str) for c in test_batch), "All chunks should be strings"

    ids = collection.add_texts(
        texts=test_batch,
        metadatas=[{"test": True, "index": i} for i in range(len(test_batch))],
        ids=[f"test-{i}" for i in range(len(test_batch))],
    )

    assert len(ids) == len(test_batch), "Should successfully add all chunks to ChromaDB"

