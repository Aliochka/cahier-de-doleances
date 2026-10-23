"""Targeted contribution reads and the unchanged historical ordinal selector."""

import json

from sqlalchemy import text
from sqlalchemy.orm import Session


def select_legacy_contribution(db: Session, form_id: int, contrib: str | None):
    try:
        requested = int(contrib) if contrib else 1
    except (ValueError, TypeError):
        requested = 1
    total = db.execute(
        text("SELECT COUNT(*)::int FROM contributions WHERE form_id = :fid"), {"fid": form_id}
    ).scalar_one()
    index = max(1, min(max(1, requested), max(total, 1)))
    row = (
        db.execute(
            text("""
            SELECT c.id FROM contributions c WHERE c.form_id = :fid
            ORDER BY c.submitted_at ASC NULLS LAST, c.id ASC OFFSET :off LIMIT 1
        """),
            {"fid": form_id, "off": index - 1},
        )
        .mappings()
        .first()
    )
    return total, index, row["id"] if row else None


def get_contribution(db: Session, form_id: int, contribution_id: int):
    return (
        db.execute(
            text("""
            SELECT c.id, c.form_id, c.submitted_at, f.name AS form_name,
                   au.id AS author_id, au.name AS author_name, au.is_anonymous AS author_is_anonymous
            FROM contributions c JOIN forms f ON f.id = c.form_id
            LEFT JOIN authors au ON au.id = c.author_id
            WHERE c.id = :cid AND c.form_id = :fid
        """),
            {"cid": contribution_id, "fid": form_id},
        )
        .mappings()
        .first()
    )


def contribution_neighbors(db: Session, form_id: int, contribution_id: int, submitted_at):
    """Same order as the ordinal selector, using bounded composite-index seeks.

    Split the dated and undated ranges so each lookup can use
    ix_contributions_form_submit_id. No COUNT, OFFSET or whole-form window.
    """
    if submitted_at is None:
        query = """
            SELECT COALESCE(
                (SELECT id FROM contributions
                 WHERE form_id = :fid AND submitted_at IS NULL AND id < :cid
                 ORDER BY id DESC LIMIT 1),
                (SELECT id FROM contributions
                 WHERE form_id = :fid AND submitted_at IS NOT NULL
                 ORDER BY submitted_at DESC, id DESC LIMIT 1)
            ) AS previous_id,
            (SELECT id FROM contributions
             WHERE form_id = :fid AND submitted_at IS NULL AND id > :cid
             ORDER BY id ASC LIMIT 1) AS next_id
        """
    else:
        query = """
            SELECT
                (SELECT id FROM contributions
                 WHERE form_id = :fid AND (submitted_at, id) < (:submitted, :cid)
                 ORDER BY submitted_at DESC, id DESC LIMIT 1) AS previous_id,
                COALESCE(
                    (SELECT id FROM contributions
                     WHERE form_id = :fid AND (submitted_at, id) > (:submitted, :cid)
                     ORDER BY submitted_at ASC, id ASC LIMIT 1),
                    (SELECT id FROM contributions
                     WHERE form_id = :fid AND submitted_at IS NULL
                     ORDER BY id ASC LIMIT 1)
                ) AS next_id
        """
    return (
        db.execute(text(query), {"fid": form_id, "cid": contribution_id, "submitted": submitted_at})
        .mappings()
        .one()
    )


def contribution_answers(db: Session, contribution_id: int, form_id: int | None = None):
    # HTML keeps its historical text filter and ordering; JSON includes all actual rows.
    condition = (
        "AND a.text IS NOT NULL AND trim(a.text) != ''"
        if form_id is None
        else "AND q.form_id = :fid"
    )
    tie_order = "" if form_id is None else ", a.position ASC NULLS LAST, a.id ASC"
    extra_fields = (
        ""
        if form_id is None
        else ", a.position AS answer_position, a.value_json, q.type, q.form_id, q.position"
    )
    return (
        db.execute(
            text(f"""
            SELECT a.id, a.question_id, a.text, q.prompt {extra_fields},
                   c.author_id, c.submitted_at
            FROM answers a JOIN questions q ON q.id = a.question_id
            JOIN contributions c ON c.id = a.contribution_id
            WHERE a.contribution_id = :cid {condition}
            ORDER BY COALESCE(q.position, 999999), q.id {tie_order}
        """),
            {"cid": contribution_id, "fid": form_id},
        )
        .mappings()
        .all()
    )


def contribution_options(db: Session, form_id: int, contribution_id: int):
    return (
        db.execute(
            text("""
            SELECT ao.answer_id, o.id, o.label, o.position
            FROM answers a JOIN questions q ON q.id = a.question_id
            JOIN answer_options ao ON ao.answer_id = a.id
            JOIN options o ON o.id = ao.option_id AND o.question_id = q.id
            WHERE a.contribution_id = :cid AND q.form_id = :fid
            ORDER BY o.position ASC NULLS LAST, o.id ASC
        """),
            {"cid": contribution_id, "fid": form_id},
        )
        .mappings()
        .all()
    )


def public_values(value_json: str | None, question_type: str):
    """Whitelist only answer content; never return the import JSON or its metadata."""
    try:
        value = json.loads(value_json) if value_json else {}
    except (ValueError, TypeError):
        value = {}
    if not isinstance(value, dict):
        value = {}
    other = (
        value.get("other_text", []) if question_type in ("single_choice", "multi_choice") else []
    )
    other = (
        [item for item in other if isinstance(item, str) and item.strip()]
        if isinstance(other, list)
        else []
    )
    scalar = value.get("value") if question_type in ("number", "scale", "date") else None
    return other, scalar if isinstance(scalar, str) else None
