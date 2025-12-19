-- Fix foreign key constraints for quiz tables to reference users table instead of auth.users
-- Also disable RLS policies that use auth.uid() since we're not using Supabase auth
-- Run this SQL in your Supabase SQL editor to fix the foreign key constraints

-- Drop existing foreign key constraints
ALTER TABLE IF EXISTS quizzes DROP CONSTRAINT IF EXISTS quizzes_user_id_fkey;
ALTER TABLE IF EXISTS quiz_attempts DROP CONSTRAINT IF EXISTS quiz_attempts_user_id_fkey;

-- Add new foreign key constraints pointing to users table
ALTER TABLE IF EXISTS quizzes 
    ADD CONSTRAINT quizzes_user_id_fkey 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE IF EXISTS quiz_attempts 
    ADD CONSTRAINT quiz_attempts_user_id_fkey 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Disable RLS since we're not using Supabase auth (auth.uid() won't work)
-- The backend will handle authorization via JWT tokens
ALTER TABLE IF EXISTS quizzes DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS quiz_questions DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS quiz_attempts DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS quiz_answers DISABLE ROW LEVEL SECURITY;

-- Drop existing RLS policies (they won't work without Supabase auth)
DROP POLICY IF EXISTS "Users can view their own quizzes" ON quizzes;
DROP POLICY IF EXISTS "Users can create their own quizzes" ON quizzes;
DROP POLICY IF EXISTS "Users can update their own quizzes" ON quizzes;
DROP POLICY IF EXISTS "Users can delete their own quizzes" ON quizzes;
DROP POLICY IF EXISTS "Users can view questions for their own quizzes" ON quiz_questions;
DROP POLICY IF EXISTS "Users can create questions for their own quizzes" ON quiz_questions;
DROP POLICY IF EXISTS "Users can view their own attempts" ON quiz_attempts;
DROP POLICY IF EXISTS "Users can create their own attempts" ON quiz_attempts;
DROP POLICY IF EXISTS "Users can update their own attempts" ON quiz_attempts;
DROP POLICY IF EXISTS "Users can view answers for their own attempts" ON quiz_answers;
DROP POLICY IF EXISTS "Users can create answers for their own attempts" ON quiz_answers;
DROP POLICY IF EXISTS "Users can update answers for their own attempts" ON quiz_answers;
