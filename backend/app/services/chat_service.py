"""
Chat service.
Handle chat messages and RAG responses.
"""
import json
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import ChatLog, Feedback
from app.rag.pipeline import RAGPipeline
from app.services.document_service import DocumentService


class ChatService:
    """Service for chat operations."""

    def __init__(self, db: Session):
        self.db = db
        self.rag = RAGPipeline()

    def process_chat(
        self,
        question: str,
        session_id: str,
        top_k: int = 5,
        retrieval_method: str = "similarity",
        reranker: str = "none",
        prompt_variant: str | None = None,
        retrieval_profile: str | None = None,
        answer_verification: bool = False,
        show_debug: bool = False
    ) -> Dict[str, Any]:
        """Process a chat question through RAG pipeline and store result."""
        try:
            readiness = DocumentService(self.db).index_readiness()
            if not readiness["ready"]:
                raise ValueError(readiness["message"])

            # Run RAG pipeline
            result = self.rag.run(
                question=question,
                top_k=top_k,
                retrieval_method=retrieval_method,
                reranker=reranker,
                prompt_variant=prompt_variant,
                retrieval_profile=retrieval_profile,
                answer_verification=answer_verification,
                show_debug=show_debug
            )

            # Store in PostgreSQL
            primary_source = (result.get("sources") or [{}])[0]
            chat_log = ChatLog(
                session_id=session_id,
                question=question,
                answer=result['answer'],
                sources_json=json.dumps(result['sources']),
                latency_seconds=result['latency_seconds'],
                top_k=result.get("settings_used", {}).get("top_k", top_k),
                retrieval_method=result.get("settings_used", {}).get("retrieval_method", retrieval_method),
                reranker=result.get("settings_used", {}).get("reranker", reranker),
                prompt_variant=result.get("settings_used", {}).get("prompt_variant"),
                retrieval_profile=result.get("settings_used", {}).get("retrieval_profile"),
                resolved_retrieval_profile=result.get("settings_used", {}).get("resolved_retrieval_profile"),
                answer_verification=result.get("settings_used", {}).get("answer_verification", False),
                no_chunks_retrieved=not bool(result.get("sources")),
                document_id=primary_source.get("document_id"),
                document_type=primary_source.get("document_type") or primary_source.get("source_type"),
                content_unit_count=primary_source.get("content_unit_count"),
            )
            self.db.add(chat_log)
            self.db.commit()

            result["chat_id"] = chat_log.id
            return result

        except Exception:
            self.db.rollback()
            raise

    def get_chat_history(
        self,
        session_id: str | None = None,
        limit: int = 50,
        include_all: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get recent chat history."""
        query = self.db.query(ChatLog)
        if not include_all:
            query = query.filter(ChatLog.session_id == session_id)
        logs = query.order_by(ChatLog.timestamp.desc()).limit(limit).all()

        return [
            {
                'id': log.id,
                'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                'question': log.question,
                'answer': log.answer,
                'sources': json.loads(log.sources_json) if log.sources_json else [],
                'latency_seconds': log.latency_seconds,
                'top_k': log.top_k,
                'retrieval_method': log.retrieval_method,
                'reranker': log.reranker,
                'prompt_variant': log.prompt_variant,
                'retrieval_profile': log.retrieval_profile,
                'resolved_retrieval_profile': log.resolved_retrieval_profile,
                'answer_verification': log.answer_verification,
            }
            for log in reversed(logs)  # Reverse to show chronologically
        ]

    def clear_chat_history(self) -> bool:
        """Clear all chat history."""
        try:
            self.db.query(Feedback).update({Feedback.chat_log_id: None})
            self.db.query(ChatLog).delete()
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            print(f"Error clearing chat history: {e}")
            return False
