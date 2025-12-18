import hashlib
import os
import json
from pathlib import Path
from datetime import datetime


def compute_file_hash(file_path: str) -> str:
    """
    Compute SHA256 hash of a file.
    
    Args:
        file_path: Path to file
    
    Returns:
        Hex string of SHA256 hash
    """
    sha256_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()


def compute_bytes_hash(content: bytes) -> str:
    """
    Compute SHA256 hash of bytes content.
    
    Args:
        content: Bytes to hash
    
    Returns:
        Hex string of SHA256 hash
    """
    return hashlib.sha256(content).hexdigest()


def ensure_directory(path: str) -> None:
    """
    Ensure a directory exists, create if it doesn't.
    
    Args:
        path: Directory path
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def save_note_as_markdown(
    note_text: str,
    output_path: str,
    metadata: dict = None
) -> str:
    """
    Save a note as a markdown (.md) file.
    
    Args:
        note_text: The note content to save
        output_path: Path where the markdown file should be saved
        metadata: Optional metadata to include in the markdown frontmatter
    
    Returns:
        Path to the saved markdown file
    """
    # Ensure the directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        ensure_directory(output_dir)
    
    # Prepare markdown content with frontmatter if metadata provided
    markdown_content = ""
    
    if metadata:
        # Add YAML frontmatter
        markdown_content += "---\n"
        markdown_content += f"created_at: {datetime.utcnow().isoformat()}\n"
        for key, value in metadata.items():
            if value is not None:
                # Handle different value types for YAML
                if isinstance(value, (dict, list)):
                    # Serialize complex types as JSON string or YAML
                    markdown_content += f"{key}: {json.dumps(value)}\n"
                elif isinstance(value, bool):
                    markdown_content += f"{key}: {str(value).lower()}\n"
                elif isinstance(value, (int, float)):
                    markdown_content += f"{key}: {value}\n"
                else:
                    # Escape strings that might contain special YAML characters
                    value_str = str(value)
                    if ':' in value_str or '\n' in value_str:
                        # Use JSON string format for strings with special chars
                        markdown_content += f"{key}: {json.dumps(value_str)}\n"
                    else:
                        markdown_content += f"{key}: {value_str}\n"
        markdown_content += "---\n\n"
    
    # Add the note content
    markdown_content += note_text
    
    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    
    return output_path


def get_note_filename(original_filename: str, file_id: str = None) -> str:
    """
    Generate a markdown filename from the original filename.
    
    Args:
        original_filename: Original filename (e.g., "document.pdf")
        file_id: Optional file ID to use as fallback
    
    Returns:
        Markdown filename (e.g., "document.md")
    """
    # Remove extension and add .md
    base_name = os.path.splitext(original_filename)[0]
    # Sanitize filename (remove invalid characters)
    base_name = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).strip()
    # If base_name is empty, use file_id
    if not base_name and file_id:
        base_name = file_id
    # If still empty, use default
    if not base_name:
        base_name = "note"
    
    return f"{base_name}.md"
