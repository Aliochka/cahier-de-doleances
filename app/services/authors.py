"""Author reads shared with HTML; no account or import metadata is selected."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_author(db: Session, author_id: int):
    return (
        db.execute(
            text("SELECT id, name, is_anonymous FROM authors WHERE id = :aid"),
            {"aid": author_id},
        )
        .mappings()
        .first()
    )


def author_contributions(db: Session, author_id: int, after_id: int, limit: int):
    # A contribution must have an actual answer to a question of its own form.
    # Only existence is checked; no answer bodies or exact counts are loaded.
    return (
        db.execute(
            text("""
                SELECT c.id, c.form_id, c.submitted_at, f.name AS form_name
                FROM contributions c JOIN forms f ON f.id = c.form_id
                WHERE c.author_id = :aid AND c.id > :after
                  AND EXISTS (
                      SELECT 1 FROM answers a JOIN questions q ON q.id = a.question_id
                      WHERE a.contribution_id = c.id AND q.form_id = c.form_id
                  )
                ORDER BY c.id ASC LIMIT :limit
            """),
            {"aid": author_id, "after": after_id, "limit": limit},
        )
        .mappings()
        .all()
    )
