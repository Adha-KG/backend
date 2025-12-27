# app/services/user_service.py
from typing import Any

from gotrue.errors import AuthApiError

from app.auth.supabase_client import get_supabase


async def sync_user_profile(user_id: str, email: str, user_data: dict[str, Any] = None) -> dict[str, Any]:
    """
    Sync user profile data to custom users table.
    Creates or updates the user profile linked to auth.users.id via auth_user_id column.
    """
    supabase = get_supabase()
    try:
        # Check if user profile exists by auth_user_id
        existing = supabase.table('users').select('*').eq('auth_user_id', str(user_id)).execute()
        
        if existing.data:
            # Update existing profile
            profile_data = {
                'email': email,
                'username': user_data.get('username') if user_data else None,
                'first_name': user_data.get('first_name') if user_data else None,
                'last_name': user_data.get('last_name') if user_data else None,
                'profile_image_url': user_data.get('profile_image_url') if user_data else None,
                'updated_at': 'now()'
            }
            result = supabase.table('users').update(profile_data).eq('auth_user_id', str(user_id)).execute()
            return result.data[0] if result.data else None
        else:
            # Create new profile (for new Supabase Auth users)
            # Use auth.users.id as both id and auth_user_id for new users
            profile_data = {
                'id': str(user_id),  # New users get auth.users.id as their primary key
                'auth_user_id': str(user_id),  # Link to auth.users
                'email': email,
                'username': user_data.get('username') if user_data else None,
                'first_name': user_data.get('first_name') if user_data else None,
                'last_name': user_data.get('last_name') if user_data else None,
                'profile_image_url': user_data.get('profile_image_url') if user_data else None,
                'created_at': 'now()',
                'updated_at': 'now()'
            }
            result = supabase.table('users').insert(profile_data).execute()
            return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error syncing user profile: {e}")
        raise


async def sign_up_user(email: str, password: str, user_data: dict[str, Any] = None) -> dict[str, Any]:
    """Sign up a new user using Supabase Auth"""
    supabase = get_supabase()
    try:
        # Prepare user metadata
        metadata = {}
        if user_data:
            if user_data.get('username'):
                metadata['username'] = user_data['username']
            if user_data.get('first_name'):
                metadata['first_name'] = user_data['first_name']
            if user_data.get('last_name'):
                metadata['last_name'] = user_data['last_name']
            if user_data.get('profile_image_url'):
                metadata['profile_image_url'] = user_data['profile_image_url']

        # Sign up with Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": metadata
            }
        })

        if not auth_response.user:
            raise ValueError("Failed to create user account")

        # Create/update profile in custom users table
        await sync_user_profile(auth_response.user.id, email, user_data)

        # Get user profile from custom users table
        user_profile = await get_user_by_id(auth_response.user.id)

        return {
            "user": {
                "id": str(auth_response.user.id),
                "email": auth_response.user.email,
                "username": user_profile.get('username') if user_profile else None,
                "first_name": user_profile.get('first_name') if user_profile else None,
                "last_name": user_profile.get('last_name') if user_profile else None,
                "profile_image_url": user_profile.get('profile_image_url') if user_profile else None
            },
            "access_token": auth_response.session.access_token if auth_response.session else None,
            "refresh_token": auth_response.session.refresh_token if auth_response.session else None,
            "token_type": "bearer"
        }
    except AuthApiError as e:
        # Handle Supabase Auth specific errors
        error_message = str(e)
        if "already registered" in error_message.lower() or "already exists" in error_message.lower():
            raise ValueError("User with this email already exists")
        raise ValueError(f"Authentication error: {error_message}")
    except Exception as e:
        print(f"Error signing up user: {e}")
        raise

async def sign_in_user(email: str, password: str) -> dict[str, Any]:
    """Sign in an existing user using Supabase Auth"""
    supabase = get_supabase()
    try:
        # Sign in with Supabase Auth
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if not auth_response.user or not auth_response.session:
            raise ValueError("Invalid email or password")

        # Update last sign in time in custom users table
        try:
            # Try to update by auth_user_id first (for existing migrated users)
            result = supabase.table('users').update({
                'last_sign_in_at': 'now()',
                'updated_at': 'now()'
            }).eq('auth_user_id', str(auth_response.user.id)).execute()
            
            # If no rows updated, try by id (for new users)
            if not result.data:
                supabase.table('users').update({
                    'last_sign_in_at': 'now()',
                    'updated_at': 'now()'
                }).eq('id', str(auth_response.user.id)).execute()
        except Exception as update_error:
            # If user profile doesn't exist yet, create it
            print(f"Warning: Could not update last_sign_in_at: {update_error}")
            # Try to sync user profile
            user_metadata = auth_response.user.user_metadata or {}
            await sync_user_profile(
                auth_response.user.id,
                auth_response.user.email,
                user_metadata
            )

        # Get user profile from custom users table
        user_profile = await get_user_by_id(auth_response.user.id)

        return {
            "user": {
                "id": str(auth_response.user.id),
                "email": auth_response.user.email,
                "username": user_profile.get('username') if user_profile else None,
                "first_name": user_profile.get('first_name') if user_profile else None,
                "last_name": user_profile.get('last_name') if user_profile else None,
                "profile_image_url": user_profile.get('profile_image_url') if user_profile else None
            },
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token,
            "token_type": "bearer"
        }
    except AuthApiError as e:
        # Handle Supabase Auth specific errors
        error_message = str(e)
        raise ValueError("Invalid email or password")
    except Exception as e:
        print(f"Error signing in user: {e}")
        raise

async def update_user(user_id: str, user_data: dict[str, Any]) -> dict[str, Any]:
    """Update user in Supabase"""
    supabase = get_supabase()
    try:
        update_data = {
            'username': user_data.get('username'),
            'first_name': user_data.get('first_name'),
            'last_name': user_data.get('last_name'),
            'profile_image_url': user_data.get('profile_image_url'),
            'updated_at': 'now()'
        }

        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}

        updated_user = supabase.table('users').update(update_data).eq('id', user_id).execute()
        return updated_user.data[0] if updated_user.data else None
    except Exception as e:
        print(f"Error updating user: {e}")
        raise

async def get_user_by_email(email: str) -> dict[str, Any] | None:
    """Get user by email"""
    supabase = get_supabase()
    try:
        result = supabase.table('users').select('*').eq('email', email).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

async def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    """
    Get user by ID (from custom users table).
    Checks both id and auth_user_id to support both new and migrated users.
    """
    supabase = get_supabase()
    try:
        # First try to find by id (for new users created after migration)
        result = supabase.table('users').select('*').eq('id', str(user_id)).execute()
        if result.data:
            return result.data[0]
        
        # If not found, try auth_user_id (for migrated users or alternative lookup)
        result = supabase.table('users').select('*').eq('auth_user_id', str(user_id)).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error getting user by ID: {e}")
        return None

async def get_all_users() -> list[dict[str, Any]]:
    """Get all users (admin only)"""
    supabase = get_supabase()
    try:
        result = supabase.table('users').select('id, email, username, first_name, last_name, profile_image_url, created_at, last_sign_in_at').order('created_at', desc=True).execute()
        return result.data
    except Exception as e:
        print(f"Error getting all users: {e}")
        return []

async def delete_user(user_id: str) -> bool:
    """Delete a user"""
    supabase = get_supabase()
    try:
        result = supabase.table('users').delete().eq('id', user_id).execute()
        return len(result.data) > 0
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False
