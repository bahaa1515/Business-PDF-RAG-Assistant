"""RAG evaluation, quality scoring, and safe optimization services."""
import csv
import json
from itertools import product
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import (
    DEFAULT_BENCHMARK_SPLIT,
    DEFAULT_CHUNKING_STRATEGY,
    DEFAULT_PROMPT_VARIANT,
    DEFAULT_RETRIEVAL_PROFILE,
    MAX_OPTIMIZATION_CONFIGURATIONS,
    MAX_TOP_K,
    SUPPORTED_BENCHMARK_SPLITS,
    SUPPORTED_CHUNKING_STRATEGIES,
    SUPPORTED_PROMPT_VARIANTS,
    SUPPORTED_RERANKERS,
    SUPPORTED_RETRIEVAL_PROFILES,
    SUPPORTED_RETRIEVAL_METHODS,
)
from app.db.models import (
    Document,
    EvaluationResult,
    EvaluationRun,
    OptimizationResult,
    OptimizationRun,
)
from app.rag.pipeline import RAGPipeline
from app.rag.providers import get_chat_settings, get_embedding_settings
from app.services.document_service import DocumentService
from app.services.quality_service import QualityService


REQUIRED_CSV_COLUMNS = {
    "question",
    "reference_answer",
    "expected_source",
    "expected_page",
    "question_type",
}
OFFICIAL_CSV_HEADER = "question,reference_answer,expected_source,expected_page,question_type"
UNANSWERABLE_QUESTION_TYPE = "unanswerable"


class EvaluationService:
    """Run labeled evaluations and bounded hyperparameter searches."""

    def __init__(self, db: Session):
        self.db = db
        self.rag = RAGPipeline()
        self.doc_service = DocumentService(db)
        self.quality = QualityService()

    def load_evaluation_questions(self, csv_path: str) -> List[Dict[str, Any]]:
        questions = []
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            missing = REQUIRED_CSV_COLUMNS - set(reader.fieldnames or [])
            if missing:
                received = ", ".join(reader.fieldnames or []) or "no header row"
                raise ValueError(
                    "Evaluation CSV is missing required columns: "
                    f"{', '.join(sorted(missing))}. "
                    f"Use header: {OFFICIAL_CSV_HEADER}. "
                    f"Received: {received}"
                )
            for row_number, row in enumerate(reader, start=2):
                question = (row.get("question") or "").strip()
                question_type = (row.get("question_type") or "").strip().lower()
                reference_answer = (row.get("reference_answer") or "").strip() or None
                expected_source = (row.get("expected_source") or "").strip() or None
                expected_page_raw = (row.get("expected_page") or "").strip()
                expected_locator = (row.get("expected_locator") or "").strip() or None

                if not question:
                    raise ValueError(f"Row {row_number}: question is required")
                if not question_type:
                    raise ValueError(f"Row {row_number}: question_type is required")
                expected_page = None
                if expected_page_raw and expected_page_raw.lower() != "none":
                    try:
                        expected_page = int(expected_page_raw)
                    except ValueError as exc:
                        raise ValueError(
                            f"Row {row_number}: expected_page must be an integer"
                        ) from exc
                    if expected_page <= 0:
                        raise ValueError(f"Row {row_number}: expected_page must be positive")

                answerable = question_type != UNANSWERABLE_QUESTION_TYPE
                if answerable and (
                    reference_answer is None
                    or expected_source is None
                    or expected_source.lower() == "none"
                    or (expected_page is None and expected_locator is None)
                ):
                    raise ValueError(
                        f"Row {row_number}: answerable questions require reference_answer, "
                        "expected_source, and either expected_page or expected_locator"
                    )
                if not answerable:
                    reference_is_refusal = (reference_answer or "").lower().startswith(
                        "the answer is not available"
                    )
                    source_is_empty = expected_source is None or expected_source.lower() == "none"
                    page_is_empty = expected_page is None and expected_page_raw.lower() in {"", "none"}
                    locator_is_empty = expected_locator is None or expected_locator.lower() == "none"
                    if not (
                        (reference_answer is None or reference_is_refusal)
                        and source_is_empty
                        and page_is_empty
                        and locator_is_empty
                    ):
                        raise ValueError(
                            f"Row {row_number}: unanswerable questions must leave expected fields empty "
                            "or use none plus the standard unavailable reference answer"
                        )
                    expected_source = None
                    expected_page = None
                    expected_locator = None
                questions.append(
                    {
                        "question": question,
                        "question_type": question_type,
                        "reference_answer": reference_answer,
                        "expected_source": expected_source,
                        "expected_page": expected_page,
                        "expected_locator": expected_locator,
                    }
                )
        if not questions:
            raise ValueError("Evaluation CSV must contain at least one question")
        self._validate_expected_sources(questions)
        return questions

    def run_evaluation(
        self,
        questions: List[Dict[str, Any]],
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        top_k: int = 5,
        retrieval_method: str = "similarity",
        reranker: str = "none",
        chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
        prompt_variant: str = DEFAULT_PROMPT_VARIANT,
        semantic_judge: bool = False,
        retrieval_profile: str = DEFAULT_RETRIEVAL_PROFILE,
        answer_verification: bool = False,
        benchmark_split: str = DEFAULT_BENCHMARK_SPLIT,
        ensure_index: bool = True,
    ) -> Dict[str, Any]:
        retrieval_profile = (retrieval_profile or DEFAULT_RETRIEVAL_PROFILE).strip().lower()
        benchmark_split = (benchmark_split or DEFAULT_BENCHMARK_SPLIT).strip().lower()
        self._validate_evaluation_configuration(
            chunk_size,
            chunk_overlap,
            top_k,
            retrieval_method,
            reranker,
            chunking_strategy,
            prompt_variant,
            retrieval_profile,
            benchmark_split,
        )
        if not questions:
            raise ValueError("Evaluation requires at least one question")

        index_result = None
        if ensure_index:
            index_result = self.doc_service.ensure_index_configuration(
                chunk_size, chunk_overlap, chunking_strategy
            )

        answerable_count = sum(q["question_type"] != UNANSWERABLE_QUESTION_TYPE for q in questions)
        unanswerable_count = len(questions) - answerable_count
        provider_metadata = self._provider_metadata()
        run = EvaluationRun(
            total_questions=len(questions),
            answerable_questions=answerable_count,
            unanswerable_questions=unanswerable_count,
            source_hit_rate=0,
            refusal_accuracy=0,
            answer_correctness=0,
            semantic_answer_correctness=None,
            faithfulness=0,
            context_relevance=0,
            average_latency=0,
            prompt_variant=prompt_variant,
            benchmark_split=benchmark_split,
            retrieval_profile=retrieval_profile,
            answer_verification=answer_verification,
            llm_model=provider_metadata.get("llm_model"),
            embedding_model=provider_metadata.get("embedding_model"),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            results = []
            totals = {
                "latency": 0.0,
                "source_hits": 0,
                "refusals": 0,
                "correctness": 0.0,
                "faithfulness": 0.0,
                "relevance": 0.0,
                "semantic": 0.0,
                "semantic_judged": 0,
            }
            for question_data in questions:
                rag_result = self.rag.run(
                    question=question_data["question"],
                    top_k=top_k,
                    retrieval_method=retrieval_method,
                    reranker=reranker,
                    prompt_variant=prompt_variant,
                    retrieval_profile=retrieval_profile,
                    answer_verification=answer_verification,
                    question_type=question_data["question_type"],
                    show_debug=True,
                )
                answer = rag_result["answer"]
                sources = rag_result.get("sources") or []
                chunks = rag_result.get("retrieved_chunks") or []
                settings_used = rag_result.get("settings_used") or {}
                contexts = [
                    chunk.get("full_text") or chunk.get("text") or chunk.get("preview") or ""
                    for chunk in chunks
                ]
                latency = float(rag_result.get("latency_seconds", 0))
                totals["latency"] += latency

                answerable = question_data["question_type"] != UNANSWERABLE_QUESTION_TYPE
                source_hit = None
                correctly_refused = None
                correctness_score = None
                correctness_explanation = None
                faithfulness = None
                context_relevance = None
                semantic_score = None
                semantic_verdict = None
                semantic_explanation = None
                if answerable:
                    source_hit = self._source_hit(sources, question_data)
                    totals["source_hits"] += int(source_hit)
                    correctness = self.quality.answer_correctness(
                        answer, question_data.get("reference_answer") or ""
                    )
                    correctness_score = correctness["score"]
                    correctness_explanation = correctness["explanation"]
                    faithfulness = self.quality.faithfulness(answer, contexts)
                    context_relevance = self.quality.context_relevance(
                        question_data["question"], contexts
                    )
                    totals["correctness"] += correctness_score
                    totals["faithfulness"] += faithfulness
                    totals["relevance"] += context_relevance
                    if semantic_judge:
                        judgment = self.quality.semantic_answer_correctness(
                            question=question_data["question"],
                            generated_answer=answer,
                            reference_answer=question_data.get("reference_answer") or "",
                        )
                        semantic_score = judgment["score"]
                        semantic_verdict = judgment["verdict"]
                        semantic_explanation = judgment["explanation"]
                        totals["semantic"] += semantic_score
                        totals["semantic_judged"] += 1
                else:
                    correctly_refused = "could not find" in answer.lower()
                    totals["refusals"] += int(correctly_refused)

                result = EvaluationResult(
                    run_id=run.id,
                    question=question_data["question"],
                    question_type=question_data["question_type"],
                    reference_answer=question_data.get("reference_answer"),
                    expected_source=question_data.get("expected_source"),
                    expected_page=question_data.get("expected_page"),
                    expected_locator=question_data.get("expected_locator"),
                    answer=answer,
                    retrieved_sources_json=json.dumps(sources),
                    source_hit=source_hit,
                    correctly_refused=correctly_refused,
                    answer_correctness=correctness_score,
                    correctness_explanation=correctness_explanation,
                    semantic_answer_correctness=semantic_score,
                    semantic_verdict=semantic_verdict,
                    semantic_explanation=semantic_explanation,
                    faithfulness=faithfulness,
                    context_relevance=context_relevance,
                    no_chunks_retrieved=not bool(chunks),
                    top_k=settings_used.get("top_k", top_k),
                    retrieval_method=settings_used.get("retrieval_method", retrieval_method),
                    reranker=settings_used.get("reranker", reranker),
                    chunking_strategy=chunking_strategy,
                    prompt_variant=prompt_variant,
                    retrieval_profile=settings_used.get("retrieval_profile", retrieval_profile),
                    resolved_retrieval_profile=settings_used.get("resolved_retrieval_profile"),
                    answer_verification=settings_used.get("answer_verification", answer_verification),
                    document_type=(
                        self._first_source_value(sources, "document_type")
                        or self._first_source_value(sources, "source_type")
                    ),
                    content_unit_count=self._first_source_value(sources, "content_unit_count"),
                    latency_seconds=latency,
                )
                self.db.add(result)
                results.append(result)

            run.source_hit_rate = totals["source_hits"] / answerable_count if answerable_count else 0.0
            run.refusal_accuracy = totals["refusals"] / unanswerable_count if unanswerable_count else 0.0
            run.answer_correctness = totals["correctness"] / answerable_count if answerable_count else 0.0
            run.semantic_answer_correctness = (
                totals["semantic"] / totals["semantic_judged"]
                if totals["semantic_judged"]
                else None
            )
            run.faithfulness = totals["faithfulness"] / answerable_count if answerable_count else 0.0
            run.context_relevance = totals["relevance"] / answerable_count if answerable_count else 0.0
            run.average_latency = totals["latency"] / len(questions)
            self.db.commit()
            return {
                "run_id": run.id,
                "total_questions": len(questions),
                "answerable_questions": answerable_count,
                "unanswerable_questions": unanswerable_count,
                "source_hit_rate": run.source_hit_rate,
                "refusal_accuracy": run.refusal_accuracy,
                "answer_correctness": run.answer_correctness,
                "semantic_answer_correctness": run.semantic_answer_correctness,
                "faithfulness": run.faithfulness,
                "context_relevance": run.context_relevance,
                "average_latency": run.average_latency,
                "prompt_variant": prompt_variant,
                "benchmark_split": benchmark_split,
                "retrieval_profile": retrieval_profile,
                "answer_verification": answer_verification,
                "llm_model": provider_metadata.get("llm_model"),
                "embedding_model": provider_metadata.get("embedding_model"),
                "configuration": {
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                    "top_k": top_k,
                    "retrieval_method": retrieval_method,
                    "reranker": reranker,
                    "chunking_strategy": chunking_strategy,
                    "prompt_variant": prompt_variant,
                    "retrieval_profile": retrieval_profile,
                    "answer_verification": answer_verification,
                    "benchmark_split": benchmark_split,
                },
                "index_result": index_result,
                "results": [self._serialize_evaluation_result(result) for result in results],
            }
        except Exception:
            self.db.rollback()
            raise

    def latest_evaluation(self) -> Dict[str, Any] | None:
        """Return the latest saved evaluation run with row-level results."""
        runs = (
            self.db.query(EvaluationRun)
            .order_by(EvaluationRun.timestamp.desc(), EvaluationRun.id.desc())
            .limit(20)
            .all()
        )
        for run in runs:
            results = (
                self.db.query(EvaluationResult)
                .filter(EvaluationResult.run_id == run.id)
                .order_by(EvaluationResult.id.asc())
                .all()
            )
            if len(results) == (run.total_questions or 0):
                return self._serialize_evaluation_run(run, results)
        return None

    def judge_semantic_correctness(self, run_id: Optional[int] = None) -> Dict[str, Any]:
        """Score existing generated answers with the configured LLM judge."""
        query = self.db.query(EvaluationRun)
        if run_id is not None:
            run = query.filter(EvaluationRun.id == run_id).first()
        else:
            run = query.order_by(EvaluationRun.timestamp.desc(), EvaluationRun.id.desc()).first()
        if not run:
            raise ValueError("Evaluation run not found.")

        results = (
            self.db.query(EvaluationResult)
            .filter(EvaluationResult.run_id == run.id)
            .order_by(EvaluationResult.id.asc())
            .all()
        )
        answerable = [
            result
            for result in results
            if result.question_type != UNANSWERABLE_QUESTION_TYPE
        ]
        if not answerable:
            raise ValueError("Evaluation run has no answerable rows to judge.")

        total = 0.0
        judged = 0
        for result in answerable:
            judgment = self.quality.semantic_answer_correctness(
                question=result.question,
                generated_answer=result.answer or "",
                reference_answer=result.reference_answer or "",
            )
            result.semantic_answer_correctness = judgment["score"]
            result.semantic_verdict = judgment["verdict"]
            result.semantic_explanation = judgment["explanation"]
            total += result.semantic_answer_correctness
            judged += 1

        run.semantic_answer_correctness = total / judged if judged else None
        self.db.commit()
        return self._serialize_evaluation_run(run, results)

    @staticmethod
    def _serialize_evaluation_run(
        run: EvaluationRun,
        results: List[EvaluationResult],
    ) -> Dict[str, Any]:
        return {
            "run_id": run.id,
            "timestamp": run.timestamp.isoformat() if run.timestamp else None,
            "total_questions": run.total_questions,
            "answerable_questions": run.answerable_questions,
            "unanswerable_questions": run.unanswerable_questions,
            "source_hit_rate": run.source_hit_rate,
            "refusal_accuracy": run.refusal_accuracy,
            "answer_correctness": run.answer_correctness,
            "semantic_answer_correctness": run.semantic_answer_correctness,
            "faithfulness": run.faithfulness,
            "context_relevance": run.context_relevance,
            "average_latency": run.average_latency,
            "prompt_variant": run.prompt_variant or DEFAULT_PROMPT_VARIANT,
            "benchmark_split": run.benchmark_split or DEFAULT_BENCHMARK_SPLIT,
            "retrieval_profile": run.retrieval_profile or DEFAULT_RETRIEVAL_PROFILE,
            "answer_verification": bool(run.answer_verification),
            "llm_model": run.llm_model,
            "embedding_model": run.embedding_model,
            "results": [
                EvaluationService._serialize_evaluation_result(result)
                for result in results
            ],
        }

    def run_optimization_experiments(
        self,
        questions: List[Dict[str, Any]],
        chunk_sizes: List[int],
        chunk_overlaps: List[int],
        top_k_values: List[int],
        retrieval_methods: List[str],
        rerankers: Optional[List[str]] = None,
        chunking_strategies: Optional[List[str]] = None,
        prompt_variants: Optional[List[str]] = None,
        semantic_judge: bool = False,
        search_mode: str = "grid",
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        if search_mode == "smart":
            configurations = self._smart_search_space()
        elif search_mode == "grid":
            configurations = self._validate_search_space(
                chunk_sizes,
                chunk_overlaps,
                top_k_values,
                retrieval_methods,
                rerankers or ["none"],
                chunking_strategies or [DEFAULT_CHUNKING_STRATEGY],
                prompt_variants or [DEFAULT_PROMPT_VARIANT],
            )
        else:
            raise ValueError("search_mode must be grid or smart")
        previous_configuration = self.doc_service.get_active_configuration()
        document_summary = self._document_summary()
        optimization_run = OptimizationRun()
        self.db.add(optimization_run)
        self.db.commit()
        self.db.refresh(optimization_run)
        try:
            all_results = []
            active_index_key = None
            for completed, (
                chunk_size,
                chunk_overlap,
                top_k,
                retrieval_method,
                reranker,
                chunking_strategy,
                prompt_variant,
            ) in enumerate(configurations):
                if cancel_check and cancel_check():
                    break
                index_key = (chunk_size, chunk_overlap, chunking_strategy)
                if index_key != active_index_key:
                    self.doc_service.index_documents(chunk_size, chunk_overlap, chunking_strategy, reset=True)
                    active_index_key = index_key
                evaluation = self.run_evaluation(
                    questions=questions,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    top_k=top_k,
                    retrieval_method=retrieval_method,
                    reranker=reranker,
                    chunking_strategy=chunking_strategy,
                    prompt_variant=prompt_variant,
                    semantic_judge=semantic_judge,
                    ensure_index=False,
                )
                result = OptimizationResult(
                    run_id=optimization_run.id,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    chunking_strategy=chunking_strategy,
                    top_k=top_k,
                    retrieval_method=retrieval_method,
                    reranker=reranker,
                    prompt_variant=prompt_variant,
                    document_type=document_summary["document_type"],
                    content_unit_count=document_summary["content_unit_count"],
                    source_hit_rate=evaluation["source_hit_rate"],
                    refusal_accuracy=evaluation["refusal_accuracy"],
                    answer_correctness=evaluation["answer_correctness"],
                    semantic_answer_correctness=evaluation.get("semantic_answer_correctness"),
                    faithfulness=evaluation["faithfulness"],
                    context_relevance=evaluation["context_relevance"],
                    average_latency=evaluation["average_latency"],
                    total_questions=evaluation["total_questions"],
                    answerable_questions=evaluation["answerable_questions"],
                    unanswerable_questions=evaluation["unanswerable_questions"],
                )
                self.db.add(result)
                all_results.append(result)
                if progress_callback:
                    progress_callback(completed + 1, len(configurations))
            self.db.commit()
            ranked = sorted(all_results, key=self._optimization_sort_key)
            serialized = [self._serialize_optimization_result(item, rank) for rank, item in enumerate(ranked, 1)]
            output_path = self._save_optimization_results(serialized)
            return {
                "run_id": optimization_run.id,
                "total_configurations": len(configurations),
                "completed_configurations": len(all_results),
                "total_questions": len(questions),
                "search_mode": search_mode,
                "semantic_judge": semantic_judge,
                "results_path": str(output_path),
                "results": serialized,
                "active_configuration": previous_configuration,
            }
        except Exception:
            self.db.rollback()
            raise
        finally:
            if previous_configuration:
                self.doc_service.index_documents(**previous_configuration, reset=True)
            else:
                self.doc_service.reset_index()

    def apply_best_configuration(self, run_id: int) -> Dict[str, Any]:
        results = self.db.query(OptimizationResult).filter(OptimizationResult.run_id == run_id).all()
        if not results:
            raise ValueError("Optimization run not found or has no results")
        best = sorted(results, key=self._optimization_sort_key)[0]
        index_result = self.doc_service.index_documents(
            best.chunk_size,
            best.chunk_overlap,
            best.chunking_strategy or DEFAULT_CHUNKING_STRATEGY,
            reset=True,
        )
        return {
            "run_id": run_id,
            "chunk_size": best.chunk_size,
            "chunk_overlap": best.chunk_overlap,
            "chunking_strategy": best.chunking_strategy or DEFAULT_CHUNKING_STRATEGY,
            "top_k": best.top_k,
            "retrieval_method": best.retrieval_method,
            "reranker": best.reranker,
            "prompt_variant": best.prompt_variant or DEFAULT_PROMPT_VARIANT,
            "index_result": index_result,
        }

    def _validate_expected_sources(self, questions: List[Dict[str, Any]]) -> None:
        names = {
            (document.original_filename or document.filename)
            for document in self.db.query(Document).all()
        }
        missing = sorted(
            {
                item["expected_source"]
                for item in questions
                if item["question_type"] != UNANSWERABLE_QUESTION_TYPE and item["expected_source"] not in names
            }
        )
        if missing:
            raise ValueError(
                "expected_source must exactly match an uploaded document filename. "
                f"Not found: {', '.join(missing)}"
            )

    @staticmethod
    def _validate_evaluation_configuration(
        chunk_size: int,
        chunk_overlap: int,
        top_k: int,
        retrieval_method: str,
        reranker: str = "none",
        chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
        prompt_variant: str = DEFAULT_PROMPT_VARIANT,
        retrieval_profile: str = DEFAULT_RETRIEVAL_PROFILE,
        benchmark_split: str = DEFAULT_BENCHMARK_SPLIT,
    ) -> None:
        DocumentService._validate_index_configuration(chunk_size, chunk_overlap, chunking_strategy)
        if top_k <= 0 or top_k > MAX_TOP_K:
            raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")
        if retrieval_method not in SUPPORTED_RETRIEVAL_METHODS:
            raise ValueError(f"retrieval_method must be one of: {', '.join(sorted(SUPPORTED_RETRIEVAL_METHODS))}")
        if reranker not in SUPPORTED_RERANKERS:
            raise ValueError(f"reranker must be one of: {', '.join(sorted(SUPPORTED_RERANKERS))}")
        if chunking_strategy not in SUPPORTED_CHUNKING_STRATEGIES:
            raise ValueError(
                f"chunking_strategy must be one of: {', '.join(sorted(SUPPORTED_CHUNKING_STRATEGIES))}"
            )
        if prompt_variant not in SUPPORTED_PROMPT_VARIANTS:
            raise ValueError(f"prompt_variant must be one of: {', '.join(sorted(SUPPORTED_PROMPT_VARIANTS))}")
        if retrieval_profile not in SUPPORTED_RETRIEVAL_PROFILES:
            raise ValueError(
                f"retrieval_profile must be one of: {', '.join(sorted(SUPPORTED_RETRIEVAL_PROFILES))}"
            )
        if benchmark_split not in SUPPORTED_BENCHMARK_SPLITS:
            raise ValueError(
                f"benchmark_split must be one of: {', '.join(sorted(SUPPORTED_BENCHMARK_SPLITS))}"
            )

    def _validate_search_space(
        self,
        chunk_sizes: List[int],
        chunk_overlaps: List[int],
        top_k_values: List[int],
        retrieval_methods: List[str],
        rerankers: List[str],
        chunking_strategies: List[str],
        prompt_variants: Optional[List[str]] = None,
    ):
        if not chunk_sizes or any(value <= 0 for value in chunk_sizes):
            raise ValueError("chunk_sizes must contain positive integers")
        if not chunk_overlaps or any(value < 0 for value in chunk_overlaps):
            raise ValueError("chunk_overlaps must contain non-negative integers")
        if not top_k_values or any(value <= 0 or value > MAX_TOP_K for value in top_k_values):
            raise ValueError(f"top_k_values must be between 1 and {MAX_TOP_K}")
        if not retrieval_methods or any(method not in SUPPORTED_RETRIEVAL_METHODS for method in retrieval_methods):
            raise ValueError(f"retrieval_methods must contain only: {', '.join(sorted(SUPPORTED_RETRIEVAL_METHODS))}")
        if not rerankers or any(value not in SUPPORTED_RERANKERS for value in rerankers):
            raise ValueError(f"rerankers must contain only: {', '.join(sorted(SUPPORTED_RERANKERS))}")
        if not chunking_strategies or any(value not in SUPPORTED_CHUNKING_STRATEGIES for value in chunking_strategies):
            raise ValueError(
                f"chunking_strategies must contain only: {', '.join(sorted(SUPPORTED_CHUNKING_STRATEGIES))}"
            )
        prompt_variants = prompt_variants or [DEFAULT_PROMPT_VARIANT]
        if not prompt_variants or any(value not in SUPPORTED_PROMPT_VARIANTS for value in prompt_variants):
            raise ValueError(
                f"prompt_variants must contain only: {', '.join(sorted(SUPPORTED_PROMPT_VARIANTS))}"
            )
        configurations = list(
            product(
                chunk_sizes,
                chunk_overlaps,
                top_k_values,
                retrieval_methods,
                rerankers,
                chunking_strategies,
                prompt_variants,
            )
        )
        invalid = [(size, overlap) for size, overlap, *_ in configurations if overlap >= size]
        if invalid:
            pairs = ", ".join(f"{size}/{overlap}" for size, overlap in sorted(set(invalid)))
            raise ValueError(f"Every chunk_overlap must be smaller than its chunk_size. Invalid combinations: {pairs}")
        if len(configurations) > MAX_OPTIMIZATION_CONFIGURATIONS:
            raise ValueError(
                f"Optimization is limited to {MAX_OPTIMIZATION_CONFIGURATIONS} configurations; "
                f"requested {len(configurations)}"
            )
        return configurations

    @staticmethod
    def _smart_search_space():
        """Eight deliberate configs for premium prompt/retrieval tuning."""
        return [
            (800, 150, 5, "hybrid", "none", "structure", "baseline_strict"),
            (800, 150, 5, "hybrid", "none", "structure", "grounded_complete"),
            (800, 150, 8, "hybrid", "none", "structure", "grounded_complete"),
            (800, 150, 8, "hybrid", "enabled", "structure", "grounded_complete"),
            (800, 150, 8, "hybrid", "enabled", "structure", "policy_procedure"),
            (800, 150, 8, "hybrid", "enabled", "structure", "multi_doc_synthesis"),
            (800, 150, 10, "hybrid", "enabled", "structure", "multi_doc_synthesis"),
            (1200, 150, 8, "mmr", "none", "structure", "multi_doc_synthesis"),
        ]

    @staticmethod
    def _optimization_sort_key(result: OptimizationResult):
        return (
            -float(result.semantic_answer_correctness or result.answer_correctness or 0),
            -float(result.faithfulness or 0),
            -float(result.source_hit_rate or 0),
            -float(result.refusal_accuracy or 0),
            float(result.average_latency or 0),
        )

    @staticmethod
    def _serialize_evaluation_result(result: EvaluationResult) -> Dict[str, Any]:
        return {
            "question": result.question,
            "question_type": result.question_type,
            "reference_answer": result.reference_answer,
            "expected_source": result.expected_source,
            "expected_page": result.expected_page,
            "expected_locator": result.expected_locator,
            "retrieved_sources": json.loads(result.retrieved_sources_json or "[]"),
            "source_hit": result.source_hit,
            "correctly_refused": result.correctly_refused,
            "answer_correctness": result.answer_correctness,
            "correctness_explanation": result.correctness_explanation,
            "semantic_answer_correctness": result.semantic_answer_correctness,
            "semantic_verdict": result.semantic_verdict,
            "semantic_explanation": result.semantic_explanation,
            "faithfulness": result.faithfulness,
            "context_relevance": result.context_relevance,
            "no_chunks_retrieved": result.no_chunks_retrieved,
            "top_k": result.top_k,
            "retrieval_method": result.retrieval_method,
            "reranker": result.reranker,
            "prompt_variant": result.prompt_variant or DEFAULT_PROMPT_VARIANT,
            "retrieval_profile": result.retrieval_profile or DEFAULT_RETRIEVAL_PROFILE,
            "resolved_retrieval_profile": result.resolved_retrieval_profile,
            "answer_verification": bool(result.answer_verification),
            "latency": result.latency_seconds,
            "generated_answer": result.answer,
        }

    @staticmethod
    def _serialize_optimization_result(result: OptimizationResult, rank: int) -> Dict[str, Any]:
        return {
            "rank": rank,
            "chunk_size": result.chunk_size,
            "chunk_overlap": result.chunk_overlap,
            "chunking_strategy": result.chunking_strategy or DEFAULT_CHUNKING_STRATEGY,
            "top_k": result.top_k,
            "retrieval_method": result.retrieval_method,
            "reranker": result.reranker,
            "prompt_variant": result.prompt_variant or DEFAULT_PROMPT_VARIANT,
            "document_type": result.document_type,
            "content_unit_count": result.content_unit_count,
            "answer_correctness": result.answer_correctness,
            "semantic_answer_correctness": result.semantic_answer_correctness,
            "faithfulness": result.faithfulness,
            "context_relevance": result.context_relevance,
            "source_hit_rate": result.source_hit_rate,
            "refusal_accuracy": result.refusal_accuracy,
            "average_latency": result.average_latency,
            "total_questions": result.total_questions,
            "answerable_questions": result.answerable_questions,
            "unanswerable_questions": result.unanswerable_questions,
        }

    def _save_optimization_results(self, results: List[Dict[str, Any]]) -> Path:
        output_dir = self._evaluation_directory() / "results"
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "optimization_results.csv"
        fieldnames = list(results[0].keys()) if results else [
            "rank", "chunk_size", "chunk_overlap", "chunking_strategy", "top_k",
            "retrieval_method", "reranker", "prompt_variant"
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        return csv_path

    @staticmethod
    def _evaluation_directory() -> Path:
        backend_root = Path(__file__).resolve().parents[2]
        backend_eval = backend_root / "eval"
        project_eval = backend_root.parent / "eval"
        return backend_eval if backend_eval.exists() else project_eval

    @staticmethod
    def _source_hit(sources: List[Dict[str, Any]], question_data: Dict[str, Any]) -> bool:
        expected_source = question_data.get("expected_source")
        if not expected_source:
            return False
        expected_page = question_data.get("expected_page")
        expected_locator = question_data.get("expected_locator")
        for source in sources:
            if source.get("filename") != expected_source:
                continue
            if expected_locator:
                candidates = {
                    str(source.get("locator") or "").strip().lower(),
                    str(source.get("locator_label") or "").strip().lower(),
                }
                if expected_locator.strip().lower() in candidates:
                    return True
                continue
            if expected_page is not None and source.get("page") == expected_page:
                return True
        return False

    @staticmethod
    def _first_source_value(sources: List[Dict[str, Any]], key: str) -> Any:
        return next((source.get(key) for source in sources if source.get(key)), None)

    def _document_summary(self) -> Dict[str, Any]:
        documents = self.db.query(Document).all()
        document_types = {
            document.document_type or "pdf"
            for document in documents
            if document.document_type or document.page_count
        }
        return {
            "document_type": next(iter(document_types)) if len(document_types) == 1 else ("mixed" if document_types else None),
            "content_unit_count": sum(document.content_unit_count or document.page_count or 0 for document in documents) or None,
        }

    @staticmethod
    def _provider_metadata() -> Dict[str, Any]:
        """Return non-secret provider metadata if the configured providers resolve."""
        metadata = {"llm_model": None, "embedding_model": None}
        try:
            metadata["llm_model"] = get_chat_settings().model
        except Exception:
            pass
        try:
            metadata["embedding_model"] = get_embedding_settings().model
        except Exception:
            pass
        return metadata
