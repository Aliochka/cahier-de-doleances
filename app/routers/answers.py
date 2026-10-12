# app/routers/answers.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.db import SessionLocal
from app.helpers import public_author
from app.services.answers import get_answer
from app.web import templates

# slugify helper (fallback si indisponible)
try:
    from app.helpers import slugify  # type: ignore
except Exception:
    import re
    import unicodedata

    _keep = re.compile(r"[^a-z0-9\s-]")
    _collapse = re.compile(r"[-\s]+")

    def slugify(value: str | None, maxlen: int = 60) -> str:
        if not value:
            return "contenu"
        value = value.replace("œ", "oe").replace("Œ", "oe").replace("æ", "ae").replace("Æ", "ae")
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
        value = _keep.sub(" ", value)
        value = _collapse.sub("-", value).strip("-")
        return value[:maxlen].rstrip("-") or "contenu"


router = APIRouter()


@router.get("/answers/{answer_id}", response_class=HTMLResponse, name="answer_detail")
def answer_detail(request: Request, answer_id: int):
    with SessionLocal() as db:
        row = get_answer(db, answer_id)

    if not row:
        raise HTTPException(status_code=404, detail="Réponse introuvable")

    q_slug = slugify(row["question_prompt"] or f"question-{row['question_id']}")
    author = public_author(row["author_id"], row["author_name"], row["author_is_anonymous"])

    answer = {
        "id": row["answer_id"],
        "text": row["answer_text"] or "",
        "question_id": row["question_id"],
        "question_prompt": row["question_prompt"],
        "question_slug": q_slug,  # → /questions/{id}-{slug}
        "author_id": row["author_id"],
        "author_name": author["name"],
        "author_slug": author["slug"],  # → /authors/{id}-{slug}
        "submitted_at": row["submitted_at"],
    }

    return templates.TemplateResponse(
        request, "answers/detail.html", {"request": request, "answer": answer}
    )
