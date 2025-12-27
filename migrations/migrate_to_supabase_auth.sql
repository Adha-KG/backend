-- Migration to Supabase Auth
-- This migration converts the custom authentication system to use Supabase Auth
-- Run this SQL in your Supabase SQL editor

-- ============================================================================
-- IMPORTANT: BACKUP YOUR DATA BEFORE RUNNING THIS MIGRATION
-- ============================================================================

-- ============================================================================
-- STEP 1: Create a backup of the users table (recommended)
-- ============================================================================
-- Uncomment the following line to create a backup:
-- CREATE TABLE users_backup AS SELECT * FROM users;

-- ============================================================================
-- STEP 2: Prepare the users table for migration
-- ============================================================================

-- First, make password_hash nullable (for gradual migration)
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;

-- Add a migration status column (optional, helps track migration progress)
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_migrated BOOLEAN DEFAULT FALSE;

-- ============================================================================
-- STEP 3: Link users table to auth.users (MODIFIED FOR EXISTING USERS)
-- ============================================================================

-- IMPORTANT: If you have existing users, DO NOT run the foreign key constraint yet!
-- The constraint below is commented out and should only be enabled AFTER
-- you've migrated all existing users to Supabase Auth.

-- Strategy: Instead of directly linking users.id to auth.users.id (which would
-- break existing users), we'll add a new column auth_user_id to track the link.

-- Add a new column to link to auth.users.id
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_user_id UUID;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_auth_user_id ON users(auth_user_id);

-- Add foreign key constraint for the new column
-- This won't affect existing users since auth_user_id will be NULL initially
ALTER TABLE users ADD CONSTRAINT users_auth_user_id_fkey 
    FOREIGN KEY (auth_user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

-- For new users created through Supabase Auth, we'll set both id and auth_user_id
-- to the same value (the auth.users.id)

-- OPTIONAL: After migrating all users, if you want to enforce the relationship:
-- 1. Ensure all users have auth_user_id populated
-- 2. Update users.id to match auth_user_id
-- 3. Add the constraint: ALTER TABLE users ADD CONSTRAINT users_id_fkey 
--    FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;

-- ============================================================================
-- STEP 4: Update indexes
-- ============================================================================

-- The existing indexes should still work, but let's ensure they're optimal
CREATE INDEX IF NOT EXISTS idx_users_id ON users(id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ============================================================================
-- STEP 5: Update foreign key constraints on other tables
-- ============================================================================

-- Update documents table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents') THEN
        -- Drop existing constraint if it exists
        ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_user_id_fkey;
        -- Add new constraint referencing users(id) which now links to auth.users(id)
        ALTER TABLE documents ADD CONSTRAINT documents_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Update files table (for notes)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'files') THEN
        ALTER TABLE files DROP CONSTRAINT IF EXISTS files_user_id_fkey;
        ALTER TABLE files ADD CONSTRAINT files_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Update chat_sessions table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_sessions') THEN
        ALTER TABLE chat_sessions DROP CONSTRAINT IF EXISTS chat_sessions_user_id_fkey;
        ALTER TABLE chat_sessions ADD CONSTRAINT chat_sessions_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Update quizzes table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'quizzes') THEN
        ALTER TABLE quizzes DROP CONSTRAINT IF EXISTS quizzes_user_id_fkey;
        ALTER TABLE quizzes ADD CONSTRAINT quizzes_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Update quiz_attempts table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'quiz_attempts') THEN
        ALTER TABLE quiz_attempts DROP CONSTRAINT IF EXISTS quiz_attempts_user_id_fkey;
        ALTER TABLE quiz_attempts ADD CONSTRAINT quiz_attempts_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- ============================================================================
-- STEP 6: Optional - Remove password_hash column (after migration is complete)
-- ============================================================================
-- ONLY run this after you've successfully migrated all users to Supabase Auth
-- and verified everything works correctly

-- ALTER TABLE users DROP COLUMN IF EXISTS password_hash;
-- ALTER TABLE users DROP COLUMN IF EXISTS auth_migrated;

-- ============================================================================
-- STEP 7: Enable Row Level Security (RLS) - IMPORTANT
-- ============================================================================

-- Enable RLS on users table
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read their own profile
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth.uid() = id);

-- Policy: Users can update their own profile
CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid() = id);

-- Policy: Service role has full access (for backend operations)
CREATE POLICY "Service role has full access to users" ON users
    FOR ALL USING (auth.role() = 'service_role');

-- Note: INSERT policy is not needed since user creation is handled through signup
-- which uses the service role or proper auth context

-- ============================================================================
-- STEP 8: Create trigger to auto-create user profile on auth signup (UPDATED)
-- ============================================================================

-- This trigger automatically creates a profile entry in the users table
-- when a new user signs up through Supabase Auth

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    -- Insert new user profile with both id and auth_user_id set to auth.users.id
    INSERT INTO public.users (
        id, 
        auth_user_id, 
        email, 
        username, 
        first_name, 
        last_name, 
        profile_image_url, 
        created_at, 
        updated_at
    )
    VALUES (
        NEW.id,  -- Use auth.users.id as the primary key for new users
        NEW.id,  -- Also store in auth_user_id for consistency
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'username', NULL),
        COALESCE(NEW.raw_user_meta_data->>'first_name', NULL),
        COALESCE(NEW.raw_user_meta_data->>'last_name', NULL),
        COALESCE(NEW.raw_user_meta_data->>'profile_image_url', NULL),
        NOW(),
        NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        auth_user_id = EXCLUDED.auth_user_id,
        email = EXCLUDED.email,
        updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create the trigger
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check users table structure
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'users' 
-- ORDER BY ordinal_position;

-- Check foreign key constraints
-- SELECT conname, contype, pg_get_constraintdef(oid) 
-- FROM pg_constraint 
-- WHERE conrelid = 'users'::regclass;

-- Check RLS status
-- SELECT tablename, rowsecurity 
-- FROM pg_tables 
-- WHERE tablename = 'users';

-- Check RLS policies
-- SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
-- FROM pg_policies
-- WHERE tablename = 'users';

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================

-- For existing users:
-- You need to create a Python script to migrate existing users to Supabase Auth:
-- 
-- 1. For each user in the custom users table:
--    a. Create Supabase Auth user using supabase.auth.admin.create_user({
--         email: user.email,
--         password: "temporary_password",  // User will need to reset
--         email_confirm: true,
--         user_metadata: {
--           username: user.username,
--           first_name: user.first_name,
--           last_name: user.last_name,
--           profile_image_url: user.profile_image_url
--         }
--       })
--    b. Update the custom users table record with the new auth.users.id
--    c. Send password reset email to user
--    d. Mark user as migrated (auth_migrated = true)
--
-- 2. Alternative approach: Require users to "re-register" with their email,
--    and auto-link to existing profile if email matches
--
-- 3. After all users are migrated, you can drop the password_hash column

-- ============================================================================
-- ROLLBACK INSTRUCTIONS
-- ============================================================================

-- If you need to rollback this migration:
-- 1. Drop the foreign key constraint: ALTER TABLE users DROP CONSTRAINT users_id_fkey;
-- 2. Make password_hash NOT NULL again: ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL;
-- 3. Drop the trigger: DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
-- 4. Drop the function: DROP FUNCTION IF EXISTS public.handle_new_user();
-- 5. Disable RLS and drop policies if needed
-- 6. Restore from backup if necessary: INSERT INTO users SELECT * FROM users_backup;

