# Unified RAG & Notes Backend - Complete Guide

## Overview

This is a unified FastAPI backend that combines:
- **RAG (Retrieval-Augmented Generation)**: Document Q&A, chat sessions, and flashcard generation
- **AI-Powered Notes**: Automated note generation from PDF uploads with customizable styles

Both systems share:
- Single Supabase database instance
- Unified ChromaDB vector store
- Shared Redis/Celery task queue
- Common LLM configuration (Google Gemini / OpenAI)
- Integrated authentication system

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Unified FastAPI Backend                  │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  RAG Routes  │  │ Notes Routes │  │  Auth Routes    │  │
│  │              │  │              │  │                 │  │
│  │ /documents   │  │ /notes       │  │ /auth           │  │
│  │ /query       │  │              │  │ /users          │  │
│  │ /chat        │  │              │  │ /admin          │  │
│  │ /flashcards  │  │              │  │                 │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬────────┘  │
│         │                 │                    │            │
│  ┌──────┴─────────────────┴────────────────────┴────────┐  │
│  │            Shared Services Layer                     │  │
│  │  - Vector Store (ChromaDB)                           │  │
│  │  - LLM Service (Gemini/OpenAI)                       │  │
│  │  - Database (Supabase)                               │  │
│  │  - Celery Tasks (Background Processing)              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌──────────┐         ┌──────────┐         ┌──────────┐
   │ Supabase │         │ ChromaDB │         │  Redis   │
   │    DB    │         │  Vectors │         │  Celery  │
   └──────────┘         └──────────┘         └──────────┘
```

---

## Quick Start

### 1. Install Dependencies

```bash
# Using Poetry (recommended)
poetry install

# Or using pip
pip install -r requirements.txt  # (generate from pyproject.toml if needed)
```

### 2. Configure Environment

Copy and configure the environment file:

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

Required configuration:
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_API_KEY` (or `OPENAI_API_KEY`)
- `REDIS_URL` for Celery

### 3. Set Up Supabase Database

Run the unified schema SQL in your Supabase SQL editor:

```bash
# Apply the schema
cat supabase_schema_unified.sql | supabase db query
# Or paste into Supabase Dashboard > SQL Editor
```

### 4. Start Services

#### Start Redis (required for Celery)
```bash
docker run -d -p 6379:6379 redis:latest
# Or use local Redis installation
```

#### Start FastAPI Server
```bash
# Development
uvicorn app.main:app --reload --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Start Celery Worker (required for notes processing)
```bash
celery -A app.celery_app worker --loglevel=INFO --pool=solo
```

#### Optional: Celery Flower (monitoring)
```bash
celery -A app.celery_app flower --port=5555
```

---

## API Endpoints

### Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/auth/signup` | Create new user account | No |
| POST | `/auth/signin` | Login and get JWT token | No |
| GET | `/users/me` | Get current user profile | Yes |

### RAG Endpoints (Documents & Q&A)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/documents/upload` | Upload document for RAG | Yes |
| GET | `/documents` | List user's documents | Yes |
| DELETE | `/documents/{id}` | Delete document | Yes |
| POST | `/query` | Ask question (non-streaming) | Yes |
| POST | `/query/stream` | Ask question (streaming) | Yes |
| GET | `/chat-sessions` | List chat sessions | Yes |
| POST | `/chat-sessions` | Create chat session | Yes |
| POST | `/flashcards/generate` | Generate flashcards | Yes |

### Notes Endpoints (AI-Powered Note Generation)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/notes/upload` | Upload PDF for note generation | No* |
| GET | `/notes/status/{file_id}` | Check processing status | No* |
| GET | `/notes/files` | List uploaded files | No* |
| GET | `/notes/notes/{file_id}` | Get generated note (JSON/HTML) | No* |
| GET | `/notes/notes/{file_id}/download` | Download note as Markdown | No* |
| GET | `/notes/notes/{file_id}/download-pdf` | Download note as PDF | No* |
| POST | `/notes/qa/{file_id}` | Ask questions about file | No* |
| POST | `/notes/files/{file_id}/retry` | Retry failed processing | No* |
| DELETE | `/notes/files/{file_id}` | Delete file and all data | No* |

**Note**: Authentication not yet implemented for notes endpoints. Add using `/users/me` dependency.

---

## Notes Features Deep Dive

### Upload PDF with Custom Styles

```bash
curl -X POST "http://localhost:8000/notes/upload" \
  -F "file=@lecture.pdf" \
  -F "note_style=descriptive" \
  -F "user_prompt=Focus on key concepts and include all formulas"
```

**Note Styles:**
- `short`: Brief bullet points, only key facts (5-7 points per section)
- `moderate`: Balanced notes with main ideas and details
- `descriptive`: Comprehensive notes with full explanations (default)

### Check Processing Status

```bash
curl "http://localhost:8000/notes/status/{file_id}"
```

**Status Flow:**
```
uploaded → processing → indexed → summarizing → completed
                                              ↘ failed
```

### Retrieve Generated Notes

```bash
# Get as JSON
curl "http://localhost:8000/notes/notes/{file_id}"

# Get as HTML
curl "http://localhost:8000/notes/notes/{file_id}?format=html"

# Download as Markdown
curl "http://localhost:8000/notes/notes/{file_id}/download" --output note.md

# Download as PDF
curl "http://localhost:8000/notes/notes/{file_id}/download-pdf" --output note.pdf
```

### Ask Questions (RAG on Notes)

```bash
curl -X POST "http://localhost:8000/notes/qa/{file_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main topics covered?",
    "n_results": 5
  }'
```

---

## Configuration Details

### Environment Variables Reference

See [.env.example](./.env.example) for complete list.

**Critical Settings:**

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPABASE_URL` | - | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | - | Service role key (bypasses RLS) |
| `GEMINI_API_KEY` | - | Google Gemini API key |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage path |
| `CHUNK_SIZE` | `1000` | Text chunk size (tokens) |
| `CHUNK_OVERLAP` | `200` | Chunk overlap (tokens) |
| `GEMINI_MAX_OUTPUT_TOKENS` | `55000` | Max LLM output tokens |

### LLM Provider Configuration

#### Google Gemini (Recommended)
```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash
```

**Rate Limits:**
- Flash: 15 requests/minute (Free tier)
- Pro: 2 requests/minute (Free tier)

#### OpenAI (Alternative)
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-3.5-turbo
```

---

## Database Schema

### Notes Tables

#### `files` Table
Stores uploaded PDF metadata with user ownership.

```sql
CREATE TABLE files (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),  -- Multi-user support
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,  -- Duplicate detection
    file_size BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',
    error TEXT,
    user_prompt TEXT,  -- Custom user instructions
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, sha256)  -- Prevent duplicate uploads per user
);
```

#### `chunks` Table
Text chunks extracted from PDFs.

#### `summaries` Table
Per-chunk summaries generated by LLM.

#### `notes` Table
Final synthesized notes (one per file).

### Row Level Security (RLS)

Policies ensure:
- Users can only access their own files/notes
- Service role (backend) can access all data for processing
- Cascading deletes maintain referential integrity

---

## Background Processing Pipeline

### Notes Processing Flow

```mermaid
graph LR
    A[Upload PDF] --> B[process_file_task]
    B --> C[Extract Text]
    C --> D[Chunk Text]
    D --> E[Generate Embeddings]
    E --> F[Store in ChromaDB & DB]
    F --> G[summarize_chunks_task]
    G --> H[Generate Summaries]
    H --> I[synthesize_notes_task]
    I --> J[Create Final Note]
    J --> K[Save & Complete]
```

### Celery Task Configuration

```python
# app/celery_app.py
celery.conf.update(
    worker_max_tasks_per_child=10,  # Prevent memory leaks
    worker_prefetch_multiplier=1,   # Fetch one task at a time
    task_acks_late=True,            # Acknowledge after completion
    task_time_limit=3600,           # 1 hour hard limit
    task_soft_time_limit=3300,      # 55 minutes soft limit
)
```

---

## Adding Authentication to Notes Endpoints

Currently, notes endpoints are public. To add authentication:

### 1. Import Auth Dependency

```python
# app/routes/notes.py
from app.auth.auth import get_current_user
from app.schemas import User
```

### 2. Add to Endpoint

```python
@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    note_style: NoteStyle = Form(NoteStyle.moderate),
    user_prompt: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)  # Add this
):
    # Use current_user.id when creating file record
    file_data = {
        "user_id": current_user.id,  # Add user_id
        "filename": saved_filename,
        # ... rest of data
    }
```

### 3. Update Database Service Calls

```python
# Filter by user_id in all queries
db.get_file(file_id, user_id=current_user.id)
db.list_files(limit=limit, offset=offset, user_id=current_user.id)
```

---

## Testing

### Health Check

```bash
curl http://localhost:8000/health
# Response: {"status":"healthy","message":"RAG API is running"}
```

### Notes Health Check

```bash
curl http://localhost:8000/notes/health
# Response: {"status":"healthy","chroma_collections":1}
```

### API Documentation

FastAPI provides automatic interactive API docs:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Deployment

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev

COPY app ./app
COPY .env .env

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

  worker:
    build: .
    command: celery -A app.celery_app worker --loglevel=INFO --pool=solo
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

  redis:
    image: redis:latest
    ports:
      - "6379:6379"
```

---

## Troubleshooting

### Common Issues

#### 1. Celery Tasks Not Processing
**Problem**: Files stuck in "uploaded" status.

**Solution**:
```bash
# Check Celery worker is running
celery -A app.celery_app inspect active

# Check Redis connection
redis-cli ping
```

#### 2. ChromaDB Errors
**Problem**: `Collection not found` or embedding errors.

**Solution**:
```bash
# Remove and recreate ChromaDB
rm -rf ./chroma_db
# Restart services
```

#### 3. Gemini Rate Limits
**Problem**: Tasks failing with rate limit errors.

**Solution**:
- Use `gemini-2.5-flash` (15 req/min vs 2 req/min for Pro)
- Tasks auto-retry with exponential backoff
- Check task logs for retry attempts

#### 4. Import Errors
**Problem**: `ModuleNotFoundError` for app modules.

**Solution**:
```bash
# Ensure you're in the backend directory
cd /path/to/backend

# Run with module path
python -m uvicorn app.main:app --reload
```

---

## File Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app with all routers
│   ├── config.py                  # Unified configuration
│   ├── celery_app.py              # Celery configuration
│   ├── schemas.py                 # Pydantic models (RAG)
│   ├── auth/                      # Authentication
│   │   ├── auth.py
│   │   └── supabase_client.py
│   ├── routes/                    # API routes
│   │   ├── auth.py                # Auth endpoints
│   │   ├── users.py               # User management
│   │   ├── documents.py           # RAG document upload
│   │   ├── query.py               # RAG Q&A
│   │   ├── chat.py                # Chat sessions
│   │   ├── flashcards.py          # Flashcard generation
│   │   ├── stats.py               # Statistics
│   │   ├── admin.py               # Admin endpoints
│   │   └── notes.py               # Notes endpoints (NEW)
│   ├── services/                  # Business logic
│   │   ├── rag.py                 # RAG service
│   │   ├── retriever.py           # Vector search
│   │   ├── vectorstore.py         # ChromaDB (RAG)
│   │   ├── embeddings.py          # Embedding service (RAG)
│   │   ├── notes_db.py            # Notes database service (NEW)
│   │   ├── notes_chroma.py        # Notes vector store (NEW)
│   │   └── notes_llm.py           # Notes LLM service (NEW)
│   ├── tasks/                     # Celery tasks
│   │   ├── __init__.py
│   │   └── notes_tasks.py         # Notes processing tasks (NEW)
│   └── utils/                     # Utilities (NEW)
│       ├── text_extraction.py     # PDF text extraction
│       ├── chunking.py            # Text chunking
│       ├── embeddings.py          # Embedding utilities
│       └── file_utils.py          # File operations
├── pyproject.toml                 # Unified dependencies
├── .env.example                   # Environment template
├── supabase_schema_unified.sql    # Database schema with user_id
└── UNIFIED_BACKEND_GUIDE.md       # This file
```

---

## Migration from Separate Services

If migrating from separate RAG and notes-app services:

### 1. Database Migration

```sql
-- Add user_id to existing files table
ALTER TABLE files ADD COLUMN user_id UUID REFERENCES auth.users(id);

-- Assign existing files to a user
UPDATE files SET user_id = '<your-user-uuid>' WHERE user_id IS NULL;

-- Make user_id required
ALTER TABLE files ALTER COLUMN user_id SET NOT NULL;

-- Update UNIQUE constraint
ALTER TABLE files DROP CONSTRAINT IF EXISTS files_sha256_key;
ALTER TABLE files ADD CONSTRAINT files_user_sha256_unique UNIQUE (user_id, sha256);
```

### 2. Environment Consolidation

Merge variables from both `.env` files:
```bash
# From notes-app
CELERY_BROKER_URL → REDIS_URL (or keep both)
CHROMA_PERSIST_DIR → use unified path

# From RAG backend
CHROMA_HOST → keep if using remote ChromaDB
```

### 3. Code Updates

- Update imports in any custom code
- Replace direct `db` references with `notes_db`
- Replace `chroma_service` with `notes_chroma_service` in notes code

---

## Performance Optimization

### ChromaDB Performance

```python
# app/config.py
EMBEDDING_BATCH_SIZE = 32  # Process embeddings in batches
```

### Celery Tuning

```bash
# Increase concurrency for multiple workers
celery -A app.celery_app worker --concurrency=4

# Use prefork pool for better isolation (Linux)
celery -A app.celery_app worker --pool=prefork
```

### Caching

Consider adding Redis caching for:
- Frequently accessed notes
- Embedding results
- User sessions

---

## Security Considerations

### Production Checklist

- [ ] Change `JWT_SECRET_KEY` to a strong random value
- [ ] Use `SUPABASE_SERVICE_ROLE_KEY` (not anon key) for backend
- [ ] Enable HTTPS for all endpoints
- [ ] Restrict CORS origins in `app/main.py`
- [ ] Enable RLS policies in Supabase
- [ ] Add rate limiting middleware
- [ ] Implement file upload validation (file types, sizes)
- [ ] Add virus scanning for uploaded files
- [ ] Use environment-specific `.env` files
- [ ] Enable logging and monitoring

---

## Support & Contributing

### Getting Help

1. Check this guide first
2. Review API docs at `/docs`
3. Check Celery worker logs
4. Enable DEBUG mode in development

### Contributing

When adding features:
1. Follow existing code structure
2. Update this guide with new endpoints/features
3. Add tests for new functionality
4. Update `pyproject.toml` for new dependencies

---

## License

[Your License Here]

---

## Changelog

### Version 2.0.0 - Unified Backend
- Merged RAG and Notes-App into single service
- Added multi-user support with user_id fields
- Unified configuration and database services
- Consolidated Celery tasks
- Integrated ChromaDB usage

### Version 1.0.0 - Original RAG Backend
- Initial RAG implementation
- Document Q&A and chat sessions
- Flashcard generation
