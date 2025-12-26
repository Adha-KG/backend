from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query, Form, Depends
from fastapi.responses import JSONResponse, Response, HTMLResponse
from markdown_pdf import MarkdownPdf, Section
import io
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from enum import Enum
import os
import json
from uuid import uuid4
from datetime import datetime
import logging
import traceback

from app.config import settings
from app.auth.auth import get_current_user
from app.services.notes_db import notes_db
from app.services.notes_chroma import notes_chroma_service
from app.services.notes_llm import llm_service
from app.tasks.notes_tasks import process_file_task, synthesize_notes_task
from app.utils.file_utils import compute_bytes_hash, ensure_directory, save_note_as_markdown

# Set up logger
logger = logging.getLogger(__name__)


# Create APIRouter
router = APIRouter(prefix="")


# Enum for note styles
class NoteStyle(str, Enum):
    """
    Note style options:
    - short: Brief bullet points, only key facts
    - moderate: Balanced notes with main points and some details
    - descriptive: Comprehensive notes with full explanations
    """
    short = "short"
    moderate = "moderate"
    descriptive = "descriptive"


# Pydantic models
class UploadResponse(BaseModel):
    file_id: str
    task_id: str
    filename: str
    status: str
    message: str


class FileStatus(BaseModel):
    file_id: str
    filename: str
    status: str
    created_at: str
    updated_at: str
    error: Optional[str] = None


class NoteResponse(BaseModel):
    file_id: str
    note_text: str
    metadata: Optional[dict] = None
    created_at: str


class QuestionRequest(BaseModel):
    question: str
    n_results: int = 5


class AnswerResponse(BaseModel):
    answer: str
    sources: List[dict]
    model_info: dict


class RetryResponse(BaseModel):
    file_id: str
    task_id: str
    message: str
    status: str


def get_note_filename(original_filename: str, file_id: str) -> str:
    """
    Generate a clean filename for the note file.

    Args:
        original_filename: Original PDF filename
        file_id: File ID

    Returns:
        Clean filename for the note
    """
    if original_filename:
        # Remove .pdf extension and sanitize filename
        base_name = original_filename.rsplit('.', 1)[0]
        # Remove or replace problematic characters
        sanitized_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in base_name)
        sanitized_name = sanitized_name.strip()
        if sanitized_name:
            return f"{sanitized_name}_notes.md"

    # Fallback to file_id based name
    return f"note_{file_id[:8]}.md"


@router.get("/")
async def notes_root():
    """Root endpoint for notes API"""
    return {
        "message": "PDF Notes API",
        "version": "1.0.0",
        "endpoints": {
            "upload": "/upload",
            "status": "/status/{file_id}",
            "note": "/notes/{file_id}",
            "download_note_md": "/notes/{file_id}/download",
            "download_note_pdf": "/notes/{file_id}/download-pdf",
            "qa": "/qa/{file_id}",
            "files": "/files",
            "retry": "/files/{file_id}/retry"
        }
    }


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Chroma
        chunk_count = notes_chroma_service.count()

        return {
            "status": "healthy",
            "chroma": {
                "connected": True,
                "total_chunks": chunk_count
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    note_style: NoteStyle = Form(NoteStyle.moderate),
    user_prompt: Optional[str] = Form(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Upload a PDF file for processing.

    Args:
        file: PDF file to upload
        note_style: Style of notes to generate:
            - short: Quick bullet points with only the most important facts
            - moderate: Balanced notes with main ideas and key details (default)
            - descriptive: Detailed comprehensive notes with full explanations
        user_prompt: Optional custom instructions for note generation

    Returns:
        Upload response with file_id and task_id

    Example:
        Upload with moderate style (default):
        curl -X POST "http://localhost:8000/upload" \\
          -F "file=@document.pdf" \\
          -F "note_style=moderate"

        Upload with short style and custom prompt:
        curl -X POST "http://localhost:8000/upload" \\
          -F "file=@document.pdf" \\
          -F "note_style=short" \\
          -F "user_prompt=Focus on methodology only"
    """
    try:
        user_id = current_user["id"]
        logger.info(f"=== Starting upload for file: {file.filename} (user_id: {user_id}) ===")
        logger.info(f"Supabase URL: {settings.supabase_url}")
        logger.info(f"Using Supabase key type: {'service_role' if settings.supabase_service_role_key else 'anon'}")

        # Validate file type
        logger.info("Step 1: Validating file type...")
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported"
            )

        # Read file content
        logger.info("Step 2: Reading file content...")
        content = await file.read()

        if not content:
            raise HTTPException(status_code=400, detail="Empty file")

        # Check file size
        logger.info(f"Step 3: Checking file size ({len(content)} bytes)...")
        if len(content) > settings.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {settings.max_file_size} bytes"
            )

        # Compute file hash
        logger.info("Step 4: Computing file hash...")
        file_hash = compute_bytes_hash(content)
        logger.info(f"File hash: {file_hash}")

        # Check if file already exists for this user
        logger.info("Step 5: Checking for existing file in database...")
        try:
            existing_file = notes_db.get_file_by_hash(file_hash, user_id=user_id)
            logger.info(f"Database check completed. Existing file: {existing_file is not None}")
        except Exception as db_error:
            logger.error(f"DATABASE ERROR during get_file_by_hash: {str(db_error)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        if existing_file:
            logger.info("File already exists, returning existing record")
            return UploadResponse(
                file_id=existing_file['id'],
                task_id="",
                filename=existing_file['original_filename'],
                status=existing_file['status'],
                message="File already exists (duplicate detected)"
            )

        # Generate unique file ID and save file
        logger.info("Step 6: Generating file ID and saving to disk...")
        file_id = str(uuid4())
        filename = f"{file_id}.pdf"
        file_path = os.path.join(settings.upload_dir, filename)
        logger.info(f"File path: {file_path}")

        # Ensure upload directory exists
        ensure_directory(settings.upload_dir)

        with open(file_path, "wb") as f:
            f.write(content)
        logger.info("File saved to disk successfully")

        # Create file record in database
        logger.info("Step 7: Creating file record in database...")
        file_data = {
            'id': file_id,
            'user_id': user_id,
            'filename': filename,
            'original_filename': file.filename,
            'file_path': file_path,
            'sha256': file_hash,
            'file_size': len(content),
            'status': 'uploaded',
            'user_prompt': user_prompt
        }
        try:
            notes_db.create_file(file_data)
            logger.info("File record created in database successfully")
        except Exception as db_error:
            logger.error(f"DATABASE ERROR during create_file: {str(db_error)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        # Enqueue processing task with note style
        logger.info("Step 8: Enqueueing processing task...")
        task = process_file_task.delay(file_id, file_path, note_style.value, user_prompt)
        logger.info(f"Task enqueued with ID: {task.id}")

        logger.info("=== Upload completed successfully ===")
        return UploadResponse(
            file_id=file_id,
            task_id=task.id,
            filename=file.filename,
            status='uploaded',
            message="File uploaded successfully and queued for processing"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"UPLOAD FAILED: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/status/{file_id}", response_model=FileStatus)
async def get_file_status(file_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get processing status of a file.

    Args:
        file_id: File ID

    Returns:
        File status information
    """
    user_id = current_user["id"]
    file_info = notes_db.get_file(file_id, user_id=user_id)

    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")

    return FileStatus(
        file_id=file_info['id'],
        filename=file_info['original_filename'],
        status=file_info['status'],
        created_at=file_info['created_at'],
        updated_at=file_info['updated_at'],
        error=file_info.get('error')
    )


@router.get("/files/{file_id}/chunks")
async def get_file_chunks(file_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get all chunks for a file (for debugging).

    Args:
        file_id: File ID

    Returns:
        List of chunks with their content
    """
    user_id = current_user["id"]
    file_info = notes_db.get_file(file_id, user_id=user_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")

    chunks = notes_db.get_chunks_by_file(file_id)

    return {
        "file_id": file_id,
        "filename": file_info['original_filename'],
        "total_chunks": len(chunks),
        "chunks": [
            {
                "chunk_id": chunk['chunk_id'],
                "chunk_index": chunk['chunk_index'],
                "text_preview": chunk['chunk_text'][:500] + "..." if len(chunk['chunk_text']) > 500 else chunk['chunk_text'],
                "text_length": len(chunk['chunk_text']),
                "token_count": chunk.get('token_count', 0)
            }
            for chunk in chunks
        ]
    }


@router.get("/files")
async def list_files(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List all uploaded files with pagination.

    Args:
        limit: Number of files to return (1-100, default 10)
        offset: Offset for pagination (default 0)

    Returns:
        Paginated list of files with metadata

    Example:
        curl -X GET "http://localhost:8001/files?limit=20&offset=0"
    """
    try:
        user_id = current_user["id"]
        result = notes_db.list_files(limit=limit, offset=offset, user_id=user_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list files: {str(e)}"
        )


@router.get("/{file_id}")
async def get_note(file_id: str, format: Optional[str] = Query(None, description="Response format: 'html' for HTML page with download button, or 'json' for JSON (default)"), current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get the generated note for a file.

    Args:
        file_id: File ID
        format: Optional format parameter ('html' or 'json'). Defaults to 'json'.
                If 'html' is specified, returns an HTML page with download button.
                If accessed via browser without format parameter, defaults to JSON for API compatibility.

    Returns:
        Generated note (JSON or HTML depending on format parameter)
    """
    # Check if file exists
    user_id = current_user["id"]
    file_info = notes_db.get_file(file_id, user_id=user_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")

    # Check status
    if file_info['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Note not ready. Current status: {file_info['status']}"
        )

    # Get note
    note = notes_db.get_note_by_file(file_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # If HTML format is requested, return HTML page with download button
    if format == 'html':
        # Import html escaping module
        import html as html_module
        # Escape HTML special characters in note text
        note_text_html = html_module.escape(note['note_text'])
        # Convert markdown-style formatting (basic conversions)
        note_text_html = note_text_html.replace('\n', '<br>')

        # Escape values for HTML template
        escaped_filename = html_module.escape(file_info.get('original_filename', file_id))
        escaped_file_id = html_module.escape(file_id)
        escaped_created_at = html_module.escape(str(note.get('created_at', 'N/A')))

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Note - {escaped_filename}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 30px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }}
        h1 {{
            margin: 0;
            color: #333;
            font-size: 24px;
        }}
        .download-btn {{
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            font-weight: 500;
            display: inline-block;
            transition: background-color 0.2s;
        }}
        .download-btn:hover {{
            background-color: #0056b3;
        }}
        .metadata {{
            color: #666;
            font-size: 14px;
            margin-bottom: 20px;
        }}
        .note-content {{
            line-height: 1.6;
            color: #333;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Note: {escaped_filename}</h1>
            <div style="display: flex; gap: 10px;">
                <a href="/notes/{escaped_file_id}/download" class="download-btn" download>Download as Markdown</a>
                <a href="/notes/{escaped_file_id}/download-pdf" class="download-btn" style="background-color: #dc3545;" download>Download as PDF</a>
            </div>
        </div>
        <div class="metadata">
            <strong>File ID:</strong> {escaped_file_id}<br>
            <strong>Created:</strong> {escaped_created_at}
        </div>
        <div class="note-content">
{note_text_html}
        </div>
    </div>
</body>
</html>
        """
        return HTMLResponse(content=html_content)

    # Default: return JSON response
    return NoteResponse(
        file_id=file_id,
        note_text=note['note_text'],
        metadata=note.get('metadata'),
        created_at=note['created_at']
    )


@router.get("/{file_id}/download/markdown")
async def download_note(file_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Download the generated note for a file as a markdown (.md) file.

    Args:
        file_id: File ID

    Returns:
        Markdown file for download
    """
    # Check if file exists
    user_id = current_user["id"]
    file_info = notes_db.get_file(file_id, user_id=user_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")

    # Check status
    if file_info['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Note not ready. Current status: {file_info['status']}"
        )

    # Get note
    note = notes_db.get_note_by_file(file_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Prepare markdown content with frontmatter
    markdown_content = ""

    # Add YAML frontmatter with metadata
    metadata = note.get('metadata', {})
    frontmatter_metadata = {
        'file_id': file_id,
        'original_filename': file_info.get('original_filename', ''),
        'created_at': note.get('created_at', ''),
    }

    # Add note metadata if available
    if metadata:
        frontmatter_metadata.update(metadata)

    # Add LLM info if available
    if note.get('llm_provider'):
        frontmatter_metadata['llm_provider'] = note['llm_provider']
    if note.get('llm_model'):
        frontmatter_metadata['llm_model'] = note['llm_model']
    if note.get('tokens_used'):
        frontmatter_metadata['tokens_used'] = note['tokens_used']

    if frontmatter_metadata:
        markdown_content += "---\n"
        for key, value in frontmatter_metadata.items():
            if value is not None:
                # Handle different value types for YAML
                if isinstance(value, (dict, list)):
                    markdown_content += f"{key}: {json.dumps(value)}\n"
                elif isinstance(value, bool):
                    markdown_content += f"{key}: {str(value).lower()}\n"
                elif isinstance(value, (int, float)):
                    markdown_content += f"{key}: {value}\n"
                else:
                    value_str = str(value)
                    if ':' in value_str or '\n' in value_str:
                        markdown_content += f"{key}: {json.dumps(value_str)}\n"
                    else:
                        markdown_content += f"{key}: {value_str}\n"
        markdown_content += "---\n\n"

    # Add the note content
    markdown_content += note['note_text']

    # Generate filename for download
    original_filename = file_info.get('original_filename', '')
    download_filename = get_note_filename(original_filename, file_id)

    # Return markdown file as download
    return Response(
        content=markdown_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{download_filename}"'
        }
    )


@router.get("/{file_id}/download/pdf")
async def download_note_pdf(file_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Download the generated note for a file as a PDF (.pdf) file.

    Args:
        file_id: File ID

    Returns:
        PDF file for download
    """
    # Check if file exists
    user_id = current_user["id"]
    file_info = notes_db.get_file(file_id, user_id=user_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")

    # Check status
    if file_info['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Note not ready. Current status: {file_info['status']}"
        )

    # Get note
    note = notes_db.get_note_by_file(file_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Get original filename for use in PDF metadata
    original_filename = file_info.get('original_filename', '')

    # For PDF, we'll use the note content without frontmatter
    # Frontmatter is not needed in PDF and can cause TOC issues
    note_text = note['note_text']

    # Ensure the document starts with an h1 heading for proper TOC generation
    note_text_stripped = note_text.strip()

    # Check if note starts with any heading
    if not note_text_stripped.startswith('#'):
        # No heading - add h1 title at the beginning
        title = original_filename.replace('.pdf', '') if original_filename else f"Note"
        markdown_content = f"# {title}\n\n{note_text}"
    else:
        # Check if it starts with h1 (# heading)
        lines = note_text_stripped.split('\n')
        first_line = lines[0].strip()

        if first_line.startswith('# ') or first_line == '#':
            # Already starts with h1, use as-is
            markdown_content = note_text
        elif first_line.startswith('##'):
            # Starts with h2 or lower - need to add h1 or convert first heading
            title = original_filename.replace('.pdf', '') if original_filename else f"Note"
            markdown_content = f"# {title}\n\n{note_text}"
        else:
            # Already has heading, use as-is
            markdown_content = note_text

    try:
        # CSS styling for better PDF appearance
        user_css = """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }
        h1 {
            font-size: 24pt;
            color: #1a1a1a;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 10px;
            margin-top: 30px;
            margin-bottom: 20px;
        }
        h2 {
            font-size: 20pt;
            color: #2a2a2a;
            margin-top: 25px;
            margin-bottom: 15px;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 5px;
        }
        h3 {
            font-size: 16pt;
            color: #3a3a3a;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        h4 {
            font-size: 14pt;
            color: #4a4a4a;
            margin-top: 15px;
            margin-bottom: 8px;
        }
        p {
            margin: 10px 0;
            text-align: justify;
        }
        ul, ol {
            margin: 10px 0;
            padding-left: 30px;
        }
        li {
            margin: 5px 0;
        }
        code {
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 10pt;
        }
        pre {
            background-color: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            border-left: 4px solid #007bff;
            margin: 15px 0;
        }
        pre code {
            background-color: transparent;
            padding: 0;
        }
        blockquote {
            border-left: 4px solid #ccc;
            margin: 15px 0;
            padding-left: 20px;
            color: #666;
            font-style: italic;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        hr {
            border: none;
            border-top: 1px solid #e0e0e0;
            margin: 20px 0;
        }
        """

        # Create PDF from markdown using markdown-pdf library
        # Try with TOC first, fallback to no TOC if hierarchy issues occur
        try:
            # Try with TOC enabled - use toc_level=1 to only include h1 headings
            pdf = MarkdownPdf(toc_level=1, optimize=True)

            # Set PDF metadata
            pdf.meta["title"] = original_filename.replace('.pdf', '') if original_filename else f"Note {file_id}"
            pdf.meta["author"] = "PDF Notes API"
            if note.get('llm_provider'):
                pdf.meta["subject"] = f"Generated using {note.get('llm_provider')}"

            # Add markdown content as a section with custom CSS
            # toc=True includes headings in table of contents
            pdf.add_section(Section(markdown_content, toc=True), user_css=user_css)

            # Convert to PDF bytes
            pdf_bytes = io.BytesIO()
            pdf.save_bytes(pdf_bytes)
            pdf_bytes.seek(0)

        except Exception as toc_error:
            # If TOC fails due to hierarchy issues, retry without TOC
            if "hierarchy" in str(toc_error).lower() or "level" in str(toc_error).lower():
                # Disable TOC and try again
                pdf = MarkdownPdf(toc_level=0, optimize=True)

                # Set PDF metadata
                pdf.meta["title"] = original_filename.replace('.pdf', '') if original_filename else f"Note {file_id}"
                pdf.meta["author"] = "PDF Notes API"
                if note.get('llm_provider'):
                    pdf.meta["subject"] = f"Generated using {note.get('llm_provider')}"

                # Add markdown content without TOC
                pdf.add_section(Section(markdown_content, toc=False), user_css=user_css)

                # Convert to PDF bytes
                pdf_bytes = io.BytesIO()
                pdf.save_bytes(pdf_bytes)
                pdf_bytes.seek(0)
            else:
                # Re-raise if it's a different error
                raise

        # Generate filename for download (replace .md with .pdf)
        md_filename = get_note_filename(original_filename, file_id)
        pdf_filename = md_filename.replace('.md', '.pdf') if md_filename.endswith('.md') else f"{md_filename}.pdf"

        # Return PDF file as download
        return Response(
            content=pdf_bytes.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{pdf_filename}"'
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}"
        )


@router.post("/{file_id}/ask", response_model=AnswerResponse)
async def ask_question(file_id: str, request: QuestionRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Ask a question about a specific file using RAG.

    Args:
        file_id: File ID to query
        request: Question request with query text

    Returns:
        Answer with sources
    """
    # Check if file exists and is processed
    user_id = current_user["id"]
    file_info = notes_db.get_file(file_id, user_id=user_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")

    if file_info['status'] not in ['indexed', 'summarizing', 'completed']:
        raise HTTPException(
            status_code=400,
            detail=f"File not ready for queries. Status: {file_info['status']}"
        )

    try:
        # First, check if chunks exist in database for this file
        db_chunks = notes_db.get_chunks_by_file(file_id)
        if not db_chunks:
            raise HTTPException(
                status_code=404,
                detail=f"No chunks found for this file. The file may not have been processed yet or chunks were not created."
            )

        # Check if chunks exist in ChromaDB for this file
        chroma_chunk_count = notes_chroma_service.count_by_file_id(file_id)
        if chroma_chunk_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No chunks found in ChromaDB for this file. Database has {len(db_chunks)} chunks, but ChromaDB has 0. The embeddings may not have been stored. Try reprocessing the file using the /files/{file_id}/retry endpoint."
            )

        # Embed the question using the embedding service from notes_chroma
        # The embedding service is accessed through notes_chroma_service
        question_embedding = notes_chroma_service.embed_text(request.question)
        question_embeddings = [question_embedding]  # Wrap in list for ChromaDB

        # Query Chroma for relevant chunks
        try:
            results = notes_chroma_service.query(
                query_embeddings=question_embeddings,
                n_results=request.n_results,
                where={"file_id": file_id},
                include=["documents", "metadatas", "distances"]
            )
        except Exception as chroma_error:
            raise HTTPException(
                status_code=500,
                detail=f"ChromaDB query failed: {str(chroma_error)}. Database has {len(db_chunks)} chunks, ChromaDB has {chroma_chunk_count} chunks for this file."
            )

        # Check if results are valid
        if not results or 'documents' not in results:
            raise HTTPException(
                status_code=404,
                detail=f"No relevant content found in ChromaDB. Database has {len(db_chunks)} chunks, ChromaDB has {chroma_chunk_count} chunks, but query returned no results."
            )

        # Handle ChromaDB result structure (documents is a list of lists)
        documents_list = results.get('documents', [])
        metadatas_list = results.get('metadatas', [])
        distances_list = results.get('distances', [])

        # Get first query result (since we only pass one query embedding)
        if not documents_list or len(documents_list) == 0 or not documents_list[0] or len(documents_list[0]) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No relevant content found for this question. Database has {len(db_chunks)} chunks for this file, but ChromaDB returned empty results. Try a different question or verify the chunks were properly indexed."
            )

        retrieved_docs = documents_list[0]
        retrieved_meta = metadatas_list[0] if metadatas_list else []
        distances = distances_list[0] if distances_list else []

        # Ensure all lists have the same length
        min_length = min(len(retrieved_docs), len(retrieved_meta) if retrieved_meta else len(retrieved_docs), len(distances) if distances else len(retrieved_docs))
        retrieved_docs = retrieved_docs[:min_length]
        retrieved_meta = retrieved_meta[:min_length] if retrieved_meta else []
        distances = distances[:min_length] if distances else [0.0] * min_length

        # Prepare sources with relevance scores
        sources = []
        for i, doc in enumerate(retrieved_docs):
            meta = retrieved_meta[i] if i < len(retrieved_meta) else {}
            distance = distances[i] if i < len(distances) else 1.0

            sources.append({
                'chunk_index': meta.get('chunk_index', i),
                'relevance_score': float(1 - distance) if distance <= 1.0 else 0.0,  # Convert distance to similarity
                'preview': doc[:200] + "..." if len(doc) > 200 else doc
            })

        # Generate answer using LLM
        answer_result = llm_service.answer_question(
            request.question,
            retrieved_docs
        )

        # Validate answer result
        if not answer_result or 'text' not in answer_result:
            raise HTTPException(
                status_code=500,
                detail="LLM service did not return a valid answer"
            )

        return AnswerResponse(
            answer=answer_result['text'],
            sources=sources,
            model_info={
                'provider': answer_result.get('provider', 'unknown'),
                'model': answer_result.get('model', 'unknown'),
                'tokens_used': answer_result.get('tokens_used', 0)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Question answering failed: {str(e)}"
        )


@router.post("/files/{file_id}/retry", response_model=RetryResponse)
async def retry_file(
    file_id: str,
    note_style: Optional[NoteStyle] = Query(None, description="Note style for retry (optional, defaults to moderate)"),
    user_prompt: Optional[str] = Query(None, description="Custom instructions for retry (optional)"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retry processing a failed file.

    This endpoint allows you to retry processing files that have failed.
    It will clean up any partial data (chunks, summaries, notes) and
    re-enqueue the file for processing.

    Args:
        file_id: File ID to retry
        note_style: Optional note style (short, moderate, descriptive).
                   If not provided, defaults to moderate.
        user_prompt: Optional custom instructions. If not provided,
                    uses the original user_prompt from the file record.

    Returns:
        Retry response with new task_id

    Example:
        Retry with default settings:
        curl -X POST "http://localhost:8001/files/{file_id}/retry"

        Retry with custom note style:
        curl -X POST "http://localhost:8001/files/{file_id}/retry?note_style=short"

        Retry with custom prompt:
        curl -X POST "http://localhost:8001/files/{file_id}/retry?user_prompt=Focus on key points"
    """
    # Check if file exists
    user_id = current_user["id"]
    file_info = notes_db.get_file(file_id, user_id=user_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")

    # Check if file has failed (or allow retrying from other non-completed statuses)
    if file_info['status'] == 'completed':
        raise HTTPException(
            status_code=400,
            detail="Cannot retry a file that is already completed. Delete and re-upload if needed."
        )

    # Check if physical file still exists
    file_path = file_info.get('file_path')
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Physical file not found at path: {file_path}. Cannot retry."
        )

    try:
        # Clean up partial data
        # 1. Delete from Chroma
        try:
            notes_chroma_service.delete_by_file_id(file_id)
        except Exception as e:
            print(f"Warning: Failed to delete from Chroma: {e}")

        # 2. Delete database records (chunks, summaries, notes)
        notes_db.cleanup_file_data(file_id)

        # Determine note_style and user_prompt to use
        retry_note_style = note_style.value if note_style else NoteStyle.moderate.value
        retry_user_prompt = user_prompt if user_prompt is not None else file_info.get('user_prompt')

        # Update file status to 'uploaded', clear error, and optionally update user_prompt
        update_data = {
            'status': 'uploaded',
            'error': None,
            'updated_at': datetime.utcnow().isoformat()
        }
        if user_prompt is not None:
            update_data['user_prompt'] = user_prompt

        # Update file record
        notes_db.update_file(file_id, update_data)

        # Re-enqueue processing task
        task = process_file_task.delay(file_id, file_path, retry_note_style, retry_user_prompt)

        return RetryResponse(
            file_id=file_id,
            task_id=task.id,
            message=f"File queued for retry with note_style='{retry_note_style}'",
            status='uploaded'
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Retry failed: {str(e)}"
        )


@router.delete("/files/{file_id}")
async def delete_file(file_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Delete a file and all associated data.

    This endpoint deletes:
    - All data from Supabase (file, chunks, summaries, notes)
    - All data from ChromaDB (embeddings)
    - Physical PDF file from uploads directory
    - Local markdown note file if it exists

    Args:
        file_id: File ID to delete

    Returns:
        Deletion confirmation
    """
    # Check if file exists
    user_id = current_user["id"]
    file_info = notes_db.get_file(file_id, user_id=user_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        deletion_steps = []

        # 1. Delete from ChromaDB (embeddings)
        try:
            notes_chroma_service.delete_by_file_id(file_id)
            deletion_steps.append("ChromaDB")
        except Exception as e:
            print(f"Warning: Failed to delete from ChromaDB: {e}")

        # 2. Delete from Supabase (chunks, summaries, notes, then file record)
        try:
            # Clean up all related data (chunks, summaries, notes)
            notes_db.cleanup_file_data(file_id)
            deletion_steps.append("Supabase (chunks, summaries, notes)")

            # Delete the file record itself
            notes_db.delete_file(file_id)
            deletion_steps.append("Supabase (file record)")
        except Exception as e:
            print(f"Warning: Failed to delete from Supabase: {e}")

        # 3. Delete physical PDF file
        try:
            file_path = file_info.get('file_path')
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                deletion_steps.append("Physical PDF file")
        except Exception as e:
            print(f"Warning: Failed to delete physical PDF file: {e}")

        # 4. Delete local markdown note file if it exists
        try:
            if settings.save_notes_locally:
                original_filename = file_info.get('original_filename', '')
                if original_filename:
                    md_filename = get_note_filename(original_filename, file_id)
                    md_file_path = os.path.join(settings.notes_dir, md_filename)
                    if os.path.exists(md_file_path):
                        os.remove(md_file_path)
                        deletion_steps.append("Local markdown note")
        except Exception as e:
            print(f"Warning: Failed to delete local markdown note: {e}")

        return {
            "message": "File deleted successfully",
            "file_id": file_id,
            "deleted_from": deletion_steps
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Deletion failed: {str(e)}"
        )
