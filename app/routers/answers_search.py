from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import text as sqltext
from app.db import SessionLocal
from app.web import templates


router = APIRouter()

PER_PAGE = 20
MAX_TEXT_LEN = 20_000

@router.get("/hx/search", response_class=HTMLResponse)
def hx_search(
    request: Request,
    q: str = Query("", description="Requête utilisateur"),
    page: int = Query(1, ge=1),
):
    q = (q or "").strip()
    if len(q) < 2:
        ctx = {
            "request": request,
            "q": q,
            "page": 1,
            "per_page": PER_PAGE,
            "total": 0,
            "results": [],
            "too_short": True,
        }
        return templates.TemplateResponse("_results_answers.html", ctx)

    offset = (page - 1) * PER_PAGE

    # Recherche phrase si espaces, sinon mot simple
    match_query = f'"{q}"' if " " in q else q

    with SessionLocal() as db:
        # Total des correspondances
        count_sql = sqltext("""
            SELECT COUNT(*)
            FROM answers_fts
            WHERE answers_fts MATCH :q
        """)
        total = db.execute(count_sql, {"q": match_query}).scalar_one()

        results = []
        if total:
            # Tri par pertinence : bm25(answers_fts) ASC (plus petit = plus pertinent)
            search_sql = sqltext("""
                SELECT a.id              AS answer_id,
                       a.text            AS answer_text,
                       a.question_id     AS question_id,
                       q.prompt          AS question_prompt,
                       c.author_id       AS author_id,
                       bm25(answers_fts) AS score
                FROM answers_fts
                JOIN answers       a ON a.id = answers_fts.rowid
                JOIN questions     q ON q.id = a.question_id
                JOIN contributions c ON c.id = a.contribution_id
                WHERE answers_fts MATCH :q
                ORDER BY bm25(answers_fts) ASC, a.id DESC
                LIMIT :limit OFFSET :offset
            """)
            rows = db.execute(
                search_sql,
                {"q": match_query, "limit": PER_PAGE, "offset": offset},
            ).mappings().all()

            for r in rows:
                text_val = r["answer_text"] or ""
                truncated = False
                if len(text_val) > MAX_TEXT_LEN:
                    text_val = text_val[:MAX_TEXT_LEN]
                    truncated = True

                results.append({
                    "answer_id": r["answer_id"],
                    "question_id": r["question_id"],
                    "question_prompt": r["question_prompt"],
                    "author_id": r["author_id"],
                    "text": text_val,
                    "truncated": truncated,
                })


    ctx = {
        "request": request,
        "q": q,
        "page": page,
        "per_page": PER_PAGE,
        "total": total,
        "results": results,
        "too_short": False,
    }
    return templates.TemplateResponse("_results_answers.html", ctx)