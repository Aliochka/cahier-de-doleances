"""Shared single-answer read, independent of account/session information."""

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session


def get_answer(db: Session, answer_id: int) -> RowMapping | None:
    return (
        db.execute(
            text("""
        SELECT
            a.id            AS answer_id,
            a.text          AS answer_text,
            q.id            AS question_id,
            q.prompt        AS question_prompt,
            q.type AS question_type, q.position AS question_position, q.form_id AS form_id,
            c.id AS contribution_id,
            c.author_id     AS author_id,
            au.name         AS author_name,
            au.is_anonymous AS author_is_anonymous,
            c.submitted_at  AS submitted_at
        FROM answers a
        JOIN contributions c ON c.id = a.contribution_id
        LEFT JOIN authors au  ON au.id = c.author_id
        JOIN questions q      ON q.id = a.question_id
        WHERE a.id = :aid
    """),
            {"aid": answer_id},
        )
        .mappings()
        .first()
    )
