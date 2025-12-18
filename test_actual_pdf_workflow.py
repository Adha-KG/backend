#!/usr/bin/env python3
"""
Test the actual PDF processing workflow to isolate the tokenizer error
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.pdf_loader import extract_text_from_pdf
from app.services.chunker import chunk_text
from app.services.vectorstore import get_collection

print("=" * 60)
print("ACTUAL PDF WORKFLOW TEST")
print("=" * 60)

# Use the actual PDF that's failing
pdf_path = "./uploads/5ded9e59-a0dc-4a3c-a49b-158ff98dd0cd_L_18_C_23.pdf"

if not os.path.exists(pdf_path):
    print(f"✗ PDF not found: {pdf_path}")
    print("Using a test PDF if available...")
    # Try to find any PDF in uploads
    uploads = [f for f in os.listdir("./uploads") if f.endswith(".pdf")]
    if uploads:
        pdf_path = f"./uploads/{uploads[0]}"
        print(f"Using: {pdf_path}")
    else:
        print("No PDFs found in uploads directory")
        sys.exit(1)

try:
    # Step 1: Extract text
    print("\nStep 1: Extracting text from PDF...")
    documents = extract_text_from_pdf(pdf_path)
    text = " ".join(doc.page_content for doc in documents)
    print(f"✓ Extracted {len(text)} characters")

    # Step 2: Chunk text
    print("\nStep 2: Chunking text...")
    chunks = chunk_text(text)
    print(f"✓ Created {len(chunks)} chunks")
    print(f"  Chunk types: {[type(c).__name__ for c in chunks[:3]]}")
    print(f"  First chunk length: {len(chunks[0]) if chunks else 0}")
    print(f"  First chunk preview: {repr(chunks[0][:100]) if chunks else 'N/A'}")

    # Step 3: Validate chunks (same as in rag_tasks.py)
    print("\nStep 3: Validating chunks...")
    validated_chunks = [str(chunk).strip() for chunk in chunks if chunk and str(chunk).strip()]
    print(f"✓ {len(validated_chunks)} valid chunks after filtering")

    # Step 4: Try to add to ChromaDB (just a small batch)
    print("\nStep 4: Adding to ChromaDB...")
    collection = get_collection("test_workflow")

    test_batch = validated_chunks[:3]  # Just test with 3 chunks
    print(f"  Testing with {len(test_batch)} chunks")
    print(f"  Types: {[type(c).__name__ for c in test_batch]}")
    print(f"  All are strings: {all(isinstance(c, str) for c in test_batch)}")

    # Debug: Print actual values
    for i, chunk in enumerate(test_batch):
        print(f"  Chunk {i}: type={type(chunk)}, len={len(chunk)}, preview={repr(chunk[:50])}")

    ids = collection.add_texts(
        texts=test_batch,
        metadatas=[{"test": True, "index": i} for i in range(len(test_batch))],
        ids=[f"test-{i}" for i in range(len(test_batch))]
    )

    print(f"✓ Successfully added {len(ids)} chunks to ChromaDB")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
