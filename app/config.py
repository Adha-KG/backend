import os
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

# Legacy config variables for backward compatibility with existing RAG code
CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")
CHROMA_HOST = os.getenv("CHROMA_HOST")
REDIS_URL = os.getenv("REDIS_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Alias for SUPABASE_ANON_KEY for compatibility


class Settings(BaseSettings):
    """Unified configuration for RAG and Notes services"""

    # Supabase
    supabase_url: str
    supabase_key: str = ""
    supabase_anon_key: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    supabase_storage_bucket: Optional[str] = None

    # Redis/Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None

    # ChromaDB
    chroma_api_key: Optional[str] = None
    chroma_host: Optional[str] = None
    chroma_persist_dir: str = "./chroma_db"

    # LLM Configuration
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    llm_provider: str = "gemini"  # gemini, openai, or local
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_output_tokens: int = 55000
    openai_model: str = "gpt-3.5-turbo"

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    transformers_cache: Optional[str] = None

    # Application Settings
    upload_dir: str = "./uploads"
    notes_dir: str = "./notes"
    save_notes_locally: bool = False
    max_file_size: int = 52428800  # 50MB

    # Text Processing (for notes)
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # JWT configuration removed - now using Supabase Auth

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Derive celery URLs from redis_url if not explicitly set
        if not self.celery_broker_url:
            self.celery_broker_url = self.redis_url
        if not self.celery_result_backend:
            # Use a different DB for results if using redis
            if self.redis_url.startswith("redis://"):
                base = self.redis_url.rsplit("/", 1)[0]
                self.celery_result_backend = f"{base}/1"
            else:
                self.celery_result_backend = self.redis_url

        # Prefer service role key when available (bypasses RLS)
        if self.supabase_service_role_key:
            self.supabase_key = self.supabase_service_role_key
        elif self.supabase_anon_key:
            self.supabase_key = self.supabase_anon_key


# Global settings instance
settings = Settings()
