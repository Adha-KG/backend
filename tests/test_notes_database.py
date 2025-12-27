"""Test notes database functionality."""
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.notes_db import notes_db


def test_supabase_config():
    """Test Supabase configuration."""
    assert settings.supabase_url, "Supabase URL should be configured"
    assert settings.supabase_key, "Supabase key should be configured"
    assert len(settings.supabase_key) > 0, "Supabase key should not be empty"


def test_list_files():
    """Test listing files from database."""
    result = notes_db.list_files(limit=10, offset=0)
    assert "files" in result, "Result should contain 'files' key"
    files = result.get("files", [])
    assert isinstance(files, list), "Files should be a list"

    # If files exist, verify structure
    if files:
        file = files[0]
        assert "id" in file, "File should have 'id'"
        assert "original_filename" in file, "File should have 'original_filename'"
        assert "status" in file, "File should have 'status'"
        assert "created_at" in file, "File should have 'created_at'"


def test_get_note_by_file():
    """Test retrieving notes for a file."""
    # First, get a list of files
    result = notes_db.list_files(limit=10, offset=0)
    files = result.get("files", [])

    if not files:
        pytest.skip("No files in database to test")

    # Try to get notes for completed files
    for file in files:
        if file.get("status") == "completed":
            file_id = file["id"]
            try:
                note = notes_db.get_note_by_file(file_id)
                if note:
                    assert "note_text" in note, "Note should have 'note_text'"
                    assert isinstance(note["note_text"], str), "Note text should be a string"
                    assert len(note["note_text"]) > 0, "Note text should not be empty"
                    break
            except Exception as e:
                pytest.fail(f"Error getting note for file {file_id}: {str(e)}")
    else:
        pytest.skip("No completed files with notes found")

