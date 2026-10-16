"""PostgreSQL searches for the public API; preserve order and candidate caps."""

import base64
import binascii
import json

from sqlalchemy import text

PER_PAGE = 20
MAX_TEXT_LEN = 20_000
MIN_ANSWER_LEN = 40
PREVIEW_MAXLEN = 1000


# --- utils cursor opaque (base64 urlsafe(JSON)) ---
def _enc_cursor(obj: dict) -> str:
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    s = base64.urlsafe_b64encode(raw).decode()
    return s.rstrip("=")


def _dec_cursor(s: str | None) -> dict | None:
    if not s:
        return None
    try:
        pad = "=" * ((4 - len(s) % 4) % 4)
        data = base64.urlsafe_b64decode(s + pad)
        return json.loads(data.decode())
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
        # Return None for invalid cursors instead of crashing
        return None


def read_answer_search(
    db,
    q: str,
    cursor: str | None,
    *,
    page_size: int = PER_PAGE,
    public_context: bool = False,
    max_text_len: int = MAX_TEXT_LEN,
):
    has_next = False
    next_cursor = None
    limit = page_size + 1
    form_sql = "AND q.form_id = c.form_id" if public_context else ""
    cur = _dec_cursor(cursor)
    rows = []
    # --- Mode 1: FTS quand q >= 2
    if len(q) >= 2:
        params = {"q": q, "limit": limit, "maxlen": max_text_len}
        cursor_sql = ""
        if cur:
            cursor_sql = "AND fm.id < :last_id"
            params["last_id"] = int(cur.get("id", 0))

        # Optimisations PostgreSQL + timeout de sécurité
        db.execute(text("SET LOCAL work_mem = '64MB'"))
        db.execute(
            text("SET LOCAL statement_timeout = '5000'")
        )  # 5 secondes MAX (au lieu de 30s+ par défaut)
        db.execute(text("SET LOCAL enable_seqscan = false"))

        # Requête FTS optimisée avec limite 1789 comme l'original
        rows = (
            db.execute(
                text(
                    f"""
                WITH fts_matches AS (
                    SELECT a.id, a.question_id, a.contribution_id, a.text
                    FROM answers a
                    WHERE a.text_tsv @@ websearch_to_tsquery('fr_unaccent', :q)
                      AND char_length(btrim(a.text)) >= 60
                    ORDER BY a.id DESC
                    LIMIT 1789
                )
                SELECT
                    fm.id               AS answer_id,
                    fm.question_id      AS question_id,
                    fm.contribution_id AS contribution_id, q.form_id, q.type AS question_type,
                    q.position AS question_position, f.name AS form_name,
                    char_length(fm.text) > :maxlen AS is_truncated,
                    q.prompt            AS question_prompt,
                    c.author_id         AS author_id,
                    c.submitted_at      AS submitted_at,
                    au.name             AS author_name,
                    au.is_anonymous     AS author_is_anonymous,
                    LEFT(fm.text, :maxlen) AS answer_text
                FROM fts_matches fm
                JOIN questions q ON q.id = fm.question_id
                LEFT JOIN forms f ON f.id = q.form_id
                JOIN contributions c ON c.id = fm.contribution_id
                LEFT JOIN authors au ON au.id = c.author_id
                WHERE q.type NOT IN ('single_choice', 'multi_choice')
                  {form_sql}
                  {cursor_sql}
                ORDER BY fm.id DESC
                LIMIT :limit
                """
                ),
                params,
            )
            .mappings()
            .all()
        )

    # --- Mode 2: timeline récente (q court ou vide)
    else:
        params = {"min_len": MIN_ANSWER_LEN, "limit": limit, "max_text": max_text_len}
        cursor_sql = ""
        if cur:
            cursor_sql = "AND a.id < :last_id"
            params["last_id"] = int(cur.get("id", 0))

        rows = (
            db.execute(
                text(
                    f"""
                WITH recent_answers AS (
                    SELECT a.id, a.text, a.question_id, c.id as contribution_id, c.author_id, c.submitted_at
                    FROM answers a
                    JOIN contributions c ON c.id = a.contribution_id
                    JOIN questions q ON q.id = a.question_id
                    WHERE a.text IS NOT NULL
                      AND char_length(btrim(a.text)) >= :min_len
                      AND q.type NOT IN ('single_choice', 'multi_choice')  -- ✅ Filtre AVANT LIMIT pour éviter 0 résultats
                      {cursor_sql}
                    ORDER BY a.id DESC
                    LIMIT 1789  -- Limite à 1789 réponses récentes filtrées (année de la Révolution française) 🇫🇷
                )
                SELECT
                    ra.id           AS answer_id,
                    LEFT(ra.text, :max_text) AS answer_text,
                    ra.question_id  AS question_id,
                    ra.contribution_id, q.form_id, q.type AS question_type,
                    q.position AS question_position, f.name AS form_name,
                    char_length(ra.text) > :max_text AS is_truncated,
                    q.prompt        AS question_prompt,
                    ra.author_id    AS author_id,
                    ra.submitted_at AS submitted_at,
                    au.name         AS author_name,
                    au.is_anonymous AS author_is_anonymous
                FROM recent_answers ra
                JOIN questions q ON q.id = ra.question_id
                LEFT JOIN forms f ON f.id = q.form_id
                LEFT JOIN authors au ON au.id = ra.author_id
                ORDER BY ra.id DESC
                LIMIT :limit
                """
                ),
                params,
            )
            .mappings()
            .all()
        )

    if len(rows) == limit:
        has_next = True
        rows = rows[:-1]
        next_cursor = _enc_cursor({"id": rows[-1]["answer_id"]})

    return rows, has_next, next_cursor


def read_catalog_search(
    db,
    q: str,
    cursor_forms: str | None,
    cursor_questions: str | None,
    *,
    section: str | None = None,
    page_size: int = PER_PAGE,
):
    cur_forms, cur_questions = _dec_cursor(cursor_forms), _dec_cursor(cursor_questions)
    forms_rows, question_rows = [], []
    has_next_forms = has_next_questions = False
    next_cursor_forms = next_cursor_questions = None
    limit = page_size + 1
    if section in (None, "forms"):
        if q:
            params = {"q": q, "limit": limit}
            cursor_sql = ""
            if cur_forms:
                cursor_sql = """
                  HAVING
                    ts_rank((f.tsv_name)::tsvector, s.tsq) < CAST(:last_score AS real)
                    OR (ts_rank((f.tsv_name)::tsvector, s.tsq) = CAST(:last_score AS real) AND f.id < :last_id)
                """
                params["last_score"] = float(cur_forms.get("score", 0.0))
                params["last_id"] = int(cur_forms.get("id", 0))

            sql_forms = text(
                f"""
                WITH s AS (SELECT plainto_tsquery('french', unaccent(:q)) AS tsq)
                SELECT
                    f.id,
                    f.name,
                    COUNT(q.id)::int AS questions_count,
                    ts_rank((f.tsv_name)::tsvector, s.tsq) AS score
                FROM forms f
                LEFT JOIN questions q ON q.form_id = f.id,
                     s
                WHERE (f.tsv_name)::tsvector @@ s.tsq
                GROUP BY f.id, f.name, s.tsq
                {cursor_sql}
                ORDER BY score DESC, id DESC
                LIMIT :limit
                """
            )
            rows = db.execute(sql_forms, params).mappings().all()
        else:
            params = {"limit": limit}
            cursor_sql = ""
            if cur_forms:
                cursor_sql = "WHERE f.id < :last_id"
                params["last_id"] = int(cur_forms.get("id", 0))
            sql_forms = text(
                f"""
                SELECT
                    f.id,
                    f.name,
                    (SELECT COUNT(*) FROM questions qq WHERE qq.form_id = f.id)::int AS questions_count
                FROM forms f
                {cursor_sql}
                ORDER BY f.id DESC
                LIMIT :limit
                """
            )
            rows = db.execute(sql_forms, params).mappings().all()

        if len(rows) == limit:
            has_next_forms = True
            rows = rows[:-1]
            tail = rows[-1]
            # si q vide : pas de score
            score_val = float(tail.get("score", 0.0) or 0.0)
            next_cursor_forms = _enc_cursor({"id": int(tail["id"]), "score": score_val})

        forms_rows = rows
    if section in (None, "questions"):
        if q:
            params = {"q": q, "limit": limit}
            cursor_sql = ""
            if cur_questions:
                cursor_sql = """
                  AND (
                    ranked.score < CAST(:last_score AS real)
                    OR (ranked.score = CAST(:last_score AS real) AND ranked.id < :last_id)
                  )
                """
                params["last_score"] = float(cur_questions.get("score", 0.0))
                params["last_id"] = int(cur_questions.get("id", 0))

            sql_questions = text(
                f"""
                WITH s AS (SELECT plainto_tsquery('french', unaccent(:q)) AS tsq),
                ranked AS (
                  SELECT
                    q.id,
                    q.question_code, q.form_id, q.position, f.name AS form_name,
                    q.prompt,
                    q.type,
                    COALESCE(st.answers_count, 0)::int AS answers_count,
                    ts_rank((q.tsv_prompt)::tsvector, s.tsq) AS score,
                    ts_headline('french', q.prompt, s.tsq,
                        'StartSel=<mark>, StopSel=</mark>, MaxFragments=1, MaxWords=18') AS prompt_hl
                  FROM questions q LEFT JOIN forms f ON f.id = q.form_id
                  LEFT JOIN question_stats st ON st.question_id = q.id, s
                  WHERE (q.tsv_prompt)::tsvector @@ s.tsq
                )
                SELECT
                    ranked.id,
                    ranked.question_code, ranked.form_id, ranked.position, ranked.form_name,
                    ranked.prompt,
                    ranked.type,
                    ranked.answers_count,
                    ranked.score,
                    ranked.prompt_hl
                FROM ranked
                WHERE 1=1
                {cursor_sql}
                ORDER BY ranked.score DESC, ranked.id DESC
                LIMIT :limit
                """
            )
            rows = db.execute(sql_questions, params).mappings().all()
        else:
            params = {"limit": limit}
            cursor_sql = ""
            if cur_questions:
                cursor_sql = "WHERE q.id < :last_id"
                params["last_id"] = int(cur_questions.get("id", 0))
            sql_questions = text(
                f"""
                SELECT
                    q.id,
                    q.question_code, q.form_id, q.position, f.name AS form_name,
                    q.prompt,
                    q.type,
                    COALESCE(st.answers_count, 0)::int AS answers_count
                FROM questions q LEFT JOIN forms f ON f.id = q.form_id
                LEFT JOIN question_stats st ON st.question_id = q.id
                {cursor_sql}
                ORDER BY q.id DESC
                LIMIT :limit
                """
            )
            rows = db.execute(sql_questions, params).mappings().all()

        if len(rows) == limit:
            has_next_questions = True
            rows = rows[:-1]
            tail = rows[-1]
            score_val = float(tail.get("score", 0.0) or 0.0)
            next_cursor_questions = _enc_cursor({"id": int(tail["id"]), "score": score_val})

        question_rows = rows
    return (
        forms_rows,
        question_rows,
        has_next_forms,
        has_next_questions,
        next_cursor_forms,
        next_cursor_questions,
    )
