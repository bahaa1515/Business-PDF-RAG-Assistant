"""RAG pipeline orchestration."""
import re
import time
from typing import Any, Dict

from app.config import REFUSAL_MESSAGE
from app.rag.generator import AnswerGenerator
from app.rag.prompt_variants import normalize_prompt_variant
from app.rag.retriever import Retriever
from app.rag.retrieval_profiles import resolve_retrieval_settings


class RAGPipeline:
    """Coordinate retrieval, prompt construction, answer generation, and formatting."""

    def __init__(self):
        self.retriever = Retriever()
        self.generator = AnswerGenerator()

    def run(
        self,
        question: str,
        top_k: int = 5,
        retrieval_method: str = "similarity",
        reranker: str = "none",
        prompt_variant: str | None = None,
        retrieval_profile: str | None = None,
        answer_verification: bool = False,
        question_type: str | None = None,
        show_debug: bool = False,
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        prompt_variant = normalize_prompt_variant(prompt_variant)
        effective = resolve_retrieval_settings(
            question=question,
            question_type=question_type,
            top_k=top_k,
            retrieval_method=retrieval_method,
            reranker=reranker,
            retrieval_profile=retrieval_profile,
        )
        chunks = self.retriever.retrieve(
            question,
            top_k=effective.top_k,
            method=effective.retrieval_method,
            reranker=effective.reranker,
        )

        if not chunks:
            latency = time.perf_counter() - start_time
            return {
                "answer": REFUSAL_MESSAGE,
                "sources": [],
                "retrieved_chunks": [] if show_debug else None,
                "latency_seconds": latency,
                "settings_used": {
                    "top_k": effective.top_k,
                    "retrieval_method": effective.retrieval_method,
                    "reranker": effective.reranker,
                    "prompt_variant": prompt_variant,
                    "retrieval_profile": effective.retrieval_profile,
                    "resolved_retrieval_profile": effective.resolved_retrieval_profile,
                    "answer_verification": answer_verification,
                },
            }

        context = _build_context(question, chunks)
        answer = self.generator.generate(question, context, prompt_variant)
        if answer_verification:
            answer = self.generator.verify_answer(question, context, answer)
        sources = [_format_source(chunk) for chunk in chunks]

        result = {
            "answer": answer,
            "sources": sources,
            "latency_seconds": time.perf_counter() - start_time,
            "settings_used": {
                "top_k": effective.top_k,
                "retrieval_method": effective.retrieval_method,
                "reranker": effective.reranker,
                "prompt_variant": prompt_variant,
                "retrieval_profile": effective.retrieval_profile,
                "resolved_retrieval_profile": effective.resolved_retrieval_profile,
                "answer_verification": answer_verification,
            },
        }
        if show_debug:
            result["retrieved_chunks"] = [
                {**_format_source(chunk), "full_text": chunk["text"]}
                for chunk in chunks
            ]
        return result


def _locator_label(chunk: Dict[str, Any]) -> str:
    return chunk.get("locator_label") or (
        f"Page {chunk['page']}" if chunk.get("page") else "Document"
    )


def _build_context(question: str, chunks: list[Dict[str, Any]]) -> str:
    evidence = _high_signal_evidence(question, chunks)
    sections = []
    if evidence:
        sections.append(
            "<high_signal_evidence>\n"
            + "\n".join(
                f"[{item['filename']} - {item['locator_label']}] {item['sentence']}"
                for item in evidence
            )
            + "\n</high_signal_evidence>"
        )
    sections.append(
        "<retrieved_chunks>\n"
        + "\n\n".join(
            f"[{chunk['filename']} - {_locator_label(chunk)}]\n{chunk['text']}"
            for chunk in chunks
        )
        + "\n</retrieved_chunks>"
    )
    return "\n\n".join(sections)


def _high_signal_evidence(
    question: str,
    chunks: list[Dict[str, Any]],
    limit: int = 6,
) -> list[Dict[str, str]]:
    question_terms = _content_terms(question)
    if not question_terms:
        return []
    action_terms = {
        "should", "must", "required", "require", "requires", "cover", "covers",
        "covered", "include", "includes", "included", "contain", "contains",
        "when", "where", "who", "why", "what", "how",
    }
    question_action_terms = question_terms & action_terms

    scored = []
    for chunk in chunks:
        for sentence in _split_sentences(chunk.get("text") or ""):
            sentence_terms = _content_terms(sentence)
            if not sentence_terms:
                continue
            overlap = len(question_terms & sentence_terms)
            if overlap == 0:
                continue
            shared_action_terms = len(question_action_terms & sentence_terms)
            directive_bonus = 4 if question_action_terms and sentence_terms & action_terms else 0
            exact_action_bonus = 15 if question_action_terms & sentence_terms & {
                "cover", "covers", "covered", "include", "includes", "included",
                "contain", "contains", "required", "require", "requires",
            } else 0
            negative_example_penalty = (
                10
                if "not" not in question_terms and re.search(r"\bshould\s+not\b", sentence, re.IGNORECASE)
                else 0
            )
            score = (
                overlap * 2
                + shared_action_terms * 8
                + directive_bonus
                + exact_action_bonus
                - negative_example_penalty
            )
            scored.append(
                {
                    "score": score,
                    "filename": str(chunk.get("filename") or "document"),
                    "locator_label": _locator_label(chunk),
                    "sentence": sentence,
                }
            )

    seen = set()
    evidence = []
    for item in sorted(scored, key=lambda value: value["score"], reverse=True):
        key = (item["filename"], item["locator_label"], item["sentence"].lower())
        if key in seen:
            continue
        seen.add(key)
        evidence.append(
            {
                "filename": item["filename"],
                "locator_label": item["locator_label"],
                "sentence": item["sentence"],
            }
        )
        if len(evidence) >= limit:
            break
    return evidence


def _split_sentences(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if not compact:
        return []
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9#\"'-])", compact)
    return [sentence.strip()[:700] for sentence in sentences if sentence.strip()]


def _content_terms(text: str) -> set[str]:
    stop_words = {
        "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from",
        "in", "is", "it", "of", "on", "or", "the", "this", "to", "with",
        "according", "guidance", "question", "answer",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 1 and token not in stop_words
    }


def _format_source(chunk: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "rank": chunk["rank"],
        "document_id": chunk.get("document_id"),
        "filename": chunk["filename"],
        "page": chunk.get("page"),
        "locator": chunk.get("locator"),
        "locator_label": _locator_label(chunk),
        "source_type": chunk.get("source_type"),
        "document_type": chunk.get("document_type") or chunk.get("source_type"),
        "content_unit_count": chunk.get("content_unit_count"),
        "section_title": chunk.get("section_title"),
        "sheet_name": chunk.get("sheet_name"),
        "chunk_id": chunk["chunk_id"],
        "preview": chunk["preview"],
        "score": chunk.get("score", 0.0),
    }
