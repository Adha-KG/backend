# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.routes import admin, auth, chat, documents, query, stats, users

app = FastAPI(
    title="RAG API",
    description="RAG API with JWT Authentication and Supabase Integration",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(documents.router)
app.include_router(query.router, prefix="/query")
app.include_router(chat.router)
app.include_router(stats.router)


@app.get("/health")
async def health_check():
    """Health check endpoint (public)"""
    return {"status": "healthy", "message": "RAG API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
