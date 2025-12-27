#!/usr/bin/env python3
"""
Test script for Supabase Auth integration
Run this script to test the authentication flows after migration
"""
import asyncio
import sys
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, '/media/ninadgns/ssd/Workspace/SDP/Adha KG/backend')

from app.auth.supabase_client import get_supabase
from app.services.user_service import sign_up_user, sign_in_user, get_user_by_id


async def test_signup():
    """Test user signup with Supabase Auth"""
    print("\n" + "="*60)
    print("Testing Signup Flow")
    print("="*60)
    
    test_email = f"test_{datetime.now().timestamp()}@example.com"
    test_password = "TestPassword123!"
    
    try:
        result = await sign_up_user(
            email=test_email,
            password=test_password,
            user_data={
                'username': 'testuser',
                'first_name': 'Test',
                'last_name': 'User',
                'profile_image_url': 'https://example.com/avatar.jpg'
            }
        )
        
        print("✓ Signup successful!")
        print(f"  User ID: {result['user']['id']}")
        print(f"  Email: {result['user']['email']}")
        print(f"  Username: {result['user']['username']}")
        print(f"  Access Token: {result['access_token'][:20]}...")
        print(f"  Refresh Token: {result['refresh_token'][:20] if result.get('refresh_token') else 'None'}...")
        
        return result
    except Exception as e:
        print(f"✗ Signup failed: {e}")
        return None


async def test_signin(email: str, password: str):
    """Test user signin with Supabase Auth"""
    print("\n" + "="*60)
    print("Testing Signin Flow")
    print("="*60)
    
    try:
        result = await sign_in_user(email=email, password=password)
        
        print("✓ Signin successful!")
        print(f"  User ID: {result['user']['id']}")
        print(f"  Email: {result['user']['email']}")
        print(f"  Username: {result['user']['username']}")
        print(f"  Access Token: {result['access_token'][:20]}...")
        print(f"  Refresh Token: {result['refresh_token'][:20] if result.get('refresh_token') else 'None'}...")
        
        return result
    except Exception as e:
        print(f"✗ Signin failed: {e}")
        return None


async def test_token_verification(access_token: str):
    """Test token verification with Supabase Auth"""
    print("\n" + "="*60)
    print("Testing Token Verification")
    print("="*60)
    
    try:
        supabase = get_supabase()
        user_response = supabase.auth.get_user(access_token)
        
        if user_response and user_response.user:
            print("✓ Token verification successful!")
            print(f"  Auth User ID: {user_response.user.id}")
            print(f"  Email: {user_response.user.email}")
            return True
        else:
            print("✗ Token verification failed: No user returned")
            return False
    except Exception as e:
        print(f"✗ Token verification failed: {e}")
        return False


async def test_get_user_profile(user_id: str):
    """Test getting user profile from custom users table"""
    print("\n" + "="*60)
    print("Testing User Profile Retrieval")
    print("="*60)
    
    try:
        profile = await get_user_by_id(user_id)
        
        if profile:
            print("✓ Profile retrieval successful!")
            print(f"  User ID: {profile['id']}")
            print(f"  Email: {profile['email']}")
            print(f"  Username: {profile.get('username')}")
            print(f"  First Name: {profile.get('first_name')}")
            print(f"  Last Name: {profile.get('last_name')}")
            return True
        else:
            print("✗ Profile retrieval failed: No profile found")
            return False
    except Exception as e:
        print(f"✗ Profile retrieval failed: {e}")
        return False


async def test_invalid_credentials():
    """Test signin with invalid credentials"""
    print("\n" + "="*60)
    print("Testing Invalid Credentials")
    print("="*60)
    
    try:
        await sign_in_user(
            email="nonexistent@example.com",
            password="wrongpassword"
        )
        print("✗ Test failed: Should have raised an error")
        return False
    except ValueError as e:
        print(f"✓ Correctly rejected invalid credentials: {e}")
        return True
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


async def test_duplicate_signup(email: str):
    """Test signup with existing email"""
    print("\n" + "="*60)
    print("Testing Duplicate Signup")
    print("="*60)
    
    try:
        await sign_up_user(
            email=email,
            password="AnotherPassword123!",
            user_data={'username': 'duplicate'}
        )
        print("✗ Test failed: Should have raised an error")
        return False
    except ValueError as e:
        print(f"✓ Correctly rejected duplicate email: {e}")
        return True
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


async def run_all_tests():
    """Run all authentication tests"""
    print("\n" + "="*80)
    print("SUPABASE AUTH INTEGRATION TESTS")
    print("="*80)
    
    results = []
    
    # Test 1: Signup
    signup_result = await test_signup()
    results.append(("Signup", signup_result is not None))
    
    if not signup_result:
        print("\n⚠ Signup failed, skipping remaining tests")
        return
    
    test_email = signup_result['user']['email']
    test_password = "TestPassword123!"
    access_token = signup_result['access_token']
    user_id = signup_result['user']['id']
    
    # Test 2: Token Verification
    token_valid = await test_token_verification(access_token)
    results.append(("Token Verification", token_valid))
    
    # Test 3: User Profile Retrieval
    profile_valid = await test_get_user_profile(user_id)
    results.append(("Profile Retrieval", profile_valid))
    
    # Test 4: Signin
    signin_result = await test_signin(test_email, test_password)
    results.append(("Signin", signin_result is not None))
    
    # Test 5: Invalid Credentials
    invalid_creds = await test_invalid_credentials()
    results.append(("Invalid Credentials", invalid_creds))
    
    # Test 6: Duplicate Signup
    duplicate = await test_duplicate_signup(test_email)
    results.append(("Duplicate Signup Prevention", duplicate))
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status:<12} {test_name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All tests passed! Supabase Auth integration is working correctly.")
    else:
        print(f"\n⚠ {total_count - passed_count} test(s) failed. Please review the errors above.")


if __name__ == "__main__":
    print("Starting Supabase Auth tests...")
    print("Make sure you have:")
    print("  1. Set SUPABASE_URL and SUPABASE_KEY in your .env file")
    print("  2. Run the database migration (migrations/migrate_to_supabase_auth.sql)")
    print("  3. Enabled Supabase Auth in your project")
    
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()

