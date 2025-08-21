# app/routers/search.py
from __future__ import annotations
import math
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import text, bindparam
from app.db import SessionLocal
from app.web import templates
from math import ceil

router = APIRouter()

PER_PAGE = 20
MAX_TEXT_LEN = 20_000
MIN_ANSWER_LEN = 60
PREVIEW_MAXLEN = 300

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
def search_questions_page(
    request: Request,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    sort: str = Query("recent")  # "popular" restera possible
):
    q = (q or "").strip()
    offset = (page - 1) * PER_PAGE

    with SessionLocal() as db:
        if q:
            # --- FTS sur les questions (pas d'affichage de count) ---
            total = db.execute(
                text("""
                    SELECT COUNT(*)
                    FROM question_fts
                    WHERE question_fts MATCH :q
                """),
                {"q": q},
            ).scalar_one()

            rows = db.execute(
                text("""
                    SELECT
                        q.id,
                        q.question_code,
                        q.prompt AS title,
                        bm25(question_fts) AS score,
                        highlight(question_fts, 0, '<mark>', '</mark>') AS prompt_hl
                    FROM question_fts
                    JOIN questions q ON q.id = question_fts.rowid
                    WHERE question_fts MATCH :q
                    ORDER BY score ASC, q.id ASC
                    LIMIT :limit OFFSET :offset
                """),
                {"q": q, "limit": PER_PAGE, "offset": offset},
            ).mappings().all()
        else:
            # --- Liste complète paginée (tri récent/populaire) ---
            total = db.execute(text("SELECT COUNT(*) FROM questions")).scalar_one()

            if sort == "popular":
                # on utilise le volume de réponses pour trier, sans l'afficher
                order_sql = "answers_count DESC, q.id ASC"
                base = text(f"""
                    SELECT
                        q.id,
                        q.question_code,
                        q.prompt AS title,
                        COALESCE(ac.cnt, 0) AS answers_count
                    FROM questions q
                    LEFT JOIN (
                        SELECT question_id, COUNT(*) AS cnt
                        FROM answers
                        WHERE text IS NOT NULL
                        GROUP BY question_id
                    ) ac ON ac.question_id = q.id
                    ORDER BY {order_sql}
                    LIMIT :limit OFFSET :offset
                """)
                rows = db.execute(base, {"limit": PER_PAGE, "offset": offset}).mappings().all()
            else:
                # plus récentes : id décroissant
                rows = db.execute(
                    text("""
                        SELECT q.id, q.question_code, q.prompt AS title
                        FROM questions q
                        ORDER BY q.id DESC
                        LIMIT :limit OFFSET :offset
                    """),
                    {"limit": PER_PAGE, "offset": offset},
                ).mappings().all()

        # --- Récupérer 3 réponses (texte) par question de la page courante ---
        question_ids = [r["id"] for r in rows]
        previews_by_qid = {qid: [] for qid in question_ids}

        if question_ids:
            sql_answers = text("""
                WITH picks AS (
                    SELECT
                        a.question_id,
                        a.id AS answer_id,
                        substr(a.text, 1, :maxlen) AS answer_text,
                        ROW_NUMBER() OVER(
                            PARTITION BY a.question_id
                            ORDER BY random()
                        ) AS rn
                    FROM answers a
                    WHERE a.question_id IN :ids
                    AND a.text IS NOT NULL
                    AND trim(a.text) <> ''
                )
                SELECT question_id, answer_id, answer_text
                FROM picks
                WHERE rn <= 3;
            """).bindparams(bindparam("ids", expanding=True))

            for ar in db.execute(
                sql_answers,
                {"ids": tuple(question_ids), "maxlen": PREVIEW_MAXLEN},
            ).mappings():
                previews_by_qid[ar["question_id"]].append(
                    {"id": ar["answer_id"], "text": ar["answer_text"]}
                )

        # attacher aux questions
        questions = []
        for r in rows:
            questions.append({
                "id": r["id"],
                "question_code": r.get("question_code"),
                "title": r.get("title"),
                "prompt_hl": r.get("prompt_hl"),
                "answers": previews_by_qid.get(r["id"], []),
            })

    total_pages = max(1, math.ceil(total / PER_PAGE))
    return templates.TemplateResponse(
        "search/questions.html",
        {
            "request": request,
            "q": q,
            "questions": questions,
            "page": page,
            "total_pages": total_pages,
            "sort": sort,
            "page_size": PER_PAGE,
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
