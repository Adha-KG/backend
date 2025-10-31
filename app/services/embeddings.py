import asyncio
import os

# import google.generativeai as genai
from chromadb import logger
from dotenv import load_dotenv
from langchain_community.embeddings import HuggingFaceEmbeddings

# import google.generativeai as genai
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODEL_OPTIONS = {
    "fast": "sentence-transformers/all-MiniLM-L6-v2",  # 80MB, 384 dimensions
    "balanced": "BAAI/bge-small-en-v1.5",  # 133MB, 384 dimensions
    "quality": "sentence-transformers/all-mpnet-base-v2",  # 438MB, 768 dimensions
    "multilingual": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # Supports 50+ languages
}

MODEL_NAME = os.getenv("EMBEDDING_MODEL", MODEL_OPTIONS["balanced"])

# Initialize cache directory
CACHE_DIR = os.getenv("TRANSFORMERS_CACHE", "./models_cache")

# Device configuration
DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")  # "cpu" or "cuda"


print(f"Loading embedding model: {MODEL_NAME}")
embedding_model = HuggingFaceEmbeddings(
    model_name=MODEL_NAME,
    cache_folder=CACHE_DIR,
    model_kwargs={'device': DEVICE},
    encode_kwargs={
        'normalize_embeddings': True,  # For better similarity search
        'batch_size': 32  # Adjust based on your needs
    }
)

async def get_embedding(text: str) -> list[float]:
    """
    Generate embedding for a single text using local HuggingFace model (async)

    Args:
        text: Input text to embed

    Returns:
        List of floats representing the embedding
    """
    try:
        # LangChain embedding call (async wrapper)
        loop = asyncio.get_running_loop()

        def generate_embedding():
            return embedding_model.embed_query(text)

        embedding = await loop.run_in_executor(None, generate_embedding)

        if not embedding or not isinstance(embedding, list):
            raise ValueError(f"Invalid embedding received: {type(embedding)}")

        logger.debug(f"Generated embedding of length {len(embedding)} for text: {text[:50]}...")
        return embedding

    except Exception:
        logger.exception(f"Failed to generate embedding for text: {text[:50]}...")
        raise

def get_embedding_sync(text: str) -> list[float]:
    """
    Generate embedding for a single text using local HuggingFace model (sync)

    Args:
        text: Input text to embed

    Returns:
        List of floats representing the embedding
    """
    try:
        embedding = embedding_model.embed_query(text)
        print(f"Using Local HuggingFace Model: {MODEL_NAME}")

        if not embedding or not isinstance(embedding, list):
            raise ValueError(f"Invalid embedding received: {type(embedding)}")

        return embedding
    except Exception as e:
        logger.exception(f"Failed to generate embedding: {e}")
        raise

# async def get_embedding(text: str) -> list[float]:
#     try:
#         # LangChain embedding call (async wrapper)
#         loop = asyncio.get_running_loop()

#         def generate_embedding():
#             return embedding_model.embed_query(text)

#         embedding = await loop.run_in_executor(None, generate_embedding)

#         if not embedding or not isinstance(embedding, list):
#             raise ValueError(f"Invalid embedding received: {type(embedding)}")

#         logger.debug(f"Generated embedding of length {len(embedding)} for text: {text[:50]}...")
#         return embedding

#     except Exception:
#         logger.exception(f"Failed to generate embedding for text: {text[:50]}...")
#         raise

# def get_embedding_sync(text: str) -> list[float]:
#     try:
#         embedding = embedding_model.embed_query(text)
#         print("Using Gemini Embeddings" , GEMINI_API_KEY)
#         if not embedding or not isinstance(embedding, list):
#             raise ValueError(f"Invalid embedding received: {type(embedding)}")
#         return embedding
#     except Exception as e:
#         logger.exception(f"Failed to generate embedding: {e}")
#         raise
