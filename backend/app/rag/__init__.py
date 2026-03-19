"""
Main RAG orchestration module
Coordinates chunking, embedding, retrieval, and LLM generation
"""

import logging
from typing import List, Dict, Optional, Tuple
import json
from datetime import datetime

from app.rag.chunking.text_chunker import TextChunker
from app.rag.embeddings.embedding_pipeline import EmbeddingPipeline
from app.rag.retrieval.vector_retriever import VectorRetriever, RankedRetriever

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Complete RAG pipeline: Chunk -> Embed -> Retrieve -> Generate
    """

    def __init__(
        self,
        embedding_model_type: str = "huggingface",
        chunk_size: int = 512,
        chunk_overlap: int = 128,
        retrieval_top_k: int = 5,
        use_cache: bool = True
    ):
        self.text_chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            strategy="semantic"
        )
        
        self.embedding_pipeline = EmbeddingPipeline(
            model_type=embedding_model_type,
            use_cache=use_cache
        )
        
        self.retriever = VectorRetriever()
        self.ranked_retriever = RankedRetriever(self.retriever)
        self.retrieval_top_k = retrieval_top_k
        
        logger.info("RAG Pipeline initialized")

    def process_page(self, page_content: str, page_url: str) -> Dict:
        """
        Process a page: chunk, embed, and store
        
        Args:
            page_content: Full page text
            page_url: Page URL identifier
            
        Returns:
            Processing result metadata
        """
        logger.info(f"Processing page: {page_url}")

        # Step 1: Chunk the content
        chunks = self.text_chunker.chunk_text(page_content, page_url)
        logger.info(f"Created {len(chunks)} chunks")

        if not chunks:
            return {
                "success": False,
                "error": "No chunks created from content",
                "page_url": page_url
            }

        # Step 2: Convert chunks to dict format
        chunk_dicts = [
            {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "start_idx": chunk.start_idx,
                "end_idx": chunk.end_idx,
                "metadata": {
                    "page_url": page_url,
                    "created_at": datetime.utcnow().isoformat()
                }
            }
            for chunk in chunks
        ]

        # Step 3: Generate embeddings
        logger.info("Generating embeddings...")
        embedded_chunks = self.embedding_pipeline.embed_chunks(chunk_dicts)

        # Step 4: Store in retriever
        self.retriever.add_documents(embedded_chunks, page_url)

        return {
            "success": True,
            "page_url": page_url,
            "chunks_created": len(chunks),
            "embedding_dimension": self.embedding_pipeline.get_dimension(),
            "processing_timestamp": datetime.utcnow().isoformat()
        }

    def retrieve_context(
        self,
        query: str,
        page_url: Optional[str] = None,
        top_k: Optional[int] = None
    ) -> List[Dict]:
        """
        Retrieve relevant chunks for a query
        
        Args:
            query: User query
            page_url: Optional specific page to search
            top_k: Number of results (uses default if not specified)
            
        Returns:
            List of relevant chunks
        """
        if not query.strip():
            return []

        top_k = top_k or self.retrieval_top_k

        # Embed query
        query_embedding = self.embedding_pipeline.embed_query(query)

        if query_embedding.size == 0:
            logger.warning("Failed to embed query")
            return []

        # Retrieve documents
        if page_url:
            results = self.retriever.retrieve_by_page(query_embedding, page_url, top_k)
        else:
            results = self.retriever.retrieve(query_embedding, top_k)

        # Rank and deduplicate
        results = self.ranked_retriever.deduplicate(results)
        results = self.ranked_retriever.rank_results(results, query, "similarity")

        logger.info(f"Retrieved {len(results)} relevant chunks for query")
        return results

    def build_context_prompt(self, retrieved_chunks: List[Dict]) -> str:
        """
        Build context string from retrieved chunks for LLM
        
        Args:
            retrieved_chunks: Retrieved relevant chunks
            
        Returns:
            Formatted context string
        """
        if not retrieved_chunks:
            return "No relevant context found."

        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            confidence = chunk.get("score", 0)
            context_parts.append(
                f"[Source {i} - Confidence: {confidence:.2f}]\n{chunk['text']}\n"
            )

        return "\n---\n".join(context_parts)

    def get_stats(self) -> Dict:
        """Get pipeline statistics"""
        stats = self.retriever.get_stats()
        stats["embedding_model"] = "huggingface-minilm"
        stats["embedding_dimension"] = self.embedding_pipeline.get_dimension()
        return stats

    def clear_page(self, page_url: str) -> None:
        """Clear stored embeddings for a page"""
        self.retriever.clear_page(page_url)
        logger.info(f"Cleared embeddings for {page_url}")

    def clear_all(self) -> None:
        """Clear all embeddings"""
        self.retriever.clear_all()
        logger.info("Cleared all embeddings")
