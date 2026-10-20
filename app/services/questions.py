"""Shared question answer keyset reads; historical filters and ordering are preserved."""

import base64
import binascii
import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

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
    if len(s) > 1024:
        raise HTTPException(status_code=400, detail="Curseur invalide")
    try:
        pad = "=" * ((4 - len(s) % 4) % 4)
        data = base64.b64decode(s + pad, altchars=b"-_", validate=True)
        cursor = json.loads(data.decode())
        if not isinstance(cursor, dict):
            raise ValueError("Invalid cursor shape")
        answer_id = cursor["id"]
        date = cursor["date"]
        if type(answer_id) is not int or not 0 < answer_id <= 9223372036854775807:
            raise ValueError("Invalid answer ID")
        if date is not None:
            if not isinstance(date, str):
                raise ValueError("Invalid date")
            date = datetime.fromisoformat(date).isoformat()
        return {"id": answer_id, "date": date}
    except (KeyError, ValueError, TypeError, UnicodeDecodeError, binascii.Error):
        raise HTTPException(status_code=400, detail="Curseur invalide") from None


def read_question_answers(
    db: Session,
    question_id: int,
    question_type: str,
    q: str | None,
    cursor: str | None,
    *,
    page_size: int = PER_PAGE,
    include_total: bool = True,
    other_only: bool = False,
):
    # --- Scroll infini + filtre
    q = (q or "").strip()
    has_next = False
    next_cursor: str | None = None
    total = 0

    limit = page_size + 1
    cur = _dec_cursor(cursor)
    min_length = 1 if question_type in ("single_choice", "multi_choice") else MIN_ANSWER_LEN
    params = {"qid": question_id, "minlen": min_length, "limit": limit}

    # Explicit choice-text view: only actual free-text Other fields, never the
    # imported text that also repeats selected labels. Keep the same keyset.
    other_array = """CASE WHEN jsonb_typeof(NULLIF(a.value_json, '')::jsonb->'other_text') = 'array'
        THEN NULLIF(a.value_json, '')::jsonb->'other_text' ELSE '[]'::jsonb END"""
    other_entries = f"jsonb_array_elements({other_array}) WITH ORDINALITY AS item(entry, ord)"
    other_condition = "jsonb_typeof(entry) = 'string' AND btrim(entry #>> '{}') <> ''"
    text_projection = (
        f"(SELECT string_agg(entry #>> '{{}}', E'\\n\\n' ORDER BY ord) FROM {other_entries} WHERE {other_condition})"
        if other_only
        else "a.text"
    )
    content_filter = (
        f"EXISTS (SELECT 1 FROM {other_entries} WHERE {other_condition})"
        if other_only
        else "a.text IS NOT NULL AND char_length(btrim(a.text)) >= :minlen"
    )

    # Curseur pour pagination keyset
    cursor_sql = ""
    if cur:
        cursor_sql = """
            AND (
                c.submitted_at < :last_date
                OR (c.submitted_at = :last_date AND a.id < :last_id)
            )
        """
        if cur["date"] is None:
            cursor_sql = """
                AND ((c.submitted_at IS NULL AND a.id < :last_id)
                     OR c.submitted_at IS NOT NULL)
            """
        else:
            params["last_date"] = cur["date"]
        params["last_id"] = cur["id"]

    # Total count (uniquement si pas de curseur - pour affichage initial)
    if include_total and not cursor:
        if q:
            total = db.execute(
                text(f"""
                    SELECT COUNT(1)
                    FROM answers a
                    JOIN contributions c ON c.id = a.contribution_id
                    WHERE a.question_id = :qid
                      AND {content_filter}
                      AND a.text ILIKE :like
                """),
                {**params, "like": f"%{q}%"},
            ).scalar_one()
        else:
            total = db.execute(
                text(f"""
                    SELECT COUNT(1)
                    FROM answers a
                    JOIN contributions c ON c.id = a.contribution_id
                    WHERE a.question_id = :qid
                      AND {content_filter}
                """),
                params,
            ).scalar_one()

    # Requête avec curseur
    if q:
        rows = (
            db.execute(
                text(f"""
                SELECT a.id AS answer_id, {text_projection} AS answer_text,
                       c.author_id AS author_id, c.submitted_at AS submitted_at,
                       c.id AS contribution_id, au.name AS author_name,
                       au.is_anonymous AS author_is_anonymous
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                LEFT JOIN authors au ON au.id = c.author_id
                WHERE a.question_id = :qid
                  AND {content_filter}
                  AND a.text ILIKE :like
                  {cursor_sql}
                ORDER BY c.submitted_at DESC NULLS FIRST, a.id DESC
                LIMIT :limit
            """),
                {**params, "like": f"%{q}%"},
            )
            .mappings()
            .all()
        )
    else:
        rows = (
            db.execute(
                text(f"""
                SELECT a.id AS answer_id, {text_projection} AS answer_text,
                       c.author_id AS author_id, c.submitted_at AS submitted_at,
                       c.id AS contribution_id, au.name AS author_name,
                       au.is_anonymous AS author_is_anonymous
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                LEFT JOIN authors au ON au.id = c.author_id
                WHERE a.question_id = :qid
                  AND {content_filter}
                  {cursor_sql}
                ORDER BY c.submitted_at DESC NULLS FIRST, a.id DESC
                LIMIT :limit
            """),
                params,
            )
            .mappings()
            .all()
        )

    has_next = len(rows) > page_size
    rows = rows[:page_size]
    if has_next:
        last_row = rows[-1]
        next_cursor = _enc_cursor(
            {
                "date": last_row["submitted_at"].isoformat() if last_row["submitted_at"] else None,
                "id": last_row["answer_id"],
            }
        )
    return rows, has_next, next_cursor, total


def get_question(db: Session, question_id: int) -> RowMapping | None:
    return (
        db.execute(
            text("""
        SELECT q.id, q.form_id, q.question_code, q.prompt, q.type, q.position, f.name AS form_name
        FROM questions q JOIN forms f ON f.id = q.form_id WHERE q.id = :qid
    """),
            {"qid": question_id},
        )
        .mappings()
        .first()
    )
