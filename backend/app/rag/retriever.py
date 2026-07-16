"""
Retriever for querying Qdrant vector store.
"""
import math
import re
from typing import List, Dict, Any
from app.rag.embeddings import EmbeddingsGenerator
from app.rag.vector_store import QdrantVectorStore


class Retriever:
    """Retrieve relevant chunks from Qdrant."""

    def __init__(self):
        self.vector_store = QdrantVectorStore()
        self.embeddings = EmbeddingsGenerator()

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        method: str = "similarity",
        reranker: str = "none",
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top_k relevant chunks for a query.
        
        Args:
            query: Question or search text
            top_k: Number of chunks to retrieve
            method: Retrieval method (similarity or mmr)
            
        Returns:
            List of retrieved chunks with scores
        """
        if method not in {"similarity", "mmr", "hybrid"}:
            raise ValueError("Unsupported retrieval method")
        if reranker not in {"none", "enabled"}:
            raise ValueError("Unsupported reranker")

        query_embedding = self.embeddings.embed_text(query)
        if method == "mmr":
            candidates = self.vector_store.search(
                query_embedding,
                max(top_k * 4, top_k),
                with_vectors=True,
            )
            results = self._maximal_marginal_relevance(query_embedding, candidates, top_k)
        elif method == "hybrid":
            semantic = self.vector_store.search(query_embedding, max(top_k * 3, top_k))
            keyword = self.vector_store.keyword_search(query, max(top_k * 3, top_k))
            results = self._reciprocal_rank_fusion(semantic, keyword, top_k)
        else:
            results = self.vector_store.search(query_embedding, top_k)

        if reranker == "enabled":
            results = self._rerank(query, results)[:top_k]

        for rank, result in enumerate(results, 1):
            result['rank'] = rank

        return results

    @staticmethod
    def _reciprocal_rank_fusion(
        semantic: List[Dict[str, Any]],
        keyword: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        fused = {}
        for result_list in (semantic, keyword):
            for rank, result in enumerate(result_list, start=1):
                key = result.get("id") or (
                    result.get("document_id"),
                    result.get("chunk_id"),
                )
                item = fused.setdefault(key, dict(result, score=0.0))
                item["score"] += 1 / (60 + rank)
        return sorted(fused.values(), key=lambda item: item["score"], reverse=True)[:top_k]

    @staticmethod
    def _rerank(query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        def score(item):
            text_tokens = set(re.findall(r"[a-z0-9]+", item.get("text", "").lower()))
            lexical = len(query_tokens & text_tokens) / len(query_tokens) if query_tokens else 0
            return lexical * 0.7 + float(item.get("score", 0)) * 0.3
        return sorted(results, key=score, reverse=True)

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        denominator = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
        if denominator == 0:
            return 0.0
        return sum(x * y for x, y in zip(a, b)) / denominator

    def _maximal_marginal_relevance(
        self,
        query_vector: List[float],
        candidates: List[Dict[str, Any]],
        top_k: int,
        diversity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Select relevant but non-redundant candidates."""
        selected = []
        remaining = [candidate for candidate in candidates if candidate.get("_vector")]

        while remaining and len(selected) < top_k:
            def mmr_score(candidate):
                relevance = self._cosine_similarity(query_vector, candidate["_vector"])
                redundancy = max(
                    (
                        self._cosine_similarity(candidate["_vector"], item["_vector"])
                        for item in selected
                    ),
                    default=0.0,
                )
                return diversity * relevance - (1 - diversity) * redundancy

            best = max(remaining, key=mmr_score)
            selected.append(best)
            remaining.remove(best)

        for candidate in selected:
            candidate.pop("_vector", None)
        return selected
