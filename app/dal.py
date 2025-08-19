# dal.py — accès lecture seule avec réflexion
from typing import List, Dict, Any
from sqlalchemy import MetaData, Table, select, text, inspect
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.engine import Result
from app.db import engine, SessionLocal

# Noms de tables/champs à ADAPTER si besoin, sans changer la DB
T_CONTRIB = "contributions"
C_ID      = "id"
C_BODY    = "body"
C_QID     = "question_id"
C_DATE    = "created_at"

FTS_TABLE = "contrib_fts"  # si existe (sinon fallback)

_metadata = MetaData()

def _table(name: str) -> Table:
    return Table(name, _metadata, autoload_with=engine)

def _has_table(name: str) -> bool:
    return inspect(engine).has_table(name)

def latest_contribs(limit: int = 6) -> List[Dict[str, Any]]:
    try:
        t = _table(T_CONTRIB)
    except NoSuchTableError:
        return []
    stmt = (
        select(
            t.c[C_ID].label("id"),
            t.c[C_QID].label("question_id"),
            t.c[C_DATE].label("created_at"),
            t.c[C_BODY].label("body"),
        )
        .order_by(t.c[C_DATE].desc())
        .limit(limit)
    )
    with SessionLocal() as s:
        rows: Result = s.execute(stmt)
        return [dict(r._mapping) for r in rows]

def search_contribs(q: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    # FTS si table présente
    if _has_table(FTS_TABLE):
        sql = text(f"""
            SELECT c.{C_ID} AS id,
                   c.{C_QID} AS question_id,
                   c.{C_DATE} AS created_at,
                   snippet({FTS_TABLE}, '<b>', '</b>', '…', 12) AS snip
            FROM {FTS_TABLE}
            JOIN {T_CONTRIB} c ON c.{C_ID} = {FTS_TABLE}.rowid
            WHERE {FTS_TABLE} MATCH :q
            ORDER BY rank
            LIMIT :limit OFFSET :offset
        """)
        with SessionLocal() as s:
            rows = s.execute(sql, {"q": q, "limit": limit, "offset": offset})
            return [dict(r._mapping) for r in rows]

    # Fallback LIKE (lent mais OK pour v1 / faible trafic)
    try:
        t = _table(T_CONTRIB)
    except NoSuchTableError:
        return []
    like = f"%{q}%"
    stmt = (
        select(
            t.c[C_ID].label("id"),
            t.c[C_QID].label("question_id"),
            t.c[C_DATE].label("created_at"),
            t.c[C_BODY].label("body"),
        )
        .where(t.c[C_BODY].like(like))
        .order_by(t.c[C_DATE].desc())
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
