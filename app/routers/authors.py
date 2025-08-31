# app/routers/authors.py
from __future__ import annotations

import math
from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.web import templates

# Slugify helper (fallback si le helper dédié n'est pas dispo)
try:
    from app.helpers import slugify  # type: ignore
except Exception:
    import re, unicodedata
    _keep = re.compile(r"[^a-z0-9\s-]")
    _collapse = re.compile(r"[-\s]+")
    def slugify(value: str | None, maxlen: int = 60) -> str:
        if not value:
            return "contenu"
        value = value.replace("œ", "oe").replace("Œ", "oe").replace("æ", "ae").replace("Æ", "ae")
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
        value = _keep.sub(" ", value)
        value = _collapse.sub("-", value).strip("-")
        return (value[:maxlen].rstrip("-") or "contenu")

router = APIRouter()

PER_PAGE = 20
MAX_TEXT_LEN = 20_000


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================================================
# 1) ROUTE CANONIQUE AVEC SLUG — GET + HEAD
#    Pattern strict avec convertisseur :int pour éviter les collisions
#    /authors/{author_id:int}-{slug}
# =========================================================
@router.api_route(
    "/authors/{author_id:int}-{slug}",
    methods=["GET", "HEAD"],
    response_class=HTMLResponse,
    name="author_detail",
)
def author_detail(
    request: Request,
    author_id: int,
    slug: str,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    # HEAD rapide : valide l'existence + slug canonique sans tout charger
    if request.method == "HEAD":
        row = db.execute(
            text("SELECT name FROM authors WHERE id = :aid"),
            {"aid": author_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Auteur introuvable")
        canonical = slugify((row["name"] or f"Auteur #{author_id}"), maxlen=60)
        if slug != canonical:
            url = request.url_for("author_detail", author_id=author_id, slug=canonical)
            return RedirectResponse(url, status_code=308)
        return Response(status_code=200)

    # GET normal
    q = (q or "").strip()
    offset = (page - 1) * PER_PAGE

    # Auteur
    row = db.execute(
        text(
            """
            SELECT
              au.id,
              au.name,
              (
                SELECT COUNT(1)
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                WHERE c.author_id = au.id
                  AND a.text IS NOT NULL
              ) AS answers_count
            FROM authors au
            WHERE au.id = :aid
            """
        ),
        {"aid": author_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Auteur introuvable")

    author_name = row["name"] or f"Auteur #{author_id}"
    canonical_slug = slugify(author_name, maxlen=60)
    if slug != canonical_slug:
        url = request.url_for("author_detail", author_id=author_id, slug=canonical_slug)
        if q:
            url += f"?q={q}" + (f"&page={page}" if page and page != 1 else "")
        elif page and page != 1:
            url += f"?page={page}"
        return RedirectResponse(url, status_code=308)

    # Listing des réponses (FTS via answers_fts si q, sinon récent)
    if q:
        q_esc = q.replace('"', '""')
        match = f'"{q_esc}"' if " " in q_esc else q_esc

        total = db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM answers_fts
                JOIN answers a       ON a.id = answers_fts.rowid
                JOIN contributions c ON c.id = a.contribution_id
                WHERE c.author_id = :aid
                  AND a.text IS NOT NULL
                  AND answers_fts MATCH :q
                """
            ),
            {"aid": author_id, "q": match},
        ).scalar_one()

        rows = db.execute(
            text(
                """
                SELECT
                  a.id           AS answer_id,
                  a.text         AS answer_text,
                  a.question_id  AS question_id,
                  q.prompt       AS question_prompt,
                  c.submitted_at AS submitted_at
                FROM answers_fts
                JOIN answers a       ON a.id = answers_fts.rowid
                JOIN contributions c ON c.id = a.contribution_id
                JOIN questions q     ON q.id = a.question_id
                WHERE c.author_id = :aid
                  AND a.text IS NOT NULL
                  AND answers_fts MATCH :q
                ORDER BY bm25(answers_fts) ASC, c.submitted_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"aid": author_id, "q": match, "limit": PER_PAGE, "offset": offset},
        ).mappings().all()
    else:
        total = db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                WHERE c.author_id = :aid
                  AND a.text IS NOT NULL
                """
            ),
            {"aid": author_id},
        ).scalar_one()

        rows = db.execute(
            text(
                """
                SELECT
                  a.id           AS answer_id,
                  a.text         AS answer_text,
                  a.question_id  AS question_id,
                  q.prompt       AS question_prompt,
                  c.submitted_at AS submitted_at
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                JOIN questions q     ON q.id = a.question_id
                WHERE c.author_id = :aid
                  AND a.text IS NOT NULL
                ORDER BY c.submitted_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"aid": author_id, "limit": PER_PAGE, "offset": offset},
        ).mappings().all()

    # Mapping vers le format attendu par answers/_card.html
    answers = []
    for r in rows:
        q_title = r["question_prompt"]
        q_slug = slugify(q_title or f"question-{r['question_id']}")
        answers.append(
            {
                "id": r["answer_id"],
                "author_id": author_id,
                "question_id": r["question_id"],
                "question_title": q_title,
                "question_slug": q_slug,
                "created_at": r["submitted_at"],
                "body": (r["answer_text"] or "")[:MAX_TEXT_LEN],
            }
        )

    total_pages = max(1, math.ceil(total / PER_PAGE))

    return templates.TemplateResponse(
        "authors/detail.html",
        {
            "request": request,
            "author": {
                "id": author_id,
                "name": row["name"],
                "answers_count": row["answers_count"],
                "slug": canonical_slug,
            },
            "answers": answers,
            "q": q,
            "page": page,
            "total_pages": total_pages,
        },
    )


# =========================================================
# 2) ROUTE LEGACY — GET + HEAD → redirection vers slug
#    Pattern strict : /authors/{author_id:int}
# =========================================================
@router.api_route(
    "/authors/{author_id:int}",
    methods=["GET", "HEAD"],
    response_class=HTMLResponse,
    name="author_detail_legacy",
)
def author_detail_legacy(
    request: Request,
    author_id: int,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    row = db.execute(
        text("SELECT id, name FROM authors WHERE id = :aid"),
        {"aid": author_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Auteur introuvable")

    canonical_slug = slugify(row["name"] or f"Auteur #{author_id}", maxlen=60)
    url = request.url_for("author_detail", author_id=author_id, slug=canonical_slug)
    if q:
        url += f"?q={q}" + (f"&page={page}" if page and page != 1 else "")
    elif page and page != 1:
        url += f"?page={page}"
    return RedirectResponse(url, status_code=308)

