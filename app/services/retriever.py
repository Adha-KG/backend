
from app.services.vectorstore import get_collection

# from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI

# def semantic_search(query: str, n_results: int = 5):
#     collection = get_collection()

#     # Generate embedding for the query
#     query_embedding = get_embedding_sync(query)

#     # Use query_embeddings instead of query_texts
#     results = collection.query(
#         query_embeddings=[query_embedding],  # Changed from query_texts
#         n_results=n_results
#     )

#     # Safer unpacking
#     documents = results.get("documents", [[]])[0]
#     ids = results.get("ids", [[]])[0]
#     distances = results.get("distances", [[]])[0]  # Optional: include distances

#     # Return with distances for relevance scoring
#     return list(zip(ids, documents, distances, strict=False))



def semantic_search(query: str, n_results: int = 5, collection_name="pdf_chunks"):
    """
    Semantic search using LangChain retriever on Chroma.
    """
    try:
        vectorstore = get_collection(collection_name)
        retriever = vectorstore.as_retriever(search_kwargs={"k": n_results})

        docs = retriever.get_relevant_documents(query)

        # Each doc is a Document with .page_content and .metadata
        return [
            {
                "text": doc.page_content,
                "metadata": doc.metadata
            }
            for doc in docs
        ]

    except Exception as e:
        raise RuntimeError(f"Semantic search failed: {e}")  # noqa: B904

