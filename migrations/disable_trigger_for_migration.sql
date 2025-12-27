-- Temporarily disable the auto-sync trigger for user migration
-- Run this BEFORE migrating users
-- This prevents the trigger from interfering with manual user creation

-- Disable the trigger
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- You can re-enable it after migration by running:
-- CREATE TRIGGER on_auth_user_created
--     AFTER INSERT ON auth.users
--     FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Verification
SELECT 'Trigger disabled successfully' as status;

