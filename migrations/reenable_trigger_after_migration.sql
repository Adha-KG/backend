-- Re-enable the auto-sync trigger after user migration is complete
-- Run this AFTER all users have been migrated
-- This ensures new signups automatically create user profiles

-- Re-create the trigger
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Verification
SELECT 'Trigger re-enabled successfully' as status;

-- Test that it works (optional)
-- You can test by signing up a new user through the API

