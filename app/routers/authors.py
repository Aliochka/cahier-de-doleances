from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.web import templates
from sqlalchemy.exc import OperationalError

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
def author_detail(request: Request, author_id: int, q: str | None = None, page: int = 1):
    return templates.TemplateResponse(
        "author.html",
        {"request": request, "author_id": author_id, "q": q or "", "page": page, "per_page": PER_PAGE},
    )

@router.get("/authors/{author_id}/partials/answers", response_class=HTMLResponse, name="author_answers_partial")
def author_answers_partial(
    request: Request,
    author_id: int,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * PER_PAGE
    total = 0
    rows = []

    if q and q.strip():
        try:
            count_sql = text("""
                SELECT COUNT(1)
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                JOIN answers_fts fts ON fts.rowid = a.id
                WHERE c.author_id = :aid
                  AND a.text IS NOT NULL
                  AND fts MATCH :q
            """)
            total = db.execute(count_sql, {"aid": author_id, "q": q}).scalar_one()

            sql = text("""
                SELECT a.id AS answer_id,
                       a.text AS answer_text,
                       q.prompt AS question_prompt,
                       c.submitted_at,
                       au.zipcode
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                JOIN authors au ON au.id = c.author_id
                JOIN questions q ON q.id = a.question_id
                JOIN answers_fts fts ON fts.rowid = a.id
                WHERE c.author_id = :aid
                  AND a.text IS NOT NULL
                  AND fts MATCH :q
                ORDER BY bm25(fts) ASC, c.submitted_at DESC
                LIMIT :limit OFFSET :offset
            """)
            rows = db.execute(sql, {"aid": author_id, "q": q, "limit": PER_PAGE, "offset": offset}).mappings().all()
        except OperationalError:
            pass
    else:
        count_sql = text("""
            SELECT COUNT(1)
            FROM answers a
            JOIN contributions c ON c.id = a.contribution_id
            WHERE c.author_id = :aid AND a.text IS NOT NULL
        """)
        total = db.execute(count_sql, {"aid": author_id}).scalar_one()

        sql = text("""
            SELECT a.id AS answer_id,
                   a.text AS answer_text,
                   q.prompt AS question_prompt,
                   c.submitted_at,
                   au.zipcode
            FROM answers a
            JOIN contributions c ON c.id = a.contribution_id
            JOIN authors au ON au.id = c.author_id
            JOIN questions q ON q.id = a.question_id
            WHERE c.author_id = :aid AND a.text IS NOT NULL
            ORDER BY c.submitted_at DESC
            LIMIT :limit OFFSET :offset
        """)
        rows = db.execute(sql, {"aid": author_id, "limit": PER_PAGE, "offset": offset}).mappings().all()

    # troncature
    results = []
    for r in rows:
        text_val = r["answer_text"] or ""
        truncated = False
        if len(text_val) > MAX_TEXT_LEN:
            text_val = text_val[:MAX_TEXT_LEN]
            truncated = True
        results.append({
            "answer_id": r["answer_id"],
            "question_prompt": r["question_prompt"],
            "text": text_val,
            "truncated": truncated,
            "zipcode": r["zipcode"],
            "submitted_at": r["submitted_at"],
        })

    return templates.TemplateResponse(
        "_author_answers.html",
        {"request": request, "results": results, "total": total, "page": page, "per_page": PER_PAGE, "author_id": author_id, "q": q or ""},
    )
