import asyncio

# import google.generativeai as genai
from chromadb import logger
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# from app.config import GEMINI_API_KEY

# Configure once, globally
# genai.configure(api_key="AIzaSyByvm5RtRNB7zMSQ1ID9OFiO0vtvzI_gEo")

# async def get_embedding(text: str) -> list[float]:

#     try:
#         # Get the current event loop
#         loop = asyncio.get_running_loop()

#         # Define the sync function to run in executor
#         def generate_embedding():
#             response = genai.embed_content(
#                 model="gemini-embedding-001",
#                 content=text
#             )
#             return response["embedding"]

#         # Run the sync API call in a thread pool executor
#         embedding = await loop.run_in_executor(None, generate_embedding)

#         # Validate the embedding
#         if not embedding or not isinstance(embedding, list):
#             raise ValueError(f"Invalid embedding received: {type(embedding)}")

#         logger.debug(f"Generated embedding of length {len(embedding)} for text: {text[:50]}...")
#         return embedding

#     except Exception:
#         logger.exception(f"Failed to generate embedding for text: {text[:50]}...")
#         raise


# def get_embedding_sync(text: str) -> list[float]:
#     """Generate embedding synchronously - better for Celery workers"""
#     try:
#         response = genai.embed_content(
#             model="models/embedding-001",
#             content=text
#         )
#         print("Using Gemini Embeddings")

#         # Handle both possible response formats
#         if hasattr(response, 'embedding'):
#             return list(response.embedding)
#         elif isinstance(response, dict) and 'embedding' in response:
#             return response['embedding']
#         else:
#             raise ValueError(f"Unexpected response format: {type(response)}")

#     except Exception as e:
#         logger.exception(f"Failed to generate embedding: {e}")
#         raise


embedding_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001",
                                               google_api_key="AIzaSyByvm5RtRNB7zMSQ1ID9OFiO0vtvzI_gEo")

async def get_embedding(text: str) -> list[float]:
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
    try:
        embedding_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001" , google_api_key="AIzaSyByvm5RtRNB7zMSQ1ID9OFiO0vtvzI_gEo")  # re-init inside
        embedding = embedding_model.embed_query(text)
        if not embedding or not isinstance(embedding, list):
            raise ValueError(f"Invalid embedding received: {type(embedding)}")
        return embedding
    except Exception as e:
        logger.exception(f"Failed to generate embedding: {e}")
        raise
