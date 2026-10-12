# app/routers/search.py
from __future__ import annotations

from html import escape
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from app.db import SessionLocal
from app.helpers import (
    highlight_text_python,
    postprocess_excerpt,
    public_author,
    slugify,  # type: ignore
)
from app.search_errors import handle_search_errors
from app.services.search import (
    MAX_TEXT_LEN,
    PER_PAGE,
    PREVIEW_MAXLEN,
    read_answer_search,
    read_catalog_search,
)
from app.web import templates

router = APIRouter()


# --- helpers UI ---
def _clean_snippet(s: str, maxlen: int) -> tuple[str, bool]:
    if s is None:
        return "", False
    is_trunc = len(s) > maxlen
    s = s[:maxlen].replace("\r", " ").replace("\n", " ")
    return s, is_trunc


# ===========================
#   /search/answers
#   - FTS Postgres
#   - keyset pagination + htmx partial
#   - SEO: noindex (full: follow / partial: nofollow — géré côté template/en-têtes)
# ===========================
@router.get("/search/answers", name="search_answers", response_class=HTMLResponse)
def search_answers(
    request: Request,
    q: str = Query("", description="Requête"),
    page: int = Query(1, ge=1),  # compat (non utilisé)
    cursor: str | None = Query(None),  # scroll infini
    partial: bool = Query(False),  # rendu fragment (htmx)
):
    q = (q or "").strip()

    answers: list[dict[str, Any]] = []
    has_next = False
    next_cursor: str | None = None

    with SessionLocal() as db, handle_search_errors(db):
        rows, has_next, next_cursor = read_answer_search(db, q, cursor)

        for r in rows:
            raw = (r["answer_text"] or "")[:MAX_TEXT_LEN]
            if len(q) >= 2:
                snippet = postprocess_excerpt(
                    highlight_text_python(escape(raw), q, max_words=35, min_words=15)
                )
            else:
                snippet, _ = _clean_snippet(raw, PREVIEW_MAXLEN)
                snippet = postprocess_excerpt(snippet)
            q_title = r["question_prompt"]
            answers.append(
                {
                    "id": r["answer_id"],
                    "author_id": r["author_id"],
                    "author_name": public_author(
                        r["author_id"], r["author_name"], r["author_is_anonymous"]
                    )["name"],
                    "question_id": r["question_id"],
                    "question_title": q_title,
                    "question_slug": slugify(q_title or f"question-{r['question_id']}"),
                    "created_at": r["submitted_at"],
                    "body": snippet,
                    "body_is_html": len(q) >= 2,
                }
            )

    ctx = {
        "request": request,
        "q": q,
        "answers": answers,
        "on_answers_search": True,  # flag metas (noindex + canonical ?q=)
        "page_size": PER_PAGE,
        "has_next": has_next,
        "next_cursor": next_cursor,
    }
    # Détecter les requêtes HTMX via headers ou paramètre
    is_htmx = partial or "HX-Request" in request.headers

    if is_htmx:
        # Si c'est un infinite scroll (cursor présent), utiliser le template d'append
        if cursor:
            resp = templates.TemplateResponse(request, "partials/_answers_list_append.html", ctx)
        else:
            # Première recherche HTMX, template complet
            resp = templates.TemplateResponse(request, "partials/_answers_list.html", ctx)
        return resp

    resp = templates.TemplateResponse(request, "search/answers.html", ctx)
    return resp


# ===========================
#   /search/questions
#   - Deux sections : FORMULAIRES + QUESTIONS
#   - FTS + ts_rank, FR + unaccent
#   - Surlignage dans le titre des questions uniquement
#   - Badge "0 réponse" basé sur question_stats.answers_count
#   - Slug renvoyé pour lier vers /questions/{id}-{slug}
#   - Scroll infini indépendant par section (cursor_forms / cursor_questions)
# ===========================
@router.get("/search/questions", name="search_questions", response_class=HTMLResponse)
def search_questions(
    request: Request,
    q: str | None = Query(None, description="Requête"),
    # scroll infini, 1 curseur par section
    cursor_forms: str | None = Query(None),
    cursor_questions: str | None = Query(None),
    # rendu fragment (htmx) : "forms" | "questions" | None
    section: str | None = Query(None),
    partial: bool = Query(False),
):
    q = (q or "").strip()

    # Résultats
    forms: list[dict] = []
    questions: list[dict] = []

    # Pagination/next-cursors (par section)
    has_next_forms = False
    has_next_questions = False
    next_cursor_forms: str | None = None
    next_cursor_questions: str | None = None

    with SessionLocal() as db, handle_search_errors(db):
        (
            forms_rows,
            question_rows,
            has_next_forms,
            has_next_questions,
            next_cursor_forms,
            next_cursor_questions,
        ) = read_catalog_search(db, q, cursor_forms, cursor_questions, section=section)
        for r in forms_rows:
            forms.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "questions_count": int(r["questions_count"]),
                    # slug utile si besoin d'URL lisibles plus tard
                    "slug": slugify(r["name"] or f"form-{r['id']}"),
                    "score": float(r.get("score", 0.0) or 0.0),
                }
            )

        for r in question_rows:
            title = r.get("prompt")
            questions.append(
                {
                    "id": r["id"],
                    "question_code": r.get("question_code"),
                    "title": title,
                    "type": r.get("type"),
                    # surlignage seulement côté titre
                    "prompt_hl": r.get("prompt_hl"),
                    "answers_count": int(r.get("answers_count", 0) or 0),
                    "slug": slugify(title or f"question-{r['id']}"),
                    "score": float(r.get("score", 0.0) or 0.0),
                }
            )

    # ---------------------------------------
    # Contexte template
    # ---------------------------------------
    ctx = {
        "request": request,
        "q": q,
        # Sections
        "forms": forms,
        "questions": questions,
        # Cursors/flags par section
        "page_size": PER_PAGE,
        "has_next_forms": has_next_forms,
        "has_next_questions": has_next_questions,
        "next_cursor_forms": next_cursor_forms,
        "next_cursor_questions": next_cursor_questions,
        # SEO hint
        "on_questions_search": True,  # (noindex + canonical ?q=) si besoin
    }

    # Détecter les requêtes HTMX via headers ou paramètre
    is_htmx = partial or "HX-Request" in request.headers

    # Rendu partiel (htmx) : une seule section
    if is_htmx:
        if section == "forms":
            return templates.TemplateResponse(request, "partials/_forms_list.html", ctx)
        if section == "questions":
            return templates.TemplateResponse(request, "partials/_questions_list.html", ctx)
        # par défaut, recharge les deux colonnes
        return templates.TemplateResponse(request, "partials/_search_sections.html", ctx)

    # Rendu complet (les 2 sections)
    return templates.TemplateResponse(request, "search/questions.html", ctx)
