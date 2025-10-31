# app/services/storage_service.py

from app.auth.supabase_client import get_supabase


async def upload_file_to_storage(file_content: bytes, file_path: str, bucket: str = 'documents') -> str | None:
    """Upload file to Supabase Storage"""
    supabase = get_supabase()
    try:
        result = supabase.storage.from_(bucket).upload(file_path, file_content)
        return file_path if result else None
    except Exception as e:
        print(f"Error uploading file: {e}")
        return None

async def delete_file_from_storage(file_path: str, bucket: str = 'documents') -> bool:
    """Delete file from Supabase Storage"""
    supabase = get_supabase()
    try:
        result = supabase.storage.from_(bucket).remove([file_path])
        return len(result) > 0
    except Exception as e:
        print(f"Error deleting file: {e}")
        return False

async def get_file_url(file_path: str, bucket: str = 'documents') -> str | None:
    """Get public URL for a file"""
    supabase = get_supabase()
    try:
        result = supabase.storage.from_(bucket).get_public_url(file_path)
        return result
    except Exception as e:
        print(f"Error getting file URL: {e}")
        return None
