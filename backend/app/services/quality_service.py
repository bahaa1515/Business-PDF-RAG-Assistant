"""Evaluation metrics for portfolio and production-oriented RAG validation."""
import json
import re
from typing import Iterable

from app.rag.generator import _chat_completion_with_retry
from app.rag.providers import get_chat_settings


class QualityService:
    """Score answers without adding extra paid LLM judge calls."""

    STOP_WORDS = {
        "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from",
        "how", "in", "is", "it", "of", "on", "or", "the", "this", "to", "what",
        "when", "where", "which", "who", "with",
    }

    @classmethod
    def _tokens(cls, value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", (value or "").lower())
            if token not in cls.STOP_WORDS
        }

    def answer_correctness(self, answer: str, reference_answer: str) -> dict:
        answer_tokens = self._tokens(answer)
        reference_tokens = self._tokens(reference_answer)
        if not reference_tokens:
            return {"score": 0.0, "explanation": "No reference answer was provided."}
        overlap = len(answer_tokens & reference_tokens)
        precision = overlap / len(answer_tokens) if answer_tokens else 0.0
        recall = overlap / len(reference_tokens)
        score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        score = round(score, 4)
        return {
            "score": score,
            "explanation": (
                f"Token semantic overlap: {overlap}/{len(reference_tokens)} reference "
                f"concepts matched (precision {precision:.2f}, recall {recall:.2f})."
            ),
        }

    def semantic_answer_correctness(
        self,
        question: str,
        generated_answer: str,
        reference_answer: str,
    ) -> dict:
        """Use the configured chat model as a semantic judge for answerable rows."""
        if not reference_answer:
            return {
                "score": 0.0,
                "verdict": "incorrect",
                "explanation": "No reference answer was provided.",
            }

        system_prompt = (
            "You are a strict but fair RAG evaluation judge. Compare the generated "
            "answer to the reference answer for whether it fully answers the question. "
            "Do not require exact wording. Do not require every reference detail when "
            "that detail is extra background and not necessary to answer the question. "
            "Do not penalize additional details merely because they are absent from "
            "the reference answer, unless they contradict the reference, change the "
            "answer, or distract from the requested answer. "
            "Do not call extra detail distracting if the generated answer clearly "
            "preserves the user's decision, policy, or procedure and the extra detail "
            "does not change what the user should do. "
            "If the generated answer fully answers the question and only adds harmless "
            "non-contradictory detail, the score should usually be at least 0.9. "
            "Do not penalize concise answers when they preserve the important meaning. "
            "Penalize missing critical requirements, missing required list items, "
            "incorrect facts, contradictions, clearly harmful extra claims, or refusing "
            "when the reference contains an answer. "
            "Return JSON only with keys: score, verdict, explanation. The score must "
            "be a number from 0 to 1. The verdict must be correct, partial, or incorrect."
        )
        user_prompt = f"""Question:
{question}

Reference answer:
{reference_answer}

Generated answer:
{generated_answer}

Scoring guide:
- 1.0: fully correct and semantically equivalent.
- 0.9: fully answers the question with harmless extra detail or minor wording/scope differences.
- 0.8: mostly correct, only minor omissions or mild distraction.
- 0.5: partially correct but missing important information.
- 0.2: mostly incorrect or too incomplete.
- 0.0: wrong, contradictory, or refused when the reference answer is available.
"""
        raw = self._judge_completion(system_prompt, user_prompt)
        return self._parse_judge_response(raw)

    def faithfulness(self, answer: str, contexts: Iterable[str]) -> float:
        answer_tokens = self._tokens(answer)
        context_tokens = self._tokens(" ".join(contexts))
        if not answer_tokens or not context_tokens:
            return 0.0
        return round(len(answer_tokens & context_tokens) / len(answer_tokens), 4)

    def context_relevance(self, question: str, contexts: Iterable[str]) -> float:
        question_tokens = self._tokens(question)
        context_tokens = self._tokens(" ".join(contexts))
        if not question_tokens or not context_tokens:
            return 0.0
        return round(len(question_tokens & context_tokens) / len(question_tokens), 4)

    @staticmethod
    def _judge_completion(system_prompt: str, user_prompt: str) -> str:
        settings = get_chat_settings()
        if settings.provider == "anthropic":
            from app.rag.generator import _generate_with_anthropic

            return _generate_with_anthropic(settings, system_prompt, user_prompt)

        response = _chat_completion_with_retry(
            model=settings.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()

    @staticmethod
    def _parse_judge_response(raw: str) -> dict:
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            payload = json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Semantic judge returned invalid JSON: {raw[:200]}") from exc

        try:
            score = float(payload.get("score"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"Semantic judge returned an invalid score: {payload}") from exc
        score = max(0.0, min(1.0, round(score, 4)))

        verdict = str(payload.get("verdict") or "").strip().lower()
        if verdict not in {"correct", "partial", "incorrect"}:
            verdict = "correct" if score >= 0.85 else "partial" if score >= 0.5 else "incorrect"

        explanation = str(payload.get("explanation") or "").strip()
        if len(explanation) > 1000:
            explanation = explanation[:997] + "..."
        return {
            "score": score,
            "verdict": verdict,
            "explanation": explanation or "Semantic judge did not provide an explanation.",
        }
