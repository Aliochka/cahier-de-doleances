# app.py
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
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
from app.logging_filters import redact_access_logs
from app.routers import (
    answers,
    api_contributions,
    api_forms,
    api_questions,
    api_search,
    auth,
    authors,
    bookmarks,
    forms,
    health,
    pages,
    questions,
    search,
    seo,
)
from app.search_errors import SearchTimeout
from app.security import AccountSecurityMiddleware, private_response
from app.web import templates

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

log = logging.getLogger("uvicorn.error")


class SearchRobotsHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)

        path = request.url.path
        if path.startswith("/search/"):
            p = (request.query_params.get("partial") or "").lower()
            tag = "noindex, nofollow" if p in ("1", "true", "yes") else "noindex, follow"

            # supprime toute occurrence existante (casse-insensible), puis fixe une seule valeur
            for k in list(resp.headers.keys()):
                if k.lower() == "x-robots-tag":
                    del resp.headers[k]
            resp.headers["X-Robots-Tag"] = tag
        return resp


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Détecte les timeouts et affiche une page d'erreur personnalisée"""

    async def dispatch(self, request: Request, call_next):
        import asyncio

        try:
            # Timeout de 29 secondes (Scalingo timeout à 30s)
            resp = await asyncio.wait_for(call_next(request), timeout=29.0)
            return resp

        except asyncio.TimeoutError:
            # Timeout détecté - page personnalisée pour les navigateurs
            accepts = request.headers.get("accept", "")
            is_browser = ("text/html" in accepts) or ("*/*" in accepts)
            is_htmx = request.headers.get("hx-request") == "true"

            if is_browser and not is_htmx and not request.url.path.startswith("/api/v1/"):
                resp = templates.TemplateResponse(
                    request, "errors/timeout.html", {"request": request}, status_code=408
                )
                resp.headers["X-Robots-Tag"] = "noindex, nofollow"
                return resp
            else:
                from fastapi.responses import JSONResponse

                return JSONResponse(status_code=408, content={"detail": "Request timeout"})


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
redact_access_logs()
app = FastAPI(debug=False)

# Application middlewares
app.add_middleware(SearchRobotsHeaderMiddleware)
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
# Static
# -----------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# -----------------------------------------------------------------------------
# Routers
# -----------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(pages.router)
app.include_router(search.router)
app.include_router(authors.router)
app.include_router(questions.router)
app.include_router(answers.router)
app.include_router(forms.router)
app.include_router(api_forms.router)
app.include_router(api_questions.router)
app.include_router(api_search.router)
app.include_router(api_contributions.router)
app.include_router(seo.router)
app.include_router(auth.router)
app.include_router(bookmarks.router)


# -----------------------------------------------------------------------------
# Exception handlers
# -----------------------------------------------------------------------------
def search_error_response(request: Request, *, timeout: bool):
    from fastapi.responses import JSONResponse

    status = 504 if timeout else 500
    code = "search_timeout" if timeout else "search_failed"
    message = (
        "La recherche a dépassé son délai. Réessayez ou simplifiez votre recherche."
        if timeout
        else "La recherche a rencontré une erreur. Veuillez réessayer."
    )
    headers = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"}
    if request.url.path.startswith("/api/v1/"):
        return JSONResponse(
            {
                "detail": "Le délai de réponse a été dépassé."
                if timeout
                else "Internal server error"
            },
            status_code=status,
            headers=headers,
        )
    if request.headers.get("hx-request") == "true" or request.query_params.get("partial") in {
        "true",
        "1",
    }:
        headers.update(
            {
                "X-Search-Error": code,
                "HX-Retarget": "#search-error",
                "HX-Reswap": "innerHTML",
                "HX-Push-Url": "false",
            }
        )
        return templates.TemplateResponse(
            request, "errors/search.html", {"message": message}, status_code=status, headers=headers
        )
    accepts = request.headers.get("accept", "")
    if "text/html" in accepts or "*/*" in accepts:
        name = "errors/timeout.html" if timeout else "errors/500.html"
        return templates.TemplateResponse(request, name, {}, status_code=status, headers=headers)
    return JSONResponse({"detail": message, "code": code}, status_code=status, headers=headers)


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
    if request.url.path in {"/search/answers", "/search/questions"}:
        log.error("Database search failed", exc_info=exc)
        return search_error_response(request, timeout=False)
    return await general_exception_handler(request, exc)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    accepts = request.headers.get("accept", "")
    is_browser = ("text/html" in accepts) or ("*/*" in accepts)
    is_htmx = request.headers.get("hx-request") == "true"

    if request.url.path.startswith("/api/v1/"):
        return await fastapi_http_exception_handler(request, exc)

    # Pages d'erreur personnalisées pour les navigateurs (pas HTMX)
    if is_browser and not is_htmx:
        if exc.status_code == 404:
            resp = templates.TemplateResponse(
                request, "errors/404.html", {"request": request}, status_code=404
            )
            resp.headers["X-Robots-Tag"] = "noindex, follow"
            return resp
        elif exc.status_code == 500:
            resp = templates.TemplateResponse(
                request, "errors/500.html", {"request": request}, status_code=500
            )
            resp.headers["X-Robots-Tag"] = "noindex, nofollow"
            return resp

    return await fastapi_http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handler pour toutes les autres exceptions (500)"""
    accepts = request.headers.get("accept", "")
    is_browser = ("text/html" in accepts) or ("*/*" in accepts)
    is_htmx = request.headers.get("hx-request") == "true"

    # Log de l'erreur pour debugging
    log.error(f"Unhandled exception: {exc}", exc_info=True)

    # Page d'erreur personnalisée pour les navigateurs
    if is_browser and not is_htmx and not request.url.path.startswith("/api/v1/"):
        resp = templates.TemplateResponse(
            request, "errors/500.html", {"request": request}, status_code=500
        )
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        return private_response(request, resp)

    # JSON pour les API/HTMX
    from fastapi.responses import JSONResponse

    return private_response(
        request, JSONResponse(status_code=500, content={"detail": "Internal server error"})
    )
