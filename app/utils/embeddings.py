from sentence_transformers import SentenceTransformer
from typing import List, Union
import numpy as np

from app.config import settings


class EmbeddingService:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.embedding_model
        self.model = SentenceTransformer(self.model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
    
    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector as list of floats
        """
        embedding = self.model.encode(text, show_progress_bar=False)
        return embedding.tolist()
    
    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = None,
        show_progress: bool = False
    ) -> List[List[float]]:
        """
        Embed a batch of texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            show_progress: Show progress bar
        
        Returns:
            List of embedding vectors
        """
        batch_size = batch_size or settings.embedding_batch_size
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress
        )
        return [emb.tolist() for emb in embeddings]
    
    def compute_similarity(
        self,
        embedding1: Union[List[float], np.ndarray],
        embedding2: Union[List[float], np.ndarray]
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        """
        if isinstance(embedding1, list):
            embedding1 = np.array(embedding1)
        if isinstance(embedding2, list):
            embedding2 = np.array(embedding2)
        
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        return float(dot_product / (norm1 * norm2))


# Global embedding service instance
embedding_service = EmbeddingService()
