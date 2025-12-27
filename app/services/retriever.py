# app/services/retriever.py
import logging
from typing import Any  # noqa: UP035

from app.services.vectorstore import get_collection

logger = logging.getLogger(__name__)

def semantic_search(query: str, 
                    n_results: int = 5, 
                    collection_name: str = "pdf_chunks",
                    where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """
    Perform semantic search using LangChain's Chroma wrapper
    
    Args:
        query: Search query string
        n_results: Number of results to return
        collection_name: Name of the collection to search
        where: Optional filter dictionary for ChromaDB where clause (e.g., {"document_id": {"$in": [...]}})
        
    Returns:
        List of dictionaries containing search results with content, metadata, and score
    """
    try:
        # Get a fresh collection instance to avoid stale cache
        collection = get_collection(collection_name)

        # Perform search with scores, applying filter if provided
        if where:
            results = collection.similarity_search_with_score(query, k=n_results, filter=where)
        else:
            results = collection.similarity_search_with_score(query, k=n_results)

        # Format results
        formatted_results = []
        for doc, score in results:
            formatted_results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score)
            })

        logger.info(f"Found {len(formatted_results)} results for query in collection '{collection_name}': '{query[:50]}...'")
        return formatted_results

    except Exception as e:
        logger.exception(f"Semantic search failed in collection '{collection_name}': {e}")
        # Return empty list instead of raising to prevent query failures
        logger.warning(f"Returning empty results due to search error")
        return []
