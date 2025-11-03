"""Statistics routes."""
from typing import Any

from chromadb import logger
from fastapi import APIRouter, Depends, HTTPException

from app.auth.auth import get_current_user
from app.services.chat_service import get_user_chat_sessions
from app.services.document_service import get_user_documents

router = APIRouter(tags=["statistics"])


@router.get("/stats")
async def get_user_stats(current_user: dict[str, Any] = Depends(get_current_user)):
    """Get current user statistics"""
    try:
        user_id = current_user["id"]
        user_documents = await get_user_documents(user_id)
        user_sessions = await get_user_chat_sessions(user_id)

        return {
            "user_id": user_id,
            "total_documents": len(user_documents),
            "total_chat_sessions": len(user_sessions),
            "documents_by_status": {
                "completed": len([doc for doc in user_documents if doc.get('embedding_status') == 'completed']),
                "processing": len([doc for doc in user_documents if doc.get('embedding_status') == 'processing']),
                "failed": len([doc for doc in user_documents if doc.get('embedding_status') == 'failed']),
                "pending": len([doc for doc in user_documents if doc.get('embedding_status') == 'pending'])
            }
        }
    except Exception as e:
        logger.exception(f"Error getting user stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user stats") from None

