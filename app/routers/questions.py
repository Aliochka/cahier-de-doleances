# app/routers/questions.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.choice_stats import choice_statistics
from app.db import SessionLocal
from app.services.questions import MAX_TEXT_LEN, get_question, read_question_answers
from app.services.questions import _dec_cursor as _dec_cursor
from app.services.questions import _enc_cursor as _enc_cursor
from app.web import templates

# Slugify helper (fallback)
try:
    from app.helpers import slugify  # type: ignore
except Exception:
    import re
    import unicodedata

    _keep = re.compile(r"[^a-z0-9\s-]")
    _collapse = re.compile(r"[-\s]+")

    def slugify(value: str | None, maxlen: int = 60) -> str:
        if not value:
            return "question"
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
        value = _keep.sub(" ", value)
        value = _collapse.sub("-", value).strip("-")
        return value[:maxlen].rstrip("-") or "question"


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _question_answers(
    db: Session, question_id: int, question_type: str, q: str | None, cursor: str | None
):
    rows, has_next, next_cursor, total = read_question_answers(
        db, question_id, question_type, q, cursor
    )
    answers = [
        {
            "id": r["answer_id"],
            "author_id": r["author_id"],
            "question_id": question_id,
            "created_at": r["submitted_at"],
            "body": (r["answer_text"] or "")[:MAX_TEXT_LEN],
        }
        for r in rows
    ]
    return answers, has_next, next_cursor, total


# =========================================================
# 0) INDEX /questions → redirige vers /search/questions
#    (évite le 404 JSON)
# =========================================================
@router.api_route(
    "/questions", methods=["GET", "HEAD"], response_class=HTMLResponse, name="questions_index"
)
def questions_index(request: Request):
    url = request.url_for("search_questions")
    return RedirectResponse(url.replace(query=request.url.query), status_code=308)


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
    page: int = Query(1, ge=1),  # legacy compat
    cursor: str | None = Query(None),  # scroll infini
    partial: bool = Query(False),  # rendu fragment (htmx)
    db: Session = Depends(get_db),
):
    # HEAD rapide : valide existence + slug sans charger la page
    if request.method == "HEAD":
        row = (
            db.execute(text("SELECT prompt FROM questions WHERE id = :qid"), {"qid": question_id})
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Question introuvable")
        canonical = slugify(row["prompt"] or f"question-{question_id}")
        if slug != canonical:
            url = request.url_for("question_detail", question_id=question_id, slug=canonical)
            return RedirectResponse(url.replace(query=request.url.query), status_code=308)
        return Response(status_code=200)

    # --- Question
    row = get_question(db, question_id)
    if not row:
        raise HTTPException(status_code=404, detail="Question introuvable")

    canonical_slug = slugify(row["prompt"] or f"question-{question_id}")
    if slug != canonical_slug:
        url = request.url_for("question_detail", question_id=question_id, slug=canonical_slug)
        return RedirectResponse(url.replace(query=request.url.query), status_code=308)

    q = (q or "").strip()
    answers, has_next, next_cursor, total = _question_answers(
        db, question_id, row["type"], q, cursor
    )

    # Rendu partiel pour HTMX
    if partial:
        return templates.TemplateResponse(
            request,
            "partials/_question_answers_list.html",
            {
                "request": request,
                "answers": answers,
                "has_next": has_next,
                "next_cursor": next_cursor,
                "q": q,
                "question": {
                    "id": row["id"],
                    "slug": canonical_slug,
                },
                "on_question_page": True,
            },
        )

    # Rendu complet
    return templates.TemplateResponse(
        request,
        "questions/detail.html",
        {
            "request": request,
            "question": {
                "id": row["id"],
                "question_code": row.get("question_code"),
                "title": row["prompt"],
                "slug": canonical_slug,
                "answers_count": total,
                "type": row["type"],
            },
            "answers": answers,
            "has_next": has_next,
            "next_cursor": next_cursor,
            "q": q,
            "page": page,  # legacy compat
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
    row = (
        db.execute(
            text("SELECT prompt FROM questions WHERE id = :qid"),
            {"qid": question_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Question introuvable")

    canonical = slugify(row["prompt"] or f"question-{question_id}")
    url = request.url_for("question_detail", question_id=question_id, slug=canonical)
    return RedirectResponse(url.replace(query=request.url.query), status_code=308)


# =========================================================
# 3) STATISTIQUES SINGLE_CHOICE — GET
# =========================================================
@router.get(
    "/questions/{question_id:int}/stats",
    response_class=JSONResponse,
    name="question_stats",
)
def question_stats(
    request: Request,
    question_id: int,
    db: Session = Depends(get_db),
):
    # Vérifier que la question existe et est de type single_choice
    question_row = get_question(db, question_id)

    if not question_row:
        raise HTTPException(status_code=404, detail="Question introuvable")

    if question_row["type"] not in ("single_choice", "multi_choice"):
        raise HTTPException(status_code=400, detail="Cette question n'est pas à choix")
    result = choice_statistics(db, question_id)
    stats_rows = result["stats"]
    total_answers = result["total_answers"]

    # Formater les données pour Chart.js
    chart_data = {
        "labels": [row["label"] for row in stats_rows],
        "datasets": [
            {
                "label": "Nombre de réponses",
                "data": [row["count"] for row in stats_rows],
                "backgroundColor": [
                    "#3b82f6",  # bleu
                    "#ef4444",  # rouge
                    "#10b981",  # vert
                    "#f59e0b",  # jaune
                    "#8b5cf6",  # violet
                    "#06b6d4",  # cyan
                ][: len(stats_rows)],
                "borderColor": [
                    "#1d4ed8",
                    "#dc2626",
                    "#059669",
                    "#d97706",
                    "#7c3aed",
                    "#0891b2",
                ][: len(stats_rows)],
                "borderWidth": 1,
            }
        ],
    }

    return {
        "question": {
            "id": question_row["id"],
            "prompt": question_row["prompt"],
            "type": question_row["type"],
        },
        "total_answers": total_answers,
        "total_selections": result["total_selections"],
        "stats": [
            {
                "option_id": row["option_id"],
                "label": row["label"],
                "count": row["count"],
                "percentage": float(row["percentage"]),
            }
            for row in stats_rows
        ],
        "chart_data": chart_data,
    }


# =========================================================
# 4) PARTIAL HTMX (liste des réponses) — GET
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
    page: int = Query(1, ge=1),  # legacy compatibility
    cursor: str | None = Query(None),
    db: Session = Depends(get_db),
):
    row = get_question(db, question_id)
    if not row:
        raise HTTPException(status_code=404, detail="Question introuvable")
    q = (q or "").strip()
    answers, has_next, next_cursor, _ = _question_answers(db, question_id, row["type"], q, cursor)
    return templates.TemplateResponse(
        request,
        "partials/_question_answers_list.html",
        {
            "request": request,
            "answers": answers,
            "has_next": has_next,
            "next_cursor": next_cursor,
            "q": q,
            "question": {"id": question_id, "slug": slugify(row["prompt"])},
            "on_question_page": True,
        },
    )
