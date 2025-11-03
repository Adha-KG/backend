"""Query and RAG routes."""
import json
from datetime import datetime
from typing import Any

from chromadb import logger
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth.auth import get_current_user
from app.schemas import QueryRequest, QueryResponse
from app.services.chat_service import (
    add_chat_message,
    create_chat_session,
    get_chat_messages,
    get_or_create_active_session,
    get_session_by_id,
)
from app.services.rag import answer_question, answer_question_stream

router = APIRouter(tags=["query"])


@router.post("", response_model=QueryResponse)
async def query_rag(
    request: QueryRequest,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Query RAG with ChatGPT-like session management"""
    try:
        user_id = current_user["id"]
        collection_name = f"user_{user_id}_docs"

        # Handle session management based on request
        if hasattr(request, 'new_chat') and request.new_chat:
            # Create new session (like "New Chat" button)
            session_name = f"Chat - {datetime.now().strftime('%m/%d %H:%M')}"
            session = await create_chat_session(
                user_id=user_id,
                session_name=session_name,
                session_type="conversation",
                document_ids=[]
            )
            session_id = session['id']
            is_new_session = True
            chat_history = []  # No history for new chat
        elif hasattr(request, 'session_id') and request.session_id:
            # Continue existing session
            session = await get_session_by_id(request.session_id)
            if not session or session['user_id'] != user_id:
                raise HTTPException(status_code=404, detail="Session not found")
            session_id = request.session_id
            is_new_session = False
            chat_history = await get_chat_messages(session_id, limit=5)
        else:
            # Use or create active session (default behavior)
            session = await get_or_create_active_session(user_id)
            session_id = session['id']
            is_new_session = session.get('message_count', 0) == 0
            chat_history = await get_chat_messages(session_id, limit=5) if not is_new_session else []

        # Generate answer with context
        answer_text = await answer_question(
            request.question,
            n_results=5,
            collection_name=collection_name,
            user_id=user_id,
            chat_history=chat_history
        )

        # Save the conversation
        await add_chat_message(
            session_id=session_id,
            content=request.question,
            retrieval_query=request.question
        )

        await add_chat_message(
            session_id=session_id,
            content=answer_text,
            source_documents=None
        )

        return {
            "answer": answer_text,
            "session_id": session_id,
            "session_name": session.get('session_name', 'New Chat'),
            "is_new_session": is_new_session,
            "message_count": session.get('message_count', 0) + 2  # +2 for the Q&A we just added
        }

    except Exception as e:
        logger.exception(f"Error during query: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query: {str(e)}") from None


@router.post("/stream")
async def query_rag_stream(
    request: QueryRequest,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Stream RAG responses with ChatGPT-like session management"""
    try:
        user_id = current_user["id"]
        collection_name = f"user_{user_id}_docs"

        # Handle session management based on request
        if hasattr(request, 'new_chat') and request.new_chat:
            # Create new session (like "New Chat" button)
            session_name = f"Chat - {datetime.now().strftime('%m/%d %H:%M')}"
            session = await create_chat_session(
                user_id=user_id,
                session_name=session_name,
                session_type="conversation",
                document_ids=[]
            )
            session_id = session['id']
            is_new_session = True
            chat_history = []  # No history for new chat
        elif hasattr(request, 'session_id') and request.session_id:
            # Continue existing session
            session = await get_session_by_id(request.session_id)
            if not session or session['user_id'] != user_id:
                raise HTTPException(status_code=404, detail="Session not found")
            session_id = request.session_id
            is_new_session = False
            chat_history = await get_chat_messages(session_id, limit=5)
        else:
            # Use or create active session (default behavior)
            session = await get_or_create_active_session(user_id)
            session_id = session['id']
            is_new_session = session.get('message_count', 0) == 0
            chat_history = await get_chat_messages(session_id, limit=5) if not is_new_session else []

        # Save the user's question first
        await add_chat_message(
            session_id=session_id,
            content=request.question,
            retrieval_query=request.question
        )

        async def generate():
            full_response_text = ""
            async for chunk in answer_question_stream(
                question=request.question,
                n_results=5,
                collection_name=collection_name,
                user_id=user_id,
                chat_history=chat_history
            ):
                # Send chunk as-is (already in SSE format)
                yield chunk

                # Parse to extract full response when done
                if chunk.startswith("data: "):
                    data_str = chunk.replace("data: ", "").strip()
                    if data_str:
                        try:
                            data = json.loads(data_str)
                            if data.get('done') and not data.get('error'):
                                full_response_text = data.get('full_response', '')
                        except json.JSONDecodeError:
                            pass  # Ignore malformed JSON

            # Save the complete response after streaming is done
            if full_response_text:
                await add_chat_message(
                    session_id=session_id,
                    content=full_response_text,
                    source_documents=None
                )

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable buffering in nginx
            }
        )

    except Exception as err:
        logger.exception(f"Error during streaming query: {err}")
        error_message = str(err)
        # Return error as SSE format
        async def error_stream():
            yield f"data: {json.dumps({'content': f'Error: {error_message}', 'done': True, 'error': True})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

