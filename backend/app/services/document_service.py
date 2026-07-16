"""Document upload, preview, indexing, and metadata management."""
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNKING_STRATEGY,
    SUPPORTED_CHUNKING_STRATEGIES,
)
from app.db.models import Document, IndexConfiguration
from app.rag.chunker import TextChunker
from app.rag.embeddings import EmbeddingsGenerator
from app.rag.loader import DocumentLoaderRegistry
from app.rag.vector_store import QdrantVectorStore
from app.utils.files import (
    RejectedUpload,
    delete_upload_file,
    expand_upload,
    save_upload_file,
)
from app.utils.security import redact_sensitive_text


class DocumentService:
    """Service for document operations."""

    def __init__(self, db: Session):
        self.db = db
        self.loader = DocumentLoaderRegistry()
        self.chunker = TextChunker()
        self.embeddings = EmbeddingsGenerator()
        self.vector_store = QdrantVectorStore()

    def upload_file(self, filename: str, file_content: bytes) -> Dict[str, Any]:
        """Process one direct file upload, including ZIP partial acceptance."""
        accepted, rejected = expand_upload(filename, file_content)
        uploaded = []
        rejected_files = list(rejected)
        for item in accepted:
            try:
                uploaded.append(self.upload_document(item.filename, item.content))
            except Exception as exc:
                rejected_files.append(RejectedUpload(item.filename, redact_sensitive_text(exc)))
        return {
            "uploaded": uploaded,
            "rejected_files": [self._serialize_rejection(item) for item in rejected_files],
            "total_uploaded": len(uploaded),
            "total_rejected": len(rejected_files),
        }

    def upload_document(self, filename: str, file_content: bytes) -> Dict[str, Any]:
        """Upload and store one non-archive document."""
        file_path = None
        try:
            file_path, stored_filename = save_upload_file(file_content, filename)
            document_data = self.loader.load_document(file_path, filename)
            doc = Document(
                filename=stored_filename,
                original_filename=filename,
                file_path=file_path,
                document_type=document_data["document_type"],
                page_count=document_data["total_pages"],
                content_unit_count=document_data["total_units"],
                chunk_count=0,
                status="uploaded",
                chunking_strategy=DEFAULT_CHUNKING_STRATEGY,
            )
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)
            return self._serialize_document(doc)
        except Exception as exc:
            self.db.rollback()
            if file_path:
                delete_upload_file(file_path)
            raise Exception(f"Failed to upload document: {str(exc)}") from exc

    def get_documents(self) -> List[Dict[str, Any]]:
        docs = self.db.query(Document).all()
        return [self._serialize_document(doc) for doc in docs]

    def get_index_configuration(self) -> Dict[str, Any]:
        config = self._get_or_create_index_configuration()
        return self._serialize_index_configuration(config)

    def set_index_configuration(
        self,
        chunk_size: int,
        chunk_overlap: int,
        chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
    ) -> Dict[str, Any]:
        self._validate_index_configuration(chunk_size, chunk_overlap, chunking_strategy)
        config = self._get_or_create_index_configuration()
        changed = (
            config.chunk_size != chunk_size
            or config.chunk_overlap != chunk_overlap
            or config.chunking_strategy != chunking_strategy
        )
        config.chunk_size = chunk_size
        config.chunk_overlap = chunk_overlap
        config.chunking_strategy = chunking_strategy
        stale_documents = self._mark_indexed_documents_needing_reindex() if changed else 0
        self.db.commit()
        return {
            "configuration": self._serialize_index_configuration(config),
            "changed": changed,
            "reindex_required": stale_documents > 0,
            "stale_documents": stale_documents,
        }

    def delete_document(self, document_id: int) -> bool:
        try:
            doc = self.db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                raise Exception("Document not found")
            delete_upload_file(self._resolve_file_path(doc.file_path))
            self.vector_store.delete_document_vectors(document_id)
            self.db.delete(doc)
            self.db.commit()
            return True
        except Exception as exc:
            self.db.rollback()
            print(f"Error deleting document: {redact_sensitive_text(exc)}")
            return False

    def preview_document(self, document_id: int, chunk_limit: int = 5) -> Dict[str, Any]:
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError("Document not found")
        document_data = self.loader.load_document(
            self._resolve_file_path(doc.file_path),
            doc.original_filename or doc.filename,
        )
        chunks = self.chunker.chunk_units(
            document_data["units"],
            document_data["document_type"],
            chunk_size=doc.chunk_size or 800,
            chunk_overlap=doc.chunk_overlap or 100,
            chunking_strategy=doc.chunking_strategy or DEFAULT_CHUNKING_STRATEGY,
        )
        first_text = next(
            (unit["text"].strip() for unit in document_data["units"] if unit["text"].strip()),
            "",
        )
        return {
            "id": doc.id,
            "filename": doc.original_filename or doc.filename,
            "document_type": doc.document_type or document_data["document_type"],
            "page_count": doc.page_count,
            "content_unit_count": doc.content_unit_count or document_data["total_units"],
            "chunk_count": doc.chunk_count,
            "status": doc.status,
            "first_text_preview": first_text[:1000],
            "chunk_previews": [
                {
                    "page": chunk.get("page_num"),
                    "locator": chunk.get("locator"),
                    "locator_label": chunk.get("locator_label"),
                    "chunk_id": chunk["chunk_id"],
                    "preview": chunk["preview"],
                }
                for chunk in chunks[:chunk_limit]
            ],
        }

    def index_documents(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
        reset: bool = True,
    ) -> Dict[str, Any]:
        try:
            self._validate_index_configuration(chunk_size, chunk_overlap, chunking_strategy)
            config = self._get_or_create_index_configuration()
            config.chunk_size = chunk_size
            config.chunk_overlap = chunk_overlap
            config.chunking_strategy = chunking_strategy
            if reset:
                self.vector_store.reset_collection()
            else:
                self.vector_store.create_collection()
            docs = self.db.query(Document).all()
            total_chunks = 0
            indexed_docs = 0
            for doc in docs:
                try:
                    document_data = self.loader.load_document(
                        self._resolve_file_path(doc.file_path),
                        doc.original_filename or doc.filename,
                    )
                    chunks = self.chunker.chunk_units(
                        document_data["units"],
                        document_data["document_type"],
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                        chunking_strategy=chunking_strategy,
                    )
                    if not chunks:
                        continue
                    texts = [chunk["text"] for chunk in chunks]
                    embeddings = self.embeddings.embed_texts(texts)
                    metadatas = [
                        {
                            "document_id": doc.id,
                            "filename": doc.original_filename or doc.filename,
                            "source_type": document_data["document_type"],
                            "document_type": document_data["document_type"],
                            "content_unit_count": document_data["total_units"],
                            "page": chunk.get("page_num"),
                            "locator": chunk.get("locator"),
                            "locator_label": chunk.get("locator_label"),
                            "section_title": chunk.get("section_title"),
                            "sheet_name": chunk.get("sheet_name"),
                            "chunk_id": chunk["chunk_id"],
                            "text": chunk["text"],
                            "preview": chunk["preview"],
                        }
                        for chunk in chunks
                    ]
                    self.vector_store.upsert_vectors(embeddings, metadatas)
                    doc.document_type = document_data["document_type"]
                    doc.page_count = document_data["total_pages"]
                    doc.content_unit_count = document_data["total_units"]
                    doc.chunk_count = len(chunks)
                    doc.status = "indexed"
                    doc.chunk_size = chunk_size
                    doc.chunk_overlap = chunk_overlap
                    doc.chunking_strategy = chunking_strategy
                    total_chunks += len(chunks)
                    indexed_docs += 1
                except Exception as exc:
                    print(f"Error indexing document {doc.id}: {redact_sensitive_text(exc)}")
                    doc.status = "failed"
            self.db.commit()
            return {
                "indexed_documents": indexed_docs,
                "total_chunks": total_chunks,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "chunking_strategy": chunking_strategy,
            }
        except Exception as exc:
            self.db.rollback()
            raise Exception(f"Indexing failed: {str(exc)}") from exc

    def ensure_index_configuration(
        self,
        chunk_size: int,
        chunk_overlap: int,
        chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
    ) -> Dict[str, Any]:
        self._validate_index_configuration(chunk_size, chunk_overlap, chunking_strategy)
        docs = self.db.query(Document).all()
        config = self._get_or_create_index_configuration()
        config_mismatch = (
            config.chunk_size != chunk_size
            or config.chunk_overlap != chunk_overlap
            or config.chunking_strategy != chunking_strategy
        )
        needs_reindex = any(
            doc.status != "indexed"
            or doc.chunk_size != chunk_size
            or doc.chunk_overlap != chunk_overlap
            or (doc.chunking_strategy or DEFAULT_CHUNKING_STRATEGY) != chunking_strategy
            for doc in docs
        ) or config_mismatch
        if needs_reindex:
            result = self.index_documents(chunk_size, chunk_overlap, chunking_strategy, reset=True)
            result["reindexed"] = True
            return result
        return {
            "indexed_documents": len(docs),
            "total_chunks": sum(doc.chunk_count or 0 for doc in docs),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "chunking_strategy": chunking_strategy,
            "reindexed": False,
        }

    def get_active_configuration(self) -> Dict[str, Any] | None:
        doc = (
            self.db.query(Document)
            .filter(Document.status == "indexed")
            .order_by(Document.id.asc())
            .first()
        )
        if not doc:
            return None
        return {
            "chunk_size": doc.chunk_size or 800,
            "chunk_overlap": doc.chunk_overlap or 100,
            "chunking_strategy": doc.chunking_strategy or DEFAULT_CHUNKING_STRATEGY,
        }

    def index_readiness(self) -> Dict[str, Any]:
        docs = self.db.query(Document).all()
        config = self._get_or_create_index_configuration()
        total = len(docs)
        stale = sum(1 for doc in docs if doc.status == "needs_reindex")
        indexed = sum(1 for doc in docs if doc.status == "indexed")
        failed = sum(1 for doc in docs if doc.status == "failed")
        uploaded = sum(1 for doc in docs if doc.status == "uploaded")
        mismatched = sum(
            1
            for doc in docs
            if doc.status == "indexed"
            and (
                doc.chunk_size != config.chunk_size
                or doc.chunk_overlap != config.chunk_overlap
                or (doc.chunking_strategy or DEFAULT_CHUNKING_STRATEGY) != config.chunking_strategy
            )
        )
        ready = stale == 0 and failed == 0 and uploaded == 0 and mismatched == 0
        return {
            "ready": ready,
            "total_documents": total,
            "indexed_documents": indexed,
            "stale_documents": stale,
            "configuration_mismatched_documents": mismatched,
            "failed_documents": failed,
            "uploaded_documents": uploaded,
            "configuration": self._serialize_index_configuration(config),
            "message": (
                "Documents are indexed."
                if ready
                else "Documents must be re-indexed before chat or evaluation can use the current embedding and chunking configuration."
            ),
        }

    @staticmethod
    def _validate_index_configuration(
        chunk_size: int,
        chunk_overlap: int,
        chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if chunking_strategy not in SUPPORTED_CHUNKING_STRATEGIES:
            raise ValueError(
                "chunking_strategy must be one of: "
                f"{', '.join(sorted(SUPPORTED_CHUNKING_STRATEGIES))}"
            )

    def _get_or_create_index_configuration(self) -> IndexConfiguration:
        config = self.db.query(IndexConfiguration).filter(IndexConfiguration.id == 1).first()
        if config:
            return config
        active = (
            self.db.query(Document)
            .filter(Document.status == "indexed")
            .order_by(Document.id.asc())
            .first()
        )
        config = IndexConfiguration(
            id=1,
            chunk_size=(active.chunk_size if active and active.chunk_size else DEFAULT_CHUNK_SIZE),
            chunk_overlap=(
                active.chunk_overlap
                if active and active.chunk_overlap is not None
                else DEFAULT_CHUNK_OVERLAP
            ),
            chunking_strategy=(
                active.chunking_strategy
                if active and active.chunking_strategy
                else DEFAULT_CHUNKING_STRATEGY
            ),
        )
        self.db.add(config)
        self.db.flush()
        return config

    def _mark_indexed_documents_needing_reindex(self) -> int:
        documents = self.db.query(Document).filter(Document.status == "indexed").all()
        for document in documents:
            document.status = "needs_reindex"
        return len(documents)

    def reset_index(self) -> bool:
        try:
            self.vector_store.reset_collection()
            docs = self.db.query(Document).all()
            for doc in docs:
                doc.status = "uploaded"
                doc.chunk_count = 0
            self.db.commit()
            return True
        except Exception as exc:
            self.db.rollback()
            print(f"Error resetting index: {redact_sensitive_text(exc)}")
            return False

    @staticmethod
    def _serialize_document(doc: Document) -> Dict[str, Any]:
        return {
            "id": doc.id,
            "filename": doc.original_filename or doc.filename,
            "original_filename": doc.original_filename or doc.filename,
            "stored_filename": doc.filename,
            "document_type": doc.document_type or "pdf",
            "page_count": doc.page_count,
            "content_unit_count": doc.content_unit_count or doc.page_count or 0,
            "chunk_count": doc.chunk_count,
            "status": doc.status,
            "upload_time": doc.upload_time.isoformat() if doc.upload_time else None,
            "chunk_size": doc.chunk_size,
            "chunk_overlap": doc.chunk_overlap,
            "chunking_strategy": doc.chunking_strategy or DEFAULT_CHUNKING_STRATEGY,
        }

    @staticmethod
    def _resolve_file_path(file_path: str) -> str:
        """Resolve stored upload paths across Docker and host-local runs."""
        raw_path = str(file_path or "")
        path = Path(raw_path)
        if path.exists():
            return str(path)
        normalized_path = raw_path.replace("\\", "/")
        if normalized_path.startswith(("/app/uploads/", "app/uploads/")):
            host_path = Path(__file__).resolve().parents[2] / "uploads" / Path(normalized_path).name
            if host_path.exists():
                return str(host_path)
        return raw_path

    @staticmethod
    def _serialize_index_configuration(config: IndexConfiguration) -> Dict[str, Any]:
        return {
            "chunk_size": config.chunk_size,
            "chunk_overlap": config.chunk_overlap,
            "chunking_strategy": config.chunking_strategy or DEFAULT_CHUNKING_STRATEGY,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }

    @staticmethod
    def _serialize_rejection(rejection: RejectedUpload) -> Dict[str, str]:
        return {"filename": rejection.filename, "reason": rejection.reason}
