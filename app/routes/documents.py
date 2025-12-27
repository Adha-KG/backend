"""Document management routes."""
import os
import uuid
from typing import Any

from chromadb import logger
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Response

from app.auth.auth import get_current_user
from app.schemas import UploadResponse
from app.services.document_service import (
    create_document,
    delete_document,
    get_document_by_id,
    get_user_documents,
)
from app.services.vectorstore import get_collection
from app.tasks import process_pdf

router = APIRouter(tags=["documents"])

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload-multiple", response_model=list[UploadResponse])
async def upload_multiple_pdfs(
    files: list[UploadFile] = File(...),
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Upload multiple PDF files at once"""
    uploaded_files = []
    user_id = current_user["id"]

    for file in files:
        # Check if filename exists and is a PDF
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename or 'unknown'} is not a PDF"
            )

        # Create unique filename with UUID
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)

        # Save file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Create document record in database
        document_data = {
            'filename': unique_filename,
            'original_filename': file.filename,
            'file_size': len(content),
            'file_type': 'pdf',
            'mime_type': file.content_type,
            'storage_path': file_path,
            'chroma_collection_name': f"user_{user_id}_docs"
        }
        db_document = await create_document(
            user_id=user_id,
            document_data=document_data
        )

        # Queue for processing (Celery task)
        task = process_pdf.delay(  # type: ignore
            file_path,
            file.filename,
            unique_filename,
            user_id=user_id,
            document_id=db_document['id']
        )

        uploaded_files.append({
            "filename": file.filename,
            "stored_as": unique_filename,
            "task_id": task.id,
            "document_id": db_document['id'],
            "message": "PDF uploaded and queued for processing"
        })

    return uploaded_files


@router.get("/documents", response_model=list[dict])
async def get_user_documents_endpoint(current_user: dict[str, Any] = Depends(get_current_user)):
    """Get current user's uploaded documents"""
    try:
        documents = await get_user_documents(current_user["id"])
        return documents
    except Exception as e:
        logger.exception(f"Error getting uploads: {e}")
        raise HTTPException(status_code=500, detail="Failed to get uploads") from None


@router.get("/documents/{document_id}/view")
async def view_pdf(
    document_id: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Serve PDF file for viewing"""
    try:
        user_id = current_user["id"]

        # Get document info
        document = await get_document_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if document['user_id'] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if file exists
        file_path = document.get('storage_path')
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="PDF file not found")

        # Read and return PDF file
        with open(file_path, "rb") as f:
            pdf_content = f.read()

        original_filename = document.get('original_filename', 'document.pdf')
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{original_filename}"',
                "Cache-Control": "public, max-age=3600"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving PDF {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.delete("/documents/{document_id}")
async def delete_pdf(
    document_id: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Delete a PDF file and all its embeddings"""
    try:
        user_id = current_user["id"]

        # Get document info
        document = await get_document_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if document['user_id'] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get user's collection
        collection_name = f"user_{user_id}_docs"
        collection = get_collection(collection_name)

        # Delete embeddings from ChromaDB
        embeddings_deleted = 0
        if document.get('chroma_document_ids'):
            try:
                collection.delete(ids=document['chroma_document_ids'])
                embeddings_deleted = len(document['chroma_document_ids'])
                logger.info(f"Deleted {embeddings_deleted} embeddings for document {document_id}")
            except Exception as e:
                logger.error(f"Error deleting embeddings: {e}")

        # Delete physical file
        if os.path.exists(document['storage_path']):
            try:
                os.remove(document['storage_path'])
                logger.info(f"Deleted file: {document['storage_path']}")
            except Exception as e:
                logger.error(f"Error deleting file: {e}")

        # Delete from database
        await delete_document(document_id, user_id)

        # Import and clear collection cache to prevent stale state
        from app.services.vectorstore import reset_collection
        try:
            # Force collection refresh after deletion
            reset_collection(collection_name)
            logger.info(f"Reset collection cache for {collection_name}")
        except Exception as e:
            logger.warning(f"Could not reset collection cache: {e}")

        return {
            "message": "PDF and embeddings deleted successfully",
            "document_id": document_id,
            "embeddings_deleted": embeddings_deleted
        }

    except Exception as e:
        logger.error(f"Error deleting PDF {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from None

