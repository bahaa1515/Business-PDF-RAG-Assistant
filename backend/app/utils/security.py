"""Security-oriented utility helpers."""
import re
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(api[_-]?key['\"\s:=]+)([A-Za-z0-9_\-\.]{8,})", re.IGNORECASE),
    re.compile(r"(authorization['\"\s:=]+bearer\s+)([A-Za-z0-9_\-\.]{8,})", re.IGNORECASE),
]


def redact_sensitive_text(value: Any) -> str:
    """Best-effort redaction for logs and error text."""
    text = str(value)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1) if match.lastindex and match.lastindex > 1 else ''}[REDACTED]", text)
    return text
