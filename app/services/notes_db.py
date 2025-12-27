"""Database service for notes functionality - unified with main backend"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

from supabase import Client, create_client

from app.config import settings

logger = logging.getLogger(__name__)


class NotesDatabase:
    """Database service for notes-related tables: notes, summaries"""

    def __init__(self):
        logger.info("Initializing NotesDatabase...")
        logger.info(f"Supabase URL: {settings.supabase_url}")
        logger.info(f"Supabase key length: {len(settings.supabase_key) if settings.supabase_key else 0}")

        try:
            self.client: Client = create_client(
                settings.supabase_url, settings.supabase_key
            )
            logger.info("Supabase client created successfully")
        except Exception as e:
            logger.error(f"Failed to create Supabase client: {str(e)}")
            raise

    # Notes table operations
    def create_note(self, note_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new note record"""
        logger.info(f"Creating note record for documents: {note_data.get('document_ids', [])}")
        try:
            response = self.client.table("notes").insert(note_data).execute()
            logger.info(f"Note record created successfully: {response.data[0].get('id') if response.data else 'unknown'}")
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create note record: {str(e)}")
            raise

    def get_note(self, note_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get note by ID, optionally filtered by user_id"""
        query = self.client.table("notes").select("*").eq("id", note_id)
        if user_id:
            query = query.eq("user_id", user_id)
        response = query.execute()
        return response.data[0] if response.data else None

    def list_notes(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List all notes for a user with pagination"""
        response = (
            self.client.table("notes")
            .select("id, document_ids, title, status, note_style, created_at, updated_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return response.data or []

    def update_note_status(
        self, note_id: str, status: str, error: Optional[str] = None
    ) -> None:
        """Update note processing status"""
        update_data = {"status": status, "updated_at": datetime.utcnow().isoformat()}
        if error:
            update_data["error"] = error
        self.client.table("notes").update(update_data).eq("id", note_id).execute()

    def update_note_content(
        self, note_id: str, note_text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update note content after generation completes"""
        update_data = {
            "note_text": note_text,
            "status": "completed",
            "updated_at": datetime.utcnow().isoformat(),
        }
        if metadata:
            update_data["metadata"] = metadata
        self.client.table("notes").update(update_data).eq("id", note_id).execute()

    def delete_note(self, note_id: str, user_id: Optional[str] = None) -> None:
        """Delete note and associated summaries"""
        # Delete summaries first
        self.delete_summaries_by_note(note_id)
        # Delete note
        query = self.client.table("notes").delete().eq("id", note_id)
        if user_id:
            query = query.eq("user_id", user_id)
        query.execute()

    # Summaries table operations
    def create_summary(self, summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new summary record"""
        response = self.client.table("summaries").insert(summary_data).execute()
        return response.data[0] if response.data else None

    def get_summaries_by_note(self, note_id: str) -> List[Dict[str, Any]]:
        """Get all summaries for a note"""
        response = (
            self.client.table("summaries")
            .select("*")
            .eq("note_id", note_id)
            .order("chunk_index")
            .execute()
        )
        return response.data or []

    def delete_summaries_by_note(self, note_id: str) -> None:
        """Delete all summaries for a note"""
        self.client.table("summaries").delete().eq("note_id", note_id).execute()


# Global instance
notes_db = NotesDatabase()
