# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.routes import admin, auth, chat, documents, flashcards, notes, query, quizzes, stats, users

app = FastAPI(
    title="Unified RAG & Notes API",
    description="RAG API with JWT Authentication, Document Q&A, and AI-Powered Note Generation",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include RAG routers
app.include_router(auth.router)
app.include_router(users.router, prefix="/users")
app.include_router(admin.router)
app.include_router(documents.router)
app.include_router(query.router, prefix="/query")
app.include_router(chat.router)
app.include_router(stats.router)
app.include_router(flashcards.router, prefix="/flashcards")
app.include_router(quizzes.router, prefix="/quizzes")

# Include Notes router
app.include_router(notes.router, prefix="/notes", tags=["notes"])


@app.get("/health")
async def health_check():
    """Health check endpoint (public)"""
    return {"status": "healthy", "message": "RAG API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
