"""Small in-memory rate limiter for single-instance deployments."""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException

from app.config import REDIS_URL, TRUST_PROXY_HEADERS

try:
    import redis
except ImportError:  # pragma: no cover - only relevant when REDIS_URL is configured
    redis = None


class InMemoryRateLimiter:
    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if len(events) >= limit:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "rate_limit_exceeded",
                        "message": "Too many requests. Please wait and try again.",
                    },
                )
            events.append(now)

    def reset(self, key: str) -> None:
        """Clear recorded attempts after a successful protected action."""
        with self._lock:
            self._events.pop(key, None)


class RedisRateLimiter:
    """Redis-backed limiter for multi-instance deployments."""

    def __init__(self, redis_url: str):
        if redis is None:
            raise RuntimeError("REDIS_URL is set but the redis package is not installed.")
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        redis_key = f"docuquery:rate-limit:{key}"
        count = int(self.client.incr(redis_key))
        if count == 1:
            self.client.expire(redis_key, window_seconds)
        if count > limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "rate_limit_exceeded",
                    "message": "Too many requests. Please wait and try again.",
                },
            )

    def reset(self, key: str) -> None:
        self.client.delete(f"docuquery:rate-limit:{key}")


rate_limiter = RedisRateLimiter(REDIS_URL) if REDIS_URL else InMemoryRateLimiter()


def client_identifier(request) -> str:
    """Return a best-effort client identifier for coarse rate limiting."""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if TRUST_PROXY_HEADERS and forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def check_ip_rate_limit(request, prefix: str, limit: int, window_seconds: int) -> None:
    rate_limiter.check(
        f"{prefix}:ip:{client_identifier(request)}",
        limit,
        window_seconds,
    )


def check_session_rate_limit(context, prefix: str, limit: int, window_seconds: int) -> None:
    rate_limiter.check(
        f"{prefix}:session:{context.session_id}",
        limit,
        window_seconds,
    )
