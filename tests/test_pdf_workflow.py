"""Test PDF workflow with Unicode cleaning."""
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


def test_pdf_extraction_and_chunking(pdf_path):
    """Test PDF text extraction and chunking."""
    # Extract and chunk
    documents = extract_text_from_pdf(pdf_path)
    text = " ".join(doc.page_content for doc in documents)
    chunks = chunk_text(text)

    assert len(chunks) > 0, "Should create at least one chunk"
    assert all(chunk and str(chunk).strip() for chunk in chunks), "All chunks should be non-empty"


def test_chunk_cleaning(pdf_path):
    """Test chunk cleaning logic."""
    documents = extract_text_from_pdf(pdf_path)
    text = " ".join(doc.page_content for doc in documents)
    chunks = chunk_text(text)

    # Clean chunks (same logic as in rag_tasks.py)
    cleaned_chunks = []
    for chunk in chunks:
        if not chunk or not str(chunk).strip():
            continue

        try:
            clean_chunk = chunk.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
            clean_chunk = "".join(
                char for char in clean_chunk if char.isprintable() or char in "\n\r\t "
            )
            clean_chunk = clean_chunk.strip()

            if clean_chunk:
                cleaned_chunks.append(clean_chunk)
        except Exception as e:
            pytest.fail(f"Failed to clean chunk: {e}")

    assert len(cleaned_chunks) > 0, "Should have cleaned chunks"
    assert all(
        isinstance(chunk, str) and chunk.strip() for chunk in cleaned_chunks
    ), "All cleaned chunks should be non-empty strings"


def test_chromadb_integration(pdf_path):
    """Test adding cleaned chunks to ChromaDB."""
    documents = extract_text_from_pdf(pdf_path)
    text = " ".join(doc.page_content for doc in documents)
    chunks = chunk_text(text)

    # Clean chunks
    cleaned_chunks = []
    for chunk in chunks:
        if not chunk or not str(chunk).strip():
            continue
        try:
            clean_chunk = chunk.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
            clean_chunk = "".join(
                char for char in clean_chunk if char.isprintable() or char in "\n\r\t "
            )
            clean_chunk = clean_chunk.strip()
            if clean_chunk:
                cleaned_chunks.append(clean_chunk)
        except Exception:
            continue

    if not cleaned_chunks:
        pytest.skip("No cleaned chunks to test")

    # Test adding to ChromaDB
    collection = get_collection("test_cleaned")
    test_batch = cleaned_chunks[:3]

    ids = collection.add_texts(
        texts=test_batch,
        metadatas=[{"index": i} for i in range(len(test_batch))],
        ids=[f"clean-test-{i}" for i in range(len(test_batch))],
    )

    assert len(ids) == len(test_batch), "Should add all test chunks to ChromaDB"

