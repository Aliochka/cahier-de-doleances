"""Robots and sitemap endpoints without browser rendering or application caches."""

from datetime import datetime, timezone
from xml.sax.saxutils import escape

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import text

from app.db import SessionLocal
from app.helpers import slugify

router = APIRouter()

SITEMAP_LIMIT_QUESTIONS = 2000
SITEMAP_LIMIT_AUTHORS = 1000
SITEMAP_LIMIT_FORMS = 50


def _base_url(request: Request) -> str:
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    netloc = request.headers.get("x-forwarded-host") or request.url.netloc
    return f"{scheme}://{netloc}"


def _fmt_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


@router.api_route("/robots.txt", methods=["GET", "HEAD"], name="robots_txt")
def robots_txt(request: Request):
    body = f"User-agent: *\nAllow: /\nSitemap: {_base_url(request)}/sitemap.xml\n"
    return PlainTextResponse("" if request.method == "HEAD" else body)


def _generate_sitemap_xml(base_url: str) -> str:
    urls: list[tuple[str, str | None]] = []
    with SessionLocal() as db:
        home_lastmod = _fmt_iso(
            db.execute(text("SELECT MAX(submitted_at) FROM contributions")).scalar()
        )
        urls.extend(
            (f"{base_url}{path}", home_lastmod)
            for path in ("/", "/search/questions", "/search/answers")
        )
        questions = db.execute(
            text("""
            SELECT q.id, q.prompt FROM questions q
            JOIN question_stats st ON st.question_id=q.id
            WHERE st.answers_count>0 ORDER BY q.id LIMIT :lim
        """),
            {"lim": SITEMAP_LIMIT_QUESTIONS},
        ).mappings()
        for q in questions:
            urls.append((f"{base_url}/questions/{q['id']}-{slugify(q['prompt'])}", None))
        authors = db.execute(
            text("""
            SELECT au.id, au.name, MAX(c.submitted_at) AS lastmod
            FROM authors au JOIN contributions c ON c.author_id=au.id
            GROUP BY au.id,au.name ORDER BY lastmod DESC NULLS LAST,au.id DESC
            LIMIT :lim
        """),
            {"lim": SITEMAP_LIMIT_AUTHORS},
        ).mappings()
        for author in authors:
            name = author["name"] or f"Auteur #{author['id']}"
            urls.append(
                (f"{base_url}/authors/{author['id']}-{slugify(name)}", _fmt_iso(author["lastmod"]))
            )
        forms = db.execute(
            text("""
            SELECT f.id, MAX(c.submitted_at) AS lastmod
            FROM forms f JOIN contributions c ON c.form_id=f.id
            GROUP BY f.id ORDER BY lastmod DESC NULLS LAST,f.id DESC LIMIT :lim
        """),
            {"lim": SITEMAP_LIMIT_FORMS},
        ).mappings()
        for form in forms:
            urls.append((f"{base_url}/forms/{form['id']}", _fmt_iso(form["lastmod"])))
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod in urls:
        parts.append(f"<url><loc>{escape(loc)}</loc>")
        if lastmod:
            parts.append(f"<lastmod>{lastmod}</lastmod>")
        parts.append("</url>")
    parts.append("</urlset>")
    return "\n".join(parts)


@router.api_route("/sitemap.xml", methods=["GET", "HEAD"], name="sitemap_xml")
def sitemap_xml(request: Request):
    content = "" if request.method == "HEAD" else _generate_sitemap_xml(_base_url(request))
    return Response(content=content, media_type="application/xml")
