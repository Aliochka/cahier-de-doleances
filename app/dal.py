# dal.py — accès lecture seule avec réflexion
from typing import List, Dict, Any
from sqlalchemy import MetaData, Table, select, text, inspect
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.engine import Result
from app.db import engine, SessionLocal

# --- Noms de tables/champs (schéma normalisé) ---
T_CONTRIB  = "contributions"
T_ANSWERS  = "answers"
C_ID       = "id"
C_QID      = "question_id"
C_TEXT     = "text"
C_DATE     = "submitted_at"

# Table FTS5 (créée dans la migration): answers_fts (content='answers', rowid=answers.id)
FTS_TABLE = "answers_fts"

_metadata = MetaData()


def _table(name: str) -> Table:
    return Table(name, _metadata, autoload_with=engine)


def _has_table(name: str) -> bool:
    return inspect(engine).has_table(name)


def latest_contribs(limit: int = 6) -> List[Dict[str, Any]]:
    """
    Retourne les dernières réponses (answers) avec leur contribution associée.
    On ordonne par contributions.submitted_at desc.
    """
    try:
        c = _table(T_CONTRIB)
        a = _table(T_ANSWERS)
    except NoSuchTableError:
        return []
    stmt = (
        select(
            c.c[C_ID].label("id"),             # contribution_id
            a.c[C_QID].label("question_id"),
            c.c[C_DATE].label("created_at"),
            a.c[C_TEXT].label("body"),         # texte brut de la réponse
        )
        .select_from(a.join(c, c.c[C_ID] == a.c["contribution_id"]))
        .order_by(c.c[C_DATE].desc())
        .limit(limit)
    )
    with SessionLocal() as s:
        rows: Result = s.execute(stmt)
        return [dict(r._mapping) for r in rows]


def search_contribs(q: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Recherche plein texte via FTS5 answers_fts → answers → contributions.
    - answers_fts.rowid = answers.id
    - snippet() sur la colonne 0 (unique) de answers_fts
    - tri par bm25(answers_fts)
    """
    if _has_table(FTS_TABLE):
        sql = text(f"""
            SELECT
              c.{C_ID}                  AS id,
              a.{C_QID}                 AS question_id,
              c.{C_DATE}                AS created_at,
              snippet({FTS_TABLE}, 0, '<b>', '</b>', '…', 12) AS snip,
              bm25({FTS_TABLE})         AS rank
            FROM {FTS_TABLE}
            JOIN {T_ANSWERS} a ON a.{C_ID} = {FTS_TABLE}.rowid
            JOIN {T_CONTRIB} c ON c.{C_ID} = a.contribution_id
            WHERE {FTS_TABLE} MATCH :q
            ORDER BY rank ASC
            LIMIT :limit OFFSET :offset
        """)
        with SessionLocal() as s:
            rows = s.execute(sql, {"q": q, "limit": limit, "offset": offset})
            return [dict(r._mapping) for r in rows]

    # --- Fallback LIKE (lent mais fonctionne sans FTS) ---
    try:
        c = _table(T_CONTRIB)
        a = _table(T_ANSWERS)
    except NoSuchTableError:
        return []
    like = f"%{q}%"
    stmt = (
        select(
            c.c[C_ID].label("id"),
            a.c[C_QID].label("question_id"),
            c.c[C_DATE].label("created_at"),
            a.c[C_TEXT].label("body"),
        )
        .select_from(a.join(c, c.c[C_ID] == a.c["contribution_id"]))
        .where(a.c[C_TEXT].like(like))
        .order_by(c.c[C_DATE].desc())
        .limit(limit)
        .offset(offset)
    )
    with SessionLocal() as s:
        rows = [dict(r._mapping) for r in s.execute(stmt)]

    # fabriquer un pseudo-snippet
    out = []
    q_low = q.lower()
    for r in rows:
        body = (r.get("body") or "")
        idx = body.lower().find(q_low)
        if idx == -1:
            snip = (body[:220] + "…") if len(body) > 220 else body
        else:
            start = max(0, idx - 80)
            end   = min(len(body), idx + len(q) + 80)
            snip  = ("…" if start > 0 else "") + body[start:end] + ("…" if end < len(body) else "")
        r["snip"] = snip
        out.append(r)
    return out
