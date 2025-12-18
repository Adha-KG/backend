-- Unified Supabase Schema for RAG + Notes Backend
-- This schema includes user_id fields for multi-user support

-- ============================================================================
-- NOTES TABLES (with user_id for multi-user support)
-- ============================================================================

-- Files table: stores uploaded PDF metadata with user ownership
CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,  -- Link to authenticated user
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,  -- Removed UNIQUE to allow same file for different users
    file_size BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',  -- uploaded, processing, indexed, summarizing, completed, failed
    error TEXT,
    user_prompt TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, sha256)  -- Same file hash allowed per user, but not duplicated per user
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files(sha256);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_files_user_sha256 ON files(user_id, sha256);

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
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;

-- Files: Users can only see their own files
CREATE POLICY "Users can view their own files" ON files
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own files" ON files
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own files" ON files
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own files" ON files
    FOR DELETE USING (auth.uid() = user_id);

-- Service role bypass (for backend operations using service_role_key)
CREATE POLICY "Service role has full access to files" ON files
    FOR ALL USING (auth.role() = 'service_role');

-- Chunks: Users can only access chunks from their own files
CREATE POLICY "Users can view chunks from their files" ON chunks
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM files
            WHERE files.id = chunks.file_id
            AND files.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert chunks for their files" ON chunks
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM files
            WHERE files.id = chunks.file_id
            AND files.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update chunks from their files" ON chunks
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM files
            WHERE files.id = chunks.file_id
            AND files.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete chunks from their files" ON chunks
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM files
            WHERE files.id = chunks.file_id
            AND files.user_id = auth.uid()
        )
    );

CREATE POLICY "Service role has full access to chunks" ON chunks
    FOR ALL USING (auth.role() = 'service_role');

-- Summaries: Users can only access summaries from their own files
CREATE POLICY "Users can view summaries from their files" ON summaries
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM files
            WHERE files.id = summaries.file_id
            AND files.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert summaries for their files" ON summaries
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM files
            WHERE files.id = summaries.file_id
            AND files.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update summaries from their files" ON summaries
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM files
            WHERE files.id = summaries.file_id
            AND files.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete summaries from their files" ON summaries
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM files
            WHERE files.id = summaries.file_id
            AND files.user_id = auth.uid()
        )
    );

CREATE POLICY "Service role has full access to summaries" ON summaries
    FOR ALL USING (auth.role() = 'service_role');

-- Notes: Users can only access notes from their own files
CREATE POLICY "Users can view notes from their files" ON notes
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM files
            WHERE files.id = notes.file_id
            AND files.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert notes for their files" ON notes
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM files
            WHERE files.id = notes.file_id
            AND files.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update notes from their files" ON notes
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM files
            WHERE files.id = notes.file_id
            AND files.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete notes from their files" ON notes
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM files
            WHERE files.id = notes.file_id
            AND files.user_id = auth.uid()
        )
    );

CREATE POLICY "Service role has full access to notes" ON notes
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================

-- If you have existing data in the files table without user_id:
-- 1. Add user_id column (done above with DEFAULT NULL)
-- 2. Update existing rows to assign them to a user:
--    UPDATE files SET user_id = '<your-user-uuid>' WHERE user_id IS NULL;
-- 3. Then make user_id NOT NULL if desired:
--    ALTER TABLE files ALTER COLUMN user_id SET NOT NULL;

-- To allow NULL user_id temporarily during migration:
-- ALTER TABLE files ALTER COLUMN user_id DROP NOT NULL;
