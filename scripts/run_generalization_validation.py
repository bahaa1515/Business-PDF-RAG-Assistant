"""Run a cost-guarded known-plus-holdout validation pass.

Default mode is dry-run only. Passing --allow-paid is required before the
script makes configured LLM or embedding calls.
"""

from __future__ import annotations

import argparse
import csv
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


KNOWN_CSV = Path(
    os.getenv(
        "GENERALIZATION_KNOWN_CSV",
        ROOT / "demo_public" / "gitlab" / "evaluation" / "gitlab_evaluation.csv",
    )
)
HOLDOUT_CSV = Path(
    os.getenv(
        "GENERALIZATION_HOLDOUT_CSV",
        ROOT / "demo_public" / "gitlab" / "evaluation" / "gitlab_holdout_evaluation.csv",
    )
)
RESULTS_DIR = Path(
    os.getenv(
        "GENERALIZATION_RESULTS_DIR",
        ROOT / "demo_public" / "gitlab" / "results",
    )
)


def count_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8-sig") as file:
        return sum(1 for _ in csv.DictReader(file))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def metric(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def run_eval(
    service: EvaluationService,
    questions: list[dict[str, Any]],
    benchmark_split: str,
) -> dict[str, Any]:
    return service.run_evaluation(
        questions=questions,
        chunk_size=1200,
        chunk_overlap=150,
        top_k=8,
        retrieval_method="mmr",
        reranker="none",
        chunking_strategy="structure",
        prompt_variant="multi_doc_synthesis",
        semantic_judge=True,
        retrieval_profile="auto",
        answer_verification=True,
        benchmark_split=benchmark_split,
        ensure_index=True,
    )


def write_summary(smoke: dict[str, Any], known: dict[str, Any], holdout: dict[str, Any]) -> None:
    lines = [
        "# Generalization Validation Results",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This validation uses public GitLab documentation and does not store API keys.",
        "It reports the frozen known benchmark separately from the unseen GitLab holdout set.",
        "",
        "## Configuration",
        "",
        "- Model, embedding model: recorded from runtime provider settings in each JSON artifact",
        "- Chunking: 1200 / 150 / structure",
        "- Retrieval profile: auto",
        "- Prompt: multi_doc_synthesis",
        "- Answer verification: enabled",
        "- Semantic judge: enabled",
        "",
        "## Results",
        "",
        f"- Smoke questions: {smoke.get('total_questions')} | semantic {metric(smoke.get('semantic_answer_correctness')):.3f} | retrieval {metric(smoke.get('source_hit_rate')):.3f} | refusal {metric(smoke.get('refusal_accuracy')):.3f}",
        f"- Known benchmark: {known.get('total_questions')} | semantic {metric(known.get('semantic_answer_correctness')):.3f} | retrieval {metric(known.get('source_hit_rate')):.3f} | refusal {metric(known.get('refusal_accuracy')):.3f}",
        f"- Holdout benchmark: {holdout.get('total_questions')} | semantic {metric(holdout.get('semantic_answer_correctness')):.3f} | retrieval {metric(holdout.get('source_hit_rate')):.3f} | refusal {metric(holdout.get('refusal_accuracy')):.3f}",
        "",
        "Do not claim a target score unless these saved artifacts prove it.",
        "",
    ]
    (RESULTS_DIR / "generalization_validation_summary.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--budget-ceiling-usd", type=float, default=3.0)
    parser.add_argument("--smoke-count", type=int, default=3)
    parser.add_argument(
        "--mode",
        choices=["all", "smoke", "known", "holdout"],
        default="all",
        help="Choose which validation split to run.",
    )
    parser.add_argument(
        "--smoke-only",
        action="store_true",
        help="Run only the small smoke validation and stop before full benchmarks.",
    )
    args = parser.parse_args()

    known_count = count_rows(KNOWN_CSV)
    holdout_count = count_rows(HOLDOUT_CSV)
    smoke_count = max(1, min(args.smoke_count, holdout_count))

    print("Generalization validation plan")
    print(f"- Known benchmark: {known_count} questions")
    print(f"- Holdout benchmark: {holdout_count} questions")
    print(f"- Smoke test: {smoke_count} holdout questions")
    mode = "smoke" if args.smoke_only else args.mode
    print(f"- Mode: {mode}")
    print("- Paid calls: controlled by selected mode")
    print(f"- Hard manual spend ceiling: ${args.budget_ceiling_usd:.2f}")

    if args.budget_ceiling_usd > 3:
        raise SystemExit("Refusing to run: budget ceiling cannot exceed $3 for this script.")

    if not args.allow_paid:
        print("Dry run only. Re-run with --allow-paid after checking the OpenAI dashboard budget.")
        return 0

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        service = EvaluationService(db)
        known_questions = service.load_evaluation_questions(str(KNOWN_CSV))
        holdout_questions = service.load_evaluation_questions(str(HOLDOUT_CSV))

        smoke = None
        known = None
        holdout = None

        if mode in {"all", "smoke"}:
            print("Running paid smoke validation...")
            smoke = run_eval(service, holdout_questions[:smoke_count], "holdout")
            dump_json(RESULTS_DIR / "generalization_smoke.json", smoke)

        if mode == "smoke":
            print("Smoke-only validation complete. Check the OpenAI dashboard spend now.")
            return 0

        if mode in {"all", "known"}:
            print("Running paid known benchmark validation...")
            known = run_eval(service, known_questions, "known")
            dump_json(RESULTS_DIR / "generalization_known_benchmark.json", known)

        if mode in {"all", "holdout"}:
            print("Running paid holdout validation...")
            holdout = run_eval(service, holdout_questions, "holdout")
            dump_json(RESULTS_DIR / "generalization_holdout_benchmark.json", holdout)

        if mode == "all":
            write_summary(smoke or {}, known or {}, holdout or {})
        print("Generalization validation complete. Check the OpenAI dashboard spend now.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
