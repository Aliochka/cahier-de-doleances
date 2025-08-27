# app/routers/seo.py
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import text
from datetime import datetime, timezone
from app.helpers import slugify  # type: ignore

from app.db import SessionLocal

router = APIRouter()

# Limites (prudents pour la perf)
SITEMAP_LIMIT_QUESTIONS = 2000
SITEMAP_LIMIT_AUTHORS   = 1000
SITEMAP_LIMIT_FORMS     = 50

CACHE_ROBOTS = "public, max-age=86400"
CACHE_SITEMAP = "public, max-age=21600"

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

@router.api_route("/sitemap.xml", methods=["GET", "HEAD"], name="sitemap_xml")
def sitemap_xml(request: Request):
    if request.method == "HEAD":
        return Response(status_code=200, headers={"Cache-Control": CACHE_SITEMAP}, media_type="application/xml; charset=utf-8")

    # base absolue
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    netloc = request.headers.get("x-forwarded-host") or request.url.netloc
    base = f"{scheme}://{netloc}"

    urls: list[tuple[str, str | None]] = []

    with SessionLocal() as db:
        # lastmod global (homepage) = dernière contribution
        home_lastmod = db.execute(text("SELECT MAX(submitted_at) FROM contributions")).scalar()
        urls.append((f"{base}/", _fmt_iso(home_lastmod)))
        
        # Pages de recherche principales
        urls.append((f"{base}/search/questions", _fmt_iso(home_lastmod)))
        urls.append((f"{base}/search/answers", _fmt_iso(home_lastmod)))

        # Questions: canonical slug + lastmod = max(submitted_at des réponses)
        q_rows = db.execute(text("""
            SELECT q.id, q.prompt, MAX(c.submitted_at) AS lastmod
            FROM questions q
            JOIN answers a       ON a.question_id = q.id
            JOIN contributions c ON c.id = a.contribution_id
            WHERE a.text IS NOT NULL
            GROUP BY q.id, q.prompt
            ORDER BY lastmod DESC NULLS LAST, q.id DESC
            LIMIT :lim
        """), {"lim": SITEMAP_LIMIT_QUESTIONS}).mappings().all()

        for r in q_rows:
            qslug = slugify(r["prompt"] or f"question-{r['id']}")
            urls.append((f"{base}/questions/{r['id']}-{qslug}", _fmt_iso(r["lastmod"])))

        # Auteurs: canonical slug + lastmod = max(submitted_at)
        a_rows = db.execute(text("""
            SELECT au.id, au.name, MAX(c.submitted_at) AS lastmod
            FROM authors au
            JOIN contributions c ON c.author_id = au.id
            JOIN answers a       ON a.contribution_id = c.id
            WHERE a.text IS NOT NULL
            GROUP BY au.id, au.name
            ORDER BY lastmod DESC NULLS LAST, au.id DESC
            LIMIT :lim
        """), {"lim": SITEMAP_LIMIT_AUTHORS}).mappings().all()

        for r in a_rows:
            name = r["name"] or f"Auteur #{r['id']}"
            aslug = slugify(name)
            urls.append((f"{base}/authors/{r['id']}-{aslug}", _fmt_iso(r["lastmod"])))

        # Formulaires: lastmod = max(submitted_at des contributions liées)
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
            urls.append((f"{base}/forms/{r['id']}", _fmt_iso(r["lastmod"])))

    # Rend XML
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
    xml = "\n".join(parts)

    return Response(
        content=xml,
        media_type="application/xml; charset=utf-8",
        headers={"Cache-Control": CACHE_SITEMAP},
    )
