# app/routers/seo.py
from __future__ import annotations
import os
from typing import Optional, Iterable
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import text

from app.db import SessionLocal

router = APIRouter()

HOST = os.getenv("CANONICAL_HOST_URL", "https://www.cahierdedoleances.fr")
CHUNK = int(os.getenv("SITEMAP_CHUNK", "200"))                   # taille de lot
SITEMAP_MAX_URLS = int(os.getenv("SITEMAP_MAX_URLS", "50000"))   # limite globale
LIGHT_LASTMOD = os.getenv("SITEMAP_LIGHT_LASTMOD", "1") == "1"   # ne calcule pas lastmod des questions

def _w3c(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")

def _url_xml(loc: str, lastmod: Optional[datetime] = None) -> str:
    lm = _w3c(lastmod)
    return f"<url><loc>{loc}</loc>{f'<lastmod>{lm}</lastmod>' if lm else ''}</url>"

@router.get("/robots.txt", include_in_schema=False)
def robots_txt() -> PlainTextResponse:
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {HOST}/sitemap.xml\n"
    )
    resp = PlainTextResponse(content)
    resp.headers["Cache-Control"] = "public, max-age=86400"  # 24h
    return resp

@router.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml() -> StreamingResponse:
    def stream() -> Iterable[bytes]:
        emitted = 0

        def emit(line: str):
            nonlocal emitted
            emitted += 1
            return (line + "\n").encode("utf-8")

        yield b'<?xml version="1.0" encoding="UTF-8"?>\n'
        yield b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

        with SessionLocal() as db:
            # lastmod global = dernière contribution
            site_lastmod = db.execute(
                text("SELECT MAX(submitted_at) AS lastmod FROM contributions")
            ).mappings().first()["lastmod"]

            # Accueil
            if emitted < SITEMAP_MAX_URLS:
                yield emit(_url_xml(f"{HOST}/", site_lastmod))

            # QUESTIONS
            last_id = 0
            while emitted < SITEMAP_MAX_URLS:
                if LIGHT_LASTMOD:
                    rows = db.execute(
                        text("""
                            SELECT q.id
                            FROM questions q
                            WHERE q.id > :last_id
                            ORDER BY q.id
                            LIMIT :chunk
                        """),
                        {"last_id": last_id, "chunk": CHUNK},
                    ).mappings().all()
                else:
                    rows = db.execute(
                        text("""
                            SELECT q.id, MAX(c.submitted_at) AS lastmod
                            FROM questions q
                            LEFT JOIN answers a ON a.question_id = q.id
                            LEFT JOIN contributions c ON c.id = a.contribution_id
                            WHERE q.id > :last_id
                            GROUP BY q.id
                            ORDER BY q.id
                            LIMIT :chunk
                        """),
                        {"last_id": last_id, "chunk": CHUNK},
                    ).mappings().all()

                if not rows:
                    break

                for r in rows:
                    if emitted >= SITEMAP_MAX_URLS:
                        break
                    loc = f"{HOST}/questions/{r['id']}"
                    lm = None if LIGHT_LASTMOD else r["lastmod"]
                    yield emit(_url_xml(loc, lm))
                    last_id = r["id"]

            # ANSWERS
            last_id = 0
            while emitted < SITEMAP_MAX_URLS:
                rows = db.execute(
                    text("""
                        SELECT a.id, c.submitted_at AS lastmod
                        FROM answers a
                        JOIN contributions c ON c.id = a.contribution_id
                        WHERE a.id > :last_id
                        ORDER BY a.id
                        LIMIT :chunk
                    """),
                    {"last_id": last_id, "chunk": CHUNK},
                ).mappings().all()
                if not rows:
                    break
                for r in rows:
                    if emitted >= SITEMAP_MAX_URLS:
                        break
                    loc = f"{HOST}/answers/{r['id']}"
                    yield emit(_url_xml(loc, r["lastmod"]))
                    last_id = r["id"]

            # AUTHORS (avec au moins une contribution)
            last_author = 0
            while emitted < SITEMAP_MAX_URLS:
                rows = db.execute(
                    text("""
                        SELECT c.author_id AS id, MAX(c.submitted_at) AS lastmod
                        FROM contributions c
                        WHERE c.author_id IS NOT NULL
                          AND c.author_id > :last_id
                        GROUP BY c.author_id
                        ORDER BY c.author_id
                        LIMIT :chunk
                    """),
                    {"last_id": last_author, "chunk": CHUNK},
                ).mappings().all()
                if not rows:
                    break
                for r in rows:
                    if emitted >= SITEMAP_MAX_URLS:
                        break
                    loc = f"{HOST}/authors/{r['id']}"
                    yield emit(_url_xml(loc, r["lastmod"]))
                    last_author = r["id"]

        yield b"</urlset>\n"

    resp = StreamingResponse(stream(), media_type="application/xml; charset=utf-8")
    resp.headers["Cache-Control"] = "public, max-age=21600"  # 6h
    return resp
