# Quiz Migration Checklist

## ⚠️ IMPORTANT: Run Migration Fix First!

Before the quiz saving features will work, you **must** run the migration fix script to update the foreign key constraints.

## Step 1: Run the Migration Fix

1. Open your Supabase SQL Editor
2. Run the contents of `fix_quiz_foreign_keys.sql`
3. This will:
   - Fix foreign key constraints to reference `users` table instead of `auth.users`
   - Disable RLS policies (since you're using JWT auth, not Supabase auth)

## Step 2: Verify Migration Success

After running the migration, verify:

```sql
-- Check foreign key constraints
SELECT 
    conname AS constraint_name,
    conrelid::regclass AS table_name,
    confrelid::regclass AS referenced_table
FROM pg_constraint
WHERE conname LIKE '%quiz%user%'
AND contype = 'f';
```

You should see:
- `quizzes_user_id_fkey` → references `users(id)`
- `quiz_attempts_user_id_fkey` → references `users(id)`

## Step 3: Test Quiz Generation

1. Generate a quiz through the frontend
2. Check the backend logs - you should see:
   - `Created quiz record {quiz_id} with status 'generating'`
   - `Inserted {count} questions into database for quiz {quiz_id}`
   - No foreign key constraint errors

3. Verify in database:
```sql
-- Check if quiz was saved
SELECT id, title, status, num_questions, created_at 
FROM quizzes 
ORDER BY created_at DESC 
LIMIT 5;

-- Check if questions were saved
SELECT quiz_id, COUNT(*) as question_count
FROM quiz_questions
GROUP BY quiz_id
ORDER BY quiz_id DESC
LIMIT 5;
```

## What Should Work After Migration

✅ Quiz generation saves to database  
✅ Questions are stored in `quiz_questions` table  
✅ Quiz status updates from 'generating' to 'ready'  
✅ Quiz retrieval by ID works  
✅ Quiz attempts can be created  
✅ Answers can be submitted  

## Troubleshooting

### If you still get foreign key errors:
- Make sure the migration script ran successfully
- Verify the `users` table exists and has the correct structure
- Check that your user_id from JWT matches a user in the `users` table

### If quizzes aren't saving:
- Check backend logs for errors
- Verify Supabase connection is working
- Ensure user exists in `users` table before generating quiz
