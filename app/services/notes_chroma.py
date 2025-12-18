"""Unified Chroma service for notes functionality"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional

from app.config import settings


class NotesChromaService:
    """ChromaDB service for notes-related vector storage"""

    def __init__(self):
        # Use the PersistentClient API (chromadb 0.4.0+)
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection_name = "pdf_chunks"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "PDF document chunks with embeddings"},
        )

    def add_chunks(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        embeddings: List[List[float]],
    ) -> None:
        """
        Add chunks to Chroma collection.

        Args:
            documents: List of text chunks
            metadatas: List of metadata dicts
            ids: List of unique IDs
            embeddings: List of embedding vectors
        """
        self.collection.add(
            documents=documents, metadatas=metadatas, ids=ids, embeddings=embeddings
        )
        # Note: PersistentClient auto-persists; no explicit persist() needed

    def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Query the collection for similar chunks.

        Args:
            query_embeddings: List of query embedding vectors
            n_results: Number of results to return
            where: Filter conditions (e.g., {"file_id": "xyz", "user_id": "123"})
            include: Fields to include in results

        Returns:
            Query results
        """
        if include is None:
            include = ["documents", "metadatas", "distances"]

        return self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
            include=include,
        )

    def get_by_ids(
        self, ids: List[str], include: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get chunks by their IDs.

        Args:
            ids: List of chunk IDs
            include: Fields to include in results

        Returns:
            Chunks data
        """
        if include is None:
            include = ["documents", "metadatas"]

        return self.collection.get(ids=ids, include=include)

    def delete_by_file_id(self, file_id: str) -> None:
        """
        Delete all chunks for a specific file.

        Args:
            file_id: File ID to delete chunks for
        """
        self.collection.delete(where={"file_id": file_id})
        # Note: PersistentClient auto-persists; no explicit persist() needed

    def count(self) -> int:
        """Get total number of chunks in collection."""
        return self.collection.count()

    def count_by_file_id(self, file_id: str) -> int:
        """
        Count chunks for a specific file ID in ChromaDB.

        Args:
            file_id: File ID to count chunks for

        Returns:
            Number of chunks for this file_id
        """
        try:
            # Get all chunks with this file_id
            result = self.collection.get(where={"file_id": file_id}, include=["documents"])
            if result and "ids" in result:
                return len(result["ids"])
            return 0
        except Exception:
            # If get fails, return 0
            return 0


# Global Chroma service instance
notes_chroma_service = NotesChromaService()
