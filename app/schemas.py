# app/schemas.py
from enum import Enum
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
    access_token: str | None = None  # None when email confirmation is required
    refresh_token: str | None = None
    token_type: str

class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None
    new_chat: bool = False

class QueryResponse(BaseModel):
    answer: str
    session_id: str | None = None
    session_name: str | None = None
    is_new_session: bool = False
    message_count: int = 0

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

class FlashcardGenerateRequest(BaseModel):
    topic: str | None = None
    document_ids: list[str] | None = None
    num_flashcards: int = 10

class Flashcard(BaseModel):
    front: str
    back: str

class FlashcardGenerateResponse(BaseModel):
    flashcards: list[Flashcard]
    topic: str | None = None
    num_generated: int

# Quiz-related schemas
class QuizGenerateRequest(BaseModel):
    document_ids: list[str]
    num_questions: int = 10
    time_limit_minutes: int = 30
    difficulty: str | None = None  # 'easy', 'medium', 'hard'
    title: str | None = None

class QuizQuestion(BaseModel):
    id: str | None = None
    question_text: str
    options: list[str]  # Exactly 4 options
    correct_answer: int  # Index 0-3
    explanation: str | None = None
    question_number: int | None = None

class QuizResponse(BaseModel):
    id: str
    user_id: str
    title: str | None = None
    document_ids: list[str]
    num_questions: int
    time_limit_minutes: int
    difficulty: str | None = None
    status: str  # 'generating', 'ready', 'failed'
    questions: list[QuizQuestion] | None = None
    created_at: str
    updated_at: str

class QuizListResponse(BaseModel):
    id: str
    title: str | None = None
    document_ids: list[str]
    num_questions: int
    time_limit_minutes: int
    difficulty: str | None = None
    status: str
    created_at: str
    updated_at: str

class QuizAttemptCreate(BaseModel):
    pass  # No additional fields needed, quiz_id comes from path

class QuizAnswerSubmit(BaseModel):
    question_id: str
    selected_answer: int  # Index 0-3
    time_spent_seconds: int | None = None

class QuizAnswerResponse(BaseModel):
    id: str
    question_id: str
    selected_answer: int | None = None
    is_correct: bool | None = None
    time_spent_seconds: int | None = None
    answered_at: str | None = None

class QuizAttemptResponse(BaseModel):
    id: str
    quiz_id: str
    user_id: str
    started_at: str
    completed_at: str | None = None
    time_spent_seconds: int | None = None
    status: str  # 'in_progress', 'completed', 'timeout', 'abandoned'
    score: int | None = None
    total_questions: int
    percentage_score: float | None = None
    answers: list[QuizAnswerResponse] | None = None
    created_at: str
    updated_at: str

class QuizAttemptListResponse(BaseModel):
    id: str
    quiz_id: str
    started_at: str
    completed_at: str | None = None
    status: str
    score: int | None = None
    total_questions: int
    percentage_score: float | None = None


# Notes-related schemas
class NoteStyle(str, Enum):
    short = "short"
    moderate = "moderate"
    descriptive = "descriptive"


class NoteGenerateRequest(BaseModel):
    document_ids: list[str]
    note_style: NoteStyle = NoteStyle.moderate
    user_prompt: str | None = None
    title: str | None = None


class NoteGenerateResponse(BaseModel):
    id: str
    user_id: str
    document_ids: list[str]
    title: str | None = None
    status: str
    task_id: str | None = None
    created_at: str
    updated_at: str


class NoteResponse(BaseModel):
    id: str
    user_id: str
    document_ids: list[str]
    title: str | None = None
    note_text: str | None = None  # None while still generating
    note_style: str
    metadata: dict | None = None
    status: str
    error: str | None = None  # Error message if failed
    created_at: str
    updated_at: str


class NoteListResponse(BaseModel):
    id: str
    document_ids: list[str]
    title: str | None = None
    status: str
    note_style: str
    created_at: str
    updated_at: str


class NoteQuestionRequest(BaseModel):
    question: str
    n_results: int = 5


class NoteAnswerResponse(BaseModel):
    answer: str
    sources: list[dict]
    model_info: dict
