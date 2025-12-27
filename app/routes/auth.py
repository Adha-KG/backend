"""Authentication routes."""
from chromadb import logger
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.auth.supabase_client import get_supabase
from app.schemas import AuthResponse, UserSignIn, UserSignUp
from app.services.user_service import sign_in_user, sign_up_user

router = APIRouter(prefix="/auth", tags=["authentication"])


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    access_token: str
    new_password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/signup", response_model=AuthResponse)
async def signup(user_data: UserSignUp):
    """Sign up a new user"""
    try:
        result = await sign_up_user(
            email=user_data.email,
            password=user_data.password,
            user_data={
                'username': user_data.username,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name,
                'profile_image_url': user_data.profile_image_url
            }
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except Exception as e:
        logger.exception(f"Error during signup: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.post("/signin", response_model=AuthResponse)
async def signin(credentials: UserSignIn):
    """Sign in an existing user"""
    try:
        result = await sign_in_user(credentials.email, credentials.password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None
    except Exception as e:
        logger.exception(f"Error during signin: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """Send password reset email"""
    try:
        supabase = get_supabase()
        supabase.auth.reset_password_email(request.email)
        return {
            "message": "Password reset email sent. Please check your inbox.",
            "email": request.email
        }
    except Exception as e:
        logger.exception(f"Error sending password reset email: {e}")
        # Return success even on error to prevent email enumeration
        return {
            "message": "If an account exists with this email, a password reset link has been sent.",
            "email": request.email
        }


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """Reset password using the token from email link"""
    try:
        supabase = get_supabase()
        # Update password for the authenticated user
        response = supabase.auth.update_user({
            "password": request.new_password
        }, access_token=request.access_token)
        
        if response.user:
            return {"message": "Password updated successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to update password")
    except Exception as e:
        logger.exception(f"Error resetting password: {e}")
        raise HTTPException(status_code=400, detail="Invalid or expired reset token") from None


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(request: RefreshTokenRequest):
    """Refresh access token using refresh token"""
    try:
        supabase = get_supabase()
        response = supabase.auth.refresh_session(request.refresh_token)
        
        if not response.session:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        return {
            "user": {
                "id": str(response.user.id),
                "email": response.user.email,
                "username": None,  # Will be populated from users table if needed
                "first_name": None,
                "last_name": None,
                "profile_image_url": None
            },
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer"
        }
    except Exception as e:
        logger.exception(f"Error refreshing token: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token") from None


@router.post("/signout")
async def signout():
    """Sign out the current user (client should clear tokens)"""
    # Note: With Supabase Auth, signout is primarily handled client-side
    # by clearing the tokens. The backend doesn't maintain session state.
    return {"message": "Signed out successfully. Please clear local tokens."}

