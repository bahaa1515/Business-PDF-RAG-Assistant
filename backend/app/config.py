"""
Backend configuration.
Load from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://docuquery_user:docuquery_password@localhost:5433/docuquery"
)

# Qdrant
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION_NAME = "document_chunks"

# RAG Defaults
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_CHUNKING_STRATEGY = "auto"
DEFAULT_TOP_K = 5
DEFAULT_RETRIEVAL_METHOD = "similarity"
DEFAULT_RERANKER = "none"
DEFAULT_PROMPT_VARIANT = "grounded_complete"
DEFAULT_RETRIEVAL_PROFILE = "manual"
DEFAULT_BENCHMARK_SPLIT = "known"
SUPPORTED_RETRIEVAL_METHODS = {"similarity", "mmr", "hybrid"}
SUPPORTED_RERANKERS = {"none", "enabled"}
SUPPORTED_RETRIEVAL_PROFILES = {"manual", "auto"}
SUPPORTED_BENCHMARK_SPLITS = {"known", "holdout", "custom"}
SUPPORTED_CHUNKING_STRATEGIES = {"auto", "recursive", "structure", "table_rows"}
SUPPORTED_PROMPT_VARIANTS = {
    "baseline_strict",
    "grounded_complete",
    "policy_procedure",
    "multi_doc_synthesis",
}
MAX_TOP_K = int(os.getenv("MAX_TOP_K", 20))
MAX_OPTIMIZATION_CONFIGURATIONS = int(os.getenv("MAX_OPTIMIZATION_CONFIGURATIONS", 50))
MAX_FILE_SIZE_MB = 50

# Refusal message
REFUSAL_MESSAGE = "I could not find this information in the uploaded documents."

# API
API_TITLE = "DocuQuery AI"
API_VERSION = "1.0.0"
BACKEND_PORT = int(os.getenv("BACKEND_PORT", 8000))
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "change-this-development-secret")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
AUTH_TOKEN_TTL_MINUTES = int(os.getenv("AUTH_TOKEN_TTL_MINUTES", 480))
PROVIDER_SETTINGS_ENCRYPTION_KEY = os.getenv("PROVIDER_SETTINGS_ENCRYPTION_KEY", "").strip()
LOGIN_RATE_LIMIT_PER_MINUTE = int(os.getenv("LOGIN_RATE_LIMIT_PER_MINUTE", 5))
CHAT_RATE_LIMIT_PER_MINUTE = int(os.getenv("CHAT_RATE_LIMIT_PER_MINUTE", 20))
FEEDBACK_RATE_LIMIT_PER_MINUTE = int(os.getenv("FEEDBACK_RATE_LIMIT_PER_MINUTE", 20))
ADMIN_READ_RATE_LIMIT_PER_MINUTE = int(os.getenv("ADMIN_READ_RATE_LIMIT_PER_MINUTE", 60))
ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE = int(os.getenv("ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE", 20))
DOCUMENT_UPLOAD_RATE_LIMIT_PER_HOUR = int(os.getenv("DOCUMENT_UPLOAD_RATE_LIMIT_PER_HOUR", 20))
EVALUATION_RATE_LIMIT_PER_HOUR = int(os.getenv("EVALUATION_RATE_LIMIT_PER_HOUR", 10))
OPTIMIZATION_RATE_LIMIT_PER_HOUR = int(os.getenv("OPTIMIZATION_RATE_LIMIT_PER_HOUR", 5))
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").strip().lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "").strip()
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5174,http://localhost:5173,http://localhost:3000"
    ).split(",")
    if origin.strip()
]


def validate_security_configuration() -> None:
    """Fail fast when production authentication credentials are unsafe."""
    if APP_ENV != "production":
        return

    errors = []
    unsafe_auth_secrets = {
        "",
        "change-this-development-secret",
        "replace_with_a_long_random_secret",
        "secret",
        "changeme",
    }
    unsafe_admin_passwords = {
        "",
        "admin",
        "password",
        "changeme",
        "replace_with_a_secure_admin_password",
    }

    if AUTH_SECRET_KEY in unsafe_auth_secrets or len(AUTH_SECRET_KEY) < 32:
        errors.append("AUTH_SECRET_KEY must be a non-default value of at least 32 characters")
    if ADMIN_PASSWORD in unsafe_admin_passwords or len(ADMIN_PASSWORD) < 12:
        errors.append("ADMIN_PASSWORD must be a non-default value of at least 12 characters")
    if (
        PROVIDER_SETTINGS_ENCRYPTION_KEY in unsafe_auth_secrets
        or len(PROVIDER_SETTINGS_ENCRYPTION_KEY) < 32
    ):
        errors.append(
            "PROVIDER_SETTINGS_ENCRYPTION_KEY must be a non-default value of at least 32 characters"
        )
    if PROVIDER_SETTINGS_ENCRYPTION_KEY == AUTH_SECRET_KEY:
        errors.append("PROVIDER_SETTINGS_ENCRYPTION_KEY must be different from AUTH_SECRET_KEY")

    if errors:
        raise RuntimeError(
            "Unsafe production authentication configuration: " + "; ".join(errors)
        )


validate_security_configuration()
