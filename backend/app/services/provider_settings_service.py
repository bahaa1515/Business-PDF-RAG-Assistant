"""Encrypted storage for admin-managed AI provider settings."""
import base64
import hashlib
import logging
import os
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover - exercised only when local deps are stale
    Fernet = None

    class InvalidToken(Exception):
        pass

from app.config import (
    APP_ENV,
    AUTH_SECRET_KEY,
    PROVIDER_SETTINGS_ENCRYPTION_KEY,
)
from app.db.database import SessionLocal
from app.db.models import Document, ProviderSetting
from app.rag.providers import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_PROVIDERS,
    LLM_PROVIDERS,
    OPENAI_COMPATIBLE_BASE_URLS,
    PROVIDER_KEY_ENV,
    PROVIDER_KEY_ENV_ALIASES,
    PROVIDER_MODEL_DEFAULTS,
)
from app.utils.security import redact_sensitive_text


SERVICE_PREFIXES = {"llm": "LLM", "embedding": "EMBEDDING"}
MASKED_SECRET = "********"
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9._:/+-]{1,255}$")
logger = logging.getLogger("app.security.provider_settings")


class ProviderSettingsError(ValueError):
    """Raised for invalid admin provider settings."""


def _encryption_material() -> str:
    # Development fallback keeps local demos usable. Production validation requires
    # a separate PROVIDER_SETTINGS_ENCRYPTION_KEY.
    return PROVIDER_SETTINGS_ENCRYPTION_KEY or AUTH_SECRET_KEY


def _fernet() -> Fernet:
    if Fernet is None:
        raise RuntimeError(
            "The cryptography package is required to store provider API keys securely. "
            "Install backend requirements before saving AI settings."
        )
    digest = hashlib.sha256(_encryption_material().encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_secret(encrypted_secret: str) -> str:
    try:
        return _fernet().decrypt(encrypted_secret.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored provider API key cannot be decrypted.") from exc


def fingerprint_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _normalize_service(service_name: str) -> str:
    normalized = (service_name or "").strip().lower()
    if normalized not in SERVICE_PREFIXES:
        raise ProviderSettingsError("Unsupported provider service.")
    return normalized


def _normalize_provider(provider: str, service_name: Optional[str] = None) -> str:
    normalized = (provider or "").strip().lower().replace("_", "-")
    if normalized not in OPENAI_COMPATIBLE_BASE_URLS:
        supported = ", ".join(sorted(OPENAI_COMPATIBLE_BASE_URLS))
        raise ProviderSettingsError(f"Unsupported provider. Supported providers: {supported}.")
    if service_name == "embedding" and normalized not in EMBEDDING_PROVIDERS:
        raise ProviderSettingsError(
            "Anthropic Claude is an LLM provider only. Choose a separate embedding provider."
        )
    if service_name == "llm" and normalized not in LLM_PROVIDERS:
        raise ProviderSettingsError("Unsupported LLM provider.")
    return normalized


def _validate_model(model: str) -> str:
    value = (model or "").strip()
    if not value:
        raise ProviderSettingsError("Model is required.")
    if not MODEL_PATTERN.match(value):
        raise ProviderSettingsError(
            "Model may only contain letters, numbers, dots, underscores, dashes, colons, slashes, and plus signs."
        )
    return value


def _validate_base_url(provider: str, base_url: Optional[str]) -> Optional[str]:
    value = (base_url or "").strip().rstrip("/")
    if provider not in {"custom", "openai-compatible"}:
        if value:
            raise ProviderSettingsError(
                "Custom base URLs are only allowed for custom or openai-compatible providers."
            )
        return None

    if not value:
        raise ProviderSettingsError("Base URL is required for custom providers.")

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ProviderSettingsError("Base URL must be a valid HTTP(S) URL.")
    if parsed.username or parsed.password:
        raise ProviderSettingsError("Base URL must not contain embedded credentials.")
    if APP_ENV == "production" and parsed.scheme != "https":
        raise ProviderSettingsError("Production custom provider URLs must use HTTPS.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ProviderSettingsError("Plain HTTP custom provider URLs are only allowed for localhost.")
    return value


def _validate_api_key(api_key: str) -> str:
    value = (api_key or "").strip()
    if not value:
        raise ProviderSettingsError("API key cannot be blank.")
    if value == MASKED_SECRET or set(value) == {"*"}:
        raise ProviderSettingsError("Masked placeholders cannot be saved as API keys.")
    if len(value) > 4096:
        raise ProviderSettingsError("API key is too long.")
    return value


def _env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _env_provider(service_name: str) -> str:
    service_prefix = SERVICE_PREFIXES[service_name]
    if service_prefix == "LLM":
        return (_env("LLM_PROVIDER") or _env("AI_PROVIDER") or "openai").lower().replace("_", "-")
    explicit = _env("EMBEDDING_PROVIDER")
    if explicit:
        return explicit.lower().replace("_", "-")
    inherited = (_env("LLM_PROVIDER") or _env("AI_PROVIDER") or "").lower().replace("_", "-")
    return inherited if inherited and inherited != "anthropic" else "openai"


def _env_model(service_name: str) -> str:
    provider = _normalize_provider(_env_provider(service_name), service_name)
    if service_name == "llm":
        return (
            _env("LLM_MODEL")
            or _env("OPENAI_MODEL")
            or PROVIDER_MODEL_DEFAULTS["llm"].get(provider)
            or DEFAULT_CHAT_MODEL
        )
    return (
        _env("EMBEDDING_MODEL")
        or _env("OPENAI_EMBEDDING_MODEL")
        or PROVIDER_MODEL_DEFAULTS["embedding"].get(provider)
        or DEFAULT_EMBEDDING_MODEL
    )


def _env_base_url(service_name: str, provider: str) -> Optional[str]:
    service_prefix = SERVICE_PREFIXES[service_name]
    explicit = _env(f"{service_prefix}_BASE_URL") or _env("AI_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    return OPENAI_COMPATIBLE_BASE_URLS.get(provider)


def _env_api_key_set(service_name: str, provider: str) -> bool:
    return _env_api_key(service_name, provider) is not None


def _env_api_key(service_name: str, provider: str) -> Optional[str]:
    service_prefix = SERVICE_PREFIXES[service_name]
    service_key = _env(f"{service_prefix}_API_KEY")
    if service_key:
        return service_key
    provider_env = PROVIDER_KEY_ENV.get(provider)
    provider_key = _env(provider_env) if provider_env else None
    if provider_key:
        return provider_key
    for alias in PROVIDER_KEY_ENV_ALIASES.get(provider, ()):
        provider_key = _env(alias)
        if provider_key:
            return provider_key
    if provider in {"openai", "openai-compatible", "custom"} and _env("OPENAI_API_KEY"):
        return _env("OPENAI_API_KEY")
    return None


class ProviderSettingsService:
    """Read and update encrypted provider settings."""

    def __init__(self, db: Session):
        self.db = db

    def get_public_settings(self) -> Dict[str, Any]:
        return {
            "provider_options": sorted(OPENAI_COMPATIBLE_BASE_URLS),
            "service_provider_options": {
                "llm": sorted(LLM_PROVIDERS),
                "embedding": sorted(EMBEDDING_PROVIDERS),
            },
            "provider_model_defaults": PROVIDER_MODEL_DEFAULTS,
            "llm": self._public_for("llm"),
            "embedding": self._public_for("embedding"),
        }

    def update_settings(
        self,
        payload: Dict[str, Any],
        audit_context: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        audit_events = []
        for service_name in ("llm", "embedding"):
            if service_name in payload and payload[service_name] is not None:
                audit_events.append(self._upsert(service_name, payload[service_name]))
        self.db.commit()
        for event in audit_events:
            _audit_provider_settings_change(event, audit_context or {})
        public = self.get_public_settings()
        public["reindex_required"] = any(event.get("reindex_required") for event in audit_events)
        return public

    def _public_for(self, service_name: str) -> Dict[str, Any]:
        row = self._get_row(service_name)
        env_provider = _normalize_provider(_env_provider(service_name), service_name)
        provider = row.provider if row else env_provider
        model = row.model if row else _env_model(service_name)
        base_url = row.base_url if row and row.base_url else _env_base_url(service_name, provider)
        requires_api_key = provider != "ollama"
        saved_key_set = bool(row and row.encrypted_api_key)
        api_key_set = saved_key_set or (requires_api_key and _env_api_key_set(service_name, provider))
        source = "saved" if row else "environment"
        return {
            "provider": provider,
            "model": model,
            "base_url": base_url or "",
            "requires_api_key": requires_api_key,
            "api_key_set": api_key_set,
            "api_key_display": MASKED_SECRET if api_key_set else "",
            "source": source,
            "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        }

    def _upsert(self, service_name: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        service_name = _normalize_service(service_name)
        provider = _normalize_provider(settings.get("provider", ""), service_name)
        model = _validate_model(settings.get("model", ""))
        base_url = _validate_base_url(provider, settings.get("base_url"))
        api_key = settings.get("api_key")
        clear_api_key = bool(settings.get("clear_api_key", False))

        if provider == "ollama":
            clear_api_key = True
            api_key = None

        row = self._get_row(service_name)
        previous_provider = row.provider if row else _normalize_provider(_env_provider(service_name), service_name)
        previous_base_url = row.base_url if row else _env_base_url(service_name, previous_provider)
        previous_model = row.model if row else _env_model(service_name)
        had_saved_key = bool(row and row.encrypted_api_key)
        if not row:
            row = ProviderSetting(service_name=service_name)
            self.db.add(row)

        provider_changed = bool(previous_provider != provider)
        base_url_changed = bool((previous_base_url or "") != (base_url or ""))
        model_changed = bool(previous_model and previous_model != model)
        if (
            had_saved_key
            and (provider_changed or base_url_changed)
            and not clear_api_key
            and not (api_key is not None and api_key != "")
        ):
            raise ProviderSettingsError(
                "Changing provider or base URL requires re-entering the API key or explicitly clearing it."
            )

        row.provider = provider
        row.model = model
        row.base_url = base_url

        key_action = "unchanged"
        if clear_api_key:
            row.encrypted_api_key = None
            row.api_key_fingerprint = None
            key_action = "cleared" if had_saved_key else "clear_requested"
        elif api_key is not None and api_key != "":
            normalized_key = _validate_api_key(api_key)
            row.encrypted_api_key = encrypt_secret(normalized_key)
            row.api_key_fingerprint = fingerprint_secret(normalized_key)
            key_action = "replaced" if had_saved_key else "added"
        elif not row.encrypted_api_key and provider != "ollama" and not _env_api_key_set(service_name, provider):
            raise ProviderSettingsError("API key is required unless one is already configured in the environment.")

        reindex_required = False
        if service_name == "embedding" and (provider_changed or base_url_changed or model_changed):
            reindex_required = self._mark_documents_needing_reindex()

        return {
            "service_name": service_name,
            "provider": provider,
            "provider_changed": provider_changed,
            "base_url_changed": base_url_changed,
            "model_changed": model_changed,
            "key_action": key_action,
            "reindex_required": reindex_required,
        }

    def _get_row(self, service_name: str) -> Optional[ProviderSetting]:
        return (
            self.db.query(ProviderSetting)
            .filter(ProviderSetting.service_name == service_name)
            .first()
        )

    def _mark_documents_needing_reindex(self) -> bool:
        documents = self.db.query(Document).filter(Document.status == "indexed").all()
        for document in documents:
            document.status = "needs_reindex"
        return bool(documents)


def _audit_provider_settings_change(event: Dict[str, Any], audit_context: Dict[str, str]) -> None:
    logger.info(
        redact_sensitive_text(
            {
                "event": "provider_settings_changed",
                "service": event["service_name"],
                "provider": event["provider"],
                "provider_changed": event["provider_changed"],
                "base_url_changed": event["base_url_changed"],
                "model_changed": event.get("model_changed", False),
                "key_action": event["key_action"],
                "reindex_required": event.get("reindex_required", False),
                "admin_session": audit_context.get("admin_session", "unknown"),
                "client_ip": audit_context.get("client_ip", "unknown"),
            }
        )
    )


def load_runtime_provider_settings(service_prefix: str) -> Optional[Dict[str, str]]:
    """Return decrypted saved settings for provider clients, or None for env fallback."""
    service_name = "llm" if service_prefix == "LLM" else "embedding"
    db = SessionLocal()
    try:
        row = (
            db.query(ProviderSetting)
            .filter(ProviderSetting.service_name == service_name)
            .first()
        )
        if not row:
            return None
        provider = _normalize_provider(row.provider, service_name)
        if provider == "ollama":
            api_key = "ollama"
        elif row.encrypted_api_key:
            api_key = decrypt_secret(row.encrypted_api_key)
        elif _env_api_key(service_name, provider):
            api_key = _env_api_key(service_name, provider)
        else:
            return None
        return {
            "provider": provider,
            "api_key": api_key,
            "model": row.model,
            "base_url": row.base_url or _env_base_url(service_name, provider) or "",
        }
    except SQLAlchemyError:
        return None
    finally:
        db.close()
