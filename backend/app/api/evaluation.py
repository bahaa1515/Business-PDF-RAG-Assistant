"""Admin-only endpoint for evaluating one RAG configuration."""
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.auth import AuthContext, require_admin
from app.api.rate_limit import check_session_rate_limit
from app.config import (
    ADMIN_READ_RATE_LIMIT_PER_MINUTE,
    DEFAULT_BENCHMARK_SPLIT,
    DEFAULT_CHUNKING_STRATEGY,
    DEFAULT_PROMPT_VARIANT,
    DEFAULT_RETRIEVAL_PROFILE,
    EVALUATION_RATE_LIMIT_PER_HOUR,
)
from app.db.database import get_db
from app.services.evaluation_service import EvaluationService


router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/latest")
async def latest_evaluation(
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    """Return the latest saved evaluation run for admin review."""
    check_session_rate_limit(
        admin,
        "evaluation-latest",
        ADMIN_READ_RATE_LIMIT_PER_MINUTE,
        60,
    )
    result = EvaluationService(db).latest_evaluation()
    return {"status": "success", "data": result}


@router.post("/{run_id}/semantic-judge")
async def judge_saved_evaluation(
    run_id: int,
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    """Use the configured LLM to semantically judge saved generated answers."""
    check_session_rate_limit(
        admin,
        "evaluation-semantic-judge",
        EVALUATION_RATE_LIMIT_PER_HOUR,
        3600,
    )
    try:
        result = EvaluationService(db).judge_semantic_correctness(run_id)
        return {"status": "success", "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/run")
async def run_evaluation(
    csv_file: UploadFile = File(...),
    chunk_size: int = Form(800),
    chunk_overlap: int = Form(100),
    top_k: int = Form(5),
    retrieval_method: str = Form("similarity"),
    reranker: str = Form("none"),
    chunking_strategy: str = Form(DEFAULT_CHUNKING_STRATEGY),
    prompt_variant: str = Form(DEFAULT_PROMPT_VARIANT),
    semantic_judge: bool = Form(False),
    retrieval_profile: str = Form(DEFAULT_RETRIEVAL_PROFILE),
    answer_verification: bool = Form(False),
    benchmark_split: str = Form(DEFAULT_BENCHMARK_SPLIT),
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    """Run one selected configuration against a required labeled CSV."""
    if not (csv_file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Evaluation requires a CSV file.")
    check_session_rate_limit(
        admin,
        "evaluation-run",
        EVALUATION_RATE_LIMIT_PER_HOUR,
        3600,
    )

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
            temp_file.write(await csv_file.read())
            temp_path = temp_file.name

        service = EvaluationService(db)
        questions = service.load_evaluation_questions(temp_path)
        result = service.run_evaluation(
            questions=questions,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            top_k=top_k,
            retrieval_method=retrieval_method,
            reranker=reranker,
            chunking_strategy=chunking_strategy,
            prompt_variant=prompt_variant,
            semantic_judge=semantic_judge,
            retrieval_profile=retrieval_profile,
            answer_verification=answer_verification,
            benchmark_split=benchmark_split,
        )
        return {"status": "success", "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
