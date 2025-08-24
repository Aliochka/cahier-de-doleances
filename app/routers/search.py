# app/routers/search.py
from __future__ import annotations

import json
import base64
from typing import Any

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import text, bindparam

from app.db import SessionLocal
from app.web import templates
from app.helpers import postprocess_excerpt

# --- slugify helper (fallback si helper dédié absent) ---
try:
    from app.helpers import slugify  # type: ignore
except Exception:
    import re, unicodedata
    _keep = re.compile(r"[^a-z0-9\s-]")
    _collapse = re.compile(r"[-\s]+")
    def slugify(value: str | None, maxlen: int = 60) -> str:
        if not value:
            return "question"
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
        value = _keep.sub(" ", value)
        value = _collapse.sub("-", value).strip("-")
        return (value[:maxlen].rstrip("-") or "question")

router = APIRouter()

PER_PAGE = 20
MAX_TEXT_LEN = 20_000
MIN_ANSWER_LEN = 60
PREVIEW_MAXLEN = 400

# --- utils cursor opaque (base64 urlsafe(JSON)) ---
def _enc_cursor(obj: dict) -> str:
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    s = base64.urlsafe_b64encode(raw).decode()
    return s.rstrip("=")

def _dec_cursor(s: str | None) -> dict | None:
    if not s:
        return None
    pad = "=" * ((4 - len(s) % 4) % 4)
    data = base64.urlsafe_b64decode(s + pad)
    return json.loads(data.decode())

# --- helpers UI ---
def _clean_snippet(s: str, maxlen: int) -> tuple[str, bool]:
    if s is None:
        return "", False
    is_trunc = len(s) > maxlen
    s = s[:maxlen].replace("\r", " ").replace("\n", " ")
    return s, is_trunc


# ===========================
#   /search/answers
#   - FTS Postgres
#   - keyset pagination + htmx partial
#   - SEO: noindex (full: follow / partial: nofollow — géré côté template/en-têtes)
# ===========================
@router.get("/search/answers", name="search_answers", response_class=HTMLResponse)
def search_answers(
    request: Request,
    q: str = Query("", description="Requête"),
    page: int = Query(1, ge=1),                 # compat (non utilisé)
    cursor: str | None = Query(None),           # scroll infini
    partial: bool = Query(False),               # rendu fragment (htmx)
):
    q = (q or "").strip()

    answers: list[dict[str, Any]] = []
    has_next = False
    next_cursor: str | None = None

    limit = PER_PAGE + 1
    cur = _dec_cursor(cursor)

    # --- Mode 1: FTS quand q >= 2
    if len(q) >= 2:
        with SessionLocal() as db:
            params = {"q": q, "limit": limit, "maxlen": MAX_TEXT_LEN}
            cursor_sql = ""
            if cur:
                cursor_sql = """
                  AND (
                    ranked.score < :last_score
                    OR (ranked.score = :last_score AND ranked.id < :last_id)
                  )
                """
                params["last_score"] = float(cur.get("score", 0.0))
                params["last_id"] = int(cur.get("id", 0))

            rows = db.execute(
                text(
                    f"""
                    WITH s AS (SELECT websearch_to_tsquery('fr_unaccent', :q) AS tsq),
                    ranked AS (
                      SELECT
                        a.id,
                        a.question_id,
                        a.contribution_id,
                        ROUND(ts_rank(a.text_tsv, s.tsq)::numeric, 6)::float AS score,
                        a.text
                      FROM answers a, s
                      WHERE a.text_tsv @@ s.tsq
                    )
                    SELECT
                        ranked.id               AS answer_id,
                        ranked.question_id      AS question_id,
                        qq.prompt               AS question_prompt,
                        c.author_id             AS author_id,
                        c.submitted_at          AS submitted_at,
                        ranked.score            AS score,
                        ts_headline('fr_unaccent',
                            LEFT(ranked.text, :maxlen),
                            s.tsq,
                            'StartSel=<mark>, StopSel=</mark>, MaxFragments=2, MaxWords=18'
                        ) AS answer_snippet,
                        LEFT(ranked.text, :maxlen) AS answer_text
                    FROM ranked
                    JOIN contributions c ON c.id = ranked.contribution_id
                    JOIN questions     qq ON qq.id = ranked.question_id,
                    s
                    WHERE 1=1
                    {cursor_sql}
                    ORDER BY ranked.score DESC, ranked.id DESC
                    LIMIT :limit
                    """
                ),
                params,
            ).mappings().all()

        # sentinelle + next_cursor
        if len(rows) == limit:
            has_next = True
            tail = rows[-1]
            next_cursor = _enc_cursor({"id": tail["answer_id"], "score": float(tail["score"])})
            rows = rows[:-1]

        # build output
        for r in rows:
            body = (r["answer_snippet"] or "").strip()
            if not body:
                raw = (r.get("answer_text") or "")[:MAX_TEXT_LEN]
                body, _ = _clean_snippet(raw, PREVIEW_MAXLEN)
            body = postprocess_excerpt(body)
            q_title = r["question_prompt"]
            answers.append(
                {
                    "id": r["answer_id"],
                    "author_id": r["author_id"],
                    "question_id": r["question_id"],
                    "question_title": q_title,
                    "question_slug": slugify(q_title or f"question-{r['question_id']}"),
                    "created_at": r["submitted_at"],
                    "body": body,
                }
            )

    # --- Mode 2: timeline récente (q court ou vide)
    else:
        with SessionLocal() as db:
            params = {"min_len": MIN_ANSWER_LEN, "limit": limit, "max_text": MAX_TEXT_LEN}
            cursor_sql = ""
            if cur:
                cursor_sql = "AND a.id < :last_id"
                params["last_id"] = int(cur.get("id", 0))

            rows = db.execute(
                text(
                    f"""
                    SELECT
                        a.id            AS answer_id,
                        LEFT(a.text, :max_text) AS answer_text,
                        a.question_id   AS question_id,
                        q.prompt        AS question_prompt,
                        c.author_id     AS author_id,
                        c.submitted_at  AS submitted_at
                    FROM answers a
                    JOIN contributions c ON c.id = a.contribution_id
                    JOIN questions     q ON q.id = a.question_id
                    WHERE a.text IS NOT NULL
                      AND char_length(btrim(a.text)) >= :min_len
                      {cursor_sql}
                    ORDER BY a.id DESC
                    LIMIT :limit
                    """
                ),
                params,
            ).mappings().all()

        if len(rows) == limit:
            has_next = True
            tail = rows[-1]
            next_cursor = _enc_cursor({"id": tail["answer_id"]})
            rows = rows[:-1]

        for r in rows:
            raw = (r["answer_text"] or "")[:MAX_TEXT_LEN]
            snippet, _ = _clean_snippet(raw, PREVIEW_MAXLEN)
            snippet = postprocess_excerpt(snippet)
            q_title = r["question_prompt"]
            answers.append(
                {
                    "id": r["answer_id"],
                    "author_id": r["author_id"],
                    "question_id": r["question_id"],
                    "question_title": q_title,
                    "question_slug": slugify(q_title or f"question-{r['question_id']}"),
                    "created_at": r["submitted_at"],
                    "body": snippet,
                }
            )

    ctx = {
        "request": request,
        "q": q,
        "answers": answers,
        "on_answers_search": True,  # flag metas (noindex + canonical ?q=)
        "page_size": PER_PAGE,
        "has_next": has_next,
        "next_cursor": next_cursor,
    }
    if partial:
        resp = templates.TemplateResponse("partials/_answers_list.html", ctx)
        return resp

    resp = templates.TemplateResponse("search/answers.html", ctx)
    return resp


# ===========================
#   /search/questions
#   - FTS + aperçus (3 dernières réponses / question)
#   - slug renvoyé pour lier vers /questions/{id}-{slug}
# ===========================
@router.get("/search/questions", name="search_questions", response_class=HTMLResponse)
def search_questions_page(
    request: Request,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),                 # compat
    cursor: str | None = Query(None),           # scroll infini
    partial: bool = Query(False),               # rendu fragment (htmx)
):
    q = (q or "").strip()

    has_next = False
    next_cursor: str | None = None
    limit = PER_PAGE + 1
    cur = _dec_cursor(cursor)

    with SessionLocal() as db:
        # 1) Sélection des questions
        if q:
            params = {"q": q, "limit": limit}
            cursor_sql = ""
            if cur:
                cursor_sql = """
                  AND (
                    ranked.score < :last_score
                    OR (ranked.score = :last_score AND ranked.id < :last_id)
                  )
                """
                params["last_score"] = float(cur.get("score", 0.0))
                params["last_id"] = int(cur.get("id", 0))

            rows = db.execute(
                text(
                    f"""
                    WITH s AS (SELECT websearch_to_tsquery('fr_unaccent', :q) AS tsq),
                    ranked AS (
                      SELECT
                        q.id,
                        q.question_code,
                        q.prompt,
                        ts_rank(q.prompt_tsv, s.tsq) AS score
                      FROM questions q, s
                      WHERE q.prompt_tsv @@ s.tsq
                    )
                    SELECT
                        ranked.id,
                        ranked.question_code,
                        ranked.prompt AS title,
                        ranked.score,
                        ts_headline('fr_unaccent', ranked.prompt, s.tsq,
                            'StartSel=<mark>, StopSel=</mark>, MaxFragments=1, MaxWords=18') AS prompt_hl
                    FROM ranked, s
                    WHERE 1=1
                    {cursor_sql}
                    ORDER BY ranked.score DESC, ranked.id DESC
                    LIMIT :limit
                    """
                ),
                params,
            ).mappings().all()

            if len(rows) == limit:
                has_next = True
                tail = rows[-1]
                next_cursor = _enc_cursor({"id": tail["id"], "score": float(tail["score"])})
                rows = rows[:-1]
        else:
            params = {"limit": limit}
            cursor_sql = ""
            if cur:
                cursor_sql = "WHERE q.id < :last_id"
                params["last_id"] = int(cur.get("id", 0))

            rows = db.execute(
                text(
                    f"""
                    SELECT q.id, q.question_code, q.prompt AS title
                    FROM questions q
                    {cursor_sql}
                    ORDER BY q.id DESC
                    LIMIT :limit
                    """
                ),
                params,
            ).mappings().all()

            if len(rows) == limit:
                has_next = True
                tail = rows[-1]
                next_cursor = _enc_cursor({"id": tail["id"]})
                rows = rows[:-1]

        # 2) Aperçus (3 réponses récentes / question) — 1 seul SQL
        question_ids = [r["id"] for r in rows]
        previews_by_qid: dict[int, list[dict]] = {qid: [] for qid in question_ids}

        if question_ids:
            sql_previews = text("""
                WITH sel AS (
                  SELECT
                    a.question_id,
                    a.id              AS answer_id,
                    a.contribution_id,
                    a.text,
                    ROW_NUMBER() OVER (PARTITION BY a.question_id ORDER BY a.id DESC) AS rn
                  FROM answers a
                  WHERE a.question_id IN :qids
                    AND a.text IS NOT NULL
                    AND char_length(btrim(a.text)) >= :min_len
                )
                SELECT
                  sel.question_id,
                  sel.answer_id,
                  sel.contribution_id,
                  sel.text,
                  c.author_id
                FROM sel
                JOIN contributions c ON c.id = sel.contribution_id
                WHERE sel.rn <= 3
                ORDER BY sel.question_id, sel.answer_id DESC
            """).bindparams(bindparam("qids", expanding=True))

            preview_rows = db.execute(
                sql_previews,
                {"qids": tuple(question_ids), "min_len": MIN_ANSWER_LEN},
            ).mappings().all()

            for r in preview_rows:
                qid = r["question_id"]
                aid = r["answer_id"]
                snippet, is_trunc = _clean_snippet((r["text"] or "")[:MAX_TEXT_LEN], PREVIEW_MAXLEN)
                previews_by_qid[qid].append(
                    {"id": aid, "author_id": r["author_id"], "text": snippet, "is_truncated": is_trunc}
                )

        # 3) Structure finale (avec slug)
        questions = []
        for r in rows:
            title = r.get("title")
            questions.append(
                {
                    "id": r["id"],
                    "question_code": r.get("question_code"),
                    "title": title,
                    "prompt_hl": r.get("prompt_hl"),
                    "slug": slugify(title or f"question-{r['id']}"),
                    "answers": previews_by_qid.get(r["id"], []),
                }
            )

    # 4) Rendu
    ctx = {
        "request": request,
        "q": q,
        "questions": questions,
        "on_questions_search": True,  # flag metas (noindex + canonical ?q=)
        "page_size": PER_PAGE,
        "has_next": has_next,
        "next_cursor": next_cursor,
    }
    if partial:
        resp = templates.TemplateResponse("partials/_questions_list.html", ctx)
        return resp

    resp = templates.TemplateResponse("search/questions.html", ctx)
    return resp
