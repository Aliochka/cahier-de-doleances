# app/routers/forms.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.choice_stats import choice_statistics
from app.db import SessionLocal
from app.helpers import slugify  # type: ignore
from app.services.contributions import contribution_answers, select_legacy_contribution
from app.services.forms import form_questions, get_form
from app.web import templates

router = APIRouter()


@router.get("/forms/{form_id}", name="form_detail", response_class=HTMLResponse)
def form_detail(
    request: Request,
    form_id: int,
    contrib: str | None = Query("1", description="Index (1..M) de la contribution à afficher"),
):
    with SessionLocal() as db:
        # 1) Infos formulaire + questions (ordre)
        row_form = get_form(db, form_id)

        if not row_form:
            # 404 template si tu en as un
            return templates.TemplateResponse(
                request, "errors/404.html", {"request": request}, status_code=404
            )

        # Liste ordonnée des questions du formulaire
        rows_questions = form_questions(db, form_id)

        # Historical contrib is a 1-based ordinal, not a contribution ID.
        total_contribs, contrib_idx, current_contrib_id = select_legacy_contribution(
            db, form_id, contrib
        )

        # 3) Réponses de la contribution courante avec métadonnées pour answer cards
        answers = []
        if current_contrib_id is not None:
            rows_answers = contribution_answers(db, current_contrib_id)

            for r in rows_answers:
                answers.append(
                    {
                        "id": r["id"],
                        "question_id": r["question_id"],
                        "question_title": r["prompt"],
                        "question_slug": slugify(r["prompt"] or f"question-{r['question_id']}"),
                        "body": r["text"],
                        "author_id": r["author_id"],
                        "created_at": r["submitted_at"],
                    }
                )

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
                all_answers.append(
                    {
                        "id": None,
                        "question_id": qid,
                        "question_title": prompt,
                        "question_slug": slugify(prompt or f"question-{qid}"),
                        "body": "",  # Réponse vide
                        "author_id": None,
                        "created_at": None,
                    }
                )

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

        return templates.TemplateResponse(request, "forms/detail.html", ctx)


@router.get("/forms/{form_id}/dashboard", name="form_dashboard", response_class=HTMLResponse)
def form_dashboard(request: Request, form_id: int):
    """
    Page dashboard d'un formulaire avec graphiques et liste des questions
    """

    with SessionLocal() as db:
        # Infos formulaire + questions
        row_form = get_form(db, form_id)

        if not row_form:
            return templates.TemplateResponse(
                request, "errors/404.html", {"request": request}, status_code=404
            )

        questions = (
            db.execute(
                text("""
                SELECT q.id, q.prompt, q.type, q.position,
                       COALESCE(st.answers_count, 0)::int AS answers_count
                FROM questions q
                LEFT JOIN question_stats st ON st.question_id = q.id
                WHERE q.form_id = :fid
                ORDER BY COALESCE(q.position, 999999), q.id
            """),
                {"fid": form_id},
            )
            .mappings()
            .all()
        )

        questions_list = []
        for q in questions:
            question_data = {
                "id": q["id"],
                "prompt": q["prompt"],
                "type": q["type"],
                "position": q["position"],
                "answers_count": q["answers_count"],
                "slug": slugify(q["prompt"] or f"question-{q['id']}"),
            }

            if q["type"] in ("single_choice", "multi_choice"):
                choice_result = choice_statistics(db, q["id"])
                stats_rows = choice_result["stats"]
                if choice_result["total_answers"]:
                    question_data["chart_data"] = {
                        "labels": [row["label"] for row in stats_rows],
                        "datasets": [
                            {
                                "data": [row["count"] for row in stats_rows],
                                "backgroundColor": [
                                    "#3b82f6",
                                    "#ef4444",
                                    "#10b981",
                                    "#f59e0b",
                                    "#8b5cf6",
                                    "#06b6d4",
                                    "#f97316",
                                    "#84cc16",
                                    "#ec4899",
                                    "#6366f1",
                                ],
                            }
                        ],
                    }
                    question_data["chart_stats"] = stats_rows
                    question_data["total_chart_answers"] = choice_result["total_answers"]

            questions_list.append(question_data)

        ctx = {
            "request": request,
            "form": {
                "id": row_form["id"],
                "name": row_form["name"],
                "questions_count": row_form["questions_count"],
            },
            "questions": questions_list,
            "on_dashboard": True,
        }

        return templates.TemplateResponse(request, "forms/dashboard.html", ctx)


@router.get(
    "/forms/{form_id}/dashboard-stats", name="form_dashboard_stats", response_class=HTMLResponse
)
def form_dashboard_stats(request: Request, form_id: int):
    """
    Récupère toutes les statistiques des questions single_choice/multi_choice d'un formulaire
    pour l'affichage dashboard (retourne HTML)
    """
    with SessionLocal() as db:
        # Vérifier que le formulaire existe
        form_row = (
            db.execute(text("SELECT id, name FROM forms WHERE id = :fid"), {"fid": form_id})
            .mappings()
            .first()
        )

        if not form_row:
            raise HTTPException(status_code=404, detail="Formulaire introuvable")

        # Récupérer toutes les questions single_choice/multi_choice du formulaire
        questions = (
            db.execute(
                text("""
            SELECT q.id, q.prompt, q.type, q.position
            FROM questions q
            WHERE q.form_id = :fid 
              AND q.type IN ('single_choice', 'multi_choice')
            ORDER BY COALESCE(q.position, 999999), q.id
        """),
                {"fid": form_id},
            )
            .mappings()
            .all()
        )

        all_stats = []

        for question in questions:
            qid = question["id"]
            qtype = question["type"]

            try:
                choice_result = choice_statistics(db, qid)
                stats_rows = choice_result["stats"]

                # Calculer le total et formater les données
                total_answers = choice_result["total_answers"]

                if total_answers > 0:  # Seulement si on a des données
                    # Données pour Chart.js compact
                    chart_data = {
                        "labels": [
                            row["label"][:30] + ("..." if len(row["label"]) > 30 else "")
                            for row in stats_rows
                        ],  # Limiter la longueur
                        "datasets": [
                            {
                                "data": [row["count"] for row in stats_rows],
                                "backgroundColor": [
                                    "#3b82f6",
                                    "#ef4444",
                                    "#10b981",
                                    "#f59e0b",
                                    "#8b5cf6",
                                    "#06b6d4",
                                    "#f97316",
                                    "#84cc16",
                                    "#ec4899",
                                    "#6366f1",
                                ][: len(stats_rows)],
                            }
                        ],
                    }

                    question_stats = {
                        "question_id": qid,
                        "question_prompt": question["prompt"][:80]
                        + ("..." if len(question["prompt"]) > 80 else ""),  # Titre court
                        "question_type": qtype,
                        "total_answers": total_answers,
                        "chart_data": chart_data,
                        "stats": [
                            {
                                "label": row["label"],
                                "count": row["count"],
                                "percentage": row["percentage"],
                            }
                            for row in stats_rows
                        ],
                    }

                    all_stats.append(question_stats)

            except Exception as e:
                print(f"Erreur pour question {qid}: {e}")
                continue

        # Retourner le template HTML pour les graphiques
        ctx = {
            "request": request,
            "form_id": form_id,
            "form_name": form_row["name"],
            "questions_stats": all_stats,
            "total_questions": len(all_stats),
        }

        return templates.TemplateResponse(request, "partials/_dashboard_charts.html", ctx)
