"""Document management routes."""
import os
import uuid
from typing import Any

from chromadb import logger
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

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
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} is not a PDF"
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

        # Queue for processing
        task = process_pdf.delay(
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
        if document.get('chroma_document_ids'):
            collection.delete(ids=document['chroma_document_ids'])

        # Delete physical file
        if os.path.exists(document['storage_path']):
            os.remove(document['storage_path'])

        # Delete from database
        await delete_document(document_id, user_id)

        return {
            "message": "PDF and embeddings deleted successfully",
            "document_id": document_id,
            "embeddings_deleted": len(document.get('chroma_document_ids', []))
        }

    except Exception as e:
        logger.error(f"Error deleting PDF {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from None

