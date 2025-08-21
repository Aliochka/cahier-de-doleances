# app/routers/authors.py
import math
from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.web import templates

router = APIRouter()

PER_PAGE = 20
MAX_TEXT_LEN = 20_000


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/authors/{author_id}", response_class=HTMLResponse, name="author_detail")
def author_detail(
    request: Request,
    author_id: int,
    q: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
):
    # Normalise requête + pagination
    q = (q or "").strip()
    offset = (page - 1) * PER_PAGE

    # Infos auteur + nb de réponses
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

    author = {
        "id": author_id,
        "name": row["name"] if row else None,
        "answers_count": row["answers_count"] if row else None,
    }

    # Si recherche : FTS sur answers_fts (phrase si espaces)
    match = None
    if q:
        q_esc = q.replace('"', '""')
        match = f'"{q_esc}"' if " " in q_esc else q_esc

    # ----- TOTAL -----
    if match:
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

    # ----- ROWS (page courante) -----
    if match:
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

    # Mapping vers le format attendu par partials/_answer_item.html
    answers = [
        {
            "id": r["answer_id"],
            "author_id": author_id,
            "question_id": r["question_id"],
            "question_title": r["question_prompt"],  # affiché au-dessus de la réponse
            "created_at": r["submitted_at"],
            "body": (r["answer_text"] or "")[:MAX_TEXT_LEN],
        }
        for r in rows
    ]

    total_pages = max(1, math.ceil(total / PER_PAGE))

    return templates.TemplateResponse(
        "authors/detail.html",
        {
            "request": request,
            "author": author,
            "answers": answers,
            "q": q,
            "page": page,
            "total_pages": total_pages,
        },
    )


# Optionnel : endpoint partial (prêt pour htmx v2), non utilisé en SSR pur
@router.get(
    "/authors/{author_id}/partials/answers",
    response_class=HTMLResponse,
    name="author_answers_partial",
)
def author_answers_partial(
    request: Request,
    author_id: int,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    # Réutilise la logique ci-dessus et renvoie seulement la liste + pagination
    resp = author_detail(request, author_id, q=q, page=page, db=db)
    ctx = dict(resp.context)
    return templates.TemplateResponse(
        "partials/_answers_list.html",
        {
            "request": request,
            "answers": ctx.get("answers", []),
            "page": ctx.get("page", 1),
            "total_pages": ctx.get("total_pages", 1),
            "q": ctx.get("q", ""),
        },
    )
