# Environment Setup Guide

## Quick Start

You have two options for setting up your environment variables:

### Option 1: Use the Consolidated Environment (Recommended)

This uses the actual credentials from both your existing repos:

```bash
# Copy the unified environment file
cp .env.unified .env

# The unified file already contains:
# ✓ Supabase credentials from notes-app (production instance)
# ✓ Gemini API key from notes-app
# ✓ Chroma Cloud credentials from RAG backend
# ✓ Redis/Celery configuration
# ✓ All application settings
```

### Option 2: Start Fresh with Template

If you want to use different credentials or start clean:

```bash
# Copy the example template
cp .env.example .env

# Then edit .env and fill in your values
nano .env  # or use your preferred editor
```

---

## What's in Each File?

### `.env.example` (Template)
- Clean template with placeholder values
- Includes all required and optional variables
- Has detailed comments explaining each setting
- Use this for new deployments or documentation

### `.env.unified` (Merged Actual Values)
- Contains real credentials merged from both repos:
  - **Supabase**: From `notes-app/.env` (ojskecyq... instance)
  - **Gemini API**: From `notes-app/.env`
  - **Chroma Cloud**: From `backend/.env` (RAG backend)
  - **Clerk**: From `backend/.env` (if needed)
- Ready to use immediately
- **SECURITY NOTE**: Contains real API keys - don't commit to git!

---

## Key Differences Between Repos

| Setting | RAG Backend | Notes-App | Unified |
|---------|-------------|-----------|---------|
| **Supabase URL** | xzryjsoh...supabase.co | ojskecyq...supabase.co | **ojskecyq** (notes) |
| **Gemini Key** | AIzaSyCmKwV... | AIzaSyCRxCS... | **AIzaSyCRxCS** (notes) |
| **ChromaDB** | Cloud (api.trychroma.com) | Local (./data/chroma) | **Both supported** |
| **Chroma Path** | N/A (using cloud) | ./data/chroma | **./chroma_db** |

### Why These Choices?

1. **Supabase**: Using notes-app instance because it has the service role key configured
2. **Gemini**: Using notes-app key (both work, but notes-app has the quota)
3. **ChromaDB**: Configured for both local and cloud - you can use either:
   - **Local** (default): Comment out `CHROMA_HOST` and `CHROMA_API_KEY`
   - **Cloud**: Keep both enabled for remote ChromaDB

---

## Configuration Tips

### Using Local ChromaDB (Recommended)

For local development, use local ChromaDB storage:

```bash
# In your .env:
CHROMA_PERSIST_DIR=./chroma_db

# Comment out or remove:
# CHROMA_HOST=https://api.trychroma.com
# CHROMA_API_KEY=ck-8XQ8ug...
```

### Using ChromaDB Cloud

For cloud-based vector storage:

```bash
# In your .env:
CHROMA_HOST=https://api.trychroma.com
CHROMA_API_KEY=ck-8XQ8ugLgDKvVgRsDMoQ29YZ3tCXV7kt3iVrMkg2Hx3c4

# Optional: Set persist dir as fallback
CHROMA_PERSIST_DIR=./chroma_db
```

### Redis Configuration

The unified config uses Redis DB 0 for broker and DB 1 for results:

```bash
# Broker (task queue)
CELERY_BROKER_URL=redis://localhost:6379/0

# Results storage
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

If you only set `REDIS_URL`, the config will auto-derive both:
```bash
# Minimal config - others will be auto-generated
REDIS_URL=redis://localhost:6379/0
```

---

## Environment Variables Reference

### Required Variables

These **must** be set for the backend to work:

```bash
# Supabase
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...  # or SUPABASE_KEY

# LLM
GEMINI_API_KEY=...  # or OPENAI_API_KEY

# Redis/Celery
REDIS_URL=...
```

### Optional Variables

These have defaults but can be customized:

```bash
# ChromaDB
CHROMA_PERSIST_DIR=./chroma_db  # default

# Embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2  # default
EMBEDDING_DEVICE=cpu  # or cuda

# Application
CHUNK_SIZE=1000  # default
CHUNK_OVERLAP=200  # default
MAX_FILE_SIZE=52428800  # 50MB default
```

---

## Security Best Practices

### ⚠️ NEVER Commit .env Files

Make sure `.env` is in your `.gitignore`:

```bash
# Check if .env is ignored
git check-ignore .env

# Should return: .env
```

### 🔑 Protect Service Role Keys

The `SUPABASE_SERVICE_ROLE_KEY` bypasses all security rules:

- ✅ **Use**: In backend/server code only
- ❌ **Never**: Expose to browsers or frontend apps
- ✅ **Use**: For Celery tasks and background processing
- ❌ **Never**: Include in client-side JavaScript

### 🔐 Rotate Keys Regularly

For production:

1. Generate new API keys monthly
2. Use different keys for dev/staging/production
3. Set up key rotation in Supabase dashboard
4. Monitor API key usage

---

## Testing Your Configuration

After setting up `.env`, test that everything works:

### 1. Test Supabase Connection

```bash
python -c "
from app.config import settings
from supabase import create_client
client = create_client(settings.supabase_url, settings.supabase_key)
print('✓ Supabase connected:', settings.supabase_url)
"
```

### 2. Test Redis Connection

```bash
redis-cli ping
# Should return: PONG
```

### 3. Test Gemini API

```bash
python -c "
import google.generativeai as genai
from app.config import settings
genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel('gemini-pro')
response = model.generate_content('Hello')
print('✓ Gemini API working')
"
```

### 4. Test ChromaDB

```bash
python -c "
from app.services.notes_chroma import notes_chroma_service
count = notes_chroma_service.count()
print(f'✓ ChromaDB connected: {count} documents')
"
```

### 5. Full Health Check

```bash
# Start the server
uvicorn app.main:app --reload &

# Test health endpoint
curl http://localhost:8000/health
curl http://localhost:8000/notes/health

# Should both return: {"status":"healthy",...}
```

---

## Troubleshooting

### "Module not found" errors

```bash
# Make sure you're in the backend directory
cd /path/to/backend

# And running from the correct path
python -m uvicorn app.main:app --reload
```

### "Connection refused" errors

```bash
# Check Redis is running
redis-cli ping

# Start Redis if needed
docker run -d -p 6379:6379 redis:latest
```

### "Supabase authentication failed"

```bash
# Verify you're using the service role key, not anon key
echo $SUPABASE_SERVICE_ROLE_KEY

# Should start with: eyJhbGci... and be very long
```

### "ChromaDB collection not found"

```bash
# Reset ChromaDB
rm -rf ./chroma_db

# Restart the server to recreate collections
```

---

## Next Steps

After configuring your environment:

1. **Install dependencies**: `poetry install`
2. **Apply database schema**: Run `supabase_schema_unified.sql` in Supabase
3. **Start services**:
   ```bash
   # Terminal 1: Redis
   docker run -d -p 6379:6379 redis:latest

   # Terminal 2: API
   uvicorn app.main:app --reload

   # Terminal 3: Celery
   celery -A app.celery_app worker --loglevel=INFO --pool=solo
   ```
4. **Test**: http://localhost:8000/docs

See [UNIFIED_BACKEND_GUIDE.md](UNIFIED_BACKEND_GUIDE.md) for complete documentation.
