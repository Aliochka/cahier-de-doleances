# app/routers/questions.py
import math
from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from app.db import SessionLocal
from app.web import templates

router = APIRouter()

PER_PAGE = 20
MIN_ANSWER_LEN = 40
MAX_TEXT_LEN = 20_000

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/questions/{question_id}", response_class=HTMLResponse, name="question_detail")
def question_detail(request: Request, question_id: int, q: str | None = Query(None), page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT q.id, q.question_code, q.prompt
        FROM questions q
        WHERE q.id = :qid
    """), {"qid": question_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Question introuvable")

    offset = (page - 1) * PER_PAGE

    # total
    if q and q.strip():
        try:
            total = db.execute(text("""
                SELECT COUNT(1)
                FROM answers a
                JOIN answers_fts fts ON fts.rowid = a.id
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND length(a.text) >= :minlen
                  AND fts MATCH :q
            """), {"qid": question_id, "minlen": MIN_ANSWER_LEN, "q": q}).scalar_one()
            use_fts = True
        except OperationalError:
            total = db.execute(text("""
                SELECT COUNT(1)
                FROM answers a
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND length(a.text) >= :minlen
                  AND a.text LIKE :like
            """), {"qid": question_id, "minlen": MIN_ANSWER_LEN, "like": f"%{q}%"}).scalar_one()
            use_fts = False
    else:
        total = db.execute(text("""
            SELECT COUNT(1)
            FROM answers a
            WHERE a.question_id = :qid
              AND a.text IS NOT NULL
              AND length(a.text) >= :minlen
        """), {"qid": question_id, "minlen": MIN_ANSWER_LEN}).scalar_one()
        use_fts = False

    # page
    if q and q.strip():
        if use_fts:
            sql = text("""
                SELECT a.id AS answer_id, a.text AS answer_text,
                       c.author_id AS author_id,
                       c.submitted_at AS submitted_at
                FROM answers a
                JOIN answers_fts fts ON fts.rowid = a.id
                JOIN contributions c ON c.id = a.contribution_id
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND length(a.text) >= :minlen
                  AND fts MATCH :q
                ORDER BY c.submitted_at DESC
                LIMIT :limit OFFSET :offset
            """)
            rows = db.execute(sql, {"qid": question_id, "minlen": MIN_ANSWER_LEN, "q": q, "limit": PER_PAGE, "offset": offset}).mappings().all()
        else:
            sql = text("""
                SELECT a.id AS answer_id, a.text AS answer_text,
                       c.author_id AS author_id,
                       c.submitted_at AS submitted_at
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND length(a.text) >= :minlen
                  AND a.text LIKE :like
                ORDER BY c.submitted_at DESC
                LIMIT :limit OFFSET :offset
            """)
            rows = db.execute(sql, {"qid": question_id, "minlen": MIN_ANSWER_LEN, "like": f"%{q}%", "limit": PER_PAGE, "offset": offset}).mappings().all()
    else:
        rows = db.execute(text("""
            SELECT a.id AS answer_id, a.text AS answer_text,
                   c.author_id AS author_id,
                   c.submitted_at AS submitted_at
            FROM answers a
            JOIN contributions c ON c.id = a.contribution_id
            WHERE a.question_id = :qid
              AND a.text IS NOT NULL
              AND length(a.text) >= :minlen
            ORDER BY c.submitted_at DESC
            LIMIT :limit OFFSET :offset
        """), {"qid": question_id, "minlen": MIN_ANSWER_LEN, "limit": PER_PAGE, "offset": offset}).mappings().all()

    answers = [{
        "id": r["answer_id"],
        "author_id": r["author_id"],
        "question_id": question_id,
        "created_at": r["submitted_at"],
        "body": (r["answer_text"] or "")[:MAX_TEXT_LEN],
    } for r in rows]

    total_pages = max(1, math.ceil(total / PER_PAGE))
    return templates.TemplateResponse(
        "questions/detail.html",
        {
            "request": request,
            "question": {"id": row["id"], "title": row["prompt"]},
            "answers": answers,
            "q": q or "",
            "page": page,
            "total_pages": total_pages,
        },
    )

# Optionnel: partial HTMX compatible
@router.get("/questions/{question_id}/partials/answers", response_class=HTMLResponse, name="question_answers_partial")
def question_answers_partial(request: Request, question_id: int, q: str | None = Query(None), page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    resp = question_detail(request, question_id, q=q, page=page, db=db)
    ctx = dict(resp.context)
    return templates.TemplateResponse("partials/_answers_list.html", {
        "request": request,
        "answers": ctx.get("answers", []),
        "page": ctx.get("page", 1),
        "total_pages": ctx.get("total_pages", 1),
        "q": ctx.get("q", ""),
    })
