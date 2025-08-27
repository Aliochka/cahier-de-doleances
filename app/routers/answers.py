# app/routers/answers.py
from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.db import SessionLocal
from app.web import templates

# slugify helper (fallback si indisponible)
try:
    from app.helpers import slugify  # type: ignore
except Exception:
    import re, unicodedata
    _keep = re.compile(r"[^a-z0-9\s-]")
    _collapse = re.compile(r"[-\s]+")
    def slugify(value: str | None, maxlen: int = 60) -> str:
        if not value:
            return "contenu"
        value = value.replace("œ","oe").replace("Œ","oe").replace("æ","ae").replace("Æ","ae")
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
        value = _keep.sub(" ", value)
        value = _collapse.sub("-", value).strip("-")
        return (value[:maxlen].rstrip("-") or "contenu")

router = APIRouter()

@router.get("/answers/{answer_id}", response_class=HTMLResponse, name="answer_detail")
def answer_detail(request: Request, answer_id: int):
    with SessionLocal() as db:
        row = db.execute(text("""
            SELECT
                a.id            AS answer_id,
                a.text          AS answer_text,
                q.id            AS question_id,
                q.prompt        AS question_prompt,
                c.author_id     AS author_id,
                au.name         AS author_name,
                c.submitted_at  AS submitted_at
            FROM answers a
            JOIN contributions c ON c.id = a.contribution_id
            LEFT JOIN authors au  ON au.id = c.author_id
            JOIN questions q      ON q.id = a.question_id
            WHERE a.id = :aid
        """), {"aid": answer_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Réponse introuvable")

    q_slug = slugify(row["question_prompt"] or f"question-{row['question_id']}")
    author_label = row["author_name"] or f"Auteur #{row['author_id']}"
    author_slug = slugify(author_label)

    answer = {
        "id": row["answer_id"],
        "text": row["answer_text"] or "",
        "question_id": row["question_id"],
        "question_prompt": row["question_prompt"],
        "question_slug": q_slug,            # → /questions/{id}-{slug}
        "author_id": row["author_id"],
        "author_name": row["author_name"],
        "author_slug": author_slug,         # → /authors/{id}-{slug}
        "submitted_at": row["submitted_at"],
    }

    return templates.TemplateResponse("answers/detail.html", {"request": request, "answer": answer})
