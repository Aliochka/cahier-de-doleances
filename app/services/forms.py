"""Shared public form reads; no contributions or individual answers are loaded."""

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session


def list_forms(db: Session) -> list[RowMapping]:
    return list(
        db.execute(
            text("""
            SELECT f.id, f.name, COUNT(q.id)::int AS questions_count
            FROM forms f
            LEFT JOIN questions q ON q.form_id = f.id
            GROUP BY f.id, f.name
            ORDER BY f.id
        """)
        )
        .mappings()
        .all()
    )


def get_form(db: Session, form_id: int) -> RowMapping | None:
    return (
        db.execute(
            text("""
        SELECT f.id, f.name, COUNT(q.id)::int AS questions_count
        FROM forms f
        LEFT JOIN questions q ON q.form_id = f.id
        WHERE f.id = :fid
        GROUP BY f.id
    """),
            {"fid": form_id},
        )
        .mappings()
        .first()
    )


def form_questions(db: Session, form_id: int) -> list[RowMapping]:
    return list(
        db.execute(
            text("""
        SELECT q.id, q.form_id, q.position, q.prompt, q.type
        FROM questions q
        WHERE q.form_id = :fid
        ORDER BY COALESCE(q.position, 999999), q.id
    """),
            {"fid": form_id},
        )
        .mappings()
        .all()
    )
