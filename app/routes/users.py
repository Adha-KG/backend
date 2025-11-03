"""User profile routes."""

from typing import Any

from chromadb import logger
from fastapi import APIRouter, Depends, HTTPException

from app.auth.auth import get_current_user
from app.schemas import UserUpdate
from app.services.user_service import update_user

router = APIRouter(tags=["users"])


@router.get("/me", response_model=dict)
async def get_current_user_profile(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Get current user profile"""
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "username": current_user["username"],
        "first_name": current_user["first_name"],
        "last_name": current_user["last_name"],
        "profile_image_url": current_user["profile_image_url"],
        "created_at": current_user["created_at"],
        "last_sign_in_at": current_user["last_sign_in_at"],
    }


@router.put("/me", response_model=dict)
async def update_current_user_profile(
    user_data: UserUpdate, current_user: dict[str, Any] = Depends(get_current_user)
):
    """Update current user profile"""
    try:
        updated_user = await update_user(
            current_user["id"], user_data.dict(exclude_unset=True)
        )
        if not updated_user:
            raise HTTPException(
                status_code=400, detail="Failed to update user"
            ) from None

        return {
            "id": updated_user["id"],
            "email": updated_user["email"],
            "username": updated_user["username"],
            "first_name": updated_user["first_name"],
            "last_name": updated_user["last_name"],
            "profile_image_url": updated_user["profile_image_url"],
        }
    except Exception as e:
        logger.exception(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user") from None
