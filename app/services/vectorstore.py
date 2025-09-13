# vectorstore.py
from chromadb.config import Settings
from langchain_chroma import Chroma

from app.services.embeddings import get_embedding_sync
from app.services.embeddings import embedding_model

# def get_collection(name: str = "pdf_chunks") -> Chroma:
#     """
#     Get or create a Chroma collection wrapped as a LangChain VectorStore.
#     """
#     client = chromadb.PersistentClient(
#         path="./chroma_db",
#         settings=Settings(anonymized_telemetry=False)
#     )

#     return Chroma(
#         client=client,
#         collection_name=name,
#         embedding_function=get_embedding_sync,  # 👈 direct functional embedding
#     )

def get_collection(name="pdf_chunks"):
    # Initialize client inside the function, not at module level
    return Chroma(
        collection_name=name,
        persist_directory="./chroma_db",
        embedding_function=embedding_model,
        client_settings=Settings(anonymized_telemetry=False)
    )
