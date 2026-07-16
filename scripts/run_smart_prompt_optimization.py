"""Run the GitLab smart prompt/retrieval optimization with saved artifacts.

This script uses the configured application providers and can make paid LLM and
embedding calls. It never prints API keys.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if (BACKEND / "app").exists() and str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
elif (ROOT / "app").exists() and str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal  # noqa: E402
from app.services.evaluation_service import EvaluationService  # noqa: E402


PROBE_CSV = Path(
    os.getenv(
        "SMART_PROBE_CSV",
        ROOT / "demo_public" / "gitlab" / "evaluation" / "gitlab_smart_probe.csv",
    )
)
FULL_CSV = Path(
    os.getenv(
        "SMART_FULL_CSV",
        ROOT / "demo_public" / "gitlab" / "evaluation" / "gitlab_evaluation.csv",
    )
)
RESULTS_DIR = Path(
    os.getenv(
        "SMART_RESULTS_DIR",
        ROOT / "demo_public" / "gitlab" / "results",
    )
)


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def metric(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def rank_key(result: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        metric(result.get("semantic_answer_correctness")),
        metric(result.get("source_hit_rate")),
        metric(result.get("refusal_accuracy")),
        -metric(result.get("average_latency")),
    )


def run_full_evaluation(
    service: EvaluationService,
    questions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    return service.run_evaluation(
        questions=questions,
        chunk_size=int(config["chunk_size"]),
        chunk_overlap=int(config["chunk_overlap"]),
        top_k=int(config["top_k"]),
        retrieval_method=str(config["retrieval_method"]),
        reranker=str(config["reranker"] or "none"),
        chunking_strategy=str(config["chunking_strategy"] or "structure"),
        prompt_variant=str(config["prompt_variant"] or "grounded_complete"),
        semantic_judge=True,
        ensure_index=True,
    )


def write_summary(probe: dict[str, Any], full_runs: list[dict[str, Any]], best: dict[str, Any]) -> None:
    summary = RESULTS_DIR / "smart_prompt_optimization_summary.md"
    lines = [
        "# Smart Prompt Optimization Results",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This run uses the configured provider settings and dummy-free real application evaluation data. It does not print or store API keys.",
        "",
        "## Probe Run",
        "",
        f"- Search mode: {probe.get('search_mode')}",
        f"- Configurations tested: {probe.get('completed_configurations')}/{probe.get('total_configurations')}",
        f"- Questions per configuration: {probe.get('total_questions')}",
        f"- Semantic judge enabled: {probe.get('semantic_judge')}",
        "",
        "## Full Runs",
        "",
    ]
    for index, result in enumerate(full_runs, start=1):
        config = result.get("configuration") or {}
        lines.extend(
            [
                f"### Full config {index}",
                "",
                f"- Prompt: {config.get('prompt_variant') or result.get('prompt_variant')}",
                f"- Chunking: {config.get('chunk_size')}/{config.get('chunk_overlap')}/{config.get('chunking_strategy')}",
                f"- Retrieval: top_k={config.get('top_k')}, method={config.get('retrieval_method')}, reranker={config.get('reranker')}",
                f"- Retrieval accuracy: {metric(result.get('source_hit_rate')):.3f}",
                f"- Semantic correctness: {metric(result.get('semantic_answer_correctness')):.3f}",
                f"- Refusal accuracy: {metric(result.get('refusal_accuracy')):.3f}",
                f"- Average latency: {metric(result.get('average_latency')):.2f}s",
                "",
            ]
        )
    best_config = best.get("configuration") or {}
    lines.extend(
        [
            "## Selected Best Run",
            "",
            f"- Prompt: {best_config.get('prompt_variant') or best.get('prompt_variant')}",
            f"- Retrieval accuracy: {metric(best.get('source_hit_rate')):.3f}",
            f"- Semantic correctness: {metric(best.get('semantic_answer_correctness')):.3f}",
            f"- Refusal accuracy: {metric(best.get('refusal_accuracy')):.3f}",
            "",
            "Use these numbers honestly. If semantic correctness is below 0.900, present the result as the measured score, not as a claimed target.",
            "",
        ]
    )
    summary.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-full-runs", type=int, default=2)
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--budget-ceiling-usd", type=float, default=3.0)
    args = parser.parse_args()

    if args.budget_ceiling_usd > 3:
        raise SystemExit("Refusing to run: budget ceiling cannot exceed $3 for this script.")
    if not args.allow_paid:
        print(
            "Dry run only. This script can make paid LLM and embedding calls. "
            "Re-run with --allow-paid after checking the OpenAI dashboard budget."
        )
        return 0

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        service = EvaluationService(db)
        probe_questions = service.load_evaluation_questions(str(PROBE_CSV))
        full_questions = service.load_evaluation_questions(str(FULL_CSV))

        print(
            "Starting smart probe: 8 configs, "
            f"{len(probe_questions)} questions, semantic judge enabled."
        )
        probe = service.run_optimization_experiments(
            questions=probe_questions,
            chunk_sizes=[800],
            chunk_overlaps=[150],
            top_k_values=[5],
            retrieval_methods=["hybrid"],
            rerankers=["none"],
            chunking_strategies=["structure"],
            prompt_variants=["grounded_complete"],
            semantic_judge=True,
            search_mode="smart",
        )
        dump_json(RESULTS_DIR / "smart_prompt_optimization_probe.json", probe)
        print(
            "Probe complete. Best semantic score: "
            f"{metric(probe['results'][0].get('semantic_answer_correctness')):.3f}"
        )

        if args.probe_only:
            return 0

        top_configs = probe["results"][: max(1, args.top_full_runs)]
        full_runs = []
        for index, config in enumerate(top_configs, start=1):
            print(f"Starting full evaluation {index}/{len(top_configs)} with prompt {config.get('prompt_variant')}.")
            result = run_full_evaluation(service, full_questions, config)
            full_runs.append(result)
            dump_json(RESULTS_DIR / f"smart_prompt_full_evaluation_{index}.json", result)
            print(
                f"Full evaluation {index} complete: semantic="
                f"{metric(result.get('semantic_answer_correctness')):.3f}, "
                f"retrieval={metric(result.get('source_hit_rate')):.3f}, "
                f"refusal={metric(result.get('refusal_accuracy')):.3f}"
            )

        best = sorted(full_runs, key=rank_key, reverse=True)[0]
        dump_json(RESULTS_DIR / "smart_prompt_best_evaluation.json", best)
        dump_json(RESULTS_DIR / "premium_openai_evaluation_result.json", best)
        write_summary(probe, full_runs, best)
        print(
            "Best full run: semantic="
            f"{metric(best.get('semantic_answer_correctness')):.3f}, "
            f"retrieval={metric(best.get('source_hit_rate')):.3f}, "
            f"refusal={metric(best.get('refusal_accuracy')):.3f}"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
