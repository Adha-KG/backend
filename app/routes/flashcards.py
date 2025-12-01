"""Flashcard generation routes."""
import json
from typing import Any

from chromadb import logger
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth.auth import get_current_user
from app.schemas import (
    FlashcardGenerateRequest,
    FlashcardGenerateResponse,
    Flashcard,
)
from app.services.flashcard_service import (
    generate_flashcards,
    generate_flashcards_stream,
)

router = APIRouter(tags=["flashcards"])


@router.post("/generate", response_model=FlashcardGenerateResponse)
async def generate_flashcards_endpoint(
    request: FlashcardGenerateRequest,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Generate flashcards from user's documents"""
    try:
        user_id = current_user["id"]
        collection_name = f"user_{user_id}_docs"
        
        # Validate number of flashcards
        num_flashcards = min(max(1, request.num_flashcards), 50)  # Limit between 1 and 50
        
        flashcards = await generate_flashcards(
            topic=request.topic,
            document_ids=request.document_ids,
            num_flashcards=num_flashcards,
            collection_name=collection_name,
            user_id=user_id,
        )
        
        if not flashcards:
            raise HTTPException(
                status_code=404,
                detail="No relevant content found to generate flashcards. Make sure you have uploaded and processed documents."
            )
        
        return FlashcardGenerateResponse(
            flashcards=[Flashcard(**card) for card in flashcards],
            topic=request.topic,
            num_generated=len(flashcards)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error generating flashcards: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate flashcards: {str(e)}"
        ) from None


@router.post("/generate/stream")
async def generate_flashcards_stream_endpoint(
    request: FlashcardGenerateRequest,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Stream flashcard generation process"""
    try:
        user_id = current_user["id"]
        collection_name = f"user_{user_id}_docs"
        
        # Validate number of flashcards
        num_flashcards = min(max(1, request.num_flashcards), 50)
        
        async def generate():
            async for chunk in generate_flashcards_stream(
                topic=request.topic,
                document_ids=request.document_ids,
                num_flashcards=num_flashcards,
                collection_name=collection_name,
                user_id=user_id,
            ):
                yield chunk
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as err:
        logger.exception(f"Error during streaming flashcard generation: {err}")
        error_message = str(err)
        async def error_stream():
            yield f"data: {json.dumps({'status': 'error', 'message': f'Error: {error_message}', 'done': True, 'error': True})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

