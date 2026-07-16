"""Store answer feedback and expose failed-question analytics."""
import json
from typing import Any, Dict

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import ChatLog, EvaluationResult, Feedback


class FeedbackService:
    def __init__(self, db: Session):
        self.db = db

    def create_feedback(
        self,
        chat_log_id: int,
        session_id: str,
        rating: str,
        comment: str | None = None,
        allow_any_session: bool = False,
    ) -> Dict[str, Any]:
        if rating not in {"up", "down"}:
            raise ValueError("rating must be up or down")
        query = self.db.query(ChatLog).filter(ChatLog.id == chat_log_id)
        if not allow_any_session:
            query = query.filter(ChatLog.session_id == session_id)
        chat = query.first()
        if not chat:
            raise ValueError("Chat answer not found")
        feedback = Feedback(
            session_id=session_id,
            chat_log_id=chat.id,
            rating=rating,
            comment=(comment or "").strip() or None,
            question=chat.question,
            answer=chat.answer,
            sources_json=chat.sources_json or "[]",
        )
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)
        return self._serialize_feedback(feedback)

    def failed_question_analytics(self, limit: int = 100) -> Dict[str, Any]:
        low_faithfulness = (
            self.db.query(EvaluationResult)
            .filter(EvaluationResult.faithfulness.isnot(None), EvaluationResult.faithfulness < 0.5)
            .limit(limit)
            .all()
        )
        no_chunks_evaluation = (
            self.db.query(EvaluationResult)
            .filter(EvaluationResult.no_chunks_retrieved.is_(True))
            .limit(limit)
            .all()
        )
        no_chunks_chat = (
            self.db.query(ChatLog)
            .filter(ChatLog.no_chunks_retrieved.is_(True))
            .order_by(ChatLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        unanswerable_not_refused = (
            self.db.query(EvaluationResult)
            .filter(
                EvaluationResult.question_type == "unanswerable",
                EvaluationResult.correctly_refused.is_(False),
            )
            .limit(limit)
            .all()
        )
        answerable_source_miss = (
            self.db.query(EvaluationResult)
            .filter(
                EvaluationResult.question_type == "answerable",
                EvaluationResult.source_hit.is_(False),
            )
            .limit(limit)
            .all()
        )
        bad_feedback = (
            self.db.query(Feedback)
            .filter(Feedback.rating == "down")
            .order_by(Feedback.timestamp.desc())
            .limit(limit)
            .all()
        )
        return {
            "low_faithfulness": [self._serialize_evaluation(item) for item in low_faithfulness],
            "bad_feedback": [self._serialize_feedback(item) for item in bad_feedback],
            "no_chunks": [
                *[self._serialize_evaluation(item) for item in no_chunks_evaluation],
                *[self._serialize_chat(item) for item in no_chunks_chat],
            ][:limit],
            "unanswerable_not_refused": [
                self._serialize_evaluation(item) for item in unanswerable_not_refused
            ],
            "answerable_source_miss": [
                self._serialize_evaluation(item) for item in answerable_source_miss
            ],
        }

    def clear_failed_question_analytics(self) -> Dict[str, int]:
        """Delete records that feed the failed-question dashboard."""
        failed_evaluation_filter = or_(
            EvaluationResult.faithfulness < 0.5,
            EvaluationResult.no_chunks_retrieved.is_(True),
            (
                (EvaluationResult.question_type == "unanswerable")
                & (EvaluationResult.correctly_refused.is_(False))
            ),
            (
                (EvaluationResult.question_type == "answerable")
                & (EvaluationResult.source_hit.is_(False))
            ),
        )
        failed_evaluation_count = (
            self.db.query(EvaluationResult)
            .filter(failed_evaluation_filter)
            .delete(synchronize_session=False)
        )
        bad_feedback_count = (
            self.db.query(Feedback)
            .filter(Feedback.rating == "down")
            .delete(synchronize_session=False)
        )
        no_chunk_chat_ids = select(ChatLog.id).where(
            ChatLog.no_chunks_retrieved.is_(True)
        )
        feedback_unlinked_count = (
            self.db.query(Feedback)
            .filter(Feedback.chat_log_id.in_(no_chunk_chat_ids))
            .update({Feedback.chat_log_id: None}, synchronize_session=False)
        )
        no_chunk_chat_count = (
            self.db.query(ChatLog)
            .filter(ChatLog.no_chunks_retrieved.is_(True))
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return {
            "failed_evaluation_results_deleted": failed_evaluation_count,
            "no_chunk_chat_logs_deleted": no_chunk_chat_count,
            "bad_feedback_deleted": bad_feedback_count,
            "feedback_unlinked": feedback_unlinked_count,
            "total_deleted": failed_evaluation_count + no_chunk_chat_count + bad_feedback_count,
        }

    @staticmethod
    def _serialize_feedback(item: Feedback) -> Dict[str, Any]:
        return {
            "id": item.id,
            "chat_log_id": item.chat_log_id,
            "timestamp": item.timestamp.isoformat() if item.timestamp else None,
            "rating": item.rating,
            "comment": item.comment,
            "question": item.question,
            "answer": item.answer,
            "sources": json.loads(item.sources_json or "[]"),
        }

    @staticmethod
    def _serialize_evaluation(item: EvaluationResult) -> Dict[str, Any]:
        return {
            "id": item.id,
            "run_id": item.run_id,
            "question": item.question,
            "answer": item.answer,
            "question_type": item.question_type,
            "faithfulness": item.faithfulness,
            "source_hit": item.source_hit,
            "correctly_refused": item.correctly_refused,
            "no_chunks_retrieved": item.no_chunks_retrieved,
        }

    @staticmethod
    def _serialize_chat(item: ChatLog) -> Dict[str, Any]:
        return {
            "id": f"chat-{item.id}",
            "run_id": None,
            "question": item.question,
            "answer": item.answer,
            "question_type": "chat",
            "faithfulness": None,
            "source_hit": None,
            "correctly_refused": None,
            "no_chunks_retrieved": item.no_chunks_retrieved,
        }
