# app/routers/answer_detail.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from app.db import SessionLocal
from app.web import templates

router = APIRouter()

@router.get("/answers/{answer_id}", response_class=HTMLResponse, name="answer_detail")
def answer_detail(request: Request, answer_id: int):
    with SessionLocal() as db:
        row = db.execute(text("""
            SELECT
                a.id              AS answer_id,
                a.text            AS answer_text,
                q.id              AS question_id,
                q.prompt          AS question_prompt,
                c.author_id       AS author_id,
                au.name           AS author_name,
                c.submitted_at    AS submitted_at
            FROM answers a
            JOIN contributions c ON c.id = a.contribution_id
            LEFT JOIN authors au  ON au.id = c.author_id
            JOIN questions q      ON q.id = a.question_id
            WHERE a.id = :aid
        """), {"aid": answer_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Réponse introuvable")

    answer = {
        "id": row["answer_id"],
        "text": row["answer_text"] or "",
        "question_id": row["question_id"],
        "question_prompt": row["question_prompt"],
        "author_id": row["author_id"],
        "author_name": row["author_name"],
        "submitted_at": row["submitted_at"],
    }

    return templates.TemplateResponse(
        "answers/detail.html",
        {"request": request, "answer": answer}
    )
