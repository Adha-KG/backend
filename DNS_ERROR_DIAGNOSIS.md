# DNS Error Diagnosis - Supabase Connection Failure

## Issue Summary

The unified backend is failing to upload files with the error:
```
Upload failed: [Errno -2] Name or service not known
```

## Root Cause

**The Supabase project URLs in your `.env` file cannot be resolved via DNS.**

### DNS Test Results

```bash
# Testing the configured Supabase URL
$ nslookup ojskecyqxhjsboszlpxg.supabase.co
** server can't find ojskecyqxhjsboszlpxg.supabase.co: NXDOMAIN

# Testing the RAG backend Supabase URL
$ nslookup xzryjsohpbhmqdjxhkil.supabase.co
** server can't find xzryjsohpbhmqdjxhkil.supabase.co: NXDOMAIN

# Verification that DNS is working
$ nslookup supabase.com
Name:	supabase.com
Address: 216.150.1.193  ✓ DNS works fine
```

## What This Means

The Supabase projects with these URLs either:
1. **Never existed** - These might be example/placeholder URLs
2. **Were deleted** - Projects may have been removed from Supabase
3. **Are paused** - Supabase projects can be paused which removes their DNS entries

## Solution

You need to use a **valid Supabase project URL**. Here are your options:

### Option 1: Create a New Supabase Project (Recommended)

1. **Go to Supabase Dashboard**: https://app.supabase.com
2. **Create a new project** or select an existing one
3. **Get your project credentials**:
   - Go to Project Settings → API
   - Copy the **Project URL** (e.g., `https://xxxxxxxxxxxxx.supabase.co`)
   - Copy the **anon public** key
   - Copy the **service_role** key (keep this secret!)

4. **Update your `.env` file**:
   ```bash
   cd "/mnt/NewVolume2/Android Projects/adha_keji/backend"
   nano .env
   ```

   Replace these lines:
   ```bash
   SUPABASE_URL=https://YOUR_ACTUAL_PROJECT_ID.supabase.co
   SUPABASE_KEY=your_anon_key_here
   SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
   ```

5. **Set up the database schema**:
   ```bash
   # In Supabase Dashboard, go to SQL Editor
   # Run the schema from: supabase_schema_unified.sql
   ```

### Option 2: Use an Existing Supabase Project

If you already have a working Supabase project:

1. Find your project at https://app.supabase.com
2. Get the URL and keys from Project Settings → API
3. Update the `.env` file as shown above
4. Make sure the database schema is set up (run `supabase_schema_unified.sql`)

### Option 3: Test with Local Development

For local testing without Supabase, you would need to:
1. Set up Supabase locally using Docker
2. Or use a different database backend (requires code changes)

## Verification Steps

After updating your `.env` file:

### 1. Test DNS Resolution
```bash
# Replace with your actual Supabase URL
nslookup YOUR_PROJECT_ID.supabase.co
# Should return an IP address, not NXDOMAIN
```

### 2. Test HTTP Connection
```bash
# Replace with your actual Supabase URL
curl -I https://YOUR_PROJECT_ID.supabase.co
# Should return HTTP 200 or similar, not connection error
```

### 3. Test Configuration Loading
```bash
cd "/mnt/NewVolume2/Android Projects/adha_keji/backend"
poetry run python -c "
from app.config import settings
print(f'Supabase URL: {settings.supabase_url}')
print(f'Key loaded: {len(settings.supabase_key) > 0}')
"
```

### 4. Restart Services
```bash
# Stop any running services (Ctrl+C)

# Start Redis
docker run -d -p 6379:6379 redis:latest

# Start API
poetry run uvicorn app.main:app --reload --port 8000

# Start Celery
poetry run celery -A app.celery_app worker --loglevel=INFO --pool=solo
```

### 5. Test Upload
```bash
# Try uploading a test PDF
curl -X POST "http://localhost:8000/notes/upload" \
  -F "file=@test.pdf" \
  -F "note_style=moderate"
```

## Enhanced Logging

I've added detailed logging to help diagnose issues:
- [app/routes/notes.py](app/routes/notes.py) - Step-by-step upload logging
- [app/services/notes_db.py](app/services/notes_db.py) - Database connection logging

The logs will now show:
- When Supabase client is initialized
- Which URL and key type is being used
- Exactly where any database operation fails
- Full traceback for all errors

## Current Status

✅ **Fixed Issues:**
- Missing `google-generativeai` dependency (removed, using REST API)
- Import errors for `process_pdf` (reorganized task structure)
- "embedded null byte" error (fixed hash function)
- Added comprehensive error logging

❌ **Current Blocker:**
- **Invalid Supabase URL** - Cannot resolve DNS for configured Supabase projects
- Need valid Supabase credentials to proceed

## Next Steps

1. **Get valid Supabase credentials** (see Option 1 or 2 above)
2. **Update `.env` file** with the new credentials
3. **Apply database schema** using `supabase_schema_unified.sql`
4. **Restart services** and test the upload endpoint
5. **Check logs** for any remaining issues

## Questions?

If you encounter any issues:
1. Check the FastAPI logs for detailed error messages
2. Verify DNS resolution: `nslookup YOUR_PROJECT_ID.supabase.co`
3. Test Supabase connection in Python:
   ```python
   from supabase import create_client
   client = create_client("YOUR_URL", "YOUR_KEY")
   # Should not raise an error
   ```

---

**Summary**: The DNS error is caused by using Supabase project URLs that don't exist or are no longer active. You need to create a new Supabase project or use credentials from an existing, active project.
