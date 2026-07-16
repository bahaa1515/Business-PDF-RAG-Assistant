"""
FastAPI application entry point.
"""
import hmac

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.config import API_TITLE, API_VERSION, CORS_ORIGINS
from app.db.database import init_db
from app.api import health, documents, chat, evaluation, feedback, provider_settings
from app.api.auth import (
    AUTH_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    UNSAFE_HTTP_METHODS,
    decode_access_token,
    router as auth_router,
    validate_csrf_token,
)
from app.api.optimization import router as optimization_router

# Initialize database on startup
init_db()

# Create FastAPI app
app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description="Production-style RAG knowledge assistant API"
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def csrf_protection(request, call_next):
    """Require a signed double-submit CSRF token for cookie-authenticated writes."""
    if request.method in UNSAFE_HTTP_METHODS and request.url.path != "/auth/login":
        if not request.headers.get("authorization"):
            session_cookie = request.cookies.get(AUTH_COOKIE_NAME)
            if session_cookie:
                try:
                    context = decode_access_token(session_cookie)
                except Exception:
                    return await call_next(request)

                header_token = request.headers.get(CSRF_HEADER_NAME)
                cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
                if (
                    not header_token
                    or not cookie_token
                    or not hmac.compare_digest(header_token, cookie_token)
                    or not validate_csrf_token(context.session_id, header_token)
                ):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": {
                                "code": "csrf_failed",
                                "message": "CSRF token is missing or invalid.",
                            }
                        },
                    )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Cache-Control", "no-store")
    return response

# Include routers
app.include_router(health.router)
app.include_router(auth_router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(evaluation.router)
app.include_router(optimization_router)
app.include_router(feedback.router)
app.include_router(provider_settings.router)


@app.get("/")
async def root():
    """API root."""
    return {
        "title": API_TITLE,
        "version": API_VERSION,
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    from app.config import BACKEND_PORT

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=BACKEND_PORT,
        reload=True
    )
