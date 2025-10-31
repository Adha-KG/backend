# app/services/document_service.py
from datetime import datetime
from typing import Any

from app.auth.supabase_client import get_supabase


async def create_document(user_id: str, document_data: dict[str, Any]) -> dict[str, Any]:
    """Create a new document record"""
    supabase = get_supabase()
    try:
        document = supabase.table('documents').insert({
            'user_id': user_id,
            'filename': document_data['filename'],
            'original_filename': document_data['original_filename'],
            'file_size': document_data['file_size'],
            'file_type': document_data['file_type'],
            'mime_type': document_data.get('mime_type'),
            'storage_path': document_data['storage_path'],
            'storage_bucket': document_data.get('storage_bucket', 'documents'),
            'chroma_collection_name': document_data['chroma_collection_name'],
            'embedding_status': 'processing',
            'metadata': document_data.get('metadata', {}),
            'tags': document_data.get('tags', [])
        }).execute()
        return document.data[0]
    except Exception as e:
        print(f"Error creating document: {e}")
        raise

async def update_document_status(document_id: str, status: str,
                               chunk_ids: list[str] = None,
                               total_chunks: int = None,
                               error: str = None):
    """Update document processing status"""
    supabase = get_supabase()
    try:
        update_data = {
            'embedding_status': status,
            'processed_at': datetime.utcnow().isoformat() if status == 'completed' else None
        }

        if chunk_ids:
            update_data['chroma_document_ids'] = chunk_ids
        if total_chunks:
            update_data['total_chunks'] = total_chunks
        if error:
            update_data['processing_error'] = error

        result = supabase.table('documents').update(update_data).eq('id', document_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error updating document status: {e}")
        raise

async def get_user_documents(user_id: str) -> list[dict[str, Any]]:
    """Get all documents for a user"""
    supabase = get_supabase()
    try:
        result = supabase.table('documents').select('*').eq('user_id', user_id).order('uploaded_at', desc=True).execute()
        return result.data
    except Exception as e:
        print(f"Error getting user documents: {e}")
        return []

async def get_document_by_id(document_id: str) -> dict[str, Any] | None:
    """Get a specific document by ID"""
    supabase = get_supabase()
    try:
        result = supabase.table('documents').select('*').eq('id', document_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error getting document: {e}")
        return None

async def delete_document(document_id: str, user_id: str) -> bool:
    """Delete a document"""
    supabase = get_supabase()
    try:
        result = supabase.table('documents').delete().eq('id', document_id).eq('user_id', user_id).execute()
        return len(result.data) > 0
    except Exception as e:
        print(f"Error deleting document: {e}")
        return False

async def get_all_documents() -> list[dict[str, Any]]:
    """Get all documents"""
    supabase = get_supabase()
    try:
        result = supabase.table('documents').select('*').order('uploaded_at', desc=True).execute()
        return result.data
    except Exception as e:
        print(f"Error getting all documents: {e}")
        return []
