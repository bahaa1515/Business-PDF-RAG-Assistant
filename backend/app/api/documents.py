"""
Document upload and management endpoints.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.document_service import DocumentService
from app.api.auth import AuthContext, require_admin
from app.api.rate_limit import check_session_rate_limit
from app.config import (
    ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
    ADMIN_READ_RATE_LIMIT_PER_MINUTE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNKING_STRATEGY,
    DOCUMENT_UPLOAD_RATE_LIMIT_PER_HOUR,
)

router = APIRouter(prefix="/documents", tags=["documents"])


class IndexConfigurationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY


@router.post("/upload")
async def upload_documents(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    """Upload supported business documents, including partial ZIP acceptance."""
    try:
        check_session_rate_limit(
            admin,
            "document-upload",
            DOCUMENT_UPLOAD_RATE_LIMIT_PER_HOUR,
            3600,
        )
        service = DocumentService(db)
        uploaded = []
        rejected_files = []

        for file in files:
            content = await file.read()
            result = service.upload_file(file.filename, content)
            uploaded.extend(result["uploaded"])
            rejected_files.extend(result["rejected_files"])

        return {
            "status": "success",
            "uploaded": uploaded,
            "rejected_files": rejected_files,
            "total": len(uploaded),
            "total_uploaded": len(uploaded),
            "total_rejected": len(rejected_files),
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/")
async def list_documents(db: Session = Depends(get_db), admin: AuthContext = Depends(require_admin)):
    """List all documents."""
    try:
        check_session_rate_limit(
            admin,
            "documents-read",
            ADMIN_READ_RATE_LIMIT_PER_MINUTE,
            60,
        )
        service = DocumentService(db)
        documents = service.get_documents()
        return {
            "status": "success",
            "documents": documents,
            "total": len(documents)
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.get("/index-status")
async def get_index_status(db: Session = Depends(get_db), admin: AuthContext = Depends(require_admin)):
    """Return index readiness and the saved target chunking configuration."""
    try:
        check_session_rate_limit(
            admin,
            "documents-index-status",
            ADMIN_READ_RATE_LIMIT_PER_MINUTE,
            60,
        )
        return {
            "status": "success",
            "data": DocumentService(db).index_readiness(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/index-settings")
async def update_index_settings(
    request: IndexConfigurationRequest,
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    """Save target chunking settings and mark the active index stale when they change."""
    try:
        check_session_rate_limit(
            admin,
            "documents-index-settings",
            ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
            60,
        )
        result = DocumentService(db).set_index_configuration(
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            chunking_strategy=request.chunking_strategy,
        )
        return {"status": "success", "data": result}
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{document_id}/preview")
async def preview_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    """Preview document metadata and extracted text."""
    try:
        check_session_rate_limit(
            admin,
            "documents-preview",
            ADMIN_READ_RATE_LIMIT_PER_MINUTE,
            60,
        )
        return {
            "status": "success",
            "data": DocumentService(db).preview_document(document_id),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    """Delete a document."""
    try:
        check_session_rate_limit(
            admin,
            "documents-delete",
            ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
            60,
        )
        service = DocumentService(db)
        success = service.delete_document(document_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )

        return {
            "status": "success",
            "deleted_id": document_id
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/reindex")
async def reindex_documents(
    chunk_size: int = 800,
    chunk_overlap: int = 100,
    chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    """Re-index documents with specified settings."""
    try:
        check_session_rate_limit(
            admin,
            "documents-reindex",
            ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
            60,
        )
        service = DocumentService(db)
        result = service.index_documents(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunking_strategy=chunking_strategy,
        )

        return {
            "status": "success",
            "result": result
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/reset-index")
async def reset_index(db: Session = Depends(get_db), admin: AuthContext = Depends(require_admin)):
    """Reset vector store and document indexing."""
    try:
        check_session_rate_limit(
            admin,
            "documents-reset-index",
            ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
            60,
        )
        service = DocumentService(db)
        success = service.reset_index()

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to reset index"
            )

        return {
            "status": "success",
            "message": "Vector store reset successfully"
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
