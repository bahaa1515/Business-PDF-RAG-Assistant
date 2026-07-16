"""
Embedding generation.
"""
import json
import os
from typing import List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.rag.providers import get_embedding_client, get_embedding_settings


class EmbeddingsGenerator:
    """Generate embeddings using the configured OpenAI-compatible provider."""

    @staticmethod
    def embed_text(text: str) -> List[float]:
        """Generate embedding for a single text."""
        return EmbeddingsGenerator.embed_texts([text])[0]

    @staticmethod
    def embed_texts(texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        settings = get_embedding_settings()
        if settings.provider == "ollama":
            return _embed_with_ollama(settings.model, texts, settings.base_url)
        if settings.provider == "gemini":
            return _embed_with_gemini(settings.model, texts, settings.api_key, settings.base_url)

        response = get_embedding_client().embeddings.create(
            input=texts,
            model=settings.model,
        )

        # Sort by index to ensure correct order
        embeddings = [None] * len(texts)
        for item in response.data:
            embeddings[item.index] = item.embedding

        return embeddings


def _ollama_native_base_url(base_url: str | None) -> str:
    base = (base_url or "http://localhost:11434").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base.rstrip("/")


def _post_ollama_json(url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama embedding request failed with HTTP {exc.code}: {body}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Ollama embedding request failed: {exc}") from exc


def _gemini_native_base_url(base_url: str | None) -> str:
    base = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    if base.endswith("/openai"):
        base = base[:-7]
    return base.rstrip("/")


def _gemini_model_path(model: str) -> str:
    normalized = (model or "").strip().lstrip("/")
    return normalized if normalized.startswith("models/") else f"models/{normalized}"


def _post_gemini_json(url: str, api_key: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini embedding request failed with HTTP {exc.code}: {body}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Gemini embedding request failed: {exc}") from exc


def _embed_with_ollama(model: str, texts: List[str], base_url: str | None) -> List[List[float]]:
    """Use Ollama's native embedding API; its OpenAI-compatible path is flaky for large batches."""
    base = _ollama_native_base_url(base_url)
    batch_size = max(1, int(os.getenv("OLLAMA_EMBED_BATCH_SIZE", "16")))
    all_embeddings = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        all_embeddings.extend(_embed_ollama_batch(base, model, batch))
    return all_embeddings


def _embed_with_gemini(
    model: str,
    texts: List[str],
    api_key: str,
    base_url: str | None,
) -> List[List[float]]:
    """Use Gemini's native embedding API; Gemini chat uses its OpenAI-compatible path."""
    base = _gemini_native_base_url(base_url)
    model_path = _gemini_model_path(model)
    batch_size = max(1, int(os.getenv("GEMINI_EMBED_BATCH_SIZE", "16")))
    all_embeddings = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        all_embeddings.extend(_embed_gemini_batch(base, model_path, api_key, batch))
    return all_embeddings


def _embed_gemini_batch(
    base: str,
    model_path: str,
    api_key: str,
    texts: List[str],
) -> List[List[float]]:
    payload = {
        "requests": [
            {
                "model": model_path,
                "content": {"parts": [{"text": text}]},
            }
            for text in texts
        ]
    }
    try:
        response = _post_gemini_json(
            f"{base}/{model_path}:batchEmbedContents",
            api_key,
            payload,
        )
        embeddings = _parse_gemini_embeddings(response, len(texts))
        if embeddings:
            return embeddings
    except RuntimeError:
        if len(texts) > 1:
            return [
                embedding
                for text in texts
                for embedding in _embed_gemini_batch(base, model_path, api_key, [text])
            ]
        raise
    return [_embed_gemini_single(base, model_path, api_key, text) for text in texts]


def _embed_gemini_single(base: str, model_path: str, api_key: str, text: str) -> List[float]:
    response = _post_gemini_json(
        f"{base}/{model_path}:embedContent",
        api_key,
        {"content": {"parts": [{"text": text}]}},
    )
    embedding = response.get("embedding")
    if isinstance(embedding, dict) and isinstance(embedding.get("values"), list):
        return embedding["values"]
    embeddings = _parse_gemini_embeddings(response, 1)
    if embeddings:
        return embeddings[0]
    raise RuntimeError("Gemini embedding response did not include an embedding vector.")


def _parse_gemini_embeddings(response: dict, expected_count: int) -> List[List[float]]:
    embeddings = response.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != expected_count:
        return []
    vectors = []
    for item in embeddings:
        if not isinstance(item, dict) or not isinstance(item.get("values"), list):
            return []
        vectors.append(item["values"])
    return vectors


def _embed_ollama_batch(base: str, model: str, texts: List[str]) -> List[List[float]]:
    try:
        payload = _post_ollama_json(
            f"{base}/api/embed",
            {"model": model, "input": texts},
        )
        embeddings = payload.get("embeddings")
        if isinstance(embeddings, list) and len(embeddings) == len(texts):
            return embeddings
    except RuntimeError:
        if len(texts) > 1:
            return [
                embedding
                for text in texts
                for embedding in _embed_ollama_batch(base, model, [text])
            ]
        raise

    # Older Ollama versions expose only /api/embeddings for one prompt at a time.
    return [_embed_ollama_single(base, model, text) for text in texts]


def _embed_ollama_single(base: str, model: str, text: str) -> List[float]:
    try:
        payload = _post_ollama_json(
            f"{base}/api/embed",
            {"model": model, "input": text},
        )
        embeddings = payload.get("embeddings")
        if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
            return embeddings[0]
    except RuntimeError:
        pass

    payload = _post_ollama_json(
        f"{base}/api/embeddings",
        {"model": model, "prompt": text},
    )
    embedding = payload.get("embedding")
    if not isinstance(embedding, list):
        raise RuntimeError("Ollama embedding response did not include an embedding vector.")
    return embedding
