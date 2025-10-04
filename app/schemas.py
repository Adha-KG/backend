from pydantic import BaseModel


class UploadResponse(BaseModel):
    filename: str
    stored_as: str
    message: str

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
