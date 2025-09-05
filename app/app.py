# app.py
from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()  # lit .env en local; en prod Scalingo: ignoré (vars lues depuis l'env)

import os
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Try Starlette first, fallback to Uvicorn (selon versions / stubs Pylance)
try:
    from starlette.middleware.proxy_headers import ProxyHeadersMiddleware  # type: ignore
except Exception:
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware  # type: ignore

from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler as fastapi_http_exception_handler

from app.web import templates
from app.routers import pages, search, authors, questions, answers, seo, forms, i18n
from app.i18n import I18nMiddleware


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
            
            if is_browser and not is_htmx:
                resp = templates.TemplateResponse("errors/timeout.html", {"request": request}, status_code=408)
                resp.headers["X-Robots-Tag"] = "noindex, nofollow"
                return resp
            else:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=408,
                    content={"detail": "Request timeout"}
                )




# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI()

# Middleware stack (executes in REVERSE order of addition)

# 1) I18n middleware (executes LAST - sees sessions)
app.add_middleware(I18nMiddleware)

# 2) Session middleware (executes BEFORE i18n - provides sessions)  
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production-very-important-security")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# 3) Other middlewares (execute BEFORE sessions)
app.add_middleware(SearchRobotsHeaderMiddleware)
app.add_middleware(TimeoutMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)

# 4) Proxy and security (execute FIRST)
app.add_middleware(ProxyHeadersMiddleware)
if IS_PROD:
    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(WwwRedirectMiddleware)
    
if IS_PROD:
    allowed_hosts = list(ALLOWED_HOSTS_BASE) + [f"*.{CANONICAL_HOST.split('.', 1)[1]}"]
else:
    allowed_hosts = ["*"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


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
app.include_router(forms.router)
app.include_router(seo.router)
app.include_router(i18n.router)

# -----------------------------------------------------------------------------
# Exception handlers
# -----------------------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    accepts = request.headers.get("accept", "")
    is_browser = ("text/html" in accepts) or ("*/*" in accepts)
    is_htmx = request.headers.get("hx-request") == "true"

    # Pages d'erreur personnalisées pour les navigateurs (pas HTMX)
    if is_browser and not is_htmx:
        if exc.status_code == 404:
            resp = templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)
            resp.headers["X-Robots-Tag"] = "noindex, follow"
            return resp
        elif exc.status_code == 500:
            resp = templates.TemplateResponse("errors/500.html", {"request": request}, status_code=500)
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
    if is_browser and not is_htmx:
        resp = templates.TemplateResponse("errors/500.html", {"request": request}, status_code=500)
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        return resp
    
    # JSON pour les API/HTMX
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

