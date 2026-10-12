"""Choice statistics based on normalized links, including single selections."""

from sqlalchemy import text


def choice_statistics(db, question_id, *, include_contributions=False):
    total = (
        db.execute(
            text("SELECT COALESCE(answers_count,0) FROM question_stats WHERE question_id=:qid"),
            {"qid": question_id},
        ).scalar()
        or 0
    )
    rows = (
        db.execute(
            text("""
        SELECT o.id AS option_id,o.label,o.position,count(ao.answer_id) AS count
        FROM options o LEFT JOIN answer_options ao ON ao.option_id=o.id
        WHERE o.question_id=:qid GROUP BY o.id,o.label,o.position
        ORDER BY o.position,o.id
    """),
            {"qid": question_id},
        )
        .mappings()
        .all()
    )
    stats = [
        dict(row, percentage=round(row["count"] * 100.0 / total, 2) if total else 0) for row in rows
    ]
    # Keep legacy dashboard work unchanged; the new distinct-contribution metric
    # is explicitly requested only by the versioned API.
    answered_contributions = None
    if include_contributions:
        extra = (
            db.execute(
                text("""
            SELECT count(*) FILTER (
                       WHERE COALESCE(jsonb_array_length(value_json::jsonb->'other_text'),0)>0
                   ) AS other_count,
                   count(DISTINCT contribution_id) AS answered_contributions_count
            FROM answers WHERE question_id=:qid
        """),
                {"qid": question_id},
            )
            .mappings()
            .one()
        )
        other = extra["other_count"]
        answered_contributions = extra["answered_contributions_count"]
    else:
        other = db.execute(
            text("""
            SELECT count(*) FROM answers WHERE question_id=:qid
              AND COALESCE(jsonb_array_length(value_json::jsonb->'other_text'),0)>0
            """),
            {"qid": question_id},
        ).scalar_one()
    if other:
        stats.append(
            {
                "option_id": 0,
                "label": "Autre (texte libre)",
                "position": 999999,
                "count": other,
                "percentage": round(other * 100.0 / total, 2) if total else 0,
            }
        )
    return {
        "total_answers": total,
        "answered_contributions_count": answered_contributions,
        "other_text_answers_count": other,
        "total_selections": sum(row["count"] for row in stats),
        "stats": stats,
    }
