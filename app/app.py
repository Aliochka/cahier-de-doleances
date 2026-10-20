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


class TransportProxyHeadersMiddleware(ProxyHeadersMiddleware):
    """Keep the socket peer before proxy processing; SSR is not a reverse proxy."""

    def __init__(self, app, *, trusted_hosts, ssr_http_client_ip):
        super().__init__(app, trusted_hosts=trusted_hosts)
        self.ssr_http_client_ip = ssr_http_client_ip

    async def __call__(self, scope, receive, send):
        if scope["type"] in {"http", "websocket"}:
            scope = dict(scope)
            client = scope.get("client")
            scope["cahier.transport_client"] = client
            # Ignore SSR forwarding headers even if an older .env.deploy still
            # lists its IP in TRUSTED_PROXY_IPS. Only its narrow HTTP API
            # exception below applies; it cannot claim to be an HTTPS proxy.
            if client and client[0] == self.ssr_http_client_ip:
                return await self.app(scope, receive, send)
        return await super().__call__(scope, receive, send)


class LocalHealthHTTPSRedirectMiddleware(HTTPSRedirectMiddleware):
    async def __call__(self, scope, receive, send):
        # Never identify an internal client from X-Forwarded-For: the proxy
        # middleware may already have rewritten scope["client"].
        client = scope.get("cahier.transport_client")
        local_health = (
            scope["type"] == "http"
            and scope.get("path") == "/healthz"
            and client
            and client[0] in {"127.0.0.1", "::1"}
        )
        internal_api = (
            scope["type"] == "http"
            and settings.SSR_HTTP_CLIENT_IP
            and client
            and client[0] == settings.SSR_HTTP_CLIENT_IP
            and scope.get("method") in {"GET", "HEAD"}
            and scope.get("path", "").startswith("/api/v1/")
            and [value for name, value in scope["headers"] if name == b"host"] == [b"app:8000"]
        )
        if local_health or internal_api:
            await self.app(scope, receive, send)
        else:
            await super().__call__(scope, receive, send)


# Proxy and security (execute FIRST)
if settings.ENFORCE_HTTPS:
    app.add_middleware(LocalHealthHTTPSRedirectMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS or ["*"])
app.add_middleware(AccountSecurityMiddleware)
# Added last, executed first: retain the socket peer, then resolve proxy scheme
# before account/host validation and HTTPS redirection.
app.add_middleware(
    TransportProxyHeadersMiddleware,
    trusted_hosts=settings.TRUSTED_PROXY_IPS,
    ssr_http_client_ip=settings.SSR_HTTP_CLIENT_IP,
)


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
