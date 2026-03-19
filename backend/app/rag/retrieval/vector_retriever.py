"""
Retrieval module for similarity search and ranking
Implements vector similarity search for RAG
"""

import logging
from typing import List, Dict, Optional, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class VectorRetriever:
    """
    In-memory vector similarity retriever
    For production, integrate with Pinecone, Supabase, or Weaviate
    """

    def __init__(self):
        self.documents: Dict[str, Dict] = {}  # Stores chunks with embeddings
        self.index: Optional[np.ndarray] = None  # For batch similarity

    def add_documents(self, documents: List[Dict], page_identifier: str) -> None:
        """
        Add documents to the retriever
        
        Args:
            documents: List of chunks with 'chunk_id', 'text', 'embedding'
            page_identifier: Unique identifier for the page
        """
        for doc in documents:
            doc_id = f"{page_identifier}#{doc.get('chunk_id', str(len(self.documents)))}"
            self.documents[doc_id] = {
                "id": doc_id,
                "text": doc.get("text", ""),
                "embedding": np.array(doc.get("embedding", [])),
                "metadata": doc.get("metadata", {}),
                "page_identifier": page_identifier
            }
        logger.info(f"Added {len(documents)} documents for {page_identifier}")

    def retrieve(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        similarity_threshold: float = 0.3
    ) -> List[Dict]:
        """
        Retrieve top-k similar documents
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of relevant documents with scores
        """
        if not self.documents or query_embedding.size == 0:
            logger.warning("No documents or empty query embedding")
            return []

        results = []

        for doc_id, doc in self.documents.items():
            if doc["embedding"].size == 0:
                continue

            # Compute cosine similarity
            similarity = cosine_similarity(
                query_embedding.reshape(1, -1),
                doc["embedding"].reshape(1, -1)
            )[0][0]

            if similarity >= similarity_threshold:
                results.append({
                    "id": doc_id,
                    "text": doc["text"],
                    "score": float(similarity),
                    "metadata": doc["metadata"],
                    "page_identifier": doc["page_identifier"]
                })

        # Sort by similarity score
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:top_k]

    def retrieve_by_page(
        self,
        query_embedding: np.ndarray,
        page_identifier: str,
        top_k: int = 5
    ) -> List[Dict]:
        """Retrieve documents from specific page only"""
        page_docs = {
            doc_id: doc
            for doc_id, doc in self.documents.items()
            if doc["page_identifier"] == page_identifier
        }

        if not page_docs:
            return []

        results = []
        for doc_id, doc in page_docs.items():
            if doc["embedding"].size == 0:
                continue

            similarity = cosine_similarity(
                query_embedding.reshape(1, -1),
                doc["embedding"].reshape(1, -1)
            )[0][0]

            results.append({
                "id": doc_id,
                "text": doc["text"],
                "score": float(similarity),
                "metadata": doc["metadata"]
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def clear_page(self, page_identifier: str) -> None:
        """Clear documents for a specific page"""
        to_delete = [
            doc_id for doc_id, doc in self.documents.items()
            if doc["page_identifier"] == page_identifier
        ]
        for doc_id in to_delete:
            del self.documents[doc_id]
        logger.info(f"Cleared {len(to_delete)} documents for {page_identifier}")

    def clear_all(self) -> None:
        """Clear all documents"""
        self.documents.clear()
        self.index = None
        logger.info("Cleared all retriever documents")

    def get_stats(self) -> Dict:
        """Get retriever statistics"""
        page_identifiers = set(
            doc["page_identifier"] for doc in self.documents.values()
        )
        return {
            "total_documents": len(self.documents),
            "unique_pages": len(page_identifiers),
            "pages": list(page_identifiers)
        }


class RankedRetriever:
    """
    Ranks and filters retrieval results
    Handles post-processing and re-ranking
    """

    def __init__(self, retriever: VectorRetriever):
        self.retriever = retriever

    def rank_results(
        self,
        results: List[Dict],
        query: str,
        ranking_mode: str = "similarity"
    ) -> List[Dict]:
        """
        Re-rank results using various strategies
        
        Args:
            results: Initial retrieval results
            query: Original query for keyword matching
            ranking_mode: Strategy for re-ranking
            
        Returns:
            Re-ranked results
        """
        if ranking_mode == "similarity":
            return results  # Already sorted by similarity

        elif ranking_mode == "keyword_boost":
            # Boost score if query keywords appear in text
            query_words = set(query.lower().split())
            for result in results:
                text_words = set(result["text"].lower().split())
                overlap = len(query_words & text_words)
                result["score"] += (overlap * 0.05)
            results.sort(key=lambda x: x["score"], reverse=True)
            return results

        elif ranking_mode == "diversity":
            # Promote diversity: avoid similar documents
            ranked = []
            threshold = 0.9
            
            for result in results:
                is_diverse = all(
                    cosine_similarity(
                        np.array(result.get("embedding", [])).reshape(1, -1),
                        np.array(r.get("embedding", [])).reshape(1, -1)
                    )[0][0] < threshold
                    for r in ranked
                    if r.get("embedding")
                )
                
                if is_diverse:
                    ranked.append(result)
            
            return ranked

        else:
            return results

    def deduplicate(self, results: List[Dict], similarity_threshold: float = 0.95) -> List[Dict]:
        """Remove near-duplicate results"""
        if not results:
            return []

        unique = [results[0]]

        for result in results[1:]:
            is_duplicate = False
            for unique_result in unique:
                # Simple text similarity check
                if self._texts_similar(result["text"], unique_result["text"], similarity_threshold):
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique.append(result)

        return unique

    @staticmethod
    def _texts_similar(text1: str, text2: str, threshold: float) -> bool:
        """Check if two texts are similar"""
        # Simple overlap-based similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return False

        overlap = len(words1 & words2)
        similarity = overlap / max(len(words1), len(words2))
        
        return similarity >= threshold
