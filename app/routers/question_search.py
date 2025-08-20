from __future__ import annotations
from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import text, bindparam
from sqlalchemy.orm import Session
from app.db import SessionLocal
from sqlalchemy.exc import OperationalError
from fastapi import HTTPException
from app.web import templates

PAGE_SIZE_DEFAULT = 20
MIN_ANSWER_LEN = 40  # filtre lisibilité

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/search/questions", response_class=HTMLResponse)
def search_questions_page(
    request: Request,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
):
    """
    Shell de la page. Les résultats sont chargés via htmx si q est présent.
    """
    return templates.TemplateResponse(
        "search_questions.html",
        {
            "request": request,
            "q": q or "",
            "page": page,
            "page_size": PAGE_SIZE_DEFAULT,
        },
    )

@router.get("/partials/search/questions", response_class=HTMLResponse)
def partials_search_questions(
    request: Request,
    q: str = Query("", min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Retourne un fragment HTML : cartes 'question' + 3 réponses aléatoires par question.
    Deux requêtes SQL seulement (FTS + réponses), pas de COUNT global pour préserver les perfs.
    """
    if not q.strip():
        return templates.TemplateResponse(
            "_results_questions.html",
            {"request": request, "results": [], "q": q, "page": page, "has_next": False},
        )

    offset = (page - 1) * page_size

    # 1) Récupérer les questions par FTS (bm25 pour la pertinence + highlight)
    # Limite "page_size + 1" pour savoir s'il y a une page suivante.
    sql_qmatch = text("""
        WITH qmatch AS (
            SELECT q.id,
                   q.question_code,
                   q.prompt,
                   bm25(question_fts) AS score,
                   highlight(question_fts, 0, '<mark>', '</mark>') AS prompt_hl
            FROM question_fts
            JOIN questions q ON q.id = question_fts.rowid
            WHERE question_fts MATCH :query
            ORDER BY score
            LIMIT :limit OFFSET :offset
        )
        SELECT * FROM qmatch;
    """)

    rows = db.execute(
        sql_qmatch,
        {
            "query": q,
            "limit": page_size + 1,  # pour détecter has_next
            "offset": offset,
        },
    ).mappings().all()

    has_next = len(rows) > page_size
    rows = rows[:page_size]

    question_ids = [r["id"] for r in rows]
    if not question_ids:
        return templates.TemplateResponse(
            "_results_questions.html",
            {"request": request, "results": [], "q": q, "page": page, "has_next": False},
        )

    # 2) Prendre jusqu'à 3 réponses aléatoires par question (une seule requête)
    # On filtre des réponses textuelles non vides, on évite les très courtes (>= 40 chars).
    sql_answers = text("""
        WITH picks AS (
            SELECT a.question_id,
                   a.id AS answer_id,
                   a.text AS answer_text,
                   ROW_NUMBER() OVER(
                       PARTITION BY a.question_id
                       ORDER BY random()
                   ) AS rn
            FROM answers a
            WHERE a.question_id IN :ids
              AND a.text IS NOT NULL
              AND length(a.text) >= 40
        )
        SELECT question_id, answer_id, answer_text
        FROM picks
        WHERE rn <= 3;
    """).bindparams(bindparam("ids", expanding=True))

    ans_rows = db.execute(sql_answers, {"ids": tuple(question_ids)}).mappings().all()

    # Regrouper par question_id côté Python
    by_qid: dict[int, list[dict]] = {qid: [] for qid in question_ids}
    for ar in ans_rows:
        by_qid[ar["question_id"]].append(
            {"id": ar["answer_id"], "text": ar["answer_text"]}
        )

    # Structurer les résultats pour le template
    results = []
    for r in rows:
        results.append(
            {
                "id": r["id"],
                "question_code": r["question_code"],
                "prompt": r["prompt"],
                "prompt_hl": r["prompt_hl"],  # HTML déjà échappé par SQLite; on marquera |safe
                "answers": by_qid.get(r["id"], []),
            }
        )

    return templates.TemplateResponse(
        "_results_questions.html",
        {
            "request": request,
            "results": results,
            "q": q,
            "page": page,
            "has_next": has_next,
        },
    )

# --- Page principale (shell) ---
@router.get("/questions/{question_id}", response_class=HTMLResponse, name="question_detail")
def question_detail(
    request: Request,
    question_id: int,
    q: str | None = Query(None, description="Recherche locale dans les réponses"),
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=100),
    db: Session = Depends(get_db),
):
    # Récupère l'énoncé de la question (title/prompt/code)
    row = db.execute(
        text("""
            SELECT q.id, q.question_code, q.prompt, q.section, f.name AS form_name
            FROM questions q
            LEFT JOIN forms f ON f.id = q.form_id
            WHERE q.id = :qid
        """),
        {"qid": question_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Question introuvable")

    return templates.TemplateResponse(
        "question.html",
        {
            "request": request,
            "question": row,
            "q": q or "",
            "page": page,
            "page_size": page_size,
            "min_answer_len": MIN_ANSWER_LEN,
        },
    )

# --- Partial HTMX : liste paginée des réponses (+ count) ---
@router.get(
    "/questions/{question_id}/partials/answers",
    response_class=HTMLResponse,
    name="question_answers_partial",
)
def question_answers_partial(
    request: Request,
    question_id: int,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=100),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size
    params = {
        "qid": question_id,
        "limit": page_size + 1,  # pour détecter has_next
        "offset": offset,
        "minlen": MIN_ANSWER_LEN,
    }

    # ----- COUNT total -----
    total = 0
    if q and q.strip():
        # Essaye FTS (answers_fts), sinon fallback LIKE
        try:
            total = db.execute(
                text("""
                    SELECT COUNT(1)
                    FROM answers a
                    JOIN answers_fts fts ON fts.rowid = a.id
                    WHERE a.question_id = :qid
                      AND a.text IS NOT NULL
                      AND length(a.text) >= :minlen
                      AND fts MATCH :q
                """),
                {**params, "q": q},
            ).scalar_one()
            use_fts = True
        except OperationalError as e:
            if "no such table: answers_fts" not in str(e):
                raise
            # Fallback LIKE
            total = db.execute(
                text("""
                    SELECT COUNT(1)
                    FROM answers a
                    WHERE a.question_id = :qid
                      AND a.text IS NOT NULL
                      AND length(a.text) >= :minlen
                      AND a.text LIKE :like
                """),
                {**params, "like": f"%{q}%"},
            ).scalar_one()
            use_fts = False
    else:
        total = db.execute(
            text("""
                SELECT COUNT(1)
                FROM answers a
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND length(a.text) >= :minlen
            """),
            params,
        ).scalar_one()
        use_fts = False

    # ----- RÉSULTATS page courante -----
    if q and q.strip():
        if use_fts:
            sql_page = text("""
                SELECT a.id AS answer_id,
                       a.text AS answer_text,
                       c.submitted_at AS submitted_at,
                       au.zipcode AS zipcode
                FROM answers a
                JOIN answers_fts fts ON fts.rowid = a.id
                JOIN contributions c ON c.id = a.contribution_id
                LEFT JOIN authors au ON au.id = c.author_id
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND length(a.text) >= :minlen
                  AND fts MATCH :q
                ORDER BY c.submitted_at DESC
                LIMIT :limit OFFSET :offset
            """)
            rows = db.execute(sql_page, {**params, "q": q}).mappings().all()
        else:
            sql_page = text("""
                SELECT a.id AS answer_id,
                       a.text AS answer_text,
                       c.submitted_at AS submitted_at,
                       au.zipcode AS zipcode
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                LEFT JOIN authors au ON au.id = c.author_id
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND length(a.text) >= :minlen
                  AND a.text LIKE :like
                ORDER BY c.submitted_at DESC
                LIMIT :limit OFFSET :offset
            """)
            rows = db.execute(sql_page, {**params, "like": f"%{q}%"}).mappings().all()
    else:
        # Sans recherche : plus récentes
        sql_page = text("""
            SELECT a.id AS answer_id,
                   a.text AS answer_text,
                   c.submitted_at AS submitted_at,
                   au.zipcode AS zipcode
            FROM answers a
            JOIN contributions c ON c.id = a.contribution_id
            LEFT JOIN authors au ON au.id = c.author_id
            WHERE a.question_id = :qid
              AND a.text IS NOT NULL
              AND length(a.text) >= :minlen
            ORDER BY c.submitted_at DESC
            LIMIT :limit OFFSET :offset
        """)
        rows = db.execute(sql_page, params).mappings().all()

    has_next = len(rows) > page_size  # on avait prévu limit=page_size+1, mais ici rows==limit (pas +1) → adaptons
    # Comme on n'a pas fetch +1 (on l’a mis dans LIMIT), on peut recalculer:
    # On considère has_next si offset+page_size < total
    has_next = (offset + page_size) < total
    rows = rows[:page_size]

    return templates.TemplateResponse(
        "_question_answers.html",
        {
            "request": request,
            "answers": rows,
            "q": q or "",
            "page": page,
            "page_size": page_size,
            "has_next": has_next,
            "total": total,
            "question_id": question_id,
        },
    )
