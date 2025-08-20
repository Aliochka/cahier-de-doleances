from typing import List, Dict, Any
from sqlalchemy import MetaData, Table, select, text, inspect
from sqlalchemy.exc import NoSuchTableError
from app.db import engine, SessionLocal


# --- Noms de tables/champs (schéma normalisé) ---
T_CONTRIB = "contributions"
T_ANSWERS = "answers"
C_ID = "id"
C_QID = "question_id"
C_BODY    = "body"
C_TEXT = "text"
C_DATE = "submitted_at"

# Table FTS5 (créée dans la migration): answers_fts (content='answers', rowid=answers.id)
FTS_TABLE = "answers_fts"

_metadata = MetaData()


def _table(name: str) -> Table:
    return Table(name, _metadata, autoload_with=engine)


def _has_table(name: str) -> bool:
    return inspect(engine).has_table(name)


def latest_contribs(limit: int = 6, min_len: int = 200):
    """
    Retourne jusqu'à `limit` réponses (answers) considérées comme
    des 'contributions de qualité' (len(text) >= min_len).
    Sélection pseudo-aléatoire performante via pivot sur answer.id.
    """
    with engine.connect() as conn:
        # bornes d'ID
        bounds = conn.execute(
            text("""
                SELECT MIN(id) AS min_id, MAX(id) AS max_id
                FROM answers
                WHERE length(text) >= :min_len
            """),
            {"min_len": min_len},
        ).mappings().first()

        if not bounds or bounds["min_id"] is None:
            return []

        min_id, max_id = int(bounds["min_id"]), int(bounds["max_id"])
        span = max_id - min_id + 1
        pivot = conn.execute(
            text("SELECT (abs(random()) % :span) + :min_id AS pivot_id"),
            {"span": span, "min_id": min_id},
        ).mappings().first()["pivot_id"]

        def fetch_side(op: str, remaining: int):
            q = text(f"""
                SELECT a.id AS id,
                       a.text AS body,
                       a.question_id AS question_id,
                       c.author_id AS author_id,
                       c.id AS contribution_id
                FROM answers a
                JOIN contributions c ON c.id = a.contribution_id
                WHERE length(a.text) >= :min_len AND a.id {op} :pivot
                ORDER BY a.id ASC
                LIMIT :lim
            """)
            return conn.execute(
                q, {"min_len": min_len, "pivot": pivot, "lim": remaining}
            ).mappings().all()

        out = []
        out += fetch_side(">=", limit)
        if len(out) < limit:
            out += fetch_side("<", limit - len(out))

        return [dict(r) for r in out[:limit]]

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
        body = r.get("body") or ""
        idx = body.lower().find(q_low)
        if idx == -1:
            snip = (body[:220] + "…") if len(body) > 220 else body
        else:
            start = max(0, idx - 80)
            end = min(len(body), idx + len(q) + 80)
            snip = (
                ("…" if start > 0 else "")
                + body[start:end]
                + ("…" if end < len(body) else "")
            )
        r["snip"] = snip
        out.append(r)
    return out
