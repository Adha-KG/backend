#!/usr/bin/env python3
"""
Quick test script to verify notes are being created and can be retrieved
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.notes_db import notes_db
from app.config import settings

print("=" * 60)
print("NOTES DATABASE TEST")
print("=" * 60)

print(f"\n✓ Supabase URL: {settings.supabase_url}")
print(f"✓ Supabase key length: {len(settings.supabase_key)}")

# Test 1: List all files
print("\n" + "=" * 60)
print("TEST 1: Listing all files")
print("=" * 60)
try:
    result = notes_db.list_files(limit=10, offset=0)
    files = result.get('files', [])
    print(f"✓ Found {len(files)} files")

    for file in files:
        print(f"\n  File: {file['original_filename']}")
        print(f"    ID: {file['id']}")
        print(f"    Status: {file['status']}")
        print(f"    Created: {file['created_at']}")

        # Test 2: Get notes for completed files
        if file['status'] == 'completed':
            print(f"\n  Checking for notes...")
            try:
                note = notes_db.get_note_by_file(file['id'])
                if note:
                    print(f"    ✓ Note found!")
                    print(f"    Note text length: {len(note['note_text'])} characters")
                    print(f"    Note preview: {note['note_text'][:200]}...")
                    print(f"    Metadata: {note.get('metadata')}")
                else:
                    print(f"    ✗ No note found for this file!")
            except Exception as e:
                print(f"    ✗ Error getting note: {str(e)}")

except Exception as e:
    print(f"✗ Error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
