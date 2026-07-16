"""Admin-only background optimization endpoints."""
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.auth import AuthContext, require_admin
from app.api.rate_limit import check_session_rate_limit, rate_limiter
from app.config import (
    ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
    ADMIN_READ_RATE_LIMIT_PER_MINUTE,
    OPTIMIZATION_RATE_LIMIT_PER_HOUR,
)
from app.db.database import get_db
from app.services.evaluation_service import EvaluationService
from app.services.optimization_jobs import optimization_jobs


router = APIRouter(prefix="/optimization", tags=["optimization"])


def parse_int_list(value: str) -> list[int]:
    try:
        return [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise ValueError("Hyperparameter number lists must contain integers only.") from exc


def parse_str_list(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


@router.post("/run")
async def run_optimization(
    csv_file: UploadFile = File(...),
    chunk_sizes: str = Form("400,800,1200"),
    chunk_overlaps: str = Form("50,150"),
    top_k_values: str = Form("3,5"),
    retrieval_methods: str = Form("similarity,hybrid"),
    rerankers: str = Form("none"),
    chunking_strategies: str = Form("auto,structure"),
    prompt_variants: str = Form("grounded_complete"),
    semantic_judge: str = Form("false"),
    search_mode: str = Form("grid"),
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    if not (csv_file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Optimization requires a CSV file.")
    rate_limiter.check(
        f"optimization:{admin.session_id}",
        OPTIMIZATION_RATE_LIMIT_PER_HOUR,
        3600,
    )
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
            temp_file.write(await csv_file.read())
            temp_path = temp_file.name
        service = EvaluationService(db)
        questions = service.load_evaluation_questions(temp_path)
        search_mode = (search_mode or "grid").strip().lower()
        payload = {
            "questions": questions,
            "chunk_sizes": parse_int_list(chunk_sizes),
            "chunk_overlaps": parse_int_list(chunk_overlaps),
            "top_k_values": parse_int_list(top_k_values),
            "retrieval_methods": parse_str_list(retrieval_methods),
            "rerankers": parse_str_list(rerankers),
            "chunking_strategies": parse_str_list(chunking_strategies),
            "prompt_variants": parse_str_list(prompt_variants),
            "semantic_judge": parse_bool(semantic_judge),
            "search_mode": search_mode,
        }
        if search_mode == "smart":
            configurations = service._smart_search_space()
        elif search_mode == "grid":
            configurations = service._validate_search_space(
                payload["chunk_sizes"],
                payload["chunk_overlaps"],
                payload["top_k_values"],
                payload["retrieval_methods"],
                payload["rerankers"],
                payload["chunking_strategies"],
                payload["prompt_variants"],
            )
        else:
            raise ValueError("search_mode must be grid or smart")
        job = optimization_jobs.start(payload, len(configurations))
        answerable_questions = sum(
            1 for question in questions if question.get("question_type") != "unanswerable"
        )
        estimated_judge_calls = len(configurations) * answerable_questions if payload["semantic_judge"] else 0
        return {
            "status": "accepted",
            "job_id": job["job_id"],
            "total_configurations": len(configurations),
            "estimated_rag_calls": len(configurations) * len(questions),
            "estimated_semantic_judge_calls": estimated_judge_calls,
            "semantic_judge": payload["semantic_judge"],
            "search_mode": search_mode,
            "warning": "Optimization may use many configured AI provider API calls.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@router.get("/jobs/{job_id}")
async def get_optimization_job(
    job_id: str,
    admin: AuthContext = Depends(require_admin),
):
    check_session_rate_limit(
        admin,
        "optimization-job-read",
        ADMIN_READ_RATE_LIMIT_PER_MINUTE,
        60,
    )
    try:
        return {"status": "success", "data": optimization_jobs.get(job_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/jobs/{job_id}/cancel")
async def cancel_optimization_job(
    job_id: str,
    admin: AuthContext = Depends(require_admin),
):
    check_session_rate_limit(
        admin,
        "optimization-job-cancel",
        ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
        60,
    )
    try:
        return {"status": "success", "data": optimization_jobs.cancel(job_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/runs/{run_id}/apply-best")
async def apply_best_configuration(
    run_id: int,
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    check_session_rate_limit(
        admin,
        "optimization-apply-best",
        ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
        60,
    )
    try:
        return {
            "status": "success",
            "data": EvaluationService(db).apply_best_configuration(run_id),
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
