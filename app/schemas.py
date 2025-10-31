# app/schemas.py
from typing import Any

from pydantic import BaseModel, EmailStr


class UserSignUp(BaseModel):
    email: EmailStr
    password: str
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    profile_image_url: str | None = None

class UserSignIn(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    profile_image_url: str | None = None

class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str

class UploadResponse(BaseModel):
    filename: str
    stored_as: str
    document_id: str | None = None
    task_id: str | None = None
    message: str

class UserUpdate(BaseModel):
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    profile_image_url: str | None = None

class ChatSessionCreate(BaseModel):
    session_name: str | None = None
    session_type: str = "general"
    document_ids: list[str] = []

class ChatMessageCreate(BaseModel):
    content: str
    tokens_used: int | None = None
    source_documents: list[dict[str, Any]] | None = None
    retrieval_query: str | None = None
