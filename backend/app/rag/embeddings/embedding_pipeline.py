"""
Embeddings generation and management for RAG pipeline
Supports multiple embedding models and caching
"""

import os
import logging
import hashlib
from typing import List, Dict, Optional
import numpy as np
from abc import ABC, abstractmethod
import json

logger = logging.getLogger(__name__)


class EmbeddingModel(ABC):
    """Abstract base class for embedding providers"""

    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for list of texts"""
        pass

    @abstractmethod
    def embed_single(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        pass


class HuggingFaceEmbeddings(EmbeddingModel):
    """
    HuggingFace embeddings using sentence-transformers
    Default: MiniLM for speed and efficiency
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Loaded embedding model: {model_name}, dimension: {self.dimension}")
        except ImportError:
            raise ImportError("Please install sentence-transformers: pip install sentence-transformers")

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts"""
        texts = [t.strip() for t in texts if t.strip()]
        if not texts:
            return np.array([])
        return self.model.encode(texts, convert_to_numpy=True)

    def embed_single(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        return self.embed([text])[0]


class OpenAIEmbeddings(EmbeddingModel):
    """
    OpenAI embeddings via API
    Requires OPENAI_API_KEY environment variable
    """

    def __init__(self, model: str = "text-embedding-ada-002"):
        try:
            import openai
            self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model = model
            self.dimension = 1536  # Ada-002 dimension
            logger.info(f"Initialized OpenAI embeddings: {model}")
        except ImportError:
            raise ImportError("Please install openai: pip install openai")

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings via OpenAI API"""
        texts = [t.strip() for t in texts if t.strip()]
        if not texts:
            return np.array([])
        
        response = self.client.embeddings.create(
            input=texts,
            model=self.model
        )
        
        embeddings = [item.embedding for item in response.data]
        return np.array(embeddings)

    def embed_single(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        return self.embed([text])[0]


class EmbeddingCache:
    """Cache for embeddings with persistence"""

    def __init__(self, cache_dir: str = ".embedding_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text hash"""
        return hashlib.md5(text.encode()).hexdigest()

    def get(self, text: str) -> Optional[np.ndarray]:
        """Get cached embedding"""
        cache_key = self._get_cache_key(text)
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.npy")
        
        if os.path.exists(cache_path):
            try:
                return np.load(cache_path)
            except Exception as e:
                logger.warning(f"Failed to load cached embedding: {e}")
        return None

    def set(self, text: str, embedding: np.ndarray) -> None:
        """Cache embedding"""
        cache_key = self._get_cache_key(text)
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.npy")
        
        try:
            np.save(cache_path, embedding)
        except Exception as e:
            logger.warning(f"Failed to cache embedding: {e}")

    def clear(self) -> None:
        """Clear all cached embeddings"""
        import shutil
        shutil.rmtree(self.cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)


class EmbeddingPipeline:
    """
    Orchestrates embedding generation with caching and model selection
    """

    def __init__(
        self,
        model_type: str = "huggingface",
        model_name: Optional[str] = None,
        use_cache: bool = True,
        cache_dir: str = ".embedding_cache"
    ):
        if model_type == "huggingface":
            self.model = HuggingFaceEmbeddings(model_name or "all-MiniLM-L6-v2")
        elif model_type == "openai":
            self.model = OpenAIEmbeddings(model_name or "text-embedding-ada-002")
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        self.cache = EmbeddingCache(cache_dir) if use_cache else None
        logger.info(f"Embedding pipeline initialized - type: {model_type}, cached: {use_cache}")

    def embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        Embed list of chunks and add embeddings to data
        
        Args:
            chunks: List of chunk dicts with 'text' key
            
        Returns:
            Chunks with added 'embedding' field
        """
        for chunk in chunks:
            chunk_text = chunk.get("text", "")
            if not chunk_text.strip():
                chunk["embedding"] = []
                continue

            # Check cache first
            if self.cache:
                cached = self.cache.get(chunk_text)
                if cached is not None:
                    chunk["embedding"] = cached.tolist()
                    continue

            # Generate new embedding
            try:
                embedding = self.model.embed_single(chunk_text)
                
                # Cache it
                if self.cache:
                    self.cache.set(chunk_text, embedding)
                
                chunk["embedding"] = embedding.tolist()
            except Exception as e:
                logger.error(f"Failed to embed chunk: {e}")
                chunk["embedding"] = []

        return chunks

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a query string
        
        Args:
            query: Query text
            
        Returns:
            Embedding vector
        """
        if not query.strip():
            return np.array([])

        # Check cache
        if self.cache:
            cached = self.cache.get(query)
            if cached is not None:
                return cached

        # Generate embedding
        embedding = self.model.embed_single(query)

        # Cache it
        if self.cache:
            self.cache.set(query, embedding)

        return embedding

    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self.model.dimension
