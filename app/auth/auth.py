from typing import Any, dict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from services import supabase_client

security = HTTPBearer()


async def sign_up(
    email: str, password: str, metadata: dict[str, Any] = None
) -> dict[str, Any]:
    """Register a new user"""
    client = supabase_client.get_client()
    try:
        response = client.auth.sign_up(
            {"email": email, "password": password, "options": {"data": metadata or {}}}
        )

        if response.user:
            return {
                "user": {
                    "id": response.user.id,
                    "email": response.user.email,
                    "created_at": response.user.created_at,
                },
                "session": response.session,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create user"
            )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))  # noqa: B904


async def sign_in(email: str, password: str) -> dict[str, Any]:
    """Sign in a user"""
    client = supabase_client.get_client()
    try:
        response = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )

        if response.session:
            return {
                "user": {"id": response.user.id, "email": response.user.email},
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "token_type": "bearer",
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
    except Exception:
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )


async def sign_out(access_token: str) -> dict[str, str]:
    """Sign out a user"""
    client = supabase_client.get_client()
    try:
        client.auth.sign_out()
        return {"message": "Successfully signed out"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))  # noqa: B904


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """Validate JWT token and return current user"""
    client = supabase_client.get_client()
    token = credentials.credentials

    try:
        # Verify token with Supabase
        user = client.auth.get_user(token)

        if user and user.user:
            return {
                "id": user.user.id,
                "email": user.user.email,
                "metadata": user.user.user_metadata,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

    except Exception:
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
