#!/usr/bin/env python3
"""
Test script to diagnose the ChromaDB embedding issue
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.embeddings import embedding_model

print("=" * 60)
print("EMBEDDING MODEL TEST")
print("=" * 60)

# Test 1: Single string
print("\nTest 1: Single string")
try:
    test_text = "This is a test sentence."
    embedding = embedding_model.embed_query(test_text)
    print(f"✓ Single embedding successful: {len(embedding)} dimensions")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: List of strings
print("\nTest 2: List of strings")
try:
    test_texts = [
        "First test sentence.",
        "Second test sentence.",
        "Third test sentence."
    ]
    embeddings = embedding_model.embed_documents(test_texts)
    print(f"✓ Batch embedding successful: {len(embeddings)} embeddings")
    print(f"  Each embedding: {len(embeddings[0])} dimensions")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Simulate ChromaDB usage
print("\nTest 3: Simulate ChromaDB add_texts")
try:
    from langchain_community.vectorstores import Chroma
    import chromadb
    from chromadb.config import Settings

    # Create temp client
    client = chromadb.Client(Settings(
        anonymized_telemetry=False,
        is_persistent=False
    ))

    # Create collection
    collection = Chroma(
        client=client,
        collection_name="test_collection",
        embedding_function=embedding_model,
    )

    # Try adding texts
    test_chunks = [
        "This is chunk 1",
        "This is chunk 2",
        "This is chunk 3"
    ]

    print(f"  Adding {len(test_chunks)} chunks to ChromaDB...")
    print(f"  Chunk types: {[type(c).__name__ for c in test_chunks]}")
    print(f"  First chunk: {repr(test_chunks[0])}")

    ids = collection.add_texts(
        texts=test_chunks,
        metadatas=[{"index": i} for i in range(len(test_chunks))],
        ids=[f"test-{i}" for i in range(len(test_chunks))]
    )

    print(f"✓ ChromaDB add_texts successful: {len(ids)} documents added")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
