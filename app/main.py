import os
import uuid

from chromadb import logger
from fastapi import FastAPI, File, HTTPException, UploadFile

from app.schemas import QueryRequest, QueryResponse, UploadResponse
from app.services.rag import answer_question
from app.services.vectorstore import get_collection
from app.tasks import process_pdf
from app.auth import sign_up ,  sign_in
app = FastAPI()
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)




@app.post("/upload-multiple", response_model=list[UploadResponse])
async def upload_multiple_pdfs(files: list[UploadFile] = File(...)):
    """Upload multiple PDF files at once"""
    uploaded_files = []

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

        # Queue for processing with metadata
        task = process_pdf.delay(file_path, file.filename, unique_filename)

        uploaded_files.append({
            "filename": file.filename,
            "stored_as": unique_filename,
            "task_id": task.id,
            "message": "PDF uploaded and queued for processing"
        })

    return uploaded_files
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

# @app.post("/query", response_model=QueryResponse)
# async def query_rag(request: QueryRequest):
#     try:
#         # Use your semantic_search function
#         # results = semantic_search(request.question, n_results=5)
#         results = []

#         # if not results:
#         #     return {"answer": "No relevant information found in uploaded PDFs."}

#         # Format the results
#         answer_parts = []
#         for i, (_doc_id, doc_text, distance) in enumerate(results, 1):
#             # Convert distance to similarity score (lower distance = higher similarity)
#             similarity = 1 - distance if distance else 1
#             answer_parts.append(f"[Result {i} - Relevance: {similarity:.2%}]\n{doc_text}")

#         answer = "\n\n".join(answer_parts)

#         return {"answer": answer}

#     except Exception as e:
#         logger.exception(f"Error during query: {e}")
#         raise HTTPException(status_code=500, detail=f"Failed to query: {str(e)}")  # noqa: B904


@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    try:
        # Call your async answer_question function
        answer_text = await answer_question(request.question, n_results=5)

        return {"answer": answer_text}

    except Exception as e:
        logger.exception(f"Error during query: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query: {str(e)}")  # noqa: B904

@app.get("/uploads" , response_model=list[UploadResponse])
async def get_uploads():
    # This is a placeholder implementation
    return [{"message": "List of uploaded PDFs"}]  # noqa: W292


@app.delete("/delete-pdf/{filename}")
async def delete_pdf(filename: str):
    """Delete a PDF file and all its embeddings from ChromaDB"""
    try:
        collection = get_collection()

        # Find the actual file in the upload directory
        file_to_delete = None
        full_path = None

        for file in os.listdir(UPLOAD_DIR):
            if file == filename or file.endswith(filename):
                file_to_delete = file
                full_path = os.path.join(UPLOAD_DIR, file)
                break

        if not file_to_delete:
            raise HTTPException(status_code=404, detail=f"PDF file {filename} not found")

        # Build where clause without $contains
        where_clause = {
            "$or": [
                {"source": full_path},  # Exact match
                {"source": os.path.join(UPLOAD_DIR, filename)},  # Try with full path
                {"original_filename": filename},
                {"unique_filename": filename},
                {"unique_filename": file_to_delete}  # The actual file name found
            ]
        }

        # Get all document IDs that match
        results = collection.get(
            where=where_clause,
            include=["metadatas"]
        )

        deleted_count = 0
        if results['ids']:
            # Delete all matching embeddings
            collection.delete(ids=results['ids'])
            deleted_count = len(results['ids'])
            logger.info(f"Deleted {deleted_count} embeddings for {filename}")
        else:
            logger.warning(f"No embeddings found for {filename}")

        # Delete the physical file
        if os.path.exists(full_path):
            os.remove(full_path)
            logger.info(f"Deleted file: {full_path}")

        return {
            "message": "PDF and embeddings deleted successfully",
            "filename": filename,
            "file_path": full_path,
            "embeddings_deleted": deleted_count
        }

    except Exception as e:
        logger.error(f"Error deleting PDF {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
