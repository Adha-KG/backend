-- Unified Supabase Schema - NOTES TABLES ONLY
-- This creates the notes tables without requiring authentication (user_id is nullable)
-- Run this in your Supabase SQL Editor

-- ============================================================================
-- NOTES TABLES (user_id is optional for now)
-- ============================================================================

-- Files table: stores uploaded PDF metadata
CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,  -- Optional for now (will reference auth.users when authentication is added)
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',  -- uploaded, processing, indexed, summarizing, completed, failed
    error TEXT,
    user_prompt TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files(sha256);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at DESC);

-- Chunks table: stores text chunks from PDFs
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    chunk_id TEXT NOT NULL UNIQUE,  -- file_id__chunk_index format
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    token_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for chunks
CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_id ON chunks(chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON chunks(file_id, chunk_index);

-- Summaries table: stores per-chunk summaries
CREATE TABLE IF NOT EXISTS summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    summary_text TEXT NOT NULL,
    llm_provider TEXT,
    llm_model TEXT,
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for summaries
CREATE INDEX IF NOT EXISTS idx_summaries_file_id ON summaries(file_id);
CREATE INDEX IF NOT EXISTS idx_summaries_chunk_id ON summaries(chunk_id);

-- Notes table: stores final synthesized notes
CREATE TABLE IF NOT EXISTS notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE UNIQUE,
    note_text TEXT NOT NULL,
    metadata JSONB,  -- store additional info like total_chunks, synthesis_method, etc.
    llm_provider TEXT,
    llm_model TEXT,
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for notes
CREATE INDEX IF NOT EXISTS idx_notes_file_id ON notes(file_id);

-- ============================================================================
-- ROW LEVEL SECURITY (Disabled for now - enable when you add authentication)
-- ============================================================================

-- Uncomment these when you're ready to enable authentication:
-- ALTER TABLE files ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE summaries ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE notes ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- USAGE INSTRUCTIONS
-- ============================================================================

-- 1. Go to your Supabase Dashboard: https://app.supabase.com
-- 2. Select your project: xzryjsohbwnoxtglehhe
-- 3. Go to SQL Editor
-- 4. Paste this entire file and click "Run"
-- 5. Verify tables were created by checking the Table Editor

-- After running this, your backend should work!
