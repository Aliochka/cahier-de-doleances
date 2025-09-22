# app/routers/seo.py
from __future__ import annotations

import os
import hashlib
import tempfile
import asyncio
import logging
import time
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse, Response, FileResponse
from sqlalchemy import text
from datetime import datetime, timezone
from app.helpers import slugify, clean_text_excerpt  # type: ignore

from app.db import SessionLocal

router = APIRouter()

@router.get("/og/test", name="og_test")
async def og_test():
    """Test endpoint pour diagnostiquer Playwright"""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            # Tenter de lancer Chromium
            browser = await p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
            await browser.close()

            return {"status": "success", "message": "Playwright et Chromium fonctionnent correctement"}

    except ImportError as e:
        return {"status": "error", "message": f"Playwright non installé: {str(e)}"}
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"Erreur Playwright: {str(e)}",
            "traceback": traceback.format_exc()
        }

# Limites (prudents pour la perf)
SITEMAP_LIMIT_QUESTIONS = 2000
SITEMAP_LIMIT_AUTHORS   = 1000
SITEMAP_LIMIT_FORMS     = 50

CACHE_ROBOTS = "public, max-age=86400"
CACHE_SITEMAP = "public, max-age=21600"
CACHE_OG_IMAGE = "public, max-age=604800"  # 1 semaine

# Cache en mémoire pour le sitemap
_sitemap_cache = {
    "xml": None,
    "timestamp": None,
    "ttl": 1800  # 30 minutes
}

# Configuration pour la génération d'images OG
OG_CACHE_DIR = Path(os.getenv("OG_CACHE_DIR", tempfile.gettempdir())) / "og_cache"
OG_CACHE_DIR.mkdir(exist_ok=True, parents=True)

# Configuration d'urgence : désactiver la génération d'images OG
OG_GENERATION_ENABLED = os.getenv("OG_GENERATION_ENABLED", "false").lower() == "true"

# Circuit breaker pour éviter les tentatives répétées
_circuit_breaker = {
    "failures": 0,
    "last_failure": None,
    "max_failures": 3,
    "cooldown_seconds": 300  # 5 minutes
}

def _is_circuit_open() -> bool:
    """Vérifie si le circuit breaker est ouvert"""
    if _circuit_breaker["failures"] >= _circuit_breaker["max_failures"]:
        if _circuit_breaker["last_failure"]:
            elapsed = time.time() - _circuit_breaker["last_failure"]
            if elapsed < _circuit_breaker["cooldown_seconds"]:
                return True
            else:
                # Reset le circuit breaker après le cooldown
                _circuit_breaker["failures"] = 0
                _circuit_breaker["last_failure"] = None
    return False

def _record_failure():
    """Enregistre un échec pour le circuit breaker"""
    _circuit_breaker["failures"] += 1
    _circuit_breaker["last_failure"] = time.time()

def _record_success():
    """Reset le circuit breaker après un succès"""
    _circuit_breaker["failures"] = 0
    _circuit_breaker["last_failure"] = None

# Logger spécialisé pour les images OG
logger = logging.getLogger("og_images")

def _fmt_iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    # force ISO8601 avec timezone si absente
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

@router.api_route("/robots.txt", methods=["GET", "HEAD"], name="robots_txt")
def robots_txt(request: Request):
    # construit l'URL absolue du sitemap
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    netloc = request.headers.get("x-forwarded-host") or request.url.netloc
    base = f"{scheme}://{netloc}"
    body = f"""User-agent: *
Allow: /
Sitemap: {base}/sitemap.xml
"""
    if request.method == "HEAD":
        return Response(status_code=200, headers={"Cache-Control": CACHE_ROBOTS}, media_type="text/plain; charset=utf-8")
    return PlainTextResponse(body, headers={"Cache-Control": CACHE_ROBOTS})

def _generate_sitemap_xml(base_url: str) -> str:
    """Génère le XML du sitemap (fonction cachée)"""
    urls: list[tuple[str, str | None]] = []

    with SessionLocal() as db:
        # lastmod global (homepage) = dernière contribution
        home_lastmod = db.execute(text("SELECT MAX(submitted_at) FROM contributions")).scalar()
        urls.append((f"{base_url}/", _fmt_iso(home_lastmod)))

        # Pages de recherche principales
        urls.append((f"{base_url}/search/questions", _fmt_iso(home_lastmod)))
        urls.append((f"{base_url}/search/answers", _fmt_iso(home_lastmod)))

        # Questions - utilise l'ancienne requête qui marche
        q_rows = db.execute(text("""
            SELECT q.id, q.prompt, MAX(c.submitted_at) AS lastmod
            FROM questions q
            JOIN answers a       ON a.question_id = q.id
            JOIN contributions c ON c.id = a.contribution_id
            WHERE a.text IS NOT NULL
            GROUP BY q.id, q.prompt
            ORDER BY lastmod DESC NULLS LAST, q.id DESC
            LIMIT :lim
        """), {"lim": 500}).mappings().all()

        for r in q_rows:
            qslug = slugify(r["prompt"] or f"question-{r['id']}")
            urls.append((f"{base_url}/questions/{r['id']}-{qslug}", _fmt_iso(r["lastmod"])))

        # Auteurs - ancienne requête qui marche
        a_rows = db.execute(text("""
            SELECT au.id, au.name, MAX(c.submitted_at) AS lastmod
            FROM authors au
            JOIN contributions c ON c.author_id = au.id
            JOIN answers a       ON a.contribution_id = c.id
            WHERE a.text IS NOT NULL
            GROUP BY au.id, au.name
            ORDER BY lastmod DESC NULLS LAST, au.id DESC
            LIMIT :lim
        """), {"lim": 300}).mappings().all()

        for r in a_rows:
            name = r["name"] or f"Auteur #{r['id']}"
            aslug = slugify(name)
            urls.append((f"{base_url}/authors/{r['id']}-{aslug}", _fmt_iso(r["lastmod"])))

        # Formulaires - ancienne requête qui marche
        f_rows = db.execute(text("""
            SELECT f.id, f.name, MAX(c.submitted_at) AS lastmod
            FROM forms f
            JOIN questions q ON q.form_id = f.id
            JOIN answers a ON a.question_id = q.id
            JOIN contributions c ON c.id = a.contribution_id
            WHERE a.text IS NOT NULL
            GROUP BY f.id, f.name
            ORDER BY lastmod DESC NULLS LAST, f.id DESC
            LIMIT :lim
        """), {"lim": SITEMAP_LIMIT_FORMS}).mappings().all()

        for r in f_rows:
            urls.append((f"{base_url}/forms/{r['id']}", _fmt_iso(r["lastmod"])))

    # Génère XML
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod in urls:
        parts.append("<url>")
        parts.append(f"<loc>{loc}</loc>")
        if lastmod:
            parts.append(f"<lastmod>{lastmod}</lastmod>")
        parts.append("</url>")
    parts.append("</urlset>")

    return "\n".join(parts)

@router.api_route("/sitemap.xml", methods=["GET", "HEAD"], name="sitemap_xml")
def sitemap_xml(request: Request):
    if request.method == "HEAD":
        return Response(status_code=200, headers={"Cache-Control": CACHE_SITEMAP}, media_type="application/xml; charset=utf-8")

    # Vérifier le cache d'abord
    current_time = time.time()
    if (_sitemap_cache["xml"] is not None and
        _sitemap_cache["timestamp"] is not None and
        current_time - _sitemap_cache["timestamp"] < _sitemap_cache["ttl"]):
        # Retourner depuis le cache
        return Response(
            content=_sitemap_cache["xml"],
            media_type="application/xml; charset=utf-8",
            headers={"Cache-Control": CACHE_SITEMAP, "X-Cache": "HIT"},
        )

    # Générer le sitemap
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    netloc = request.headers.get("x-forwarded-host") or request.url.netloc
    base_url = f"{scheme}://{netloc}"

    try:
        xml = _generate_sitemap_xml(base_url)

        # Mettre en cache
        _sitemap_cache["xml"] = xml
        _sitemap_cache["timestamp"] = current_time

        return Response(
            content=xml,
            media_type="application/xml; charset=utf-8",
            headers={"Cache-Control": CACHE_SITEMAP, "X-Cache": "MISS"},
        )
    except Exception as e:
        logger.error(f"Erreur génération sitemap: {str(e)}")
        # Fallback basique si erreur
        fallback_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>{base_url}/</loc></url>
</urlset>'''
        return Response(
            content=fallback_xml,
            media_type="application/xml; charset=utf-8",
            headers={"Cache-Control": "no-cache"},
        )

@router.get("/sitemap/clear-cache", name="sitemap_clear_cache")
def clear_sitemap_cache():
    """Vide le cache du sitemap (utile pour forcer la régénération)"""
    _sitemap_cache["xml"] = None
    _sitemap_cache["timestamp"] = None
    return {"status": "success", "message": "Cache du sitemap vidé"}

# =====================================
# IMAGES OG - DÉSACTIVÉES TEMPORAIREMENT
# =====================================

@router.get("/og/answer/{answer_id}.png", name="og_answer_image")
async def og_answer_image(answer_id: int):
    """Images OG temporairement désactivées pour économiser les ressources"""
    logger.info(f"Génération d'images OG désactivée (answer {answer_id})")
    raise HTTPException(status_code=503, detail="Génération d'images temporairement désactivée pour maintenance")

@router.get("/og/question/{question_id}.png", name="og_question_image")
async def og_question_image(question_id: int):
    """Images OG temporairement désactivées pour économiser les ressources"""
    logger.info(f"Génération d'images OG désactivée (question {question_id})")
    raise HTTPException(status_code=503, detail="Génération d'images temporairement désactivée pour maintenance")

@router.get("/og/form/{form_id}.png", name="og_form_image")
async def og_form_image(form_id: int):
    """Images OG temporairement désactivées pour économiser les ressources"""
    logger.info(f"Génération d'images OG désactivée (form {form_id})")
    raise HTTPException(status_code=503, detail="Génération d'images temporairement désactivée pour maintenance")

@router.get("/og/status", name="og_status")
def og_status():
    """Status des images OG et du circuit breaker"""
    return {
        "generation_enabled": OG_GENERATION_ENABLED,
        "circuit_breaker": {
            "failures": _circuit_breaker["failures"],
            "is_open": _is_circuit_open(),
            "cooldown_remaining": max(0, _circuit_breaker["cooldown_seconds"] - (time.time() - (_circuit_breaker["last_failure"] or 0))) if _circuit_breaker["last_failure"] else 0
        }
    }