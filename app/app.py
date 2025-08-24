# app.py
from __future__ import annotations

import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

# Try Starlette first, fallback to Uvicorn (selon versions / stubs Pylance)
try:
    from starlette.middleware.proxy_headers import ProxyHeadersMiddleware  # type: ignore
except Exception:
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware  # type: ignore

from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler as fastapi_http_exception_handler

from app.web import templates
from app.routers import pages, search, authors, questions, answers, seo

load_dotenv()  # lit .env en local; en prod Scalingo: ignoré (vars lues depuis l'env)

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

ENV = os.getenv("ENV", "dev").lower()           # "prod" en prod Scalingo
IS_PROD = ENV == "prod"

CANONICAL_HOST = os.getenv("CANONICAL_HOST", "www.cahierdedoleances.fr")

ALLOWED_HOSTS_BASE = {
    CANONICAL_HOST,
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "cahier-de-doleances.osc-fr1.scalingo.io",  # ajuste si besoin
}

log = logging.getLogger("uvicorn.error")

# -----------------------------------------------------------------------------
# Middleware de redirection vers le host canonique (ignore le port en local)
# -----------------------------------------------------------------------------
class WwwRedirectMiddleware(BaseHTTPMiddleware):
    """
    Redirige tout host ≠ CANONICAL_HOST vers le host canonique.
    Ignore les hôtes de dev / réseaux locaux. 308 pour préserver méthode/query.
    """
    async def dispatch(self, request: Request, call_next):
        # En dev, pas de redirection
        if not IS_PROD:
            return await call_next(request)

        host_header = request.headers.get("host", "")  # ex: '127.0.0.1:8000'
        hostname = (request.url.hostname or host_header.split(":", 1)[0]).lower()

        if not hostname:
            return await call_next(request)

        # Réseaux/dev => pas de redirection
        if hostname in ("localhost", "127.0.0.1") or hostname.endswith(".local") \
           or hostname.startswith("10.") or hostname.startswith("192.168."):
            return await call_next(request)

        # Autorisés explicitement ?
        if hostname == CANONICAL_HOST or hostname in ALLOWED_HOSTS_BASE:
            return await call_next(request)

        # Redirige vers l'hôte canonique (en https)
        new_url = request.url.replace(netloc=CANONICAL_HOST, scheme="https")
        return RedirectResponse(str(new_url), status_code=308)


class SearchRobotsHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        path = request.url.path

        if path.startswith("/search/"):
            p = (request.query_params.get("partial") or "").lower()
            is_partial = p in ("1", "true", "yes")
            tag = "noindex, nofollow" if is_partial else "noindex, follow"

            # Si déjà posé par le handler, on ne touche pas ; sinon on garantie l'en-tête (HEAD, etc.)
            if "X-Robots-Tag" not in resp.headers:
                resp.headers["X-Robots-Tag"] = tag
        return resp



# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI()

# 1) Faire confiance aux en-têtes du proxy (X-Forwarded-Proto/Host)
app.add_middleware(ProxyHeadersMiddleware)

# 2) Forcer HTTPS & host canonique uniquement en prod
if IS_PROD:
    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(WwwRedirectMiddleware)

# 3) TrustedHost : strict en prod, permissif en dev
if IS_PROD:
    allowed_hosts = list(ALLOWED_HOSTS_BASE) + [f"*.{CANONICAL_HOST.split('.', 1)[1]}"]
else:
    allowed_hosts = ["*"]  # plus simple pour le dev local

app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# 4) Compression (utile pour sitemap, listes, etc.)
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(SearchRobotsHeaderMiddleware)


# -----------------------------------------------------------------------------
# Static
# -----------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# -----------------------------------------------------------------------------
# Routers
# -----------------------------------------------------------------------------
app.include_router(pages.router)
app.include_router(search.router)
app.include_router(authors.router)
app.include_router(questions.router)
app.include_router(answers.router)
app.include_router(seo.router)

# -----------------------------------------------------------------------------
# 404 HTML (navigateur), JSON sinon (API/HTMX)
# -----------------------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    accepts = request.headers.get("accept", "")
    is_browser = ("text/html" in accepts) or ("*/*" in accepts)
    is_htmx = request.headers.get("hx-request") == "true"

    if exc.status_code == 404 and is_browser and not is_htmx:
        resp = templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)
        resp.headers["X-Robots-Tag"] = "noindex, follow"
        return resp

    return await fastapi_http_exception_handler(request, exc)
