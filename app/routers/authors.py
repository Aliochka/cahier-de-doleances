# app/routers/authors.py
import math
from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
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
def author_detail(request: Request, author_id: int, q: str | None = None, page: int = 1, db: Session = Depends(get_db)):
    offset = (page - 1) * PER_PAGE

    author = {"id": author_id, "name": None, "answers_count": None}

    # infos auteur + nombre de réponses
    row = db.execute(text("""
        SELECT au.id, au.name, COUNT(a.id) AS answers_count
        FROM authors au
        LEFT JOIN contributions c ON c.author_id = au.id
        LEFT JOIN answers a ON a.contribution_id = c.id AND a.text IS NOT NULL
        WHERE au.id = :aid
    """), {"aid": author_id}).mappings().first()
    if row:
        author = {"id": row["id"], "name": row["name"], "answers_count": row["answers_count"]}

    # total
    if q and q.strip():
        try:
            total = db.execute(text("""
                SELECT COUNT(1)
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                JOIN answers_fts fts ON fts.rowid = a.id
                WHERE c.author_id = :aid AND a.text IS NOT NULL AND fts MATCH :q
            """), {"aid": author_id, "q": q}).scalar_one()
            use_fts = True
        except OperationalError:
            total = db.execute(text("""
                SELECT COUNT(1)
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                WHERE c.author_id = :aid AND a.text IS NOT NULL AND a.text LIKE :like
            """), {"aid": author_id, "like": f"%{q}%"}).scalar_one()
            use_fts = False
    else:
        total = db.execute(text("""
            SELECT COUNT(1)
            FROM answers a
            JOIN contributions c ON c.id = a.contribution_id
            WHERE c.author_id = :aid AND a.text IS NOT NULL
        """), {"aid": author_id}).scalar_one()
        use_fts = False

    # page
    if q and q.strip():
        if use_fts:
            sql = text("""
                SELECT a.id AS answer_id, a.text AS answer_text,
                       a.question_id AS question_id,
                       c.submitted_at AS submitted_at
                FROM answers a
                JOIN answers_fts fts ON fts.rowid = a.id
                JOIN contributions c ON c.id = a.contribution_id
                WHERE c.author_id = :aid AND a.text IS NOT NULL AND fts MATCH :q
                ORDER BY c.submitted_at DESC
                LIMIT :limit OFFSET :offset
            """)
            rows = db.execute(sql, {"aid": author_id, "q": q, "limit": PER_PAGE, "offset": offset}).mappings().all()
        else:
            sql = text("""
                SELECT a.id AS answer_id, a.text AS answer_text,
                       a.question_id AS question_id,
                       c.submitted_at AS submitted_at
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                WHERE c.author_id = :aid AND a.text IS NOT NULL AND a.text LIKE :like
                ORDER BY c.submitted_at DESC
                LIMIT :limit OFFSET :offset
            """)
            rows = db.execute(sql, {"aid": author_id, "like": f"%{q}%", "limit": PER_PAGE, "offset": offset}).mappings().all()
    else:
        rows = db.execute(text("""
            SELECT a.id AS answer_id, a.text AS answer_text,
                   a.question_id AS question_id,
                   c.submitted_at AS submitted_at
            FROM answers a
            JOIN contributions c ON c.id = a.contribution_id
            WHERE c.author_id = :aid AND a.text IS NOT NULL
            ORDER BY c.submitted_at DESC
            LIMIT :limit OFFSET :offset
        """), {"aid": author_id, "limit": PER_PAGE, "offset": offset}).mappings().all()

    answers = [{
        "id": r["answer_id"],
        "author_id": author_id,
        "question_id": r["question_id"],
        "created_at": r["submitted_at"],
        "body": (r["answer_text"] or "")[:MAX_TEXT_LEN],
    } for r in rows]

    total_pages = max(1, math.ceil(total / PER_PAGE))
    return templates.TemplateResponse(
        "authors/detail.html",
        {
            "request": request,
            "author": author,
            "answers": answers,
            "q": q or "",
            "page": page,
            "total_pages": total_pages,
        },
    )

# Optionnel: partial HTMX compatible
@router.get("/authors/{author_id}/partials/answers", response_class=HTMLResponse, name="author_answers_partial")
def author_answers_partial(request: Request, author_id: int, q: str | None = Query(None), page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    # on réutilise la logique ci-dessus mais ne renvoie que la liste
    resp = author_detail(request, author_id, q=q, page=page, db=db)
    ctx = dict(resp.context)
    return templates.TemplateResponse("partials/_answers_list.html", {
        "request": request,
        "answers": ctx.get("answers", []),
        "page": ctx.get("page", 1),
        "total_pages": ctx.get("total_pages", 1),
        "q": ctx.get("q", ""),
    })
