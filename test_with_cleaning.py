#!/usr/bin/env python3
"""
Test PDF workflow with Unicode cleaning
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.pdf_loader import extract_text_from_pdf
from app.services.chunker import chunk_text
from app.services.vectorstore import get_collection

pdf_path = "./uploads/5ded9e59-a0dc-4a3c-a49b-158ff98dd0cd_L_18_C_23.pdf"

if not os.path.exists(pdf_path):
    uploads = [f for f in os.listdir("./uploads") if f.endswith(".pdf")]
    if uploads:
        pdf_path = f"./uploads/{uploads[0]}"
    else:
        print("No PDFs found")
        sys.exit(1)

try:
    # Extract and chunk
    documents = extract_text_from_pdf(pdf_path)
    text = " ".join(doc.page_content for doc in documents)
    chunks = chunk_text(text)

    print(f"Raw chunks: {len(chunks)}")

    # Clean chunks (same logic as in rag_tasks.py)
    cleaned_chunks = []
    for chunk in chunks:
        if not chunk or not str(chunk).strip():
            continue

        try:
            clean_chunk = chunk.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
            clean_chunk = ''.join(char for char in clean_chunk if char.isprintable() or char in '\n\r\t ')
            clean_chunk = clean_chunk.strip()

            if clean_chunk:
                cleaned_chunks.append(clean_chunk)
        except Exception as e:
            print(f"Failed to clean chunk: {e}")
            continue

    print(f"Cleaned chunks: {len(cleaned_chunks)}")
    print(f"First cleaned chunk preview: {repr(cleaned_chunks[0][:100])}")

    # Test adding to ChromaDB
    collection = get_collection("test_cleaned")
    test_batch = cleaned_chunks[:3]

    print(f"\nTesting with {len(test_batch)} chunks...")
    ids = collection.add_texts(
        texts=test_batch,
        metadatas=[{"index": i} for i in range(len(test_batch))],
        ids=[f"clean-test-{i}" for i in range(len(test_batch))]
    )

    print(f"✓ SUCCESS! Added {len(ids)} chunks to ChromaDB")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
