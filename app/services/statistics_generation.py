"""Explicit maintenance only: coherent source snapshot and atomic publication."""

import time
from uuid import uuid4

from sqlalchemy import text

from app.choice_stats import _format_statistics, choice_statistics
from app.services.published_statistics import METHOD, digest

LOCK = 684021002


class GenerationError(RuntimeError):
    pass


def generate(db, *, checkpoint=lambda phase: None):
    """Caller owns a REPEATABLE READ transaction; never commits on its behalf.

    Advisory transaction lock excludes competing generators. The final source-row
    lock fences publication against concurrent source mutations (serialization
    failure rolls back everything if our repeatable snapshot became stale).
    """
    started = time.monotonic()
    if not db.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOCK}).scalar_one():
        raise GenerationError("Une génération est déjà en cours.")
    source = (
        db.execute(text("SELECT corpus_id,revision FROM statistics_source WHERE id=1"))
        .mappings()
        .one()
    )
    questions = (
        db.execute(text("SELECT id,form_id,type FROM questions ORDER BY id")).mappings().all()
    )
    form_count = db.execute(text("SELECT count(*) FROM forms")).scalar_one()
    checkpoint("source")
    # Verify attachments before aggregating; never persist citizen text/identity.
    invalid = db.execute(
        text("""
        SELECT EXISTS(SELECT 1 FROM answers a JOIN questions q ON q.id=a.question_id
          JOIN contributions c ON c.id=a.contribution_id WHERE q.form_id<>c.form_id)
        OR EXISTS(SELECT 1 FROM answer_options ao JOIN answers a ON a.id=ao.answer_id
          JOIN options o ON o.id=ao.option_id WHERE a.question_id<>o.question_id)
        OR EXISTS(SELECT 1 FROM answers WHERE value_json IS NOT NULL AND
          jsonb_typeof(value_json::jsonb->'other_text') IS NOT NULL AND
          jsonb_typeof(value_json::jsonb->'other_text') NOT IN ('array','null'))
    """)
    ).scalar_one()
    if invalid:
        raise GenerationError("Relations ou champs Autre incohérents.")
    totals = {
        r["question_id"]: r
        for r in db.execute(
            text("""
        SELECT question_id,count(*) AS total,count(DISTINCT contribution_id) AS contributions,
          count(*) FILTER(WHERE COALESCE(jsonb_array_length(NULLIF(value_json::jsonb->'other_text','null'::jsonb)),0)>0) AS other
        FROM answers GROUP BY question_id
    """)
        ).mappings()
    }
    counters = dict(
        db.execute(text("SELECT question_id,answers_count FROM question_stats")).tuples().all()
    )
    options = {}
    for row in db.execute(
        text("""
        SELECT o.question_id,o.id AS option_id,o.label,o.position,count(ao.answer_id) AS count
        FROM options o LEFT JOIN answer_options ao ON ao.option_id=o.id
        GROUP BY o.question_id,o.id,o.label,o.position ORDER BY o.question_id,o.position,o.id
    """)
    ).mappings():
        options.setdefault(row["question_id"], []).append(dict(row))
    checkpoint("aggregated")
    payloads = []
    from app.routers.api_questions import statistics_fields

    for question in questions:
        qid = question["id"]
        total = totals.get(qid, {"total": 0, "contributions": 0, "other": 0})
        if counters.get(qid, 0) != total["total"]:
            raise GenerationError(f"Compteur absent ou incohérent pour la question {qid}.")
        stats = None
        if question["type"] in ("single_choice", "multi_choice"):
            rows = options.get(qid, [])
            if any(r["count"] > total["total"] for r in rows):
                raise GenerationError("Effectif d'option supérieur au dénominateur.")
            values = _format_statistics(
                total["total"], rows, total["other"], total["contributions"]
            )
            stats = statistics_fields(question, values).model_dump(mode="json")
        payloads.append(
            {
                "question_id": str(qid),
                "form_id": str(question["form_id"]),
                "answers_count": total["total"],
                "statistics": stats,
            }
        )
    # Small independent historical comparison before the publication fence.
    sample = set()
    for kind in ("single_choice", "multi_choice"):
        match = next((q for q in questions if q["type"] == kind), None)
        if match:
            sample.add(match["id"])
    with_other = [
        q
        for q in questions
        if q["type"] in ("single_choice", "multi_choice")
        and totals.get(q["id"], {}).get("other", 0)
    ]
    if with_other:
        sample.add(max(with_other, key=lambda q: totals[q["id"]]["other"])["id"])
    by_id = {q["id"]: q for q in questions}
    payload_by_id = {int(p["question_id"]): p for p in payloads}
    for qid in sorted(sample):
        historical = statistics_fields(
            by_id[qid], choice_statistics(db, qid, include_contributions=True)
        ).model_dump(mode="json")
        if historical != payload_by_id[qid]["statistics"]:
            raise GenerationError("Écart avec les statistiques historiques.")
    checkpoint("validated")
    # Locks only this tiny row during publication, never public readers.
    current = db.execute(
        text("SELECT revision FROM statistics_source WHERE id=1 FOR UPDATE")
    ).scalar_one()
    if current != source["revision"]:
        raise GenerationError("Le corpus a changé pendant le calcul. Relancer explicitement.")
    generation = str(uuid4())
    content_hash = digest(payloads)
    db.execute(
        text("""
      INSERT INTO statistics_generations(id,corpus_id,source_revision,method_version,question_count,form_count,content_hash)
      VALUES (:id,:corpus,:revision,:method,:questions,:forms,:hash)
    """),
        {
            "id": generation,
            "corpus": source["corpus_id"],
            "revision": current,
            "method": METHOD,
            "questions": len(questions),
            "forms": form_count,
            "hash": content_hash,
        },
    )
    if payloads:
        import json

        db.execute(
            text("""
          INSERT INTO question_statistics_snapshots(generation_id,question_id,form_id,answers_count,statistics,content_hash)
          VALUES (:generation,:question_id,:form_id,:answers_count,CAST(:payload AS jsonb),:hash)
        """),
            [
                {
                    **p,
                    "generation": generation,
                    "payload": json.dumps(p["statistics"], ensure_ascii=False)
                    if p["statistics"] is not None
                    else None,
                    "hash": digest(p),
                }
                for p in payloads
            ],
        )
    checkpoint("prepared")
    db.execute(
        text("UPDATE statistics_source SET published_generation=:id WHERE id=1"), {"id": generation}
    )
    checkpoint("published")
    return {
        "generation_id": generation,
        "questions": len(questions),
        "forms": form_count,
        "source_revision": current,
        "content_hash": content_hash,
        "historical_sample_questions": [str(qid) for qid in sorted(sample)],
        "seconds": time.monotonic() - started,
    }
