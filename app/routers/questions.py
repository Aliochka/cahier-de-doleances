# app/routers/questions.py
from __future__ import annotations

import math
from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.web import templates

# Slugify helper (fallback)
try:
    from app.helpers import slugify  # type: ignore
except Exception:
    import re, unicodedata
    _keep = re.compile(r"[^a-z0-9\s-]")
    _collapse = re.compile(r"[-\s]+")
    def slugify(value: str | None, maxlen: int = 60) -> str:
        if not value:
            return "question"
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
        value = _keep.sub(" ", value)
        value = _collapse.sub("-", value).strip("-")
        return (value[:maxlen].rstrip("-") or "question")

router = APIRouter()

PER_PAGE = 20
MIN_ANSWER_LEN = 60
MAX_TEXT_LEN = 20_000

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =========================================================
# 0) INDEX /questions → redirige vers /search/questions
#    (évite le 404 JSON)
# =========================================================
@router.api_route("/questions", methods=["GET", "HEAD"], response_class=HTMLResponse, name="questions_index")
def questions_index(request: Request):
    url = request.url_for("search_questions")
    return RedirectResponse(url, status_code=308)

# =========================================================
# 1) DÉTAIL (canonique) /questions/{id:int}-{slug}  — GET + HEAD
# =========================================================
@router.api_route(
    "/questions/{question_id:int}-{slug}",
    methods=["GET", "HEAD"],
    response_class=HTMLResponse,
    name="question_detail",
)
def question_detail(
    request: Request,
    question_id: int,
    slug: str,
    q: str | None = Query(None, description="Filtre texte dans les réponses"),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    # HEAD rapide : valide existence + slug sans charger la page
    if request.method == "HEAD":
        row = db.execute(text("SELECT prompt FROM questions WHERE id = :qid"), {"qid": question_id}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Question introuvable")
        canonical = slugify(row["prompt"] or f"question-{question_id}")
        if slug != canonical:
            url = request.url_for("question_detail", question_id=question_id, slug=canonical)
            return RedirectResponse(url, status_code=308)
        return Response(status_code=200)

    # DEBUG: ?debug=1 → infos JSON (utile si besoin)
    if "debug" in request.query_params:
        row = db.execute(text("SELECT id, prompt FROM questions WHERE id=:qid"), {"qid": question_id}).mappings().first()
        return JSONResponse(
            {
                "qid": question_id,
                "row_is_none": row is None,
                "prompt": (row or {}).get("prompt") if row else None,
                "requested_slug": slug,
                "canonical": slugify(((row or {}).get("prompt") or f"question-{question_id}") if row else f"question-{question_id}"),
            },
            status_code=200 if row else 404,
        )

    # --- Question
    row = db.execute(
        text("SELECT id, question_code, prompt FROM questions WHERE id = :qid"),
        {"qid": question_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Question introuvable")

    canonical_slug = slugify(row["prompt"] or f"question-{question_id}")
    if slug != canonical_slug:
        url = request.url_for("question_detail", question_id=question_id, slug=canonical_slug)
        if q:
            url += f"?q={q}" + (f"&page={page}" if page and page != 1 else "")
        elif page and page != 1:
            url += f"?page={page}"
        return RedirectResponse(url, status_code=308)

    # --- Pagination + filtre
    q = (q or "").strip()
    offset = (page - 1) * PER_PAGE
    params = {"qid": question_id, "minlen": MIN_ANSWER_LEN}

    # total
    if q:
        total = db.execute(
            text("""
                SELECT COUNT(1)
                FROM answers a
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND char_length(btrim(a.text)) >= :minlen
                  AND a.text ILIKE :like
            """),
            {**params, "like": f"%{q}%"},
        ).scalar_one()
    else:
        total = db.execute(
            text("""
                SELECT COUNT(1)
                FROM answers a
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND char_length(btrim(a.text)) >= :minlen
            """),
            params,
        ).scalar_one()

    # page rows
    if q:
        rows = db.execute(
            text("""
                SELECT a.id AS answer_id, a.text AS answer_text,
                       c.author_id AS author_id, c.submitted_at AS submitted_at
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND char_length(btrim(a.text)) >= :minlen
                  AND a.text ILIKE :like
                ORDER BY c.submitted_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {**params, "like": f"%{q}%", "limit": PER_PAGE, "offset": offset},
        ).mappings().all()
    else:
        rows = db.execute(
            text("""
                SELECT a.id AS answer_id, a.text AS answer_text,
                       c.author_id AS author_id, c.submitted_at AS submitted_at
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND char_length(btrim(a.text)) >= :minlen
                ORDER BY c.submitted_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {**params, "limit": PER_PAGE, "offset": offset},
        ).mappings().all()

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
            "question": {
                "id": row["id"],
                "question_code": row.get("question_code"),
                "title": row["prompt"],
                "slug": canonical_slug,
            },
            "answers": answers,
            "q": q,
            "page": page,
            "total_pages": total_pages,
            "on_question_page": True,
        },
    )

# =========================================================
# 2) LEGACY /questions/{id:int} → redirection vers slug
# =========================================================
@router.api_route(
    "/questions/{question_id:int}",
    methods=["GET", "HEAD"],
    response_class=HTMLResponse,
    name="question_detail_legacy",
)
def question_detail_legacy(
    request: Request,
    question_id: int,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    row = db.execute(
        text("SELECT prompt FROM questions WHERE id = :qid"),
        {"qid": question_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Question introuvable")

    canonical = slugify(row["prompt"] or f"question-{question_id}")
    url = request.url_for("question_detail", question_id=question_id, slug=canonical)
    if q:
        url += f"?q={q}" + (f"&page={page}" if page and page != 1 else "")
    elif page and page != 1:
        url += f"?page={page}"
    return RedirectResponse(url, status_code=308)

# =========================================================
# 3) PARTIAL HTMX (liste des réponses) — GET
# =========================================================
@router.get(
    "/questions/{question_id:int}/partials/answers",
    response_class=HTMLResponse,
    name="question_answers_partial",
)
def question_answers_partial(
    request: Request,
    question_id: int,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    # Réutilise la vue principale pour rester DRY
    resp = question_detail(request, question_id, slug=slugify("x"), q=q, page=page, db=db)
    if isinstance(resp, RedirectResponse):
        # si slug faux dans l’appel direct, on renvoie vide plutôt que rediriger
        return templates.TemplateResponse(
            "partials/_answers_list.html",
            {"request": request, "answers": [], "page": 1, "total_pages": 1, "q": q or ""},
        )
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
