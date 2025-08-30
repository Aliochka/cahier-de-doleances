# app/routers/questions.py
from __future__ import annotations

import math
import json
import base64
from typing import Any
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

# --- utils cursor opaque (base64 urlsafe(JSON)) ---
def _enc_cursor(obj: dict) -> str:
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    s = base64.urlsafe_b64encode(raw).decode()
    return s.rstrip("=")

def _dec_cursor(s: str | None) -> dict | None:
    if not s:
        return None
    pad = "=" * ((4 - len(s) % 4) % 4)
    data = base64.urlsafe_b64decode(s + pad)
    return json.loads(data.decode())

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
    page: int = Query(1, ge=1),                 # legacy compat
    cursor: str | None = Query(None),           # scroll infini
    partial: bool = Query(False),               # rendu fragment (htmx)
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

    # --- Scroll infini + filtre
    q = (q or "").strip()
    answers: list[dict[str, Any]] = []
    has_next = False
    next_cursor: str | None = None
    total = 0

    limit = PER_PAGE + 1
    cur = _dec_cursor(cursor)
    params = {"qid": question_id, "minlen": MIN_ANSWER_LEN, "limit": limit}
    
    # Curseur pour pagination keyset
    cursor_sql = ""
    if cur:
        cursor_sql = """
            AND (
                c.submitted_at < :last_date
                OR (c.submitted_at = :last_date AND a.id < :last_id)
            )
        """
        params["last_date"] = cur.get("date")
        params["last_id"] = int(cur.get("id", 0))

    # Total count (uniquement si pas de curseur - pour affichage initial)
    if not cursor:
        if q:
            total = db.execute(
                text("""
                    SELECT COUNT(1)
                    FROM answers a
                    JOIN contributions c ON c.id = a.contribution_id
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
                    JOIN contributions c ON c.id = a.contribution_id
                    WHERE a.question_id = :qid
                      AND a.text IS NOT NULL
                      AND char_length(btrim(a.text)) >= :minlen
                """),
                params,
            ).scalar_one()

    # Requête avec curseur
    if q:
        rows = db.execute(
            text(f"""
                SELECT a.id AS answer_id, a.text AS answer_text,
                       c.author_id AS author_id, c.submitted_at AS submitted_at
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND char_length(btrim(a.text)) >= :minlen
                  AND a.text ILIKE :like
                  {cursor_sql}
                ORDER BY c.submitted_at DESC, a.id DESC
                LIMIT :limit
            """),
            {**params, "like": f"%{q}%"},
        ).mappings().all()
    else:
        rows = db.execute(
            text(f"""
                SELECT a.id AS answer_id, a.text AS answer_text,
                       c.author_id AS author_id, c.submitted_at AS submitted_at
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                WHERE a.question_id = :qid
                  AND a.text IS NOT NULL
                  AND char_length(btrim(a.text)) >= :minlen
                  {cursor_sql}
                ORDER BY c.submitted_at DESC, a.id DESC
                LIMIT :limit
            """),
            params,
        ).mappings().all()

    # Traitement des résultats
    if len(rows) > PER_PAGE:
        has_next = True
        rows = rows[:-1]  # Retire le dernier élément (sentinel)
        last_row = rows[-1]
        next_cursor = _enc_cursor({
            "date": last_row["submitted_at"].isoformat() if last_row["submitted_at"] else None,
            "id": last_row["answer_id"],
        })

    answers = [{
        "id": r["answer_id"],
        "author_id": r["author_id"],
        "question_id": question_id,
        "created_at": r["submitted_at"],
        "body": (r["answer_text"] or "")[:MAX_TEXT_LEN],
    } for r in rows]

    # Rendu partiel pour HTMX
    if partial:
        return templates.TemplateResponse(
            "partials/_answers_list.html",
            {
                "request": request,
                "answers": answers,
                "has_next": has_next,
                "next_cursor": next_cursor,
                "q": q,
                "on_question_page": True,
            },
        )

    # Récupérer le type de question pour l'affichage conditionnel des stats
    question_type = db.execute(
        text("SELECT type FROM questions WHERE id = :qid"),
        {"qid": question_id}
    ).scalar_one_or_none()

    # Rendu complet
    return templates.TemplateResponse(
        "questions/detail.html",
        {
            "request": request,
            "question": {
                "id": row["id"],
                "question_code": row.get("question_code"),
                "title": row["prompt"],
                "slug": canonical_slug,
                "answers_count": total,
                "type": question_type,
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
    question_row = db.execute(
        text("SELECT id, type, prompt FROM questions WHERE id = :qid"),
        {"qid": question_id},
    ).mappings().first()
    
    if not question_row:
        raise HTTPException(status_code=404, detail="Question introuvable")
    
    if question_row["type"] != "single_choice":
        raise HTTPException(status_code=400, detail="Cette question n'est pas de type single_choice")
    
    # Récupérer les statistiques par option
    stats_rows = db.execute(
        text("""
            SELECT 
                o.id as option_id,
                o.label,
                o.position,
                COALESCE(COUNT(ao.option_id), 0) as count,
                COALESCE(ROUND(COUNT(ao.option_id) * 100.0 / NULLIF(SUM(COUNT(ao.option_id)) OVER(), 0), 2), 0) as percentage
            FROM options o
            LEFT JOIN answer_options ao ON ao.option_id = o.id
            WHERE o.question_id = :qid
            GROUP BY o.id, o.label, o.position
            ORDER BY o.position
        """),
        {"qid": question_id},
    ).mappings().all()
    
    # Calculer le total des réponses
    total_answers = sum(row["count"] for row in stats_rows)
    
    # Formater les données pour Chart.js
    chart_data = {
        "labels": [row["label"] for row in stats_rows],
        "datasets": [{
            "label": "Nombre de réponses",
            "data": [row["count"] for row in stats_rows],
            "backgroundColor": [
                "#3b82f6",  # bleu
                "#ef4444",  # rouge
                "#10b981",  # vert
                "#f59e0b",  # jaune
                "#8b5cf6",  # violet
                "#06b6d4",  # cyan
            ][:len(stats_rows)],
            "borderColor": [
                "#1d4ed8",
                "#dc2626", 
                "#059669",
                "#d97706",
                "#7c3aed",
                "#0891b2",
            ][:len(stats_rows)],
            "borderWidth": 1
        }]
    }
    
    return {
        "question": {
            "id": question_row["id"],
            "prompt": question_row["prompt"],
            "type": question_row["type"]
        },
        "total_answers": total_answers,
        "stats": [
            {
                "option_id": row["option_id"],
                "label": row["label"],
                "count": row["count"],
                "percentage": float(row["percentage"])
            }
            for row in stats_rows
        ],
        "chart_data": chart_data
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
