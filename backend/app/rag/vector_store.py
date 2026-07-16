"""
Qdrant vector store setup and management.
"""
import math
import re
import json
from collections import Counter
from typing import List, Dict, Any
from urllib.error import URLError
from urllib.request import urlopen
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from app.config import QDRANT_URL, QDRANT_COLLECTION_NAME


class QdrantVectorStore:
    """Manage vector storage in Qdrant."""

    def __init__(self):
        """Initialize Qdrant client."""
        self.client = QdrantClient(url=QDRANT_URL)
        self.collection_name = QDRANT_COLLECTION_NAME
        # Dimension for text-embedding-3-small is 1536
        self.vector_size = 1536

    def collection_exists(self) -> bool:
        """Check if collection exists."""
        collections = self.client.get_collections()
        return any(c.name == self.collection_name for c in collections.collections)

    def create_collection(self, vector_size: int | None = None):
        """Create vector collection in Qdrant."""
        size = vector_size or self.vector_size
        if not self.collection_exists():
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=size,
                    distance=Distance.COSINE
                )
            )

    def collection_vector_size(self) -> int | None:
        """Return the configured dense-vector size for the active collection."""
        if not self.collection_exists():
            return None
        try:
            with urlopen(
                f"{QDRANT_URL.rstrip('/')}/collections/{self.collection_name}",
                timeout=10,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError):
            return self.vector_size

        vectors_config = (
            payload.get("result", {})
            .get("config", {})
            .get("params", {})
            .get("vectors")
        )
        if isinstance(vectors_config, dict) and "size" in vectors_config:
            return vectors_config["size"]
        if isinstance(vectors_config, dict):
            first_config = next(iter(vectors_config.values()), {})
            if isinstance(first_config, dict):
                return first_config.get("size")
        return None

    def ensure_collection_for_vectors(self, vector_size: int) -> None:
        """Ensure Qdrant collection matches the actual embedding dimension."""
        current_size = self.collection_vector_size()
        if current_size == vector_size:
            return
        if current_size is not None:
            self.client.delete_collection(collection_name=self.collection_name)
        self.create_collection(vector_size=vector_size)

    def upsert_vectors(
        self,
        vectors: List[List[float]],
        metadatas: List[Dict[str, Any]]
    ) -> List[int]:
        """
        Upsert vectors with metadata to Qdrant.
        
        Args:
            vectors: List of embedding vectors
            metadatas: List of metadata dicts with:
                - document_id
                - filename
                - page
                - chunk_id
                - text
                - preview
                
        Returns:
            List of point IDs
        """
        if not vectors:
            return []
        self.ensure_collection_for_vectors(len(vectors[0]))

        points = []
        for idx, (vector, metadata) in enumerate(zip(vectors, metadatas)):
            point_id = hash(f"{metadata['document_id']}_{metadata['chunk_id']}") % (2**31)
            point_id = abs(point_id)  # Ensure positive
            
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=metadata
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        return [p.id for p in points]

    def search(
        self,
        vector: List[float],
        top_k: int = 5,
        with_vectors: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Returns:
        [
            {
                'id': int,
                'score': float,
                'document_id': int,
                'filename': str,
                'page': int,
                'chunk_id': int,
                'text': str,
                'preview': str
            }
        ]
        """
        if not self.collection_exists():
            return []
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=top_k,
            with_vectors=with_vectors,
        )

        return [
            {
                'id': result.id,
                'score': result.score,
                '_vector': result.vector if with_vectors else None,
                **result.payload
            }
            for result in results
        ]

    def keyword_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Run a lightweight BM25-style keyword search over Qdrant payload text."""
        if not self.collection_exists():
            return []
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=1000,
            with_payload=True,
            with_vectors=False,
        )
        query_terms = re.findall(r"[a-z0-9]+", query.lower())
        documents = [re.findall(r"[a-z0-9]+", point.payload.get("text", "").lower()) for point in points]
        document_frequencies = Counter(
            term for terms in documents for term in set(terms)
        )
        total = max(len(documents), 1)
        scored = []
        for point, terms in zip(points, documents):
            counts = Counter(terms)
            score = sum(
                counts[term] * math.log(1 + total / (1 + document_frequencies[term]))
                for term in query_terms
            )
            if score > 0:
                scored.append({"id": point.id, "score": score, **point.payload})
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:top_k]

    def delete_document_vectors(self, document_id: int) -> None:
        """Delete every vector associated with a document."""
        if not self.collection_exists():
            return
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )

    def reset_collection(self, vector_size: int | None = None):
        """Delete and recreate collection."""
        if self.collection_exists():
            self.client.delete_collection(collection_name=self.collection_name)
        self.create_collection(vector_size=vector_size)

    def check_connection(self) -> bool:
        """Check if Qdrant is reachable."""
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            print(f"Qdrant connection failed: {e}")
            return False
