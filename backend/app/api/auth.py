"""Authentication and role authorization helpers."""
import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.api.rate_limit import check_ip_rate_limit, client_identifier, rate_limiter
from app.config import (
    ADMIN_PASSWORD,
    APP_ENV,
    AUTH_SECRET_KEY,
    AUTH_TOKEN_TTL_MINUTES,
    LOGIN_RATE_LIMIT_PER_MINUTE,
)


router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)
AUTH_COOKIE_NAME = "docuquery_session"
CSRF_COOKIE_NAME = "docuquery_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
UNSAFE_HTTP_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
COOKIE_SECURE = APP_ENV == "production"
COOKIE_SAMESITE = "lax"


class LoginRequest(BaseModel):
    role: Literal["user", "admin"]
    password: Optional[str] = None


@dataclass(frozen=True)
class AuthContext:
    role: str
    session_id: str


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_access_token(
    role: str,
    session_id: Optional[str] = None,
    expires_in_seconds: Optional[int] = None,
) -> str:
    payload = {
        "role": role,
        "session_id": session_id or uuid.uuid4().hex,
        "exp": int(time.time()) + (
            AUTH_TOKEN_TTL_MINUTES * 60
            if expires_in_seconds is None
            else expires_in_seconds
        ),
    }
    encoded_payload = _base64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signature = hmac.new(
        AUTH_SECRET_KEY.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_base64url_encode(signature)}"


def create_csrf_token(session_id: str) -> str:
    nonce = secrets.token_urlsafe(32)
    signature = hmac.new(
        AUTH_SECRET_KEY.encode("utf-8"),
        f"{session_id}:{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{nonce}.{_base64url_encode(signature)}"


def validate_csrf_token(session_id: str, token: Optional[str]) -> bool:
    if not token or "." not in token:
        return False
    nonce, supplied_signature = token.split(".", 1)
    expected_signature = hmac.new(
        AUTH_SECRET_KEY.encode("utf-8"),
        f"{session_id}:{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    try:
        decoded_signature = _base64url_decode(supplied_signature)
    except Exception:
        return False
    return hmac.compare_digest(expected_signature, decoded_signature)


def set_auth_cookies(response: Response, access_token: str, csrf_token: str) -> None:
    max_age = AUTH_TOKEN_TTL_MINUTES * 60
    response.set_cookie(
        AUTH_COOKIE_NAME,
        access_token,
        max_age=max_age,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )


def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=AUTH_TOKEN_TTL_MINUTES * 60,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME, httponly=True, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
    response.delete_cookie(CSRF_COOKIE_NAME, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)


def decode_access_token(token: str) -> AuthContext:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected_signature = hmac.new(
            AUTH_SECRET_KEY.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        supplied_signature = _base64url_decode(encoded_signature)

        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise ValueError("Invalid signature")

        payload = json.loads(_base64url_decode(encoded_payload))
        role = payload.get("role")
        session_id = payload.get("session_id")
        if role not in {"user", "admin"}:
            raise ValueError("Invalid role")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("Invalid session")
        if int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("Token expired")
        return AuthContext(role=role, session_id=session_id)
    except (ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )


def get_current_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthContext:
    if credentials and credentials.scheme.lower() == "bearer":
        return decode_access_token(credentials.credentials)

    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    if cookie_token:
        return decode_access_token(cookie_token)

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization required.",
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session.",
    )


def get_current_role(context: AuthContext = Depends(get_current_context)) -> str:
    return context.role


def require_admin(context: AuthContext = Depends(get_current_context)) -> AuthContext:
    if context.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: admin access required.",
        )
    return context


@router.post("/login")
async def login(login_request: LoginRequest, request: Request, response: Response):
    check_ip_rate_limit(request, "login", LOGIN_RATE_LIMIT_PER_MINUTE, 60)
    if login_request.role == "admin":
        client_host = client_identifier(request)
        rate_limit_key = f"admin-login:{client_host}"
        rate_limiter.check(rate_limit_key, LOGIN_RATE_LIMIT_PER_MINUTE, 60)
        if not hmac.compare_digest(login_request.password or "", ADMIN_PASSWORD):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin password.",
            )
        rate_limiter.reset(rate_limit_key)

    token = create_access_token(login_request.role)
    context = decode_access_token(token)
    csrf_token = create_csrf_token(context.session_id)
    set_auth_cookies(response, token, csrf_token)
    return {
        "status": "success",
        "role": login_request.role,
        "session_id": context.session_id,
        "csrf_token": csrf_token,
    }


@router.get("/me")
async def get_session(
    response: Response,
    context: AuthContext = Depends(get_current_context),
):
    csrf_token = create_csrf_token(context.session_id)
    set_csrf_cookie(response, csrf_token)
    return {
        "status": "success",
        "role": context.role,
        "session_id": context.session_id,
        "csrf_token": csrf_token,
    }


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"status": "success"}
