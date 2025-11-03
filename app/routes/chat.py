"""Chat session routes."""
from typing import Any

from chromadb import logger
from fastapi import APIRouter, Depends, HTTPException

from app.auth.auth import get_current_user
from app.schemas import (
    ChatMessageCreate,
    ChatSessionCreate,
    QueryRequest,
    QueryResponse,
)
from app.services.chat_service import (
    add_chat_message,
    create_chat_session,
    delete_chat_session,
    get_chat_messages,
    get_user_chat_sessions,
    update_session_name,
)
from app.services.rag import answer_question

router = APIRouter(prefix="/chat-sessions", tags=["chat"])


@router.put("/{session_id}/name")
async def update_session_name_endpoint(
    session_id: str,
    new_name: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Update a chat session's name"""
    try:
        success = await update_session_name(session_id, current_user["id"], new_name)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found or access denied")
        return {"message": "Session name updated successfully"}
    except Exception as e:
        logger.exception(f"Error updating session name: {e}")
        raise HTTPException(status_code=500, detail="Failed to update session name") from None


@router.post("", response_model=dict)
async def create_chat_session_endpoint(
    session_data: ChatSessionCreate,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Create a new chat session"""
    try:
        user_id = current_user["id"]

        session = await create_chat_session(
            user_id=user_id,
            session_name=session_data.session_name,
            session_type=session_data.session_type,
            document_ids=session_data.document_ids
        )
        return session
    except Exception as e:
        logger.exception(f"Error creating chat session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create chat session") from None


@router.get("", response_model=list[dict])
async def get_user_chat_sessions_endpoint(current_user: dict[str, Any] = Depends(get_current_user)):
    """Get user's chat sessions"""
    try:
        sessions = await get_user_chat_sessions(current_user["id"])
        return sessions
    except Exception as e:
        logger.exception(f"Error getting chat sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat sessions") from None


@router.post("/{session_id}/messages", response_model=dict)
async def add_chat_message_endpoint(
    session_id: str,
    message_data: ChatMessageCreate,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Add a message to a chat session"""
    try:
        user_id = current_user["id"]

        # Verify user owns the session
        sessions = await get_user_chat_sessions(user_id)
        session_exists = any(s['id'] == session_id for s in sessions)

        if not session_exists:
            raise HTTPException(status_code=404, detail="Chat session not found or access denied")

        message = await add_chat_message(
            session_id=session_id,
            content=message_data.content,
            tokens_used=message_data.tokens_used,
            source_documents=message_data.source_documents,
            retrieval_query=message_data.retrieval_query
        )
        return message
    except Exception as e:
        logger.exception(f"Error adding chat message: {e}")
        raise HTTPException(status_code=500, detail="Failed to add chat message") from None


@router.get("/{session_id}/messages", response_model=list[dict])
async def get_chat_messages_endpoint(
    session_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    limit: int = 50
):
    """Get messages for a chat session"""
    try:
        user_id = current_user["id"]

        # Verify user owns the session
        sessions = await get_user_chat_sessions(user_id)
        session_exists = any(s['id'] == session_id for s in sessions)

        if not session_exists:
            raise HTTPException(status_code=404, detail="Chat session not found or access denied")

        messages = await get_chat_messages(session_id, limit)
        return messages
    except Exception as e:
        logger.exception(f"Error getting chat messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat messages") from None


@router.delete("/{session_id}")
async def delete_chat_session_endpoint(
    session_id: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Delete a chat session"""
    try:
        user_id = current_user["id"]
        success = await delete_chat_session(session_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Chat session not found or access denied")

        return {"message": "Chat session deleted successfully"}
    except Exception as e:
        logger.exception(f"Error deleting chat session: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete chat session") from None


@router.post("/{session_id}/query", response_model=QueryResponse)
async def query_with_chat_context(
    session_id: str,
    request: QueryRequest,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Query RAG with chat session context"""
    try:
        user_id = current_user["id"]

        # Verify user owns the session
        sessions = await get_user_chat_sessions(user_id)
        session_exists = any(s['id'] == session_id for s in sessions)

        if not session_exists:
            raise HTTPException(status_code=404, detail="Chat session not found or access denied")

        # Get recent chat history for context
        chat_history = await get_chat_messages(session_id, limit=5)

        # Get user's collection name
        collection_name = f"user_{user_id}_docs"

        # Call your async answer_question function with chat context
        answer_text = await answer_question(
            request.question,  # noqa: W291
            n_results=5,
            collection_name=collection_name,
            user_id=user_id,
            chat_history=chat_history
        )

        # Add the Q&A to chat history
        await add_chat_message(
            session_id=session_id,
            content=f"Q: {request.question}\nA: {answer_text}",
            retrieval_query=request.question
        )

        return {"answer": answer_text}

    except Exception as e:
        logger.exception(f"Error during query with chat context: {e}")
        raise HTTPException(status_code=500, detail="Failed to query") from None

