"""Question-aware retrieval profile selection for RAG calls."""
from dataclasses import dataclass
import re

from app.config import (
    DEFAULT_RETRIEVAL_PROFILE,
    SUPPORTED_RETRIEVAL_PROFILES,
)


@dataclass(frozen=True)
class RetrievalSettings:
    """Effective retrieval settings selected for one question."""

    top_k: int
    retrieval_method: str
    reranker: str
    retrieval_profile: str
    resolved_retrieval_profile: str


_MULTI_DOC_PATTERNS = re.compile(
    r"\b(compare|difference|different|between|decide between|versus|vs\.?|synthesize)\b",
    re.IGNORECASE,
)
_POLICY_PATTERNS = re.compile(
    r"\b(should|policy|procedure|process|when|how should|what should|required|warning|request|report)\b",
    re.IGNORECASE,
)
_PRODUCT_PATTERNS = re.compile(
    r"\b(service desk|docs?|feature|troubleshoot|email|ticket|tiers?|offerings?)\b",
    re.IGNORECASE,
)


def normalize_retrieval_profile(retrieval_profile: str | None) -> str:
    """Return a supported retrieval profile name."""
    profile = (retrieval_profile or DEFAULT_RETRIEVAL_PROFILE).strip().lower()
    if profile not in SUPPORTED_RETRIEVAL_PROFILES:
        raise ValueError(
            "retrieval_profile must be one of: "
            + ", ".join(sorted(SUPPORTED_RETRIEVAL_PROFILES))
        )
    return profile


def resolve_retrieval_settings(
    question: str,
    question_type: str | None,
    top_k: int,
    retrieval_method: str,
    reranker: str,
    retrieval_profile: str | None = None,
) -> RetrievalSettings:
    """Resolve manual settings or choose a conservative automatic profile."""
    profile = normalize_retrieval_profile(retrieval_profile)
    if profile == "manual":
        return RetrievalSettings(top_k, retrieval_method, reranker, profile, "manual")

    question_type = (question_type or "").strip().lower()
    text = question or ""

    if question_type == "multi_document_reasoning" or _MULTI_DOC_PATTERNS.search(text):
        return RetrievalSettings(10, "hybrid", "none", profile, "auto_multi_document")

    if question_type in {"policy_procedure", "customer_support_behavior"} or _POLICY_PATTERNS.search(text):
        return RetrievalSettings(8, "hybrid", "none", profile, "auto_policy")

    if question_type == "product_technical_documentation" or _PRODUCT_PATTERNS.search(text):
        return RetrievalSettings(6, "hybrid", "none", profile, "auto_product")

    return RetrievalSettings(5, "hybrid", "none", profile, "auto_focused")
