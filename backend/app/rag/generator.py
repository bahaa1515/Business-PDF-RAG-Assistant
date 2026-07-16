"""
LLM answer generation.
"""
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.rag.providers import get_chat_client, get_chat_settings
from app.rag.prompt_variants import get_system_prompt, normalize_prompt_variant


class AnswerGenerator:
    """Generate answers using the configured OpenAI-compatible chat provider."""

    @staticmethod
    def generate(
        question: str,
        context: str,
        prompt_variant: str | None = None,
    ) -> str:
        """
        Generate answer using the configured LLM provider.
        
        Args:
            question: User question
            context: Retrieved document context
            
        Returns:
            Generated answer
        """
        variant = normalize_prompt_variant(prompt_variant)
        system_prompt = get_system_prompt(variant)

        user_prompt = f"""<retrieved_context>
{context}
</retrieved_context>

<question>
{question}
</question>

Answer:"""

        settings = get_chat_settings()
        if settings.provider == "anthropic":
            return _generate_with_anthropic(settings, system_prompt, user_prompt)

        response = _chat_completion_with_retry(
            model=settings.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()

    @staticmethod
    def verify_answer(
        question: str,
        context: str,
        draft_answer: str,
    ) -> str:
        """Review a draft answer against retrieved context and return the final answer."""
        system_prompt = """You are DocuQuery AI's grounded-answer verifier.

Review the draft answer against the retrieved context and the exact user question.

Rules:
1. Use only the retrieved context.
2. Keep the answer if it is fully supported and directly answers the question.
3. Remove unsupported claims, distracting extra details, and scope drift.
4. If the draft misses a critical supported detail, add only that supported detail.
5. If the question asks what something should cover, include, require, or contain, prefer the direct requirement sentence over examples or channel/background details.
6. When the draft answers with examples but misses an explicit requirement from context, rewrite it around the requirement and keep examples only if needed.
7. If the context does not support an answer, return exactly:
   "I could not find this information in the uploaded documents."
8. Preserve citations that are supported by the context.
9. Return the final answer only. Do not explain your review."""

        user_prompt = f"""<retrieved_context>
{context}
</retrieved_context>

<question>
{question}
</question>

<draft_answer>
{draft_answer}
</draft_answer>

Final answer:"""

        settings = get_chat_settings()
        if settings.provider == "anthropic":
            return _generate_with_anthropic(settings, system_prompt, user_prompt)

        response = _chat_completion_with_retry(
            model=settings.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()


def _chat_completion_with_retry(**kwargs):
    """Call the configured OpenAI-compatible chat client with rate-limit backoff."""
    max_attempts = 6
    for attempt in range(max_attempts):
        try:
            return get_chat_client().chat.completions.create(**kwargs)
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt == max_attempts - 1:
                raise
            time.sleep(min(2 ** attempt, 20))


def _is_rate_limit_error(exc: Exception) -> bool:
    return (
        getattr(exc, "status_code", None) == 429
        or exc.__class__.__name__ == "RateLimitError"
        or "rate limit" in str(exc).lower()
    )


def _anthropic_base_url(base_url: str | None) -> str:
    return (base_url or "https://api.anthropic.com").rstrip("/")


def _post_anthropic_json(url: str, api_key: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Anthropic chat request failed with HTTP {exc.code}: {body}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Anthropic chat request failed: {exc}") from exc


def _generate_with_anthropic(settings, system_prompt: str, user_prompt: str) -> str:
    payload = {
        "model": settings.model,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    response = _post_anthropic_json(
        f"{_anthropic_base_url(settings.base_url)}/v1/messages",
        settings.api_key,
        payload,
    )
    content = response.get("content") or []
    text_parts = [
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    answer = "".join(text_parts).strip()
    if not answer:
        raise RuntimeError("Anthropic chat response did not include text content.")
    return answer
