# main.py
import os
import uuid
from datetime import datetime
from typing import Any

from chromadb import logger
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.auth.auth import get_current_user
from app.schemas import (
    AuthResponse,
    ChatMessageCreate,
    ChatSessionCreate,
    QueryRequest,
    QueryResponse,
    UploadResponse,
    UserSignIn,
    UserSignUp,
    UserUpdate,
)
from app.services.chat_service import (
    add_chat_message,
    create_chat_session,
    delete_chat_session,
    get_chat_messages,
    get_or_create_active_session,
    get_session_by_id,
    get_user_chat_sessions,
    update_session_name,
)
from app.services.document_service import (
    create_document,
    delete_document,
    get_all_documents,
    get_document_by_id,
    get_user_documents,
)
from app.services.rag import answer_question
from app.services.user_service import (
    get_all_users,
    sign_in_user,
    sign_up_user,
    update_user,
)
from app.services.vectorstore import get_collection
from app.tasks import process_pdf

app = FastAPI(
    title="RAG API",
    description="RAG API with JWT Authentication and Supabase Integration",
    version="1.0.0"
)
#trying something new
# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ============================================
# AUTHENTICATION ENDPOINTS (PUBLIC)
# ============================================

@app.post("/auth/signup", response_model=AuthResponse)
async def signup(user_data: UserSignUp):
    """Sign up a new user"""
    try:
        result = await sign_up_user(
            email=user_data.email,
            password=user_data.password,
            user_data={
                'username': user_data.username,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name,
                'profile_image_url': user_data.profile_image_url
            }
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error during signup: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/auth/signin", response_model=AuthResponse)
async def signin(credentials: UserSignIn):
    """Sign in an existing user"""
    try:
        result = await sign_in_user(credentials.email, credentials.password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.exception(f"Error during signin: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint (public)"""
    return {"status": "healthy", "message": "RAG API is running"}

# ============================================
# USER ENDPOINTS (PROTECTED)
# ============================================

@app.get("/me", response_model=dict)
async def get_current_user_profile(current_user: dict[str, Any] = Depends(get_current_user)):
    """Get current user profile"""
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "username": current_user["username"],
        "first_name": current_user["first_name"],
        "last_name": current_user["last_name"],
        "profile_image_url": current_user["profile_image_url"],
        "created_at": current_user["created_at"],
        "last_sign_in_at": current_user["last_sign_in_at"]
    }

@app.put("/me", response_model=dict)
async def update_current_user_profile(
    user_data: UserUpdate,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Update current user profile"""
    try:
        updated_user = await update_user(current_user["id"], user_data.dict(exclude_unset=True))
        if not updated_user:
            raise HTTPException(status_code=400, detail="Failed to update user")

        return {
            "id": updated_user["id"],
            "email": updated_user["email"],
            "username": updated_user["username"],
            "first_name": updated_user["first_name"],
            "last_name": updated_user["last_name"],
            "profile_image_url": updated_user["profile_image_url"]
        }
    except Exception as e:
        logger.exception(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user")

# Admin endpoints (you might want to add role-based access control)
@app.get("/admin/users", response_model=list[dict])
async def get_all_users_endpoint(current_user: dict[str, Any] = Depends(get_current_user)):
    """Get all users (admin endpoint)"""
    try:
        users = await get_all_users()
        return users
    except Exception as e:
        logger.exception(f"Error getting users: {e}")
        raise HTTPException(status_code=500, detail="Failed to get users")

# ============================================
# DOCUMENT ENDPOINTS (PROTECTED)
# ============================================

@app.post("/upload-multiple", response_model=list[UploadResponse])
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

# @app.post("/upload", response_model=UploadResponse)
# async def upload_pdf(
#     File: list[UploadFile] = File(...),
#     current_user: dict[str, Any] = Depends(get_current_user)
# ):
#     """Upload single PDF file"""
#     for file in File:
#         if not file.filename.lower().endswith(".pdf"):
#             raise HTTPException(status_code=400, detail="Only PDF files are allowed")

#         user_id = current_user["id"]
#         unique_filename = f"{uuid.uuid4()}_{file.filename}"
#         file_path = os.path.join(UPLOAD_DIR, unique_filename)

#         with open(file_path, "wb") as f:
#             content = await file.read()
#             f.write(content)

#         # Create document record
#         document_data = {
#             'filename': unique_filename,
#             'original_filename': file.filename,
#             'file_size': len(content),
#             'file_type': 'pdf',
#             'mime_type': file.content_type,
#             'storage_path': file_path,
#             'chroma_collection_name': f"user_{user_id}_docs"
#         }

#         db_document = await create_document(
#             user_id=user_id,
#             document_data=document_data
#         )

#         process_pdf.delay(file_path, file.filename, unique_filename, user_id, db_document['id'])

#         return {
#             "filename": file.filename,
#             "stored_as": unique_filename,
#             "document_id": db_document['id'],
#             "message": "PDF uploaded and queued for processing"
#         }

@app.get("/documents", response_model=list[dict])
async def get_user_documents_endpoint(current_user: dict[str, Any] = Depends(get_current_user)):
    """Get current user's uploaded documents"""
    try:
        documents = await get_user_documents(current_user["id"])
        return documents
    except Exception as e:
        logger.exception(f"Error getting uploads: {e}")
        raise HTTPException(status_code=500, detail="Failed to get uploads")

@app.delete("/documents/{document_id}")
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
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# QUERY ENDPOINTS (PROTECTED)
# ============================================

@app.post("/query", response_model=QueryResponse)
async def query_rag(
    request: QueryRequest,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Query RAG with ChatGPT-like session management"""
    try:
        user_id = current_user["id"]
        collection_name = f"user_{user_id}_docs"

        # Handle session management based on request
        if hasattr(request, 'new_chat') and request.new_chat:
            # Create new session (like "New Chat" button)
            session_name = f"Chat - {datetime.now().strftime('%m/%d %H:%M')}"
            session = await create_chat_session(
                user_id=user_id,
                session_name=session_name,
                session_type="conversation",
                document_ids=[]
            )
            session_id = session['id']
            is_new_session = True
            chat_history = []  # No history for new chat
        elif hasattr(request, 'session_id') and request.session_id:
            # Continue existing session
            session = await get_session_by_id(request.session_id)
            if not session or session['user_id'] != user_id:
                raise HTTPException(status_code=404, detail="Session not found")
            session_id = request.session_id
            is_new_session = False
            chat_history = await get_chat_messages(session_id, limit=5)
        else:
            # Use or create active session (default behavior)
            session = await get_or_create_active_session(user_id)
            session_id = session['id']
            is_new_session = session.get('message_count', 0) == 0
            chat_history = await get_chat_messages(session_id, limit=5) if not is_new_session else []

        # Generate answer with context
        answer_text = await answer_question(
            request.question,
            n_results=5,
            collection_name=collection_name,
            user_id=user_id,
            chat_history=chat_history
        )

        # Save the conversation
        await add_chat_message(
            session_id=session_id,
            content=request.question,
            retrieval_query=request.question
        )

        await add_chat_message(
            session_id=session_id,
            content=answer_text,
            source_documents=None
        )

        return {
            "answer": answer_text,
            "session_id": session_id,
            "session_name": session.get('session_name', 'New Chat'),
            "is_new_session": is_new_session,
            "message_count": session.get('message_count', 0) + 2  # +2 for the Q&A we just added
        }

    except Exception as e:
        logger.exception(f"Error during query: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query: {str(e)}")

# ============================================
# CHAT SESSION ENDPOINTS (PROTECTED)
# ============================================
@app.put("/chat-sessions/{session_id}/name")
async def update_session_name_endpoint(
    session_id: str,
    new_name: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Update a chat session's name"""
    try:
        success = await update_session_name(session_id, current_user["id"], new_name)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found or access denied")
        return {"message": "Session name updated successfully"}
    except Exception as e:
        logger.exception(f"Error updating session name: {e}")
        raise HTTPException(status_code=500, detail="Failed to update session name")


@app.post("/chat-sessions", response_model=dict)
async def create_chat_session_endpoint(
    session_data: ChatSessionCreate,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Create a new chat session"""
    try:
        user_id = current_user["id"]

        session = await create_chat_session(
            user_id=user_id,
            session_name=session_data.session_name,
            session_type=session_data.session_type,
            document_ids=session_data.document_ids
        )
        return session
    except Exception as e:
        logger.exception(f"Error creating chat session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create chat session")

@app.get("/chat-sessions", response_model=list[dict])
async def get_user_chat_sessions_endpoint(current_user: dict[str, Any] = Depends(get_current_user)):
    """Get user's chat sessions"""
    try:
        sessions = await get_user_chat_sessions(current_user["id"])
        return sessions
    except Exception as e:
        logger.exception(f"Error getting chat sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat sessions")

@app.post("/chat-sessions/{session_id}/messages", response_model=dict)
async def add_chat_message_endpoint(
    session_id: str,
    message_data: ChatMessageCreate,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Add a message to a chat session"""
    try:
        user_id = current_user["id"]

        # Verify user owns the session
        sessions = await get_user_chat_sessions(user_id)
        session_exists = any(s['id'] == session_id for s in sessions)

        if not session_exists:
            raise HTTPException(status_code=404, detail="Chat session not found or access denied")

        message = await add_chat_message(
            session_id=session_id,
            content=message_data.content,
            tokens_used=message_data.tokens_used,
            source_documents=message_data.source_documents,
            retrieval_query=message_data.retrieval_query
        )
        return message
    except Exception as e:
        logger.exception(f"Error adding chat message: {e}")
        raise HTTPException(status_code=500, detail="Failed to add chat message")

@app.get("/chat-sessions/{session_id}/messages", response_model=list[dict])
async def get_chat_messages_endpoint(
    session_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    limit: int = 50
):
    """Get messages for a chat session"""
    try:
        user_id = current_user["id"]

        # Verify user owns the session
        sessions = await get_user_chat_sessions(user_id)
        session_exists = any(s['id'] == session_id for s in sessions)

        if not session_exists:
            raise HTTPException(status_code=404, detail="Chat session not found or access denied")

        messages = await get_chat_messages(session_id, limit)
        return messages
    except Exception as e:
        logger.exception(f"Error getting chat messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat messages")

@app.delete("/chat-sessions/{session_id}")
async def delete_chat_session_endpoint(
    session_id: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Delete a chat session"""
    try:
        user_id = current_user["id"]
        success = await delete_chat_session(session_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Chat session not found or access denied")

        return {"message": "Chat session deleted successfully"}
    except Exception as e:
        logger.exception(f"Error deleting chat session: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete chat session")

# ============================================
# ADVANCED QUERY WITH CHAT CONTEXT (PROTECTED)
# ============================================

@app.post("/chat-sessions/{session_id}/query", response_model=QueryResponse)
async def query_with_chat_context(
    session_id: str,
    request: QueryRequest,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Query RAG with chat session context"""
    try:
        user_id = current_user["id"]

        # Verify user owns the session
        sessions = await get_user_chat_sessions(user_id)
        session_exists = any(s['id'] == session_id for s in sessions)

        if not session_exists:
            raise HTTPException(status_code=404, detail="Chat session not found or access denied")

        # Get recent chat history for context
        chat_history = await get_chat_messages(session_id, limit=5)

        # Get user's collection name
        collection_name = f"user_{user_id}_docs"

        # Call your async answer_question function with chat context
        answer_text = await answer_question(
            request.question,  # noqa: W291
            n_results=5,
            collection_name=collection_name,
            user_id=user_id,
            chat_history=chat_history
        )

        # Add the Q&A to chat history
        await add_chat_message(
            session_id=session_id,
            content=f"Q: {request.question}\nA: {answer_text}",
            retrieval_query=request.question
        )

        return {"answer": answer_text}

    except Exception as e:
        logger.exception(f"Error during query with chat context: {e}")
        raise HTTPException(status_code=500, detail="Failed to query")

# ============================================
# STATISTICS ENDPOINTS (PROTECTED)
# ============================================

@app.get("/stats")
async def get_user_stats(current_user: dict[str, Any] = Depends(get_current_user)):
    """Get current user statistics"""
    try:
        user_id = current_user["id"]
        user_documents = await get_user_documents(user_id)
        user_sessions = await get_user_chat_sessions(user_id)

        return {
            "user_id": user_id,
            "total_documents": len(user_documents),
            "total_chat_sessions": len(user_sessions),
            "documents_by_status": {
                "completed": len([doc for doc in user_documents if doc.get('embedding_status') == 'completed']),
                "processing": len([doc for doc in user_documents if doc.get('embedding_status') == 'processing']),
                "failed": len([doc for doc in user_documents if doc.get('embedding_status') == 'failed']),
                "pending": len([doc for doc in user_documents if doc.get('embedding_status') == 'pending'])
            }
        }
    except Exception as e:
        logger.exception(f"Error getting user stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user stats")

@app.get("/admin/stats")
async def get_admin_stats(current_user: dict[str, Any] = Depends(get_current_user)):
    """Get system statistics (admin endpoint)"""
    try:
        # You might want to add role-based access control here
        total_users = len(await get_all_users())
        total_documents = len(await get_all_documents())

        return {
            "total_users": total_users,
            "total_documents": total_documents,
            "status": "operational"
        }
    except Exception as e:
        logger.exception(f"Error getting admin stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get admin stats")  # noqa: B904

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
