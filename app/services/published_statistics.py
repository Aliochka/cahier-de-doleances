"""Only persistent, published aggregates are read by public HTTP requests."""

import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import Engine, text

from app.schemas.choice_statistics import QuestionStatistics
from app.schemas.forms import StatisticsAvailability

METHOD = "historical-answers-v1"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def consistent_read(db):
    """Keep documentary metadata and publication in the same PostgreSQL view.

    A caller supplying an already transactional Connection (isolated test fixtures)
    owns its isolation level. Normal HTTP sessions own an Engine connection.
    """
    get_bind = getattr(db, "get_bind", None)
    if get_bind and isinstance(get_bind(), Engine):
        db.connection(
            execution_options={"isolation_level": "REPEATABLE READ", "postgresql_readonly": True}
        )


def read_published(db, *, form_id=None, question_id=None):
    rows = (
        db.execute(
            text("""
        SELECT s.corpus_id AS current_corpus,s.revision AS current_revision,
               g.id,g.corpus_id,g.source_revision,g.method_version,g.calculated_at,g.question_count,
               (SELECT count(*) FROM question_statistics_snapshots n WHERE n.generation_id=g.id) AS actual_count,
               q.question_id,q.form_id,q.answers_count,q.statistics,q.content_hash
        FROM statistics_source s
        LEFT JOIN statistics_generations g ON g.id=s.published_generation
        LEFT JOIN question_statistics_snapshots q ON q.generation_id=g.id
             AND (:fid IS NULL OR q.form_id=:fid) AND (:qid IS NULL OR q.question_id=:qid)
        WHERE s.id=1
    """),
            {"fid": form_id, "qid": question_id},
        )
        .mappings()
        .all()
    )

    def unavailable(reason):
        return StatisticsAvailability(status="unavailable", reason=reason), {}

    if not rows or rows[0]["id"] is None:
        return unavailable("absent")
    first = rows[0]
    if (
        first["current_corpus"] != first["corpus_id"]
        or first["current_revision"] != first["source_revision"]
        or first["method_version"] != METHOD
    ):
        return unavailable("incompatible")
    if first["actual_count"] != first["question_count"]:
        return unavailable("incomplete")
    result = {}
    try:
        for row in rows:
            if row["question_id"] is None:
                continue
            value = {
                "question_id": str(row["question_id"]),
                "form_id": str(row["form_id"]),
                "answers_count": row["answers_count"],
                "statistics": row["statistics"],
            }
            if digest(value) != row["content_hash"]:
                return unavailable("incomplete")
            stats = (
                QuestionStatistics.model_validate(row["statistics"])
                if row["statistics"] is not None
                else None
            )
            if stats and (
                stats.question_id != value["question_id"]
                or stats.total_answers != value["answers_count"]
            ):
                return unavailable("incomplete")
            result[row["question_id"]] = (row["answers_count"], stats)
    except (ValueError, TypeError):
        return unavailable("incomplete")
    return StatisticsAvailability(
        status="available",
        generation_id=str(first["id"]),
        calculated_at=first["calculated_at"],
        method_version=first["method_version"],
    ), result


def require_published(db, *, form_id=None, question_id=None):
    availability, values = read_published(db, form_id=form_id, question_id=question_id)
    if availability.status != "available":
        raise HTTPException(
            503, "Les statistiques sont indisponibles. Leur publication est nécessaire."
        )
    return values
