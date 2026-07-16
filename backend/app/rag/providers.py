"""
AI provider configuration for chat generation and embeddings.

The runtime uses the OpenAI Python SDK for OpenAI-compatible APIs. This keeps
the app provider-flexible without storing customer API keys in the browser.
"""
import os
from dataclasses import dataclass
from typing import Dict, Optional

from openai import OpenAI


DEFAULT_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

OPENAI_COMPATIBLE_BASE_URLS: Dict[str, Optional[str]] = {
    "openai": None,
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openai-compatible": None,
    "custom": None,
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "together": "https://api.together.xyz/v1",
    "deepseek": "https://api.deepseek.com",
    "xai": "https://api.x.ai/v1",
    "ollama": "http://localhost:11434/v1",
    "anthropic": None,
}

PROVIDER_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "together": "TOGETHER_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "xai": "XAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

PROVIDER_KEY_ENV_ALIASES = {
    "gemini": ("GOOGLE_API_KEY",),
}

LLM_PROVIDERS = set(OPENAI_COMPATIBLE_BASE_URLS)
EMBEDDING_PROVIDERS = set(OPENAI_COMPATIBLE_BASE_URLS) - {"anthropic"}

PROVIDER_MODEL_DEFAULTS = {
    "llm": {
        "openai": DEFAULT_CHAT_MODEL,
        "gemini": "gemini-2.5-flash",
        "anthropic": "claude-sonnet-4-5",
        "ollama": "qwen2.5:7b-instruct",
    },
    "embedding": {
        "openai": DEFAULT_EMBEDDING_MODEL,
        "gemini": "gemini-embedding-001",
        "ollama": "nomic-embed-text",
    },
}


@dataclass(frozen=True)
class AIProviderSettings:
    provider: str
    api_key: str
    model: str
    base_url: Optional[str] = None


def _normalize_provider(provider: Optional[str]) -> str:
    return (provider or "openai").strip().lower().replace("_", "-")


def _env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = _env(name)
        if value:
            return value
    return None


def _resolve_provider(service_prefix: str) -> str:
    if service_prefix == "LLM":
        return _normalize_provider(_first_env("LLM_PROVIDER", "AI_PROVIDER"))
    embedding_provider = _first_env("EMBEDDING_PROVIDER")
    if embedding_provider:
        return _normalize_provider(embedding_provider)
    inherited_provider = _normalize_provider(_first_env("LLM_PROVIDER", "AI_PROVIDER"))
    if inherited_provider == "anthropic":
        return "openai"
    return inherited_provider


def _provider_specific_key(provider: str) -> Optional[str]:
    env_name = PROVIDER_KEY_ENV.get(provider)
    if env_name:
        value = _env(env_name)
        if value:
            return value
    for alias in PROVIDER_KEY_ENV_ALIASES.get(provider, ()):
        value = _env(alias)
        if value:
            return value
    return None


def _resolve_api_key(service_prefix: str, provider: str) -> str:
    if provider == "ollama":
        return _first_env(f"{service_prefix}_API_KEY", "OLLAMA_API_KEY") or "ollama"

    key = _first_env(f"{service_prefix}_API_KEY")
    if not key:
        key = _provider_specific_key(provider)
    if not key and provider in {"openai", "openai-compatible", "custom"}:
        key = _first_env("OPENAI_API_KEY")
    if key:
        return key

    raise RuntimeError(
        f"{service_prefix}_API_KEY is required for provider '{provider}'. "
        "You may also use the provider-specific key environment variable."
    )


def _resolve_base_url(service_prefix: str, provider: str) -> Optional[str]:
    explicit_base_url = _first_env(f"{service_prefix}_BASE_URL", "AI_BASE_URL")
    if explicit_base_url:
        return explicit_base_url.rstrip("/")

    if provider not in OPENAI_COMPATIBLE_BASE_URLS:
        supported = ", ".join(sorted(OPENAI_COMPATIBLE_BASE_URLS))
        raise RuntimeError(f"Unsupported provider '{provider}'. Supported providers: {supported}")

    if service_prefix == "EMBEDDING" and provider not in EMBEDDING_PROVIDERS:
        raise RuntimeError("Anthropic Claude does not provide embeddings in this app; choose a separate embedding provider.")

    base_url = OPENAI_COMPATIBLE_BASE_URLS[provider]
    if provider in {"openai-compatible", "custom"} and not base_url:
        raise RuntimeError(f"{service_prefix}_BASE_URL is required for provider '{provider}'")
    return base_url


def _resolve_model(service_prefix: str, provider: str) -> str:
    if service_prefix == "LLM":
        return (
            _first_env("LLM_MODEL", "OPENAI_MODEL")
            or PROVIDER_MODEL_DEFAULTS["llm"].get(provider)
            or DEFAULT_CHAT_MODEL
        )
    return (
        _first_env("EMBEDDING_MODEL", "OPENAI_EMBEDDING_MODEL")
        or PROVIDER_MODEL_DEFAULTS["embedding"].get(provider)
        or DEFAULT_EMBEDDING_MODEL
    )


def _settings(service_prefix: str) -> AIProviderSettings:
    try:
        from app.services.provider_settings_service import load_runtime_provider_settings

        saved_settings = load_runtime_provider_settings(service_prefix)
    except ImportError:
        saved_settings = None

    if saved_settings:
        base_url = saved_settings.get("base_url") or None
        return AIProviderSettings(
            provider=saved_settings["provider"],
            api_key=saved_settings["api_key"],
            model=saved_settings["model"],
            base_url=base_url,
        )

    provider = _resolve_provider(service_prefix)
    return AIProviderSettings(
        provider=provider,
        api_key=_resolve_api_key(service_prefix, provider),
        model=_resolve_model(service_prefix, provider),
        base_url=_resolve_base_url(service_prefix, provider),
    )


def get_chat_settings() -> AIProviderSettings:
    """Resolve chat-generation provider settings from environment variables."""
    return _settings("LLM")


def get_embedding_settings() -> AIProviderSettings:
    """Resolve embedding provider settings from environment variables."""
    return _settings("EMBEDDING")


def create_openai_compatible_client(settings: AIProviderSettings) -> OpenAI:
    """Create an SDK client for OpenAI or an OpenAI-compatible provider."""
    kwargs = {"api_key": settings.api_key}
    if settings.base_url:
        kwargs["base_url"] = settings.base_url
    return OpenAI(**kwargs)


def get_chat_client() -> OpenAI:
    return create_openai_compatible_client(get_chat_settings())


def get_embedding_client() -> OpenAI:
    return create_openai_compatible_client(get_embedding_settings())
