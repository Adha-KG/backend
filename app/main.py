import os
import uuid

from chromadb import logger
from fastapi import FastAPI, File, HTTPException, UploadFile

from app.schemas import QueryRequest, QueryResponse, UploadResponse
from app.services.retriever import semantic_search
from app.tasks import process_pdf

app = FastAPI()
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    process_pdf.delay(file_path)

    return {
        "filename": file.filename,
        "stored_as": unique_filename,
        "message": "PDF uploaded and queued for processing"
    }

@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    try:
        # Use your semantic_search function
        results = semantic_search(request.question, n_results=5)

        if not results:
            return {"answer": "No relevant information found in uploaded PDFs."}

        # Format the results
        answer_parts = []
        for i, (_doc_id, doc_text, distance) in enumerate(results, 1):
            # Convert distance to similarity score (lower distance = higher similarity)
            similarity = 1 - distance if distance else 1
            answer_parts.append(f"[Result {i} - Relevance: {similarity:.2%}]\n{doc_text}")

        answer = "\n\n".join(answer_parts)

        return {"answer": answer}

    except Exception as e:
        logger.exception(f"Error during query: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query: {str(e)}")  # noqa: B904

@app.get("/uploads" , response_model=list[UploadResponse])
async def get_uploads():
    # This is a placeholder implementation
    return [{"message": "List of uploaded PDFs"}]  # noqa: W292
