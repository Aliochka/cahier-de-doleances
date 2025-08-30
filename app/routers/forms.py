# app/routers/forms.py
from __future__ import annotations

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
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


@router.get("/forms/{form_id}/dashboard", name="form_dashboard", response_class=HTMLResponse)
def form_dashboard(request: Request, form_id: int):
    """
    Page dashboard d'un formulaire avec graphiques et liste des questions
    """
    with SessionLocal() as db:
        # Infos formulaire + questions
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
            return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

        # Récupérer toutes les questions du formulaire avec stats et les données graphiques si applicable
        questions = db.execute(
            text("""
                SELECT q.id, q.prompt, q.type, q.position,
                       COALESCE(st.answers_count, 0)::int AS answers_count
                FROM questions q
                LEFT JOIN question_stats st ON st.question_id = q.id
                WHERE q.form_id = :fid
                ORDER BY COALESCE(q.position, 999999), q.id
            """),
            {"fid": form_id},
        ).mappings().all()

        questions_list = []
        for q in questions:
            question_data = {
                "id": q["id"],
                "prompt": q["prompt"],
                "type": q["type"],
                "position": q["position"],
                "answers_count": q["answers_count"],
                "slug": slugify(q["prompt"] or f"question-{q['id']}")
            }
            
            # Si c'est une question à choix, récupérer les stats pour le graphique
            if q["type"] in ("single_choice", "multi_choice"):
                try:
                    if q["type"] == "single_choice":
                        # Statistiques pour single_choice
                        stats_rows = db.execute(text("""
                            SELECT 
                                o.id as option_id,
                                o.label,
                                o.position,
                                COALESCE(COUNT(ao.option_id), 0) as count,
                                COALESCE(ROUND(COUNT(ao.option_id) * 100.0 / NULLIF(SUM(COUNT(ao.option_id)) OVER(), 0), 2), 0) as percentage
                            FROM options o
                            LEFT JOIN answer_options ao ON ao.option_id = o.id
                            WHERE o.question_id = :qid
                            GROUP BY o.id, o.label, o.position
                            ORDER BY o.position
                            LIMIT 10
                        """), {"qid": q["id"]}).mappings().all()
                        
                    elif q["type"] == "multi_choice":
                        # Statistiques pour multi_choice (parsing des pipes)
                        answers_rows = db.execute(text("""
                            SELECT a.text
                            FROM answers a
                            JOIN contributions c ON c.id = a.contribution_id
                            WHERE a.question_id = :qid
                              AND a.text IS NOT NULL
                              AND a.text LIKE '%|%'
                        """), {"qid": q["id"]}).mappings().all()
                        
                        # Parser les options
                        option_counts = {}
                        total_responses = 0
                        
                        for row in answers_rows:
                            if row["text"]:
                                options = [opt.strip() for opt in row["text"].split("|") if opt.strip()]
                                total_responses += 1
                                for option in options:
                                    option_counts[option] = option_counts.get(option, 0) + 1
                        
                        # Convertir en format standard (top 10)
                        stats_rows = []
                        for i, (label, count) in enumerate(sorted(option_counts.items(), key=lambda x: x[1], reverse=True)[:10]):
                            percentage = round(count * 100.0 / total_responses, 2) if total_responses > 0 else 0
                            stats_rows.append({
                                "option_id": i,
                                "label": label,
                                "position": i,
                                "count": count,
                                "percentage": percentage
                            })
                    
                    # Calculer le total et formater les données
                    total_answers = sum(row["count"] for row in stats_rows)
                    
                    if total_answers > 0:  # Seulement si on a des données
                        # Données pour Chart.js compact
                        chart_data = {
                            "labels": [row["label"][:30] + ("..." if len(row["label"]) > 30 else "") for row in stats_rows],
                            "datasets": [{
                                "data": [row["count"] for row in stats_rows],
                                "backgroundColor": ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#6366f1"][:len(stats_rows)]
                            }]
                        }
                        
                        question_data["chart_data"] = chart_data
                        question_data["chart_stats"] = [{
                            "label": row["label"],
                            "count": row["count"],
                            "percentage": row["percentage"]
                        } for row in stats_rows]
                        question_data["total_chart_answers"] = total_answers
                        
                except Exception as e:
                    print(f"Erreur pour question {q['id']}: {e}")
                    # En cas d'erreur, on continue sans graphique
            
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

        return templates.TemplateResponse("forms/dashboard.html", ctx)


@router.get("/forms/{form_id}/dashboard-stats", name="form_dashboard_stats", response_class=HTMLResponse)
def form_dashboard_stats(request: Request, form_id: int):
    """
    Récupère toutes les statistiques des questions single_choice/multi_choice d'un formulaire
    pour l'affichage dashboard (retourne HTML)
    """
    with SessionLocal() as db:
        # Vérifier que le formulaire existe
        form_row = db.execute(
            text("SELECT id, name FROM forms WHERE id = :fid"),
            {"fid": form_id}
        ).mappings().first()
        
        if not form_row:
            raise HTTPException(status_code=404, detail="Formulaire introuvable")
        
        # Récupérer toutes les questions single_choice/multi_choice du formulaire
        questions = db.execute(text("""
            SELECT q.id, q.prompt, q.type, q.position
            FROM questions q
            WHERE q.form_id = :fid 
              AND q.type IN ('single_choice', 'multi_choice')
            ORDER BY COALESCE(q.position, 999999), q.id
        """), {"fid": form_id}).mappings().all()
        
        all_stats = []
        
        for question in questions:
            qid = question["id"]
            qtype = question["type"]
            
            try:
                if qtype == "single_choice":
                    # Statistiques pour single_choice
                    stats_rows = db.execute(text("""
                        SELECT 
                            o.id as option_id,
                            o.label,
                            o.position,
                            COALESCE(COUNT(ao.option_id), 0) as count,
                            COALESCE(ROUND(COUNT(ao.option_id) * 100.0 / NULLIF(SUM(COUNT(ao.option_id)) OVER(), 0), 2), 0) as percentage
                        FROM options o
                        LEFT JOIN answer_options ao ON ao.option_id = o.id
                        WHERE o.question_id = :qid
                        GROUP BY o.id, o.label, o.position
                        ORDER BY o.position
                        LIMIT 10
                    """), {"qid": qid}).mappings().all()
                    
                elif qtype == "multi_choice":
                    # Statistiques pour multi_choice (parsing des pipes)
                    answers_rows = db.execute(text("""
                        SELECT a.text
                        FROM answers a
                        JOIN contributions c ON c.id = a.contribution_id
                        WHERE a.question_id = :qid
                          AND a.text IS NOT NULL
                          AND a.text LIKE '%|%'
                    """), {"qid": qid}).mappings().all()
                    
                    # Parser les options
                    option_counts = {}
                    total_responses = 0
                    
                    for row in answers_rows:
                        if row["text"]:
                            options = [opt.strip() for opt in row["text"].split("|") if opt.strip()]
                            total_responses += 1
                            for option in options:
                                option_counts[option] = option_counts.get(option, 0) + 1
                    
                    # Convertir en format standard (top 10)
                    stats_rows = []
                    for i, (label, count) in enumerate(sorted(option_counts.items(), key=lambda x: x[1], reverse=True)[:10]):
                        percentage = round(count * 100.0 / total_responses, 2) if total_responses > 0 else 0
                        stats_rows.append({
                            "option_id": i,
                            "label": label,
                            "position": i,
                            "count": count,
                            "percentage": percentage
                        })
                
                # Calculer le total et formater les données
                total_answers = sum(row["count"] for row in stats_rows)
                
                if total_answers > 0:  # Seulement si on a des données
                    # Données pour Chart.js compact
                    chart_data = {
                        "labels": [row["label"][:30] + ("..." if len(row["label"]) > 30 else "") for row in stats_rows],  # Limiter la longueur
                        "datasets": [{
                            "data": [row["count"] for row in stats_rows],
                            "backgroundColor": ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#6366f1"][:len(stats_rows)]
                        }]
                    }
                    
                    question_stats = {
                        "question_id": qid,
                        "question_prompt": question["prompt"][:80] + ("..." if len(question["prompt"]) > 80 else ""),  # Titre court
                        "question_type": qtype,
                        "total_answers": total_answers,
                        "chart_data": chart_data,
                        "stats": [{
                            "label": row["label"],
                            "count": row["count"],
                            "percentage": row["percentage"]
                        } for row in stats_rows]
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
            "total_questions": len(all_stats)
        }
        
        return templates.TemplateResponse("partials/_dashboard_charts.html", ctx)
