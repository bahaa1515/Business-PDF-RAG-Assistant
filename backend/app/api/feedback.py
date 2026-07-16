"""Feedback and admin failed-question analytics endpoints."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import AuthContext, get_current_context, require_admin
from app.api.rate_limit import check_session_rate_limit
from app.config import (
    ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
    ADMIN_READ_RATE_LIMIT_PER_MINUTE,
    FEEDBACK_RATE_LIMIT_PER_MINUTE,
)
from app.db.database import get_db
from app.services.feedback_service import FeedbackService


router = APIRouter(tags=["feedback"])


class FeedbackRequest(BaseModel):
    chat_log_id: int
    rating: Literal["up", "down"]
    comment: Optional[str] = None


@router.post("/feedback")
async def create_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_current_context),
):
    check_session_rate_limit(
        context,
        "feedback",
        FEEDBACK_RATE_LIMIT_PER_MINUTE,
        60,
    )
    try:
        data = FeedbackService(db).create_feedback(
            request.chat_log_id,
            context.session_id,
            request.rating,
            request.comment,
            allow_any_session=context.role == "admin",
        )
        return {"status": "success", "data": data}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/analytics/failed-questions")
async def failed_question_analytics(
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    check_session_rate_limit(
        admin,
        "analytics-failed-questions",
        ADMIN_READ_RATE_LIMIT_PER_MINUTE,
        60,
    )
    return {"status": "success", "data": FeedbackService(db).failed_question_analytics(limit)}


@router.delete("/analytics/failed-questions")
async def clear_failed_question_analytics(
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    check_session_rate_limit(
        admin,
        "analytics-failed-questions-clear",
        ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
        60,
    )
    return {
        "status": "success",
        "data": FeedbackService(db).clear_failed_question_analytics(),
    }
