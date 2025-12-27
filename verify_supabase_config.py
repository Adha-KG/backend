#!/usr/bin/env python3
"""
Verify Supabase configuration

This script checks if your Supabase keys are valid and configured correctly.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("\n" + "="*80)
print("SUPABASE CONFIGURATION VERIFICATION")
print("="*80)

# Check environment variables
print("\n1. Checking environment variables...")

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase_anon_key = os.getenv('SUPABASE_ANON_KEY')
supabase_service_key = os.getenv('SUPABASE_SERVICE_KEY')
supabase_service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not supabase_url:
    print("   ✗ SUPABASE_URL is not set")
else:
    print(f"   ✓ SUPABASE_URL: {supabase_url}")

if not supabase_key and not supabase_anon_key:
    print("   ✗ SUPABASE_KEY or SUPABASE_ANON_KEY is not set")
else:
    key_to_use = supabase_key or supabase_anon_key
    print(f"   ✓ SUPABASE_KEY/ANON_KEY: {key_to_use[:20]}...")

if supabase_service_key or supabase_service_role_key:
    service_key = supabase_service_key or supabase_service_role_key
    print(f"   ✓ SUPABASE_SERVICE_KEY: {service_key[:20]}...")
else:
    print("   ⚠️  SUPABASE_SERVICE_KEY not set (optional but recommended)")

# Try to import and create client
print("\n2. Testing Supabase client creation...")

try:
    sys.path.insert(0, '/media/ninadgns/ssd/Workspace/SDP/Adha KG/backend')
    from app.auth.supabase_client import get_supabase, get_service_client
    
    # Test anon client
    try:
        supabase = get_supabase()
        print("   ✓ Anon client created successfully")
    except Exception as e:
        print(f"   ✗ Failed to create anon client: {e}")
        sys.exit(1)
    
    # Test service client
    try:
        service_client = get_service_client()
        print("   ✓ Service client created successfully")
    except ValueError as e:
        print(f"   ⚠️  Service client not available: {e}")
    except Exception as e:
        print(f"   ✗ Failed to create service client: {e}")
        
except Exception as e:
    print(f"   ✗ Failed to import supabase client: {e}")
    sys.exit(1)

# Test database connection with anon key
print("\n3. Testing database connection (anon key)...")

try:
    # Simple query to test connection
    result = supabase.rpc('get_postgrest_version').execute()
    print("   ✓ Database connection successful")
except Exception as e:
    error_msg = str(e)
    if "Invalid API key" in error_msg or "401" in error_msg:
        print(f"   ✗ Invalid API key: {error_msg}")
        print("\n   How to fix:")
        print("   1. Go to your Supabase project dashboard")
        print("   2. Settings → API")
        print("   3. Copy the 'anon' 'public' key")
        print("   4. Update SUPABASE_KEY in your .env file")
    elif "404" in error_msg or "not found" in error_msg:
        print("   ⚠️  Connection works but RPC function not found (this is okay)")
    else:
        print(f"   ✗ Connection failed: {error_msg}")

# Test users table access
print("\n4. Testing users table access...")

try:
    result = supabase.table('users').select('id', count='exact').limit(1).execute()
    count = result.count if hasattr(result, 'count') else len(result.data)
    print(f"   ✓ Users table accessible ({count} total users)")
except Exception as e:
    error_msg = str(e)
    if "401" in error_msg or "Invalid API key" in error_msg:
        print(f"   ✗ Unauthorized: Your API key is invalid")
        print("\n   The anon key in your .env doesn't match your Supabase project")
        print("   Get the correct key from: Supabase Dashboard → Settings → API")
    elif "permission denied" in error_msg.lower() or "not authorized" in error_msg.lower():
        print(f"   ✗ Permission denied (RLS is blocking)")
        print("   This is expected if RLS is enabled on the users table")
        print("   Use SUPABASE_SERVICE_KEY for migration operations")
    elif "relation" in error_msg.lower() and "does not exist" in error_msg.lower():
        print(f"   ✗ Users table doesn't exist")
        print("   Run the database migration: migrations/migrate_to_supabase_auth.sql")
    else:
        print(f"   ✗ Failed to access users table: {error_msg}")

# Test service client (if available)
if supabase_service_key or supabase_service_role_key:
    print("\n5. Testing service client access...")
    try:
        service_client = get_service_client()
        result = service_client.table('users').select('id', count='exact').limit(1).execute()
        count = result.count if hasattr(result, 'count') else len(result.data)
        print(f"   ✓ Service client can access users table ({count} total users)")
        print("   ✓ Ready to migrate users!")
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Invalid API key" in error_msg:
            print(f"   ✗ Service key is invalid")
            print("   Get the correct key from: Supabase Dashboard → Settings → API → service_role (secret)")
        else:
            print(f"   ✗ Service client error: {error_msg}")

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)

if supabase_url and (supabase_key or supabase_anon_key):
    print("\n✓ Basic configuration is present")
    print("\nNext steps:")
    print("  1. Verify API keys are correct (see errors above)")
    print("  2. Run database migration: migrations/migrate_to_supabase_auth.sql")
    print("  3. Add SUPABASE_SERVICE_KEY to .env for user migration")
    print("  4. Run: python migrate_existing_users.py --status")
else:
    print("\n✗ Configuration incomplete")
    print("\nRequired in .env file:")
    print("  SUPABASE_URL=https://your-project.supabase.co")
    print("  SUPABASE_KEY=your_anon_key_here")
    print("  SUPABASE_SERVICE_KEY=your_service_role_key_here  # For migration")

print("\n" + "="*80)

