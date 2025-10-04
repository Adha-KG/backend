import os
import uuid
from typing import Any  # noqa: UP035

import config
from fastapi import HTTPException, UploadFile, status
from services import supabase_client

# Module-level storage configuration
BUCKET_NAME = config.SUPABASE_STORAGE_BUCKET

def _ensure_bucket_exists():
    """Ensure storage bucket exists"""
    try:
        client = supabase_client.get_client()
        buckets = client.storage.list_buckets()
        bucket_names = [b.name for b in buckets]

        if BUCKET_NAME not in bucket_names:
            # Use admin client to create bucket
            admin_client = supabase_client.get_admin_client()
            admin_client.storage.create_bucket(
                BUCKET_NAME,
                {"public": False}
            )
    except Exception as e:
        print(f"Error checking/creating bucket: {e}")

# Initialize bucket on module load
_ensure_bucket_exists()

async def upload_file(
    file: UploadFile,  # noqa: W291
    user_id: str,
    folder: str | None = None
) -> dict[str, Any]:
    """Upload file to Supabase storage"""
    client = supabase_client.get_client()
    try:
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"

        # Create path with user isolation
        if folder:
            file_path = f"{user_id}/{folder}/{unique_filename}"
        else:
            file_path = f"{user_id}/{unique_filename}"

        # Read file content
        content = await file.read()
        await file.seek(0)  # Reset file pointer

        # Upload to Supabase
        client.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=content,
            file_options={"content-type": file.content_type}
        )

        return {
            "file_path": file_path,
            "original_name": file.filename,
            "size": len(content),
            "content_type": file.content_type,
            "storage_bucket": BUCKET_NAME
        }

    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )

async def download_file(file_path: str, user_id: str) -> bytes:
    """Download file from Supabase storage"""
    client = supabase_client.get_client()
    try:
        # Verify user has access to this file
        if not file_path.startswith(f"{user_id}/"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        response = client.storage.from_(BUCKET_NAME).download(file_path)
        return response

    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {str(e)}"
        )

async def delete_file(file_path: str, user_id: str) -> bool:
    """Delete file from Supabase storage"""
    client = supabase_client.get_client()
    try:
        # Verify user has access to this file
        if not file_path.startswith(f"{user_id}/"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        client.storage.from_(BUCKET_NAME).remove([file_path])
        return True

    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )

async def list_user_files(user_id: str, folder: str | None = None) -> list[dict[str, Any]]:
    """List all files for a user"""
    client = supabase_client.get_client()
    try:
        path = f"{user_id}/{folder}" if folder else user_id
        response = client.storage.from_(BUCKET_NAME).list(path)

        # Format response
        files = []
        for item in response:
            files.append({
                "name": item.get("name", ""),
                "size": item.get("metadata", {}).get("size", 0),
                "created_at": item.get("created_at", ""),
                "updated_at": item.get("updated_at", ""),
                "path": f"{path}/{item.get('name', '')}"
            })

        return files

    except Exception:
        return []

async def get_signed_url(file_path: str, user_id: str, expires_in: int = 3600) -> str:
    """Generate a signed URL for temporary file access"""
    client = supabase_client.get_client()
    try:
        # Verify user has access to this file
        if not file_path.startswith(f"{user_id}/"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        response = client.storage.from_(BUCKET_NAME).create_signed_url(
            path=file_path,
            expires_in=expires_in
        )

        return response["signedURL"]

    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create signed URL: {str(e)}"
        )  # noqa: W292
