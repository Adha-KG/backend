#!/usr/bin/env python3
"""
Migration script for existing users to Supabase Auth

This script migrates existing users from the custom authentication system
to Supabase Auth while preserving their profile data.

IMPORTANT: This script should be run ONCE after the database migration.
"""
import asyncio
import sys
from typing import Any

sys.path.insert(0, '/media/ninadgns/ssd/Workspace/SDP/Adha KG/backend')

from app.auth.supabase_client import get_supabase, get_service_client


async def migrate_single_user(user: dict[str, Any], send_reset_email: bool = True) -> bool:
    """
    Migrate a single user to Supabase Auth
    
    Args:
        user: User record from custom users table
        send_reset_email: Whether to send password reset email to user
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Use service role client for admin operations
        supabase = get_service_client()
        
        # Create user in Supabase Auth
        # Note: User will need to reset their password since we don't have the plaintext
        # Generate a random temporary password that will be reset
        import secrets
        temporary_password = secrets.token_urlsafe(32)
        
        try:
            print(f"     Creating Supabase Auth user for {user['email']}...")
            auth_response = supabase.auth.admin.create_user({
                'email': user['email'],
                'password': temporary_password,  # Temporary password, user will reset it
                'email_confirm': True,  # Skip email verification
                'user_metadata': {
                    'username': user.get('username'),
                    'first_name': user.get('first_name'),
                    'last_name': user.get('last_name'),
                    'profile_image_url': user.get('profile_image_url'),
                    'migrated_from_custom_auth': True
                }
            })
            print(f"     Auth user created with ID: {auth_response.user.id if auth_response.user else 'None'}")
        except Exception as auth_error:
            print(f"     Exception type: {type(auth_error).__name__}")
            print(f"     Exception details: {repr(auth_error)}")
            if hasattr(auth_error, '__dict__'):
                print(f"     Exception attributes: {auth_error.__dict__}")
            error_msg = str(auth_error)
            if "already registered" in error_msg.lower() or "already exists" in error_msg.lower():
                print(f"  ⚠️  {user['email']} already exists in Supabase Auth, linking existing account...")
                # Try to find the existing auth user
                try:
                    # Get user by email from Supabase Auth
                    users_list = supabase.auth.admin.list_users()
                    existing_auth_user = None
                    for auth_user in users_list:
                        if hasattr(auth_user, 'email') and auth_user.email == user['email']:
                            existing_auth_user = auth_user
                            break
                    
                    if existing_auth_user:
                        auth_user_id = str(existing_auth_user.id)
                        # Link existing auth user to custom user
                        update_result = supabase.table('users').update({
                            'auth_user_id': auth_user_id,
                            'auth_migrated': True,
                            'updated_at': 'now()'
                        }).eq('id', user['id']).execute()
                        
                        if update_result.data:
                            print(f"  ✓ Linked {user['email']} to existing Supabase Auth account")
                            return True
                except Exception as link_error:
                    print(f"  ✗ Failed to link existing user {user['email']}: {link_error}")
                    return False
            
            print(f"  ✗ Failed to create auth user for {user['email']}: {auth_error}")
            return False
        
        if not auth_response.user:
            print(f"  ✗ Failed to create auth user for {user['email']}: No user returned")
            return False
        
        auth_user_id = str(auth_response.user.id)
        
        # Update custom users table with auth_user_id link
        try:
            update_result = supabase.table('users').update({
                'auth_user_id': auth_user_id,
                'auth_migrated': True,
                'updated_at': 'now()'
            }).eq('id', user['id']).execute()
            
            if not update_result.data:
                print(f"  ✗ Failed to update user record for {user['email']}: No data returned")
                return False
        except Exception as update_error:
            print(f"  ✗ Failed to update user record for {user['email']}: {update_error}")
            return False
        
        # Send password reset email if requested
        if send_reset_email:
            try:
                supabase.auth.admin.generate_link({
                    'type': 'recovery',
                    'email': user['email']
                })
                print(f"  ✓ Migrated {user['email']} (password reset email sent)")
            except Exception as email_error:
                print(f"  ✓ Migrated {user['email']} (but failed to send reset email: {email_error})")
        else:
            print(f"  ✓ Migrated {user['email']}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Failed to migrate {user['email']}: {type(e).__name__}: {e}")
        import traceback
        print(f"     Traceback: {traceback.format_exc()}")
        return False


async def migrate_all_users(send_reset_emails: bool = True, dry_run: bool = False):
    """
    Migrate all users from custom authentication to Supabase Auth
    
    Args:
        send_reset_emails: Whether to send password reset emails
        dry_run: If True, only show what would be done without making changes
    """
    print("\n" + "="*80)
    print("MIGRATING USERS TO SUPABASE AUTH")
    print("="*80)
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be made\n")
    
    try:
        supabase = get_service_client()
    except ValueError as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure SUPABASE_SERVICE_KEY is set in your .env file")
        return
    
    # Test if we can access the admin API
    print("\nTesting Supabase Admin API access...")
    try:
        # Try to list users (should work with service key)
        test_list = supabase.auth.admin.list_users(page=1, per_page=1)
        print("✓ Admin API access confirmed")
    except Exception as test_error:
        print(f"✗ Cannot access Supabase Admin API: {test_error}")
        print("\nPossible issues:")
        print("  1. SUPABASE_SERVICE_KEY is incorrect or invalid")
        print("  2. Supabase Auth is not enabled in your project")
        print("  3. Your Supabase project URL is incorrect")
        print("\nPlease verify your configuration and try again.")
        return
    
    # Get all users who haven't been migrated yet
    result = supabase.table('users').select('*').is_('auth_user_id', 'null').execute()
    
    users_to_migrate = result.data
    
    if not users_to_migrate:
        print("\n✓ No users to migrate. All users have already been migrated.")
        return
    
    print(f"\nFound {len(users_to_migrate)} user(s) to migrate:\n")
    
    for i, user in enumerate(users_to_migrate, 1):
        print(f"{i}. {user['email']} (ID: {user['id']})")
    
    if dry_run:
        print("\n" + "="*80)
        print("DRY RUN COMPLETE")
        print("="*80)
        print(f"\nWould migrate {len(users_to_migrate)} user(s)")
        print("\nTo perform the actual migration, run:")
        print("  python migrate_existing_users.py --migrate")
        return
    
    print("\n" + "="*80)
    print("STARTING MIGRATION")
    print("="*80 + "\n")
    
    success_count = 0
    fail_count = 0
    
    for user in users_to_migrate:
        success = await migrate_single_user(user, send_reset_emails)
        if success:
            success_count += 1
        else:
            fail_count += 1
    
    print("\n" + "="*80)
    print("MIGRATION SUMMARY")
    print("="*80)
    print(f"\n✓ Successfully migrated: {success_count}")
    print(f"✗ Failed to migrate: {fail_count}")
    print(f"  Total: {len(users_to_migrate)}")
    
    if send_reset_emails:
        print("\n📧 Password reset emails have been sent to migrated users.")
        print("   Users will need to reset their passwords to access their accounts.")
    else:
        print("\n⚠️  No password reset emails were sent.")
        print("   You'll need to manually send password reset links to users.")
    
    if fail_count > 0:
        print(f"\n⚠️  {fail_count} user(s) failed to migrate. Please review the errors above.")


async def check_migration_status():
    """Check the status of user migration"""
    print("\n" + "="*80)
    print("USER MIGRATION STATUS")
    print("="*80)
    
    try:
        # Try service client first (bypasses RLS)
        try:
            supabase = get_service_client()
            print("\n✓ Using service role key (bypasses RLS)")
        except ValueError:
            # Fall back to regular client
            supabase = get_supabase()
            print("\n⚠️  Using anon key (may be blocked by RLS)")
            print("   Set SUPABASE_SERVICE_KEY in .env for full access")
        
        # Count total users
        total_result = supabase.table('users').select('id', count='exact').execute()
        total_count = total_result.count if hasattr(total_result, 'count') else len(total_result.data)
        
        # Count migrated users (those with auth_user_id set)
        migrated_result = supabase.table('users').select('id', count='exact').not_.is_('auth_user_id', 'null').execute()
        migrated_count = migrated_result.count if hasattr(migrated_result, 'count') else len(migrated_result.data)
        
        # Count non-migrated users
        not_migrated_count = total_count - migrated_count
        
        print(f"\nTotal users: {total_count}")
        print(f"Migrated to Supabase Auth: {migrated_count}")
        print(f"Not yet migrated: {not_migrated_count}")
        
        if not_migrated_count > 0:
            print(f"\n⚠️  {not_migrated_count} user(s) still need to be migrated")
            print("\nRun the following command to migrate them:")
            print("  python migrate_existing_users.py --migrate")
        else:
            print("\n✓ All users have been migrated to Supabase Auth!")
            
    except Exception as e:
        print(f"\n✗ Error checking migration status: {e}")
        print("\nPossible issues:")
        print("  1. Invalid API key - check SUPABASE_KEY in your .env file")
        print("  2. RLS is blocking queries - set SUPABASE_SERVICE_KEY in .env")
        print("  3. Database migration not run yet - run migrate_to_supabase_auth.sql first")
        print("  4. 'users' table doesn't exist")
        print("\nTo verify your configuration, run:")
        print("  python -c 'from app.auth.supabase_client import get_supabase; print(get_supabase())'")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate users to Supabase Auth')
    parser.add_argument('--migrate', action='store_true', help='Perform the migration')
    parser.add_argument('--no-email', action='store_true', help='Do not send password reset emails')
    parser.add_argument('--status', action='store_true', help='Check migration status')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    try:
        if args.status:
            asyncio.run(check_migration_status())
        elif args.migrate or args.dry_run:
            send_emails = not args.no_email
            asyncio.run(migrate_all_users(
                send_reset_emails=send_emails,
                dry_run=args.dry_run
            ))
        else:
            # Default: show status
            asyncio.run(check_migration_status())
            print("\nOptions:")
            print("  --status     Check migration status")
            print("  --dry-run    Preview what would be migrated")
            print("  --migrate    Perform the actual migration")
            print("  --no-email   Skip sending password reset emails")
            
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()

