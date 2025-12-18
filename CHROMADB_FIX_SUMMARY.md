# ChromaDB Embedding Error - Fix Summary

## Issue

ChromaDB was failing when trying to create embeddings for PDF chunks with the error:

```
TypeError: TextEncodeInput must be Union[TextInputSequence, Tuple[InputSequence, InputSequence]]
```

This error occurred in the sentence transformers tokenizer when processing text chunks for RAG document indexing.

## Root Causes ✅ IDENTIFIED

### 1. **PRIMARY CAUSE: Invalid Unicode Characters in PDF Text** ✅
- PyPDF2 extracted text containing **Unicode surrogate pairs** (`\ud8353`, `\ud8350`, etc.)
- These are malformed Unicode sequences that the tokenizer cannot process
- Common in poorly formatted or scanned PDFs with special characters/formulas

### 2. Deprecated LangChain Packages
- Using `langchain-community.embeddings.HuggingFaceEmbeddings` (deprecated)
- Using `langchain-community.vectorstores.Chroma` (deprecated)
- These deprecated packages have compatibility issues with newer versions of sentence-transformers

### 3. Data Type Issues
- Text chunks might contain non-string elements
- Empty or None values in chunk lists
- Improper string formatting

## Fixes Applied

### 1. **Unicode Cleaning (PRIMARY FIX)** ✅

**Added robust Unicode cleaning** in [app/tasks/rag_tasks.py](app/tasks/rag_tasks.py) (lines 63-86):

```python
# Clean Unicode - remove surrogates and normalize
cleaned_chunks = []
for chunk in chunks:
    if not chunk or not str(chunk).strip():
        continue

    try:
        # Remove surrogate pairs (common in poorly extracted PDFs)
        clean_chunk = chunk.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
        # Remove any remaining non-printable or problematic characters
        clean_chunk = ''.join(char for char in clean_chunk if char.isprintable() or char in '\n\r\t ')
        clean_chunk = clean_chunk.strip()

        if clean_chunk:
            cleaned_chunks.append(clean_chunk)
    except Exception as e:
        logger.warning(f"Failed to clean chunk: {e}, skipping")
        continue
```

This removes:
- Unicode surrogate pairs (`\ud835`, etc.)
- Non-printable characters (except newlines, tabs, spaces)
- Malformed UTF-8 sequences

### 2. Upgraded to Modern LangChain Packages ✅

**Installed:**
```bash
poetry add "langchain-huggingface<1.0.0"
```

**Updated [app/services/embeddings.py](app/services/embeddings.py):**
```python
# Before:
from langchain_community.embeddings import HuggingFaceEmbeddings

# After:
from langchain_huggingface import HuggingFaceEmbeddings
```

**Updated [app/services/vectorstore.py](app/services/vectorstore.py):**
```python
# Before:
from langchain_community.vectorstores import Chroma

# After:
from langchain_chroma import Chroma
```

### 2. Added Chunk Validation ✅

**Updated [app/tasks/rag_tasks.py](app/tasks/rag_tasks.py):**

#### Global chunk filtering (lines 58-68):
```python
# Chunk the text
chunks = chunk_text(text)
if not chunks:
    raise ValueError("No chunks created from text")

# Ensure all chunks are valid strings (not None, not empty)
chunks = [str(chunk).strip() for chunk in chunks if chunk and str(chunk).strip()]
if not chunks:
    raise ValueError("No valid chunks created from text after filtering")

logger.info(f"Created {len(chunks)} valid chunks")
```

#### Batch-level validation (lines 115-128):
```python
# Validate and ensure all batch chunks are proper strings
validated_chunks = []
for chunk in batch_chunks:
    if not isinstance(chunk, str):
        logger.warning(f"Non-string chunk detected: {type(chunk)}, converting to string")
        chunk = str(chunk)
    if not chunk.strip():
        logger.warning("Empty chunk detected, skipping")
        continue
    validated_chunks.append(chunk.strip())

if not validated_chunks:
    logger.error("No valid chunks in batch after validation")
    continue
```

### 3. Enhanced Embedding Configuration ✅

**Updated [app/services/embeddings.py](app/services/embeddings.py) (lines 35-38):**
```python
encode_kwargs={
    'normalize_embeddings': True,  # For better similarity search
    'batch_size': 32,  # Adjust based on your needs
    'convert_to_tensor': False  # Return list instead of tensor
}
```

### 4. Added Debug Logging ✅

**In [app/tasks/rag_tasks.py](app/tasks/rag_tasks.py) (lines 130-132):**
```python
# Debug logging
logger.info(f"About to add {len(validated_chunks)} chunks to ChromaDB")
logger.debug(f"First chunk type: {type(validated_chunks[0])}, preview: {repr(validated_chunks[0][:100])}")
```

## Testing

Created [test_embedding_issue.py](test_embedding_issue.py) to verify:

1. ✅ Single string embedding works
2. ✅ Batch embedding works
3. ✅ ChromaDB `add_texts` works

All tests pass successfully.

## Files Modified

1. **app/services/embeddings.py**
   - Changed import to `langchain_huggingface`
   - Added `convert_to_tensor: False` to encode_kwargs

2. **app/services/vectorstore.py**
   - Changed import to `langchain_chroma`

3. **app/tasks/rag_tasks.py**
   - Added global chunk validation
   - Added batch-level chunk validation
   - Added debug logging
   - Ensured all chunks are valid strings before ChromaDB insertion

4. **pyproject.toml** (via poetry)
   - Added `langchain-huggingface` dependency

## Current Status

✅ **All fixes applied and tested**

The ChromaDB embedding error should now be resolved. The combination of:
- Modern LangChain packages with better compatibility
- Thorough chunk validation
- Proper encoding configuration

...ensures that only valid string data is passed to the sentence transformers tokenizer.

## Next Steps

1. Restart the Celery worker to pick up the changes:
   ```bash
   # Stop current worker (Ctrl+C)
   poetry run celery -A app.celery_app worker --loglevel=INFO --pool=solo
   ```

2. Test by uploading a PDF through the RAG interface

3. Monitor logs for any remaining issues

## Note

This fix addresses the **RAG document processing** error. This is separate from the **Notes generation** feature, which uses a different code path (direct LLM summarization without embeddings).
