# app/routers/authors.py
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.helpers import public_author
from app.services.authors import get_author
from app.web import templates

# Slugify helper (fallback si le helper dédié n'est pas dispo)
try:
    from app.helpers import slugify  # type: ignore
except Exception:
    import re
    import unicodedata

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
        return value[:maxlen].rstrip("-") or "contenu"


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
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    # HEAD rapide : valide l'existence + slug canonique sans tout charger
    if request.method == "HEAD":
        row = get_author(db, author_id)
        if not row:
            raise HTTPException(status_code=404, detail="Auteur introuvable")
        canonical = public_author(author_id, row["name"], row["is_anonymous"])["slug"]
        if slug != canonical:
            url = request.url_for("author_detail", author_id=author_id, slug=canonical)
            return RedirectResponse(url.replace(query=request.url.query), status_code=308)
        return Response(status_code=200)

    # GET normal
    offset = (page - 1) * PER_PAGE

    # Auteur
    row = (
        db.execute(
            text(
                """
            SELECT
              au.id,
              au.name,
              au.is_anonymous,
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
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Auteur introuvable")

    author = public_author(author_id, row["name"], row["is_anonymous"])
    canonical_slug = author["slug"]
    if slug != canonical_slug:
        url = request.url_for("author_detail", author_id=author_id, slug=canonical_slug)
        url = url.replace(query=request.url.query)
        return RedirectResponse(url, status_code=308)

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

    rows = (
        db.execute(
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
            ORDER BY c.submitted_at DESC NULLS FIRST, a.id DESC
            LIMIT :limit OFFSET :offset
            """
            ),
            {"aid": author_id, "limit": PER_PAGE, "offset": offset},
        )
        .mappings()
        .all()
    )

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
        request,
        "authors/detail.html",
        {
            "request": request,
            "author": {
                **author,
                "answers_count": row["answers_count"],
                "slug": canonical_slug,
            },
            "answers": answers,
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
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    row = get_author(db, author_id)
    if not row:
        raise HTTPException(status_code=404, detail="Auteur introuvable")

    canonical_slug = public_author(author_id, row["name"], row["is_anonymous"])["slug"]
    url = request.url_for("author_detail", author_id=author_id, slug=canonical_slug)
    url = url.replace(query=request.url.query)
    return RedirectResponse(url, status_code=308)
