# app/services/user_service.py
import os
from datetime import datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.auth.supabase_client import get_supabase

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict[str, Any]) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict[str, Any] | None:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return {"user_id": user_id, "email": payload.get("email")}
    except jwt.PyJWTError:
        return None

async def sign_up_user(email: str, password: str, user_data: dict[str, Any] = None) -> dict[str, Any]:
    """Sign up a new user"""
    supabase = get_supabase()
    try:
        # Check if user already exists
        existing_user = await get_user_by_email(email)
        if existing_user:
            raise ValueError("User with this email already exists")

        # Hash password
        hashed_password = hash_password(password)

        # Create user data
        insert_data = {
            'email': email,
            'password_hash': hashed_password,
            'username': user_data.get('username') if user_data else None,
            'first_name': user_data.get('first_name') if user_data else None,
            'last_name': user_data.get('last_name') if user_data else None,
            'profile_image_url': user_data.get('profile_image_url') if user_data else None
        }

        new_user = supabase.table('users').insert(insert_data).execute()
        user = new_user.data[0]

        # Create JWT token
        token_data = {"sub": user['id'], "email": user['email']}
        access_token = create_access_token(token_data)

        return {
            "user": {
                "id": user['id'],
                "email": user['email'],
                "username": user['username'],
                "first_name": user['first_name'],
                "last_name": user['last_name'],
                "profile_image_url": user['profile_image_url']
            },
            "access_token": access_token,
            "token_type": "bearer"
        }
    except Exception as e:
        print(f"Error signing up user: {e}")
        raise

async def sign_in_user(email: str, password: str) -> dict[str, Any]:
    """Sign in an existing user"""
    supabase = get_supabase()
    try:
        # Get user by email
        result = supabase.table('users').select('*').eq('email', email).execute()
        if not result.data:
            raise ValueError("Invalid email or password")

        user = result.data[0]

        # Verify password
        if not verify_password(password, user['password_hash']):
            raise ValueError("Invalid email or password")

        # Update last sign in time
        supabase.table('users').update({
            'last_sign_in_at': 'now()',
            'updated_at': 'now()'
        }).eq('id', user['id']).execute()

        # Create JWT token
        token_data = {"sub": user['id'], "email": user['email']}
        access_token = create_access_token(token_data)

        return {
            "user": {
                "id": user['id'],
                "email": user['email'],
                "username": user['username'],
                "first_name": user['first_name'],
                "last_name": user['last_name'],
                "profile_image_url": user['profile_image_url']
            },
            "access_token": access_token,
            "token_type": "bearer"
        }
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
    """Get user by ID"""
    supabase = get_supabase()
    try:
        result = supabase.table('users').select('*').eq('id', user_id).execute()
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
