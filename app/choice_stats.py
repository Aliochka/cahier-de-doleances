"""Choice statistics based on normalized links, shared by single and grouped reads."""

from collections import defaultdict

from sqlalchemy import bindparam, text


def choice_statistics_many(db, question_ids, *, include_contributions=False):
    """Three targeted aggregate reads regardless of question count; no answer rows loaded."""
    if not question_ids:
        return {}
    params = {"qids": list(question_ids)}

    def query(sql):
        return db.execute(text(sql).bindparams(bindparam("qids", expanding=True)), params)

    totals = dict(
        query(
            "SELECT question_id, COALESCE(answers_count,0) FROM question_stats WHERE question_id IN :qids"
        )
        .tuples()
        .all()
    )
    options = (
        query("""
        SELECT o.question_id, o.id AS option_id, o.label, o.position,
               count(ao.answer_id) AS count
        FROM options o LEFT JOIN answer_options ao ON ao.option_id=o.id
        WHERE o.question_id IN :qids
        GROUP BY o.question_id,o.id,o.label,o.position
        ORDER BY o.question_id,o.position,o.id
    """)
        .mappings()
        .all()
    )
    distinct_sql = (
        ", count(DISTINCT contribution_id) AS contributions" if include_contributions else ""
    )
    extras = {
        row["question_id"]: row
        for row in query(f"""
            SELECT question_id, count(*) FILTER (
                WHERE COALESCE(jsonb_array_length(value_json::jsonb->'other_text'),0)>0
            ) AS other_count {distinct_sql}
            FROM answers WHERE question_id IN :qids GROUP BY question_id
        """)
        .mappings()
        .all()
    }
    by_question = defaultdict(list)
    for row in options:
        by_question[row["question_id"]].append(
            {key: row[key] for key in ("option_id", "label", "position", "count")}
        )
    return {
        qid: _format_statistics(
            totals.get(qid, 0),
            by_question[qid],
            extras.get(qid, {}).get("other_count", 0),
            extras.get(qid, {}).get("contributions", 0) if include_contributions else None,
        )
        for qid in question_ids
    }


def _format_statistics(total, rows, other, answered_contributions):
    stats = [
        dict(row, percentage=round(row["count"] * 100.0 / total, 2) if total else 0) for row in rows
    ]
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


def choice_statistics(db, question_id, *, include_contributions=False):
    return choice_statistics_many(db, [question_id], include_contributions=include_contributions)[
        question_id
    ]
