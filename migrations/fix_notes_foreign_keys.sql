-- Fix Notes Tables to Work with Custom Users Table
-- This migration fixes the foreign key constraints and RLS policies for notes tables
-- to work with the custom 'users' table instead of Supabase's 'auth.users' table
-- Run this SQL in your Supabase SQL editor

-- ============================================================================
-- STEP 1: Create the users table (if it doesn't exist)
-- ============================================================================
-- Based on the user_service.py implementation, the users table should have:
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    profile_image_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_sign_in_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ============================================================================
-- STEP 2: Drop existing foreign key constraints from files table
-- ============================================================================
-- The files table currently references auth.users(id), we need to change it to users(id)
ALTER TABLE IF EXISTS files DROP CONSTRAINT IF EXISTS files_user_id_fkey;

-- ============================================================================
-- STEP 3: Add new foreign key constraint pointing to users table
-- ============================================================================
ALTER TABLE IF EXISTS files 
    ADD CONSTRAINT files_user_id_fkey 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- ============================================================================
-- STEP 4: Disable Row Level Security (RLS) on all notes-related tables
-- ============================================================================
-- Since we're not using Supabase auth (auth.uid() won't work with custom JWT tokens),
-- we need to disable RLS and rely on backend authentication via JWT tokens

ALTER TABLE IF EXISTS files DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS chunks DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS summaries DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS notes DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- STEP 5: Drop existing RLS policies (they won't work without Supabase auth)
-- ============================================================================

-- Drop files policies
DROP POLICY IF EXISTS "Users can view their own files" ON files;
DROP POLICY IF EXISTS "Users can insert their own files" ON files;
DROP POLICY IF EXISTS "Users can update their own files" ON files;
DROP POLICY IF EXISTS "Users can delete their own files" ON files;
DROP POLICY IF EXISTS "Service role has full access to files" ON files;

-- Drop chunks policies
DROP POLICY IF EXISTS "Users can view chunks from their files" ON chunks;
DROP POLICY IF EXISTS "Users can insert chunks for their files" ON chunks;
DROP POLICY IF EXISTS "Users can update chunks from their files" ON chunks;
DROP POLICY IF EXISTS "Users can delete chunks from their files" ON chunks;
DROP POLICY IF EXISTS "Service role has full access to chunks" ON chunks;

-- Drop summaries policies
DROP POLICY IF EXISTS "Users can view summaries from their files" ON summaries;
DROP POLICY IF EXISTS "Users can insert summaries for their files" ON summaries;
DROP POLICY IF EXISTS "Users can update summaries from their files" ON summaries;
DROP POLICY IF EXISTS "Users can delete summaries from their files" ON summaries;
DROP POLICY IF EXISTS "Service role has full access to summaries" ON summaries;

-- Drop notes policies
DROP POLICY IF EXISTS "Users can view notes from their files" ON notes;
DROP POLICY IF EXISTS "Users can insert notes for their files" ON notes;
DROP POLICY IF EXISTS "Users can update notes from their files" ON notes;
DROP POLICY IF EXISTS "Users can delete notes from their files" ON notes;
DROP POLICY IF EXISTS "Service role has full access to notes" ON notes;

-- ============================================================================
-- STEP 6: Verify the changes
-- ============================================================================
-- You can verify the changes with these queries:

-- Check if users table exists and has correct structure
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'users' 
-- ORDER BY ordinal_position;

-- Check foreign key constraints on files table
-- SELECT conname, contype, pg_get_constraintdef(oid) 
-- FROM pg_constraint 
-- WHERE conrelid = 'files'::regclass;

-- Check RLS status
-- SELECT tablename, rowsecurity 
-- FROM pg_tables 
-- WHERE tablename IN ('files', 'chunks', 'summaries', 'notes');

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================
-- 1. If you have existing data in the files table with user_id values that don't 
--    exist in the users table, you'll need to either:
--    a) Create those users in the users table first, or
--    b) Set user_id to NULL temporarily (requires making column nullable), or
--    c) Delete those orphaned records
--
-- 2. To make user_id nullable temporarily during migration (if needed):
--    ALTER TABLE files ALTER COLUMN user_id DROP NOT NULL;
--
-- 3. To make user_id NOT NULL after migration:
--    ALTER TABLE files ALTER COLUMN user_id SET NOT NULL;
--
-- 4. The backend now handles all authorization via JWT tokens and passes user_id
--    to all database queries, so RLS is not needed.
--
-- 5. Make sure to update your Supabase client in the backend to use the service_role_key
--    or ensure the anon key has appropriate permissions without RLS.
