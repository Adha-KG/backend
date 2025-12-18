import tiktoken
import nltk
from typing import List, Dict, Any

from app.config import settings

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)


class TextChunker:
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        encoding_name: str = "cl100k_base"
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.encoding = tiktoken.get_encoding(encoding_name)
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encoding.encode(text))
    
    def split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using NLTK"""
        return nltk.sent_tokenize(text)
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Chunk text into overlapping segments with sentence awareness.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk
        
        Returns:
            List of chunk dictionaries with text, token_count, and metadata
        """
        sentences = self.split_into_sentences(text)
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            
            # If a single sentence exceeds chunk_size, split it by words
            if sentence_tokens > self.chunk_size:
                # If we have accumulated sentences, save them first
                if current_chunk:
                    chunk_text = " ".join(current_chunk)
                    chunks.append({
                        'text': chunk_text,
                        'token_count': self.count_tokens(chunk_text),
                        'metadata': metadata or {}
                    })
                    current_chunk = []
                    current_tokens = 0
                
                # Split long sentence by words
                words = sentence.split()
                word_chunk = []
                word_tokens = 0
                
                for word in words:
                    word_token_count = self.count_tokens(word + " ")
                    if word_tokens + word_token_count > self.chunk_size and word_chunk:
                        chunk_text = " ".join(word_chunk)
                        chunks.append({
                            'text': chunk_text,
                            'token_count': self.count_tokens(chunk_text),
                            'metadata': metadata or {}
                        })
                        # Keep overlap
                        overlap_words = []
                        overlap_tokens = 0
                        for w in reversed(word_chunk):
                            w_tokens = self.count_tokens(w + " ")
                            if overlap_tokens + w_tokens <= self.chunk_overlap:
                                overlap_words.insert(0, w)
                                overlap_tokens += w_tokens
                            else:
                                break
                        word_chunk = overlap_words
                        word_tokens = overlap_tokens
                    
                    word_chunk.append(word)
                    word_tokens += word_token_count
                
                if word_chunk:
                    chunk_text = " ".join(word_chunk)
                    current_chunk = [chunk_text]
                    current_tokens = self.count_tokens(chunk_text)
            
            # Normal sentence processing
            elif current_tokens + sentence_tokens > self.chunk_size:
                # Save current chunk
                if current_chunk:
                    chunk_text = " ".join(current_chunk)
                    chunks.append({
                        'text': chunk_text,
                        'token_count': self.count_tokens(chunk_text),
                        'metadata': metadata or {}
                    })
                    
                    # Keep overlap
                    overlap_sentences = []
                    overlap_tokens = 0
                    for sent in reversed(current_chunk):
                        sent_tokens = self.count_tokens(sent)
                        if overlap_tokens + sent_tokens <= self.chunk_overlap:
                            overlap_sentences.insert(0, sent)
                            overlap_tokens += sent_tokens
                        else:
                            break
                    
                    current_chunk = overlap_sentences
                    current_tokens = overlap_tokens
                
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
        
        # Add the last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'token_count': self.count_tokens(chunk_text),
                'metadata': metadata or {}
            })
        
        return chunks
    
    def chunk_with_page_info(
        self,
        pages_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Chunk text while preserving page information.
        
        Args:
            pages_data: List of dicts with 'page_number' and 'text'
        
        Returns:
            List of chunks with page range metadata
        """
        all_chunks = []
        
        for page_data in pages_data:
            page_num = page_data['page_number']
            text = page_data['text']
            
            page_chunks = self.chunk_text(
                text,
                metadata={'page_start': page_num, 'page_end': page_num}
            )
            all_chunks.extend(page_chunks)
        
        return all_chunks


# Utility function for simple chunking
def chunk_text_simple(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None
) -> List[Dict[str, Any]]:
    """
    Simple function to chunk text.
    """
    chunker = TextChunker(chunk_size, chunk_overlap)
    return chunker.chunk_text(text)
