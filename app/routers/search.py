# app/routers/search.py
from __future__ import annotations
import math
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import text, bindparam
from app.db import SessionLocal
from app.web import templates
from math import ceil


router = APIRouter()

PER_PAGE = 20
MAX_TEXT_LEN = 20_000
MIN_ANSWER_LEN = 60
PREVIEW_MAXLEN = 400

# --- Recherche RÉPONSES (/search/answers) ---
@router.get("/search/answers", name="search_answers", response_class=HTMLResponse)
def search_answers(
    request: Request,
    q: str = Query("", description="Requête"),
    page: int = Query(1, ge=1),
):
    q = (q or "").strip()
    answers: list[dict] = []
    total = 0
    total_pages = 1
    has_next = False

    offset = (page - 1) * PER_PAGE

    # Mode 1 — RECHERCHE FTS quand q >= 2
    if len(q) >= 2:
        match_query = f'"{q}"' if " " in q else q
        with SessionLocal() as db:
            # total résultats FTS
            total = db.execute(
                text("""
                    SELECT COUNT(*)
                    FROM answers_fts
                    WHERE answers_fts MATCH :q
                """),
                {"q": match_query},
            ).scalar_one()

            rows = []
            if total:
                rows = db.execute(
                    text("""
                        SELECT
                            a.id                 AS answer_id,
                            a.question_id        AS question_id,
                            q.prompt             AS question_prompt,
                            c.author_id          AS author_id,
                            c.submitted_at       AS submitted_at,
                            bm25(answers_fts)    AS score,
                            -- extrait surligné (colonne 0 = texte dans answers_fts)
                            snippet(answers_fts, 0, '<mark>', '</mark>', '…', 18) AS answer_snippet,
                            a.text               AS answer_text
                        FROM answers_fts
                        JOIN answers       a ON a.id = answers_fts.rowid
                        JOIN contributions c ON c.id = a.contribution_id
                        JOIN questions     q ON q.id = a.question_id
                        WHERE answers_fts MATCH :q
                        ORDER BY bm25(answers_fts) ASC, a.id DESC
                        LIMIT :limit OFFSET :offset
                    """),
                    {"q": match_query, "limit": PER_PAGE, "offset": offset},
                ).mappings().all()

        for r in rows:
            # Utilise le snippet FTS ; fallback si vide
            body = (r["answer_snippet"] or "").strip()
            if not body:
                raw = (r.get("answer_text") or "")[:MAX_TEXT_LEN]
                body, _ = _clean_snippet(raw, PREVIEW_MAXLEN)
            answers.append({
                "id": r["answer_id"],
                "author_id": r["author_id"],
                "question_id": r["question_id"],
                "question_title": r["question_prompt"],
                "created_at": r["submitted_at"],
                "body": body,  # contient déjà <mark>…</mark> si snippet()
            })

        total_pages = max(1, ceil(total / PER_PAGE))
        has_next = page < total_pages

    # Mode 2 — TIMELINE RÉCENTE quand q est vide / trop court
    else:
        with SessionLocal() as db:
            # essaie d'utiliser le compteur O(1), sinon fallback COUNT(*)
            try:
                total = db.execute(
                    text("SELECT valid_count FROM answer_valid_stats WHERE id = 1")
                ).scalar_one_or_none()
            except Exception:
                total = None

            if total is None:
                total = db.execute(
                    text("""
                        SELECT COUNT(*)
                        FROM answers a
                        WHERE a.text IS NOT NULL
                          AND trim(a.text) <> ''
                          AND length(a.text) >= :min_len
                    """),
                    {"min_len": MIN_ANSWER_LEN},
                ).scalar_one()

            rows = db.execute(
                text("""
                    SELECT
                        a.id            AS answer_id,
                        a.text          AS answer_text,
                        a.question_id   AS question_id,
                        q.prompt        AS question_prompt,
                        c.author_id     AS author_id,
                        c.submitted_at  AS submitted_at
                    FROM answers a
                    JOIN contributions c ON c.id = a.contribution_id
                    JOIN questions     q ON q.id = a.question_id
                    WHERE a.text IS NOT NULL
                      AND trim(a.text) <> ''
                      AND length(a.text) >= :min_len
                    ORDER BY a.id DESC
                    LIMIT :limit OFFSET :offset
                """),
                {
                    "min_len": MIN_ANSWER_LEN,
                    "limit": PER_PAGE,
                    "offset": offset,
                },
            ).mappings().all()

        for r in rows:
            raw = (r["answer_text"] or "")[:MAX_TEXT_LEN]
            snippet, _ = _clean_snippet(raw, PREVIEW_MAXLEN)
            answers.append({
                "id": r["answer_id"],
                "author_id": r["author_id"],
                "question_id": r["question_id"],
                "question_title": r["question_prompt"],
                "created_at": r["submitted_at"],
                "body": snippet,
            })

        total_pages = max(1, ceil(total / PER_PAGE))
        has_next = page < total_pages

    # Rendu
    return templates.TemplateResponse(
        "search/answers.html",
        {
            "request": request,
            "q": q,
            "page": page,
            "answers": answers,          # pour partials/_answers_list.html
            "on_answers_search": True,
            "page_size": PER_PAGE,
            "has_next": has_next,
            "total_pages": total_pages,  # défini dans les deux modes
        },
    )





# --- Recherche QUESTIONS (/search/questions) ---
def _clean_snippet(s: str, maxlen: int) -> tuple[str, bool]:
    if s is None:
        return "", False
    is_trunc = len(s) > maxlen
    s = s[:maxlen].replace("\r", " ").replace("\n", " ")
    return s, is_trunc


@router.get("/search/questions", name="search_questions", response_class=HTMLResponse)
def search_questions_page(
    request: Request,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
):
    q = (q or "").strip()
    offset = (page - 1) * PER_PAGE

    has_next = False
    total_pages = None

    with SessionLocal() as db:
        # 1) Sélection des questions
        if q:
            # Phase 1 : hits FTS (rowid + rank), pas de COUNT(*)
            hits_sql = text("""
                SELECT rowid AS qid, bm25(question_fts) AS rank
                FROM question_fts
                WHERE question_fts MATCH :q
                ORDER BY rank ASC, rowid ASC
                LIMIT :limit_plus_one OFFSET :offset
            """)
            hit_rows = db.execute(
                hits_sql,
                {"q": q, "limit_plus_one": PER_PAGE + 1, "offset": offset},
            ).mappings().all()

            has_next = len(hit_rows) > PER_PAGE
            hit_rows = hit_rows[:PER_PAGE]
            hit_ids = [r["qid"] for r in hit_rows]
            rank_by_id = {r["qid"]: r["rank"] for r in hit_rows}

            if hit_ids:
                # Phase 2 : détails + highlight uniquement pour ces ids
                data_sql = text("""
                        WITH ids(qid, rank) AS (
                        VALUES {}
                        )
                        SELECT
                        q.id,
                        q.question_code,
                        q.prompt AS title,
                        i.rank AS score,
                        highlight(question_fts, 0, '<mark>', '</mark>') AS prompt_hl
                        FROM ids i
                        JOIN question_fts
                        ON question_fts.rowid = i.qid
                        AND question_fts MATCH :q           -- <- indispensable pour highlight()
                        JOIN questions q ON q.id = i.qid
                        ORDER BY i.rank ASC, q.id ASC
                    """.format(",".join(f"({qid}, :rank_{qid})" for qid in hit_ids)))

                params = {f"rank_{qid}": rank_by_id[qid] for qid in hit_ids}
                params["q"] = q

                rows = db.execute(data_sql, params).mappings().all()
            else:
                rows = []
        else:
            total = db.execute(text("SELECT COUNT(*) FROM questions")).scalar_one()
            rows = db.execute(
                text("""
                    SELECT q.id, q.question_code, q.prompt AS title
                    FROM questions q
                    ORDER BY q.id DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": PER_PAGE, "offset": offset},
            ).mappings().all()
            total_pages = max(1, math.ceil(total / PER_PAGE))

        # 2) Aperçus (3 réponses récentes / question) — rapide
        question_ids = [r["id"] for r in rows]
        previews_by_qid: dict[int, list[dict]] = {qid: [] for qid in question_ids}

        if question_ids:
            # (a) N sous-requêtes LIMIT 3, encapsulées
            parts = []
            params_answers: dict[str, object] = {}
            for i, qid in enumerate(question_ids):
                qi = f"qid_{i}"
                parts.append(f"""
                    SELECT * FROM (
                        SELECT
                          a.question_id,
                          a.id           AS answer_id,
                          a.contribution_id
                        FROM answers a
                        WHERE a.question_id = :{qi}
                          AND a.text IS NOT NULL
                          AND trim(a.text) <> ''
                        ORDER BY a.id DESC
                        LIMIT 3
                    )
                """)
                params_answers[qi] = qid

            answer_rows = []
            if parts:
                sql_answers = text(" UNION ALL ".join(parts))
                answer_rows = db.execute(sql_answers, params_answers).mappings().all()

            # (b) auteurs pour ces contributions
            contrib_ids = tuple({r["contribution_id"] for r in answer_rows})
            author_by_cid: dict[int, int] = {}
            if contrib_ids:
                sql_auth = text("""
                    SELECT id AS contribution_id, author_id
                    FROM contributions
                    WHERE id IN :cids
                """).bindparams(bindparam("cids", expanding=True))
                for row in db.execute(sql_auth, {"cids": contrib_ids}).mappings():
                    author_by_cid[row["contribution_id"]] = row["author_id"]

            # (c) textes pour ces answers
            if answer_rows:
                ans_ids = tuple(r["answer_id"] for r in answer_rows)
                sql_texts = text("""
                    SELECT id AS answer_id, text
                    FROM answers
                    WHERE id IN :ans_ids
                """).bindparams(bindparam("ans_ids", expanding=True))
                text_by_aid = {
                    r["answer_id"]: r["text"]
                    for r in db.execute(sql_texts, {"ans_ids": ans_ids}).mappings()
                }
            else:
                text_by_aid = {}

            # (d) build previews
            for r in answer_rows:
                qid = r["question_id"]
                aid = r["answer_id"]
                cid = r["contribution_id"]
                snippet, is_trunc = _clean_snippet(text_by_aid.get(aid, "") or "", PREVIEW_MAXLEN)
                previews_by_qid[qid].append({
                    "id": aid,
                    "author_id": author_by_cid.get(cid),
                    "text": snippet,
                    "is_truncated": is_trunc,
                })

        # 3) Structure finale
        questions = []
        for r in rows:
            questions.append({
                "id": r["id"],
                "question_code": r.get("question_code"),
                "title": r.get("title"),
                "prompt_hl": r.get("prompt_hl"),  # présent en mode FTS
                "answers": previews_by_qid.get(r["id"], []),
            })

    # 4) Rendu
    ctx = {
        "request": request,
        "q": q,
        "questions": questions,
        "page": page,
        "page_size": PER_PAGE,
        "has_next": has_next if q else page < (total_pages or 1),
        "total_pages": None if q else total_pages,
    }
    return templates.TemplateResponse("search/questions.html", ctx)



# # --- Alias HTMX : /hx/search -> partials/_answers_list.html ---
# @router.get("/hx/search", response_class=HTMLResponse)
# def hx_search(request: Request, q: str = Query("", description="Requête utilisateur"), page: int = Query(1, ge=1)):
#     q = (q or "").strip()
#     PER_PAGE = 20
#     MAX_TEXT_LEN = 20_000
#     answers, total = [], 0

#     if len(q) >= 2:
#         match_query = f'"{q}"' if " " in q else q
#         offset = (page - 1) * PER_PAGE
#         with SessionLocal() as db:
#             total = db.execute(text("""
#                 SELECT COUNT(*)
#                 FROM answers_fts
#                 WHERE answers_fts MATCH :q
#             """), {"q": match_query}).scalar_one()

#             if total:
#                 rows = db.execute(text("""
#                     SELECT a.id           AS answer_id,
#                            a.text         AS answer_text,
#                            a.question_id  AS question_id,
#                            c.author_id    AS author_id,
#                            c.submitted_at AS submitted_at,
#                            bm25(answers_fts) AS score
#                     FROM answers_fts
#                     JOIN answers       a ON a.id = answers_fts.rowid
#                     JOIN contributions c ON c.id = a.contribution_id
#                     WHERE answers_fts MATCH :q
#                     ORDER BY bm25(answers_fts) ASC, a.id DESC
#                     LIMIT :limit OFFSET :offset
#                 """), {"q": match_query, "limit": PER_PAGE, "offset": offset}).mappings().all()

#                 for r in rows:
#                     txt = (r["answer_text"] or "")[:MAX_TEXT_LEN]
#                     answers.append({
#                         "id": r["answer_id"],
#                         "author_id": r["author_id"],
#                         "question_id": r["question_id"],
#                         "created_at": r["submitted_at"],
#                         "body": txt,  # attendu par answers/_card.html
#                     })

#     total_pages = max(1, ceil(total / PER_PAGE)) if q else 1
#     return templates.TemplateResponse(
#         "partials/_answers_list.html",
#         {
#             "request": request,
#             "answers": answers,
#             "page": page,
#             "total_pages": total_pages,
#             "q": q,
#         },
#     )
