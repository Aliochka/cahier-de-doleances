# app/routers/search.py
from __future__ import annotations
import math
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from app.db import SessionLocal
from app.web import templates
from math import ceil

router = APIRouter()

PER_PAGE = 20
MAX_TEXT_LEN = 20_000

# --- Recherche RÉPONSES (/search/answers) ---
@router.get("/search/answers", name="search_answers", response_class=HTMLResponse)
def search_answers(request: Request, q: str = Query("", description="Requête"), page: int = Query(1, ge=1)):
    q = (q or "").strip()
    answers = []
    total = 0

    if len(q) >= 2:
        match_query = f'"{q}"' if " " in q else q
        offset = (page - 1) * PER_PAGE
        with SessionLocal() as db:
            total = db.execute(text("""
                SELECT COUNT(*)
                FROM answers_fts
                WHERE answers_fts MATCH :q
            """), {"q": match_query}).scalar_one()

            if total:
               rows = db.execute(text("""
                SELECT a.id              AS answer_id,
                    a.text            AS answer_text,
                    a.question_id     AS question_id,
                    q.prompt          AS question_prompt,
                    c.author_id       AS author_id,
                    c.submitted_at    AS submitted_at,
                    bm25(answers_fts) AS score
                FROM answers_fts
                JOIN answers       a ON a.id = answers_fts.rowid
                JOIN contributions c ON c.id = a.contribution_id
                JOIN questions     q ON q.id = a.question_id
                WHERE answers_fts MATCH :q
                ORDER BY bm25(answers_fts) ASC, a.id DESC
                LIMIT :limit OFFSET :offset
            """), {"q": match_query, "limit": PER_PAGE, "offset": offset}).mappings().all()

            answers = []
            for r in rows:
                txt = (r["answer_text"] or "")[:MAX_TEXT_LEN]
                answers.append({
                    "id": r["answer_id"],
                    "author_id": r["author_id"],
                    "question_id": r["question_id"],
                    "question_title": r["question_prompt"],   # 👈 utilisé par le partial
                    "created_at": r["submitted_at"],
                    "body": txt,
                })


    total_pages = max(1, math.ceil(total / PER_PAGE)) if q else 1
    return templates.TemplateResponse(
        "search/answers.html",
        {
            "request": request,
            "q": q,
            "page": page,
            "total_pages": total_pages,
            "answers": answers,   # <- pour partials/_answers_list.html
        },
    )

# --- Recherche QUESTIONS (/search/questions) ---
@router.get("/search/questions", name="search_questions", response_class=HTMLResponse)
def search_questions(request: Request, q: str = Query("", description="Requête"), page: int = Query(1, ge=1)):
    q = (q or "").strip()
    questions = []
    total = 0

    if len(q) >= 1:
        offset = (page - 1) * PER_PAGE
        with SessionLocal() as db:
            # total approximé (pas de COUNT(*) global si trop coûteux)
            # ici on calcule réellement le total pour la pagination simple
            total = db.execute(text("""
                SELECT COUNT(1)
                FROM question_fts
                WHERE question_fts MATCH :query
            """), {"query": q}).scalar_one()

            rows = db.execute(text("""
                SELECT q.id, q.prompt
                FROM question_fts
                JOIN questions q ON q.id = question_fts.rowid
                WHERE question_fts MATCH :query
                ORDER BY bm25(question_fts) ASC, q.id ASC
                LIMIT :limit OFFSET :offset
            """), {"query": q, "limit": PER_PAGE, "offset": offset}).mappings().all()

            for r in rows:
                questions.append({
                    "id": r["id"],
                    "title": r["prompt"],  # <- pour questions/_card.html
                })

    total_pages = max(1, math.ceil(total / PER_PAGE)) if q else 1
    return templates.TemplateResponse(
        "search/questions.html",
        {
            "request": request,
            "q": q,
            "page": page,
            "total_pages": total_pages,
            "questions": questions,  # <- pour partials/_questions_list.html
        },
    )

# --- Alias HTMX : /hx/search -> partials/_answers_list.html ---
@router.get("/hx/search", response_class=HTMLResponse)
def hx_search(request: Request, q: str = Query("", description="Requête utilisateur"), page: int = Query(1, ge=1)):
    q = (q or "").strip()
    PER_PAGE = 20
    MAX_TEXT_LEN = 20_000
    answers, total = [], 0

    if len(q) >= 2:
        match_query = f'"{q}"' if " " in q else q
        offset = (page - 1) * PER_PAGE
        with SessionLocal() as db:
            total = db.execute(text("""
                SELECT COUNT(*)
                FROM answers_fts
                WHERE answers_fts MATCH :q
            """), {"q": match_query}).scalar_one()

            if total:
                rows = db.execute(text("""
                    SELECT a.id           AS answer_id,
                           a.text         AS answer_text,
                           a.question_id  AS question_id,
                           c.author_id    AS author_id,
                           c.submitted_at AS submitted_at,
                           bm25(answers_fts) AS score
                    FROM answers_fts
                    JOIN answers       a ON a.id = answers_fts.rowid
                    JOIN contributions c ON c.id = a.contribution_id
                    WHERE answers_fts MATCH :q
                    ORDER BY bm25(answers_fts) ASC, a.id DESC
                    LIMIT :limit OFFSET :offset
                """), {"q": match_query, "limit": PER_PAGE, "offset": offset}).mappings().all()

                for r in rows:
                    txt = (r["answer_text"] or "")[:MAX_TEXT_LEN]
                    answers.append({
                        "id": r["answer_id"],
                        "author_id": r["author_id"],
                        "question_id": r["question_id"],
                        "created_at": r["submitted_at"],
                        "body": txt,  # attendu par partials/_answer_item.html
                    })

    total_pages = max(1, ceil(total / PER_PAGE)) if q else 1
    return templates.TemplateResponse(
        "partials/_answers_list.html",
        {
            "request": request,
            "answers": answers,
            "page": page,
            "total_pages": total_pages,
            "q": q,
        },
    )
