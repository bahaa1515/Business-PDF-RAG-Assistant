"""
Health check endpoint.
"""
from fastapi import APIRouter, HTTPException
from app.db.database import check_db_connection
from app.rag.vector_store import QdrantVectorStore

router = APIRouter()


@router.get("/health")
async def health_check():
    """Check backend and service health."""
    try:
        db_ok = check_db_connection()
        vector_store = QdrantVectorStore()
        qdrant_ok = vector_store.check_connection()

        status = "healthy" if (db_ok and qdrant_ok) else "degraded"

        return {
            "status": status,
            "database": "connected" if db_ok else "disconnected",
            "vector_store": "connected" if qdrant_ok else "disconnected"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )
