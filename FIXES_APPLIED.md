# Fixes Applied to Resolve Startup Errors

## Issues Found and Fixed

### 1. Missing `google-generativeai` Package

**Error:**
```
ModuleNotFoundError: No module named 'google.generativeai'
```

**Fix:**
- Added `google-generativeai = "^0.8.3"` to `pyproject.toml`
- This package is required by `app/services/notes_llm.py`

**Action Required:**
```bash
poetry install
# or
poetry add google-generativeai
```

---

### 2. Import Error for `process_pdf`

**Error:**
```
ImportError: cannot import name 'process_pdf' from 'app.tasks'
```

**Root Cause:**
- Had both `app/tasks.py` (file) and `app/tasks/` (directory)
- Python was treating `app.tasks` as the directory, not the file
- The directory's `__init__.py` didn't export `process_pdf`

**Fix:**
1. Moved `app/tasks.py` → `app/tasks/rag_tasks.py`
2. Updated `app/tasks/__init__.py` to export `process_pdf`
3. Updated `app/celery_app.py` to include both task modules:
   - `app.tasks.rag_tasks` (RAG PDF processing)
   - `app.tasks.notes_tasks` (Notes processing)

---

## Updated File Structure

```
app/
├── tasks/
│   ├── __init__.py          # Exports process_pdf
│   ├── rag_tasks.py         # RAG PDF processing (moved from tasks.py)
│   └── notes_tasks.py       # Notes processing pipeline
├── celery_app.py            # Updated includes
└── ...
```

---

## How to Apply Fixes

### Step 1: Install Missing Dependencies

```bash
cd /mnt/NewVolume2/Android\ Projects/adha_keji/backend

# Install all dependencies including the new google-generativeai package
poetry install
```

### Step 2: Restart Services

```bash
# Stop any running services (Ctrl+C on each terminal)

# Start Redis
docker run -d -p 6379:6379 redis:latest

# Start FastAPI (Terminal 1)
poetry run uvicorn app.main:app --reload --port 8000

# Start Celery Worker (Terminal 2)
poetry run celery -A app.celery_app worker --loglevel=INFO --pool=solo
```

### Alternative: Use run.sh

```bash
./run.sh
```

---

## Verification

After applying fixes, verify everything works:

### 1. Check Celery Task Discovery

```bash
poetry run celery -A app.celery_app inspect registered
```

**Expected output should include:**
- `app.tasks.rag_tasks.process_pdf`
- `app.tasks.notes_tasks.process_file_task`
- `app.tasks.notes_tasks.summarize_chunks_task`
- `app.tasks.notes_tasks.synthesize_notes_task`

### 2. Test API Health

```bash
curl http://localhost:8000/health
curl http://localhost:8000/notes/health
```

**Expected:**
```json
{"status":"healthy","message":"..."}
```

### 3. Test API Docs

Open in browser:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## What Changed

### `pyproject.toml`
```diff
+ google-generativeai = "^0.8.3"
```

### `app/celery_app.py`
```diff
- include=["app.tasks", "app.tasks.notes_tasks"]
+ include=["app.tasks.rag_tasks", "app.tasks.notes_tasks"]
```

### `app/tasks/__init__.py`
```python
# NEW FILE - exports process_pdf for backwards compatibility
from app.tasks.rag_tasks import process_pdf

__all__ = ["process_pdf"]
```

### File Move
```
app/tasks.py → app/tasks/rag_tasks.py
```

---

## Additional Notes

### Why This Structure?

**Old Structure (Broken):**
```
app/
├── tasks.py              # RAG tasks
└── tasks/                # Notes tasks directory
    └── notes_tasks.py
```
**Problem:** Python treats `app.tasks` as the directory, not the file

**New Structure (Fixed):**
```
app/
└── tasks/
    ├── __init__.py       # Exports for backwards compatibility
    ├── rag_tasks.py      # RAG tasks (moved from tasks.py)
    └── notes_tasks.py    # Notes tasks
```
**Solution:** All tasks are in the `tasks/` package, properly organized

---

## Troubleshooting

### If you still get import errors:

```bash
# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete

# Reinstall
poetry install --no-cache
```

### If Celery doesn't start:

```bash
# Check Redis is running
redis-cli ping  # Should return PONG

# Check environment variables
cat .env | grep REDIS_URL
cat .env | grep CELERY
```

### If API doesn't start:

```bash
# Check for syntax errors
poetry run python -m py_compile app/main.py

# Check imports
poetry run python -c "from app.main import app; print('OK')"
```

---

## Summary

✅ Added `google-generativeai` to dependencies
✅ Reorganized task structure to avoid Python import conflicts
✅ Updated Celery configuration to include both task modules
✅ Maintained backwards compatibility with existing code

Your unified backend should now start without errors! 🎉
