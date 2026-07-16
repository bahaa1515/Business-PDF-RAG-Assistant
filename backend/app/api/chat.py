"""
Chat endpoints.
"""
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.chat_service import ChatService
from app.api.auth import AuthContext, get_current_context, require_admin
from app.api.rate_limit import check_session_rate_limit, rate_limiter
from app.config import (
    ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
    ADMIN_READ_RATE_LIMIT_PER_MINUTE,
    CHAT_RATE_LIMIT_PER_MINUTE,
    DEFAULT_RETRIEVAL_METHOD,
    DEFAULT_RERANKER,
    DEFAULT_RETRIEVAL_PROFILE,
    DEFAULT_TOP_K,
    MAX_TOP_K,
    SUPPORTED_RERANKERS,
    SUPPORTED_RETRIEVAL_PROFILES,
    SUPPORTED_RETRIEVAL_METHODS,
    SUPPORTED_PROMPT_VARIANTS,
)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Chat request payload."""
    question: str
    top_k: int = 5
    retrieval_method: str = "similarity"
    reranker: str = "none"
    prompt_variant: str | None = None
    retrieval_profile: str = DEFAULT_RETRIEVAL_PROFILE
    answer_verification: bool = False
    show_debug: bool = False


@router.post("/")
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_current_context),
):
    """Process a chat question."""
    try:
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="Question is required.")
        top_k = request.top_k
        retrieval_method = request.retrieval_method
        show_debug = request.show_debug

        rate_limiter.check(
            f"chat:{context.session_id}",
            CHAT_RATE_LIMIT_PER_MINUTE,
            60,
        )
        reranker = request.reranker
        prompt_variant = request.prompt_variant
        retrieval_profile = request.retrieval_profile
        answer_verification = request.answer_verification
        if context.role == "user":
            top_k = DEFAULT_TOP_K
            retrieval_method = DEFAULT_RETRIEVAL_METHOD
            reranker = DEFAULT_RERANKER
            prompt_variant = None
            retrieval_profile = DEFAULT_RETRIEVAL_PROFILE
            answer_verification = False
            show_debug = False
        else:
            if top_k <= 0 or top_k > MAX_TOP_K:
                raise HTTPException(status_code=400, detail=f"top_k must be between 1 and {MAX_TOP_K}.")
            if retrieval_method not in SUPPORTED_RETRIEVAL_METHODS:
                raise HTTPException(status_code=400, detail="Unsupported retrieval method.")
            if reranker not in SUPPORTED_RERANKERS:
                raise HTTPException(status_code=400, detail="Unsupported reranker.")
            if prompt_variant and prompt_variant not in SUPPORTED_PROMPT_VARIANTS:
                raise HTTPException(status_code=400, detail="Unsupported prompt variant.")
            if retrieval_profile not in SUPPORTED_RETRIEVAL_PROFILES:
                raise HTTPException(status_code=400, detail="Unsupported retrieval profile.")

        service = ChatService(db)
        result = service.process_chat(
            question=request.question,
            session_id=context.session_id,
            top_k=top_k,
            retrieval_method=retrieval_method,
            reranker=reranker,
            prompt_variant=prompt_variant,
            retrieval_profile=retrieval_profile,
            answer_verification=answer_verification,
            show_debug=show_debug
        )

        return {
            "status": "success",
            "data": result
        }

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "index_not_ready",
                "message": str(exc),
            },
        )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "rag_request_failed",
                "message": "The answer service is temporarily unavailable. Please try again.",
            },
        )


@router.get("/history")
async def get_chat_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_current_context),
):
    """Get chat history."""
    try:
        check_session_rate_limit(
            context,
            "chat-history-admin" if context.role == "admin" else "chat-history-user",
            ADMIN_READ_RATE_LIMIT_PER_MINUTE if context.role == "admin" else CHAT_RATE_LIMIT_PER_MINUTE,
            60,
        )
        service = ChatService(db)
        history = service.get_chat_history(
            session_id=context.session_id,
            limit=limit,
            include_all=context.role == "admin",
        )

        return {
            "status": "success",
            "history": history,
            "total": len(history)
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.delete("/history")
async def clear_chat_history(
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    """Clear chat history."""
    try:
        check_session_rate_limit(
            admin,
            "chat-history-clear",
            ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
            60,
        )
        service = ChatService(db)
        success = service.clear_chat_history()

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to clear chat history"
            )

        return {
            "status": "success",
            "message": "Chat history cleared"
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
