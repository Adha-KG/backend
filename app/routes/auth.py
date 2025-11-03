"""Authentication routes."""
from chromadb import logger
from fastapi import APIRouter, HTTPException

from app.schemas import AuthResponse, UserSignIn, UserSignUp
from app.services.user_service import sign_in_user, sign_up_user

router = APIRouter(prefix="/auth", tags=["authentication"])


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

