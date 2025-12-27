#!/usr/bin/env python3
"""
Test script to diagnose Supabase Admin API create_user issues
"""
import sys
import secrets

sys.path.insert(0, '/media/ninadgns/ssd/Workspace/SDP/Adha KG/backend')

from app.auth.supabase_client import get_service_client

print("\n" + "="*80)
print("TESTING SUPABASE ADMIN CREATE_USER")
print("="*80)

try:
    print("\n1. Getting service client...")
    supabase = get_service_client()
    print("   ✓ Service client created")
except Exception as e:
    print(f"   ✗ Failed to get service client: {e}")
    print("\nMake sure SUPABASE_SERVICE_KEY is set in your .env file")
    sys.exit(1)

print("\n2. Testing admin API access...")
try:
    users_list = supabase.auth.admin.list_users(page=1, per_page=1)
    print(f"   ✓ Admin API accessible")
    print(f"   Found users in system (showing first if any)")
except Exception as e:
    print(f"   ✗ Cannot access admin API: {type(e).__name__}: {e}")
    sys.exit(1)

print("\n3. Attempting to create a test user...")
test_email = f"test_{secrets.token_hex(4)}@example.com"
test_password = secrets.token_urlsafe(32)

print(f"   Test email: {test_email}")
print(f"   Test password length: {len(test_password)} chars")

try:
    print("   Calling supabase.auth.admin.create_user()...")
    
    response = supabase.auth.admin.create_user({
        'email': test_email,
        'password': test_password,
        'email_confirm': True,
        'user_metadata': {
            'test': True,
            'created_by': 'test_script'
        }
    })
    
    print(f"   ✓ User created successfully!")
    print(f"   User ID: {response.user.id}")
    print(f"   Email: {response.user.email}")
    print(f"   Email confirmed: {response.user.email_confirmed_at is not None}")
    
    # Clean up test user
    print("\n4. Cleaning up test user...")
    try:
        supabase.auth.admin.delete_user(str(response.user.id))
        print("   ✓ Test user deleted")
    except Exception as cleanup_error:
        print(f"   ⚠️  Couldn't delete test user: {cleanup_error}")
        print(f"   You may need to manually delete: {test_email}")
    
    print("\n" + "="*80)
    print("SUCCESS! Supabase Admin API is working correctly.")
    print("="*80)
    print("\nThe issue is not with the Admin API.")
    print("Run the migration again with the updated verbose logging.")
    
except Exception as e:
    print(f"   ✗ Failed to create user")
    print(f"   Exception type: {type(e).__name__}")
    print(f"   Exception message: {str(e)}")
    print(f"   Exception repr: {repr(e)}")
    
    if hasattr(e, '__dict__'):
        print(f"   Exception attributes: {e.__dict__}")
    
    if hasattr(e, 'args'):
        print(f"   Exception args: {e.args}")
    
    import traceback
    print(f"\n   Full traceback:")
    traceback.print_exc()
    
    print("\n" + "="*80)
    print("DIAGNOSIS")
    print("="*80)
    
    error_str = str(e).lower()
    
    if "database error" in error_str:
        print("\n❌ Database Error")
        print("\nPossible causes:")
        print("  1. Supabase Auth is not enabled in your project")
        print("     → Go to Supabase Dashboard → Authentication → Enable Email provider")
        print("  2. Email confirmations are required but not configured")
        print("     → Go to Supabase Dashboard → Authentication → Email → Disable 'Confirm email'")
        print("  3. Password requirements not met")
        print("     → Check your project's password policy settings")
        print("  4. Database trigger/function error")
        print("     → Check Supabase logs for more details")
    
    elif "invalid api key" in error_str or "401" in error_str:
        print("\n❌ Invalid API Key")
        print("\nYour SUPABASE_SERVICE_KEY is incorrect.")
        print("Get the correct key from: Supabase Dashboard → Settings → API → service_role key")
    
    elif "rate limit" in error_str or "429" in error_str:
        print("\n❌ Rate Limited")
        print("\nYou've made too many requests. Wait a few minutes and try again.")
    
    else:
        print("\n❌ Unknown Error")
        print("\nCheck the error details above and:")
        print("  1. Verify Supabase Auth is enabled in your project")
        print("  2. Check Supabase logs in your dashboard")
        print("  3. Verify your project URL and service key are correct")
    
    sys.exit(1)

