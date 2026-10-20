# app.py
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import DBAPIError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

# Try Starlette first, fallback to Uvicorn (selon versions / stubs Pylance)
try:
    from starlette.middleware.proxy_headers import ProxyHeadersMiddleware  # type: ignore
except Exception:
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware  # type: ignore

from fastapi.exception_handlers import http_exception_handler as fastapi_http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.hybrid_runtime import lifespan
from app.logging_filters import redact_access_logs
from app.routers import (
    api_contributions,
    api_forms,
    api_hybrid_search,
    api_questions,
    auth,
    bookmarks,
    health,
    seo,
)
from app.search_errors import SearchTimeout
from app.security import AccountSecurityMiddleware, private_response

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

log = logging.getLogger("uvicorn.error")


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Return a JSON error when a request times out"""

    async def dispatch(self, request: Request, call_next):
        import asyncio

        try:
            # Timeout de 29 secondes (Scalingo timeout à 30s)
            resp = await asyncio.wait_for(call_next(request), timeout=29.0)
            return resp

        except asyncio.TimeoutError:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=408, content={"detail": "Request timeout"})


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
redact_access_logs()
app = FastAPI(debug=False, lifespan=lifespan)

# Application middlewares
app.add_middleware(TimeoutMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)


class LocalHealthHTTPSRedirectMiddleware(HTTPSRedirectMiddleware):
    async def __call__(self, scope, receive, send):
        # Only the container's loopback readiness probe may use plain HTTP.
        client = scope.get("client")
        if (
            scope["type"] == "http"
            and scope.get("path") == "/healthz"
            and client
            and client[0] in {"127.0.0.1", "::1"}
        ):
            await self.app(scope, receive, send)
        else:
            await super().__call__(scope, receive, send)


# Proxy and security (execute FIRST)
if settings.ENFORCE_HTTPS:
    app.add_middleware(LocalHealthHTTPSRedirectMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS or ["*"])
app.add_middleware(AccountSecurityMiddleware)
# Added last, executed first: scheme must be resolved before HTTPS redirection.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=settings.TRUSTED_PROXY_IPS)


# -----------------------------------------------------------------------------
# Routers
# -----------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(api_forms.router)
app.include_router(api_questions.router)
app.include_router(api_hybrid_search.router)
app.include_router(api_contributions.router)
app.include_router(seo.router)
app.include_router(auth.router)
app.include_router(bookmarks.router)


# -----------------------------------------------------------------------------
# Exception handlers
# -----------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path == "/api/v1/search":
        return api_hybrid_search.failure(
            request, 422, "invalid_query", "Requête ou curseur invalide."
        )
    return await request_validation_exception_handler(request, exc)


def search_error_response(request: Request, *, timeout: bool):
    from fastapi.responses import JSONResponse

    status = 504 if timeout else 500
    return JSONResponse(
        {"detail": "Le délai de réponse a été dépassé." if timeout else "Internal server error"},
        status_code=status,
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
    )


@app.exception_handler(SearchTimeout)
async def search_timeout_handler(request: Request, exc: SearchTimeout):
    return search_error_response(request, timeout=True)


@app.exception_handler(DBAPIError)
async def database_exception_handler(request: Request, exc: DBAPIError):
    if request.url.path.startswith("/api/v1/"):
        from fastapi.responses import JSONResponse
        from sqlalchemy.exc import OperationalError

        status = 503 if isinstance(exc, OperationalError) else 500
        log.error("Public API database failure", exc_info=exc)
        return private_response(
            request,
            JSONResponse(
                {"detail": "Service indisponible" if status == 503 else "Internal server error"},
                status_code=status,
                headers={"Cache-Control": "no-store"},
            ),
        )
    return await general_exception_handler(request, exc)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return await fastapi_http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handler pour toutes les autres exceptions (500)"""
    log.error(f"Unhandled exception: {exc}", exc_info=True)

    from fastapi.responses import JSONResponse

    return private_response(
        request, JSONResponse(status_code=500, content={"detail": "Internal server error"})
    )
