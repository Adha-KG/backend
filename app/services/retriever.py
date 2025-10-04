# app/services/retriever.py
import logging
from typing import Any  # noqa: UP035

from app.services.vectorstore import get_collection

logger = logging.getLogger(__name__)

def semantic_search(query: str, n_results: int = 5) -> list[dict[str, Any]]:
    """
    Perform semantic search using LangChain's Chroma wrapper
    
    Args:
        query: Search query string
        n_results: Number of results to return
        
    Returns:
        List of dictionaries containing search results with content, metadata, and score
    """  # noqa: W293
    try:
        # Get the collection
        collection = get_collection()

        # Perform search with scores
        results = collection.similarity_search_with_score(query, k=n_results)

        # Format results
        formatted_results = []
        for doc, score in results:
            formatted_results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score)
            })

        logger.info(f"Found {len(formatted_results)} results for query: '{query[:50]}...'")
        return formatted_results

    except Exception as e:
        logger.exception(f"Semantic search failed: {e}")
        raise RuntimeError(f"Semantic search failed: {e}") from e
