# app/routers/forms.py
from __future__ import annotations

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from app.db import SessionLocal
from app.web import templates
from app.helpers import slugify  # type: ignore

router = APIRouter()

@router.get("/forms/{form_id}", name="form_detail", response_class=HTMLResponse)
def form_detail(
    request: Request,
    form_id: int,
    contrib: int | None = Query(1, ge=1, description="Index (1..M) de la contribution à afficher"),
):
    contrib = contrib or 1

    with SessionLocal() as db:
        # 1) Infos formulaire + questions (ordre)
        row_form = db.execute(
            text("""
                SELECT f.id, f.name,
                       COUNT(q.id)::int AS questions_count
                FROM forms f
                LEFT JOIN questions q ON q.form_id = f.id
                WHERE f.id = :fid
                GROUP BY f.id
            """),
            {"fid": form_id},
        ).mappings().first()

        if not row_form:
            # 404 template si tu en as un
            return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

        # Liste ordonnée des questions du formulaire
        rows_questions = db.execute(
            text("""
                SELECT q.id, q.position, q.prompt
                FROM questions q
                WHERE q.form_id = :fid
                ORDER BY COALESCE(q.position, 999999), q.id
            """),
            {"fid": form_id},
        ).mappings().all()

        # 2) Compte des contributions et sélection de l'index demandé
        row_counts = db.execute(
            text("""
                SELECT COUNT(*)::int AS total
                FROM contributions c
                WHERE c.form_id = :fid
            """),
            {"fid": form_id},
        ).mappings().first()

        total_contribs = row_counts["total"] if row_counts else 0

        contrib_idx = max(1, min(contrib, max(total_contribs, 1)))  # clamp 1..M (si 0, on force à 1)

        # ID de la contribution k (ordre stable submitted_at ASC, id ASC)
        row_contrib = db.execute(
            text("""
                SELECT c.id
                FROM contributions c
                WHERE c.form_id = :fid
                ORDER BY c.submitted_at ASC NULLS LAST, c.id ASC
                OFFSET :off LIMIT 1
            """),
            {"fid": form_id, "off": contrib_idx - 1},
        ).mappings().first()

        current_contrib_id = row_contrib["id"] if row_contrib else None

        # 3) Réponses de la contribution courante avec métadonnées pour answer cards
        answers = []
        if current_contrib_id is not None:
            rows_answers = db.execute(
                text("""
                    SELECT a.id, a.question_id, a.text, q.prompt,
                           c.author_id, c.submitted_at
                    FROM answers a
                    JOIN questions q ON q.id = a.question_id
                    JOIN contributions c ON c.id = a.contribution_id
                    WHERE a.contribution_id = :cid
                      AND a.text IS NOT NULL
                      AND trim(a.text) != ''
                    ORDER BY COALESCE(q.position, 999999), q.id
                """),
                {"cid": current_contrib_id},
            ).mappings().all()
            
            for r in rows_answers:
                answers.append({
                    "id": r["id"],
                    "question_id": r["question_id"],
                    "question_title": r["prompt"],
                    "question_slug": slugify(r["prompt"] or f"question-{r['question_id']}"),
                    "body": r["text"],
                    "author_id": r["author_id"],
                    "created_at": r["submitted_at"],
                })

        # 4) Construction de toutes les questions avec ou sans réponses pour affichage complet
        questions = []
        answers_map: dict[int, dict] = {a["question_id"]: a for a in answers}
        all_answers = []  # Toutes les questions formatées comme des answer cards
        
        for q in rows_questions:
            qid = int(q["id"])
            prompt = q["prompt"]
            question = {
                "id": qid,
                "position": q["position"],
                "prompt": prompt,
                "slug": slugify(prompt or f"question-{qid}"),
                "answer_text": answers_map.get(qid, {}).get("body", ""),
            }
            questions.append(question)
            
            # Créer un objet answer card pour chaque question
            if qid in answers_map:
                # Question avec réponse existante
                all_answers.append(answers_map[qid])
            else:
                # Question sans réponse - créer une entry vide
                all_answers.append({
                    "id": None,
                    "question_id": qid,
                    "question_title": prompt,
                    "question_slug": slugify(prompt or f"question-{qid}"),
                    "body": "",  # Réponse vide
                    "author_id": None,
                    "created_at": None,
                })

        ctx = {
            "request": request,
            "form": {
                "id": row_form["id"],
                "name": row_form["name"],
                "questions_count": row_form["questions_count"],
            },
            "questions": questions,
            "answers": all_answers,
            "total_contribs": total_contribs,
            "contrib_idx": contrib_idx,
            "current_contrib_id": current_contrib_id,
            "on_form_page": True,
        }

        return templates.TemplateResponse("forms/detail.html", ctx)
