# app/routers/search.py
from __future__ import annotations

import json
import base64
import hashlib
import datetime
from typing import Any

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.db import SessionLocal
from app.web import templates
from app.helpers import postprocess_excerpt
from app.helpers import slugify  # type: ignore


router = APIRouter()


# Cache helper functions
def get_cache_key(query: str = "", cursor: str = "") -> str:
    """Generate cache key for search query"""
    if not query.strip():
        return f"timeline:{cursor}" if cursor else "timeline"
    
    # Normalize query for consistent caching
    normalized_query = query.strip().lower()
    key_base = f"search:{normalized_query}"
    
    if cursor:
        key_base += f":{cursor}"
        
    return key_base


def get_search_popularity(db, query: str) -> int:
    """Get search count for a query"""
    if not query.strip():
        return 1000  # Timeline is always "popular"
    
    result = db.execute(
        text("SELECT search_count FROM search_stats WHERE query_text = :query"),
        {"query": query.strip().lower()}
    ).mappings().first()
    
    return result["search_count"] if result else 0


def get_cache_ttl_minutes(popularity: int) -> int:
    """Get TTL in minutes based on query popularity"""
    if popularity >= 100:
        return 30  # Very popular: 30 minutes
    elif popularity >= 20:
        return 15  # Popular: 15 minutes  
    elif popularity >= 5:
        return 5   # Medium: 5 minutes
    else:
        return 0   # Rare: no cache


def track_search_query(db, query: str):
    """Increment search counter for a query"""
    if not query.strip():
        return  # Don't track timeline
        
    normalized_query = query.strip().lower()
    
    try:
        # Upsert search stats
        db.execute(
            text("""
                INSERT INTO search_stats (query_text, search_count, last_searched)
                VALUES (:query, 1, NOW())
                ON CONFLICT (query_text)
                DO UPDATE SET 
                    search_count = search_stats.search_count + 1,
                    last_searched = NOW()
            """),
            {"query": normalized_query}
        )
        # Don't commit here - let the session context manager handle it
    except Exception:
        raise  # Re-raise to let the session context handle rollback


def get_cached_results(db, cache_key: str, ttl_minutes: int) -> dict | None:
    """Get cached results if not expired"""
    if ttl_minutes == 0:
        return None  # No cache for rare queries
        
    try:
        result = db.execute(
            text("""
                SELECT results_json, created_at 
                FROM search_cache 
                WHERE cache_key = :key
                  AND created_at > NOW() - INTERVAL '%s minutes'
            """ % ttl_minutes),
            {"key": cache_key}
        ).mappings().first()
        
        if result:
            return json.loads(result["results_json"])
            
    except Exception:
        pass  # Silent fail
        
    return None


def save_cached_results(db, cache_key: str, results: dict, popularity: int):
    """Save results to cache"""
    try:
        db.execute(
            text("""
                INSERT INTO search_cache (cache_key, results_json, search_count, created_at)
                VALUES (:key, :json, :count, NOW())
                ON CONFLICT (cache_key)
                DO UPDATE SET 
                    results_json = :json,
                    search_count = :count,
                    created_at = NOW()
            """),
            {
                "key": cache_key, 
                "json": json.dumps(results, ensure_ascii=False, default=str),
                "count": popularity
            }
        )
        db.commit()
            
    except Exception:
        try:
            db.rollback()
        except:
            pass  # Silent fail

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

    # Cache logic with single session like dashboard cache
    with SessionLocal() as db:
        # Track search query
        track_search_query(db, q)
        
        # Check cache
        cache_key = get_cache_key(q, cursor or "")
        popularity = get_search_popularity(db, q)
        ttl_minutes = get_cache_ttl_minutes(popularity)
        
        cached_results = get_cached_results(db, cache_key, ttl_minutes)
        if cached_results:
            # Cache hit! Return cached results
            return templates.TemplateResponse(
                "search/answers.html",
                {
                    "request": request,
                    "q": q,
                    "answers": cached_results["answers"],
                    "has_next": cached_results["has_next"],
                    "next_cursor": cached_results.get("next_cursor"),
                    "search_mode": "answers"
                }
            )

        # Initialize variables for both modes
        rows = []
        has_next = False
        next_cursor = None
        
        # Cache miss - proceed with normal search
        # --- Mode 1: FTS quand q >= 2
        if len(q) >= 2:
            params = {"q": q, "limit": limit, "maxlen": MAX_TEXT_LEN}
            cursor_sql = ""
            if cur:
                cursor_sql = "AND fr.id < :last_id"
                params["last_id"] = int(cur.get("id", 0))

            # Augmenter work_mem pour cette session seulement
            db.execute(text("SET work_mem = '32MB'"))
            
            rows = db.execute(
                text(
                    f"""
                    WITH s AS (SELECT websearch_to_tsquery('fr_unaccent', :q) AS tsq),
                    fts_matches AS (
                      SELECT a.id, a.question_id, a.contribution_id, a.text
                      FROM answers a, s
                      WHERE a.text_tsv @@ s.tsq
                        AND char_length(btrim(a.text)) >= 60
                    ),
                    filtered_results AS (
                      SELECT fm.id, fm.question_id, fm.contribution_id, fm.text, qq.prompt AS question_prompt
                      FROM fts_matches fm
                      JOIN questions qq ON qq.id = fm.question_id
                      WHERE qq.type NOT IN ('single_choice', 'multi_choice')
                      ORDER BY fm.id DESC
                    )
                    SELECT
                        fr.id               AS answer_id,
                        fr.question_id      AS question_id,
                        fr.question_prompt  AS question_prompt,
                        c.author_id         AS author_id,
                        c.submitted_at      AS submitted_at,
                        LEFT(fr.text, :maxlen) AS answer_text,
                        ts_headline('fr_unaccent', LEFT(fr.text, :maxlen), s.tsq, 
                                   'StartSel=<mark>, StopSel=</mark>, MaxWords=60, MinWords=40') AS highlighted_text
                    FROM filtered_results fr
                    JOIN contributions c ON c.id = fr.contribution_id, s
                    WHERE 1=1
                    {cursor_sql}
                    ORDER BY fr.id DESC
                    LIMIT :limit
                    """
                ),
                params,
            ).mappings().all()

        # sentinelle + next_cursor  
        if len(rows) == limit:
            has_next = True
            tail = rows[-1]
            next_cursor = _enc_cursor({"id": tail["answer_id"]})
            rows = rows[:-1]

        # build output
        for r in rows:
            # Utiliser le highlighting de PostgreSQL
            highlighted = r.get("highlighted_text") or ""
            # Fallback sur le texte brut si pas de highlighting
            if not highlighted.strip():
                raw = (r.get("answer_text") or "")[:MAX_TEXT_LEN]
                body, _ = _clean_snippet(raw, PREVIEW_MAXLEN)
                body = postprocess_excerpt(body)
            else:
                body = highlighted.strip()
                
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
                      AND q.type NOT IN ('single_choice', 'multi_choice')
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

        # Save to cache after successful search (same session) - AFTER both modes
        # Re-get cache info for saving (variables may be out of scope)
        cache_key_save = get_cache_key(q, cursor or "")
        popularity_save = get_search_popularity(db, q)
        ttl_minutes_save = get_cache_ttl_minutes(popularity_save)
        
        if ttl_minutes_save > 0:  # Only cache if worth it
            cache_data = {
                "answers": answers,
                "has_next": has_next,
                "next_cursor": next_cursor
            }
            save_cached_results(db, cache_key_save, cache_data, popularity_save)

    ctx = {
        "request": request,
        "q": q,
        "answers": answers,
        "on_answers_search": True,  # flag metas (noindex + canonical ?q=)
        "page_size": PER_PAGE,
        "has_next": has_next,
        "next_cursor": next_cursor,
    }
    # Détecter les requêtes HTMX via headers ou paramètre
    is_htmx = partial or "HX-Request" in request.headers
    
    if is_htmx:
        # Si c'est un infinite scroll (cursor présent), utiliser le template d'append
        if cursor:
            resp = templates.TemplateResponse("partials/_answers_list_append.html", ctx)
        else:
            # Première recherche HTMX, template complet
            resp = templates.TemplateResponse("partials/_answers_list.html", ctx)
        return resp

    resp = templates.TemplateResponse("search/answers.html", ctx)
    return resp


# ===========================
#   /search/questions
#   - Deux sections : FORMULAIRES + QUESTIONS
#   - FTS + BM25 (strict), FR + unaccent
#   - Surlignage dans le titre des questions uniquement
#   - Badge "0 réponse" basé sur question_stats.answers_count
#   - Slug renvoyé pour lier vers /questions/{id}-{slug}
#   - Scroll infini indépendant par section (cursor_forms / cursor_questions)
# ===========================
@router.get("/search/questions", name="search_questions", response_class=HTMLResponse)
def search_questions(
    request: Request,
    q: str | None = Query(None, description="Requête"),
    # scroll infini, 1 curseur par section
    cursor_forms: str | None = Query(None),
    cursor_questions: str | None = Query(None),
    # rendu fragment (htmx) : "forms" | "questions" | None
    section: str | None = Query(None),
    partial: bool = Query(False),
):
    q = (q or "").strip()

    # Cursors décodés
    cur_forms = _dec_cursor(cursor_forms)
    cur_questions = _dec_cursor(cursor_questions)

    # Résultats
    forms: list[dict] = []
    questions: list[dict] = []

    # Pagination/next-cursors (par section)
    has_next_forms = False
    has_next_questions = False
    next_cursor_forms: str | None = None
    next_cursor_questions: str | None = None

    limit = PER_PAGE + 1  # +1 pour détecter la page suivante

    with SessionLocal() as db:
        # -------------------------------------------------
        # SECTION "FORMULAIRES"
        # -------------------------------------------------
        if section in (None, "forms"):
            if q:
                params = {"q": q, "limit": limit}
                cursor_sql = ""
                if cur_forms:
                    cursor_sql = """
                      HAVING
                        score < :last_score
                        OR (score = :last_score AND MAX(f.id) < :last_id)
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
                tail = rows[-1]
                # si q vide : pas de score
                score_val = float(tail.get("score", 0.0) or 0.0)
                next_cursor_forms = _enc_cursor({"id": int(tail["id"]), "score": score_val})
                rows = rows[:-1]

            for r in rows:
                forms.append(
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "questions_count": int(r["questions_count"]),
                        # slug utile si besoin d'URL lisibles plus tard
                        "slug": slugify(r["name"] or f"form-{r['id']}"),
                        "score": float(r.get("score", 0.0) or 0.0),
                    }
                )

        # -------------------------------------------------
        # SECTION "QUESTIONS"
        # -------------------------------------------------
        if section in (None, "questions"):
            if q:
                params = {"q": q, "limit": limit}
                cursor_sql = ""
                if cur_questions:
                    cursor_sql = """
                      AND (
                        ranked.score < :last_score
                        OR (ranked.score = :last_score AND ranked.id < :last_id)
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
                        q.question_code,
                        q.prompt,
                        q.type,
                        COALESCE(st.answers_count, 0)::int AS answers_count,
                        ts_rank((q.tsv_prompt)::tsvector, s.tsq) AS score,
                        ts_headline('french', q.prompt, s.tsq,
                            'StartSel=<mark>, StopSel=</mark>, MaxFragments=1, MaxWords=18') AS prompt_hl
                      FROM questions q
                      LEFT JOIN question_stats st ON st.question_id = q.id, s
                      WHERE (q.tsv_prompt)::tsvector @@ s.tsq
                    )
                    SELECT
                        ranked.id,
                        ranked.question_code,
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
                        q.question_code,
                        q.prompt,
                        q.type,
                        COALESCE(st.answers_count, 0)::int AS answers_count
                    FROM questions q
                    LEFT JOIN question_stats st ON st.question_id = q.id
                    {cursor_sql}
                    ORDER BY q.id DESC
                    LIMIT :limit
                    """
                )
                rows = db.execute(sql_questions, params).mappings().all()

            if len(rows) == limit:
                has_next_questions = True
                tail = rows[-1]
                score_val = float(tail.get("score", 0.0) or 0.0)
                next_cursor_questions = _enc_cursor({"id": int(tail["id"]), "score": score_val})
                rows = rows[:-1]

            for r in rows:
                title = r.get("prompt")
                questions.append(
                    {
                        "id": r["id"],
                        "question_code": r.get("question_code"),
                        "title": title,
                        "type": r.get("type"),
                        # surlignage seulement côté titre
                        "prompt_hl": r.get("prompt_hl"),
                        "answers_count": int(r.get("answers_count", 0) or 0),
                        "slug": slugify(title or f"question-{r['id']}"),
                        "score": float(r.get("score", 0.0) or 0.0),
                    }
                )

    # ---------------------------------------
    # Contexte template
    # ---------------------------------------
    ctx = {
        "request": request,
        "q": q,
        # Sections
        "forms": forms,
        "questions": questions,
        # Cursors/flags par section
        "page_size": PER_PAGE,
        "has_next_forms": has_next_forms,
        "has_next_questions": has_next_questions,
        "next_cursor_forms": next_cursor_forms,
        "next_cursor_questions": next_cursor_questions,
        # SEO hint
        "on_questions_search": True,  # (noindex + canonical ?q=) si besoin
    }

    # Détecter les requêtes HTMX via headers ou paramètre
    is_htmx = partial or "HX-Request" in request.headers
    
    # Rendu partiel (htmx) : une seule section
    if is_htmx:
        if section == "forms":
            return templates.TemplateResponse("partials/_forms_list.html", ctx)
        if section == "questions":
            return templates.TemplateResponse("partials/_questions_list.html", ctx)
        # par défaut, recharge les deux colonnes
        return templates.TemplateResponse("partials/_search_sections.html", ctx)

    # Rendu complet (les 2 sections)
    return templates.TemplateResponse("search/questions.html", ctx)

