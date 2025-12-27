"""Notes generation routes - unified with main document upload system."""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import Response, HTMLResponse
from markdown_pdf import MarkdownPdf, Section
import io
from typing import Any
import json
import logging

from app.auth.auth import get_current_user
from app.auth.supabase_client import get_supabase
from app.services.notes_db import notes_db
from app.services.notes_llm import llm_service
from app.services.vectorstore import get_collection
from app.tasks.notes_tasks import generate_notes_task
from app.schemas import (
    NoteStyle,
    NoteGenerateRequest,
    NoteGenerateResponse,
    NoteResponse,
    NoteListResponse,
    NoteQuestionRequest,
    NoteAnswerResponse,
)

# Set up logger
logger = logging.getLogger(__name__)

# Create APIRouter
router = APIRouter(prefix="")


@router.get("/")
async def notes_root():
    """Root endpoint for notes API"""
    return {
        "message": "AI Notes Generation API",
        "version": "2.0.0",
        "description": "Generate comprehensive notes from your uploaded documents",
        "endpoints": {
            "generate": "POST /generate - Generate notes from document_ids",
            "list": "GET / - List all your notes",
            "get": "GET /{note_id} - Get a specific note",
            "delete": "DELETE /{note_id} - Delete a note",
            "download_markdown": "GET /{note_id}/download/markdown - Download as .md",
            "download_pdf": "GET /{note_id}/download/pdf - Download as .pdf",
            "ask": "POST /{note_id}/ask - Ask questions about note sources"
        }
    }


# Legacy endpoint handlers - return helpful migration messages
@router.get("/files")
async def legacy_files_endpoint(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """
    Legacy endpoint - files are now managed via /documents.

    The notes system has been unified with the main document upload system.
    Files are now uploaded via /upload-multiple and managed via /documents.
    Use POST /notes/generate with document_ids to generate notes.
    """
    raise HTTPException(
        status_code=410,  # Gone
        detail={
            "message": "This endpoint has been deprecated. The notes system now uses the unified document upload.",
            "migration": {
                "upload_files": "Use POST /upload-multiple to upload PDFs",
                "list_files": "Use GET /documents to list your uploaded documents",
                "generate_notes": "Use POST /notes/generate with document_ids from your documents",
                "list_notes": "Use GET /notes to list generated notes"
            }
        }
    )


@router.post("/upload")
async def legacy_upload_endpoint(current_user: dict[str, Any] = Depends(get_current_user)):
    """Legacy upload endpoint - now use /upload-multiple"""
    raise HTTPException(
        status_code=410,  # Gone
        detail={
            "message": "This endpoint has been deprecated. Use the unified document upload system.",
            "migration": {
                "upload_files": "Use POST /upload-multiple to upload PDFs",
                "generate_notes": "Use POST /notes/generate with document_ids after uploading"
            }
        }
    )


@router.get("/status/{file_id}")
async def legacy_status_endpoint(file_id: str, current_user: dict[str, Any] = Depends(get_current_user)):
    """Legacy status endpoint - now check document status via /documents"""
    raise HTTPException(
        status_code=410,  # Gone
        detail={
            "message": "This endpoint has been deprecated.",
            "migration": {
                "check_document_status": "Use GET /documents to check document embedding_status",
                "check_note_status": "Use GET /notes/{note_id} to check note generation status"
            }
        }
    )


@router.post("/generate", response_model=NoteGenerateResponse)
async def generate_notes_endpoint(
    request: NoteGenerateRequest,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """
    Generate notes from user's documents.

    This endpoint generates comprehensive notes from one or more documents
    that have been uploaded via the /upload-multiple endpoint.

    Args:
        request: NoteGenerateRequest with:
            - document_ids: List of document IDs to generate notes from
            - note_style: Style of notes ('short', 'moderate', 'descriptive')
            - user_prompt: Optional custom instructions
            - title: Optional title for the notes

    Returns:
        NoteGenerateResponse with note_id and task_id for tracking

    Example:
        POST /notes/generate
        {
            "document_ids": ["doc-id-1", "doc-id-2"],
            "note_style": "moderate",
            "title": "Chapter 5 Notes"
        }
    """
    try:
        user_id = current_user["id"]
        collection_name = f"user_{user_id}_docs"

        # Validate document_ids belong to user and are processed
        supabase = get_supabase()
        if not request.document_ids:
            raise HTTPException(
                status_code=400,
                detail="At least one document_id is required"
            )

        docs_result = supabase.table('documents').select(
            'id, embedding_status, original_filename'
        ).eq('user_id', user_id).in_('id', request.document_ids).execute()

        if len(docs_result.data) != len(request.document_ids):
            raise HTTPException(
                status_code=400,
                detail="One or more document IDs are invalid or do not belong to you"
            )

        # Check all documents are processed
        for doc in docs_result.data:
            if doc['embedding_status'] != 'completed':
                raise HTTPException(
                    status_code=400,
                    detail=f"Document '{doc.get('original_filename', doc['id'])}' is not yet processed. Status: {doc['embedding_status']}"
                )

        # Create note record with 'generating' status
        note_data = {
            'user_id': user_id,
            'document_ids': request.document_ids,
            'title': request.title,
            'note_style': request.note_style.value,
            'status': 'generating'
        }
        note_record = notes_db.create_note(note_data)

        if not note_record:
            raise HTTPException(
                status_code=500,
                detail="Failed to create note record"
            )

        # Queue the generation task
        task = generate_notes_task.delay(
            note_id=note_record['id'],
            document_ids=request.document_ids,
            note_style=request.note_style.value,
            user_prompt=request.user_prompt,
            collection_name=collection_name,
            user_id=user_id
        )

        return NoteGenerateResponse(
            id=note_record['id'],
            user_id=user_id,
            document_ids=request.document_ids,
            title=request.title,
            status='generating',
            task_id=task.id,
            created_at=note_record['created_at'],
            updated_at=note_record['updated_at']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error generating notes: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate notes: {str(e)}"
        )


@router.get("", response_model=list[NoteListResponse])
async def list_notes_endpoint(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """
    List all notes for the current user.

    Args:
        limit: Number of notes to return (1-100, default 50)
        offset: Offset for pagination (default 0)

    Returns:
        List of notes with metadata
    """
    try:
        user_id = current_user["id"]
        notes = notes_db.list_notes(user_id, limit=limit, offset=offset)

        return [
            NoteListResponse(
                id=note['id'],
                document_ids=note.get('document_ids', []),
                title=note.get('title'),
                status=note.get('status', 'unknown'),
                note_style=note.get('note_style', 'moderate'),
                created_at=note['created_at'],
                updated_at=note['updated_at']
            )
            for note in notes
        ]

    except Exception as e:
        logger.exception(f"Error listing notes: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list notes: {str(e)}"
        )


@router.get("/{note_id}")
async def get_note_endpoint(
    note_id: str,
    format: str | None = Query(None, description="Response format: 'html' for HTML page, or 'json' (default)"),
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """
    Get a specific note with its content.

    Args:
        note_id: Note ID
        format: Optional format ('html' or 'json', default 'json')

    Returns:
        Note with full content (or status info if still processing)
    """
    user_id = current_user["id"]
    note = notes_db.get_note(note_id, user_id=user_id)

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # If HTML format is requested - only allow for completed notes
    if format == 'html':
        if note['status'] != 'completed':
            raise HTTPException(
                status_code=400,
                detail=f"Note not ready for HTML view. Current status: {note['status']}"
            )
        import html as html_module
        note_text_html = html_module.escape(note.get('note_text', ''))
        note_text_html = note_text_html.replace('\n', '<br>')

        escaped_title = html_module.escape(note.get('title') or 'Untitled Note')
        escaped_note_id = html_module.escape(note_id)
        escaped_created_at = html_module.escape(str(note.get('created_at', 'N/A')))

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escaped_title}</title>
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
        h1 {{ margin: 0; color: #333; font-size: 24px; }}
        .download-btn {{
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            font-weight: 500;
            display: inline-block;
        }}
        .download-btn:hover {{ background-color: #0056b3; }}
        .metadata {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        .note-content {{ line-height: 1.6; color: #333; white-space: pre-wrap; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{escaped_title}</h1>
            <div style="display: flex; gap: 10px;">
                <a href="/notes/{escaped_note_id}/download/markdown" class="download-btn">Download Markdown</a>
                <a href="/notes/{escaped_note_id}/download/pdf" class="download-btn" style="background-color: #dc3545;">Download PDF</a>
            </div>
        </div>
        <div class="metadata">
            <strong>Note ID:</strong> {escaped_note_id}<br>
            <strong>Created:</strong> {escaped_created_at}
        </div>
        <div class="note-content">{note_text_html}</div>
    </div>
</body>
</html>
        """
        return HTMLResponse(content=html_content)

    # Default: return JSON response - always return note data regardless of status
    # This allows frontend to poll for status updates
    return {
        "id": note['id'],
        "user_id": note['user_id'],
        "document_ids": note.get('document_ids', []),
        "title": note.get('title'),
        "note_text": note.get('note_text'),  # Will be None/null if not completed
        "note_style": note.get('note_style', 'moderate'),
        "metadata": note.get('metadata'),
        "status": note['status'],
        "error": note.get('error'),  # Include error message if failed
        "created_at": note['created_at'],
        "updated_at": note['updated_at']
    }


@router.delete("/{note_id}")
async def delete_note_endpoint(
    note_id: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """
    Delete a note.

    Args:
        note_id: Note ID to delete

    Returns:
        Deletion confirmation
    """
    user_id = current_user["id"]

    # Check if note exists
    note = notes_db.get_note(note_id, user_id=user_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    try:
        notes_db.delete_note(note_id, user_id=user_id)
        return {"message": "Note deleted successfully", "note_id": note_id}
    except Exception as e:
        logger.exception(f"Error deleting note: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete note: {str(e)}"
        )


@router.get("/{note_id}/download/markdown")
async def download_note_markdown(
    note_id: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """
    Download the note as a markdown (.md) file.

    Args:
        note_id: Note ID

    Returns:
        Markdown file for download
    """
    user_id = current_user["id"]
    note = notes_db.get_note(note_id, user_id=user_id)

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if note['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Note not ready. Current status: {note['status']}"
        )

    # Prepare markdown content with frontmatter
    markdown_content = ""
    metadata = note.get('metadata', {})

    frontmatter_metadata = {
        'note_id': note_id,
        'title': note.get('title', ''),
        'document_ids': note.get('document_ids', []),
        'note_style': note.get('note_style', 'moderate'),
        'created_at': note.get('created_at', ''),
    }

    if metadata:
        frontmatter_metadata.update(metadata)

    if frontmatter_metadata:
        markdown_content += "---\n"
        for key, value in frontmatter_metadata.items():
            if value is not None:
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

    markdown_content += note.get('note_text', '')

    # Generate filename
    title = note.get('title', '')
    if title:
        sanitized_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title)
        download_filename = f"{sanitized_title[:50]}_notes.md"
    else:
        download_filename = f"note_{note_id[:8]}.md"

    return Response(
        content=markdown_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{download_filename}"'}
    )


@router.get("/{note_id}/download/pdf")
async def download_note_pdf(
    note_id: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """
    Download the note as a PDF (.pdf) file.

    Args:
        note_id: Note ID

    Returns:
        PDF file for download
    """
    user_id = current_user["id"]
    note = notes_db.get_note(note_id, user_id=user_id)

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if note['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Note not ready. Current status: {note['status']}"
        )

    title = note.get('title') or 'Notes'
    note_text = note.get('note_text', '')

    # Ensure document starts with h1 heading
    note_text_stripped = note_text.strip()
    if not note_text_stripped.startswith('#'):
        markdown_content = f"# {title}\n\n{note_text}"
    elif not note_text_stripped.startswith('# '):
        markdown_content = f"# {title}\n\n{note_text}"
    else:
        markdown_content = note_text

    try:
        user_css = """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }
        h1 { font-size: 24pt; color: #1a1a1a; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }
        h2 { font-size: 20pt; color: #2a2a2a; border-bottom: 1px solid #e0e0e0; padding-bottom: 5px; }
        h3 { font-size: 16pt; color: #3a3a3a; }
        p { margin: 10px 0; text-align: justify; }
        ul, ol { margin: 10px 0; padding-left: 30px; }
        li { margin: 5px 0; }
        code { background-color: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
        pre { background-color: #f4f4f4; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff; }
        blockquote { border-left: 4px solid #ccc; padding-left: 20px; color: #666; font-style: italic; }
        """

        try:
            pdf = MarkdownPdf(toc_level=1, optimize=True)
            pdf.meta["title"] = title
            pdf.meta["author"] = "AI Notes Generator"
            pdf.add_section(Section(markdown_content, toc=True), user_css=user_css)
            pdf_bytes = io.BytesIO()
            pdf.save_bytes(pdf_bytes)
            pdf_bytes.seek(0)
        except Exception as toc_error:
            if "hierarchy" in str(toc_error).lower() or "level" in str(toc_error).lower():
                pdf = MarkdownPdf(toc_level=0, optimize=True)
                pdf.meta["title"] = title
                pdf.meta["author"] = "AI Notes Generator"
                pdf.add_section(Section(markdown_content, toc=False), user_css=user_css)
                pdf_bytes = io.BytesIO()
                pdf.save_bytes(pdf_bytes)
                pdf_bytes.seek(0)
            else:
                raise

        # Generate filename
        if title != 'Notes':
            sanitized_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title)
            pdf_filename = f"{sanitized_title[:50]}_notes.pdf"
        else:
            pdf_filename = f"note_{note_id[:8]}.pdf"

        return Response(
            content=pdf_bytes.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{pdf_filename}"'}
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}"
        )


@router.post("/{note_id}/ask", response_model=NoteAnswerResponse)
async def ask_question_about_note(
    note_id: str,
    request: NoteQuestionRequest,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """
    Ask a question about the source documents of a note using RAG.

    This endpoint uses the original document chunks to answer questions,
    providing context from the source material.

    Args:
        note_id: Note ID
        request: Question request with query text

    Returns:
        Answer with sources from the original documents
    """
    user_id = current_user["id"]

    # Get the note to find associated documents
    note = notes_db.get_note(note_id, user_id=user_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    document_ids = note.get('document_ids', [])
    if not document_ids:
        raise HTTPException(
            status_code=400,
            detail="Note has no associated documents"
        )

    try:
        collection_name = f"user_{user_id}_docs"
        collection = get_collection(collection_name)

        # Retrieve chunks from all associated documents
        all_chunks = []
        for doc_id in document_ids:
            try:
                results = collection._collection.get(
                    where={"document_id": doc_id},
                    include=["documents", "metadatas"]
                )
                if results and results.get("documents"):
                    for i, doc_text in enumerate(results["documents"]):
                        all_chunks.append({
                            "text": doc_text,
                            "document_id": doc_id,
                            "chunk_index": results["metadatas"][i].get("chunk_index", i) if results.get("metadatas") else i
                        })
            except Exception as e:
                logger.warning(f"Error retrieving chunks for document {doc_id}: {e}")

        if not all_chunks:
            raise HTTPException(
                status_code=404,
                detail="No content found in the source documents"
            )

        # Use semantic search to find relevant chunks
        # For now, we'll do a simple similarity search using the collection
        search_results = collection.similarity_search_with_score(
            request.question,
            k=request.n_results,
            filter={"document_id": {"$in": document_ids}} if len(document_ids) > 1 else {"document_id": document_ids[0]}
        )

        if not search_results:
            raise HTTPException(
                status_code=404,
                detail="No relevant content found for this question"
            )

        # Prepare sources
        sources = []
        retrieved_docs = []
        for doc, score in search_results:
            retrieved_docs.append(doc.page_content)
            sources.append({
                'chunk_index': doc.metadata.get('chunk_index', 0),
                'document_id': doc.metadata.get('document_id', ''),
                'relevance_score': float(1 - score) if score <= 1.0 else 0.0,
                'preview': doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            })

        # Generate answer using LLM
        answer_result = llm_service.answer_question(
            request.question,
            retrieved_docs
        )

        if not answer_result or 'text' not in answer_result:
            raise HTTPException(
                status_code=500,
                detail="LLM service did not return a valid answer"
            )

        return NoteAnswerResponse(
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
        logger.exception(f"Question answering failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Question answering failed: {str(e)}"
        )
