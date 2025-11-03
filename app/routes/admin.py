"""Admin routes."""
from typing import Any

from chromadb import logger
from fastapi import APIRouter, Depends, HTTPException

from app.auth.auth import get_current_user
from app.services.document_service import get_all_documents
from app.services.user_service import get_all_users

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[dict])
async def get_all_users_endpoint(current_user: dict[str, Any] = Depends(get_current_user)):
    """Get all users (admin endpoint)"""
    try:
        users = await get_all_users()
        return users
    except Exception as e:
        logger.exception(f"Error getting users: {e}")
        raise HTTPException(status_code=500, detail="Failed to get users") from None


@router.get("/stats")
async def get_admin_stats(current_user: dict[str, Any] = Depends(get_current_user)):
    """Get system statistics (admin endpoint)"""
    try:
        # You might want to add role-based access control here
        total_users = len(await get_all_users())
        total_documents = len(await get_all_documents())

        return {
            "total_users": total_users,
            "total_documents": total_documents,
            "status": "operational"
        }
    except Exception as e:
        logger.exception(f"Error getting admin stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get admin stats") from None

