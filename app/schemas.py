from pydantic import BaseModel


class UploadResponse(BaseModel):
    message: str

class QueryRequest(BaseModel):
    question: str
    

class QueryResponse(BaseModel):
    answer: str
