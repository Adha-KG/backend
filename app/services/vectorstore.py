# vectorstore.py
import chromadb
from chromadb.config import Settings
from langchain_community.vectorstores import Chroma

from app.services.embeddings import embedding_model

# Global client instance
_chroma_client = None

def get_chroma_client():
    """Get or create a singleton ChromaDB client"""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(anonymized_telemetry=False)
        )
    return _chroma_client

def get_collection(name="pdf_chunks"):
    """Get a Chroma collection with proper client management"""
    client = get_chroma_client()
    
    return Chroma(
        client=client,
        collection_name=name,
        embedding_function=embedding_model,
    )

def reset_collection(name="pdf_chunks"):
    """Reset/clear a collection - useful after deletions"""
    try:
        client = get_chroma_client()
        # Try to delete and recreate the collection
        try:
            client.delete_collection(name)
        except Exception:
            pass  # Collection might not exist
        # Recreate it
        client.get_or_create_collection(name)
    except Exception as e:
        print(f"Error resetting collection {name}: {e}")
        # If reset fails, recreate the client
        global _chroma_client
        _chroma_client = None
