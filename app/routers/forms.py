# app/routers/forms.py
from __future__ import annotations

import json
import time
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from app.db import SessionLocal
from app.web import templates
from app.helpers import slugify  # type: ignore

router = APIRouter()

@router.get("/forms/{form_id}/test-cache")
def test_cache_simple(form_id: int):
    """Test simple du cache PostgreSQL pour débogage"""
    results = {"steps": []}
    
    try:
        # Étape 1: Tester la connexion de base
        with SessionLocal() as db:
            result = db.execute(text("SELECT 1 as test")).mappings().first()
            results["steps"].append(f"✅ DB connection: {result['test']}")
        
        # Étape 2: Tester SELECT sur cache table
        with SessionLocal() as db:
            count = db.execute(text("SELECT COUNT(*) as c FROM dashboard_cache")).mappings().first()
            results["steps"].append(f"✅ Cache table access: {count['c']} entries")
        
        # Étape 3: Tester INSERT simple
        with SessionLocal() as db:
            db.execute(text("""
                DELETE FROM dashboard_cache WHERE form_id = :fid
            """), {"fid": form_id})
            db.commit()
            results["steps"].append("✅ DELETE test passed")
        
        # Étape 4: Tester INSERT
        with SessionLocal() as db:
            db.execute(text("""
                INSERT INTO dashboard_cache (form_id, stats_json) 
                VALUES (:fid, :json)
            """), {"fid": form_id, "json": '{"test": "debug"}'})
            db.commit()
            results["steps"].append("✅ INSERT test passed")
        
        # Étape 5: Vérifier INSERT
        with SessionLocal() as db:
            check = db.execute(text("""
                SELECT stats_json FROM dashboard_cache WHERE form_id = :fid
            """), {"fid": form_id}).mappings().first()
            if check:
                results["steps"].append(f"✅ INSERT verified: {check['stats_json']}")
            else:
                results["steps"].append("❌ INSERT not found!")
        
        return {"success": True, "results": results}
        
    except Exception as e:
        return {"success": False, "error": str(e), "results": results}


# Cache TTL en secondes (30 minutes)
DASHBOARD_CACHE_TTL = 1800

def get_dashboard_stats_cached(db, form_id: int) -> list:
    """
    Récupère les statistiques dashboard avec cache fichier temporaire
    """
    import os
    import tempfile
    
    cache_file = os.path.join(tempfile.gettempdir(), f"dashboard_cache_{form_id}.json")
    
    # 1. Vérifier le cache fichier
    if os.path.exists(cache_file):
        try:
            # Vérifier âge du fichier (30 minutes = 1800 secondes)
            file_age = time.time() - os.path.getmtime(cache_file)
            if file_age < DASHBOARD_CACHE_TTL:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            # Fichier corrompu, on l'ignore
            pass
    
    # 2. Calculer les stats
    try:
        stats = calculate_dashboard_stats(db, form_id)
        
        # 3. Sauver dans le cache fichier
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False)
    except Exception as e:
        # Fallback si calcul échoue - retourner liste vide
        return []
    
    return stats


def calculate_dashboard_stats(db, form_id: int) -> list:
    """
    Calcule toutes les statistiques dashboard - version simplifiée pour débogage
    """
    try:
        # Récupération simple des questions d'abord
        results = db.execute(
            text("""
                SELECT q.id, q.prompt, q.type, q.position,
                       COALESCE(st.answers_count, 0)::int AS answers_count
                FROM questions q
                LEFT JOIN question_stats st ON st.question_id = q.id
                WHERE q.form_id = :form_id
                ORDER BY COALESCE(q.position, 999999), q.id
            """),
            {"form_id": form_id}
        ).mappings().all()
        
        questions_list = []
        for r in results:
            question_data = {
                "id": r["id"],
                "prompt": r["prompt"],
                "type": r["type"],
                "position": r["position"],
                "answers_count": r["answers_count"],
                "slug": slugify(r["prompt"] or f"question-{r['id']}")
            }
            
            # Pour l'instant, on revient à l'ancienne méthode pour déboguer
            if r["type"] == "single_choice":
                try:
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
                    """), {"qid": r["id"]}).mappings().all()
                    
                    if stats_rows:
                        total_answers = sum(row["count"] for row in stats_rows)
                        if total_answers > 0:
                            chart_data = {
                                "labels": [row["label"][:30] + ("..." if len(row["label"]) > 30 else "") for row in stats_rows],
                                "datasets": [{
                                    "data": [row["count"] for row in stats_rows],
                                    "backgroundColor": ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#6366f1"][:len(stats_rows)]
                                }]
                            }
                            question_data["chart_data"] = chart_data
                            question_data["chart_stats"] = [dict(row) for row in stats_rows]
                            question_data["total_chart_answers"] = total_answers
                except Exception as e:
                    print(f"Erreur single_choice {r['id']}: {e}")
            
            elif r["type"] == "multi_choice":
                try:
                    # Version SQL optimisée pour multi_choice
                    stats = db.execute(text("""
                        WITH parsed_options AS (
                            SELECT 
                                trim(unnest(string_to_array(a.text, '|'))) as option_name
                            FROM answers a
                            WHERE a.question_id = :qid 
                              AND a.text LIKE '%|%'
                              AND a.text IS NOT NULL
                        )
                        SELECT 
                            option_name as label,
                            COUNT(*) as count
                        FROM parsed_options
                        WHERE option_name != ''
                        GROUP BY option_name
                        ORDER BY count DESC
                        LIMIT 10
                    """), {"qid": r["id"]}).mappings().all()
                    
                    if stats:
                        total_responses = sum(row["count"] for row in stats)
                        if total_responses > 0:
                            chart_data = {
                                "labels": [row["label"][:30] + ("..." if len(row["label"]) > 30 else "") for row in stats],
                                "datasets": [{
                                    "data": [row["count"] for row in stats],
                                    "backgroundColor": ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#6366f1"][:len(stats)]
                                }]
                            }
                            
                            chart_stats = []
                            for i, row in enumerate(stats):
                                chart_stats.append({
                                    "option_id": i,
                                    "label": row["label"],
                                    "position": i,
                                    "count": row["count"],
                                    "percentage": round(row["count"] * 100.0 / total_responses, 2)
                                })
                            
                            question_data["chart_data"] = chart_data
                            question_data["chart_stats"] = chart_stats
                            question_data["total_chart_answers"] = total_responses
                except Exception as e:
                    print(f"Erreur multi_choice {r['id']}: {e}")
            
            questions_list.append(question_data)
        
        return questions_list
        
    except Exception as e:
        print(f"Erreur calculate_dashboard_stats: {e}")
        return []


def invalidate_dashboard_cache(db, form_id: int):
    """Invalide le cache dashboard pour un formulaire"""
    db.execute(
        text("DELETE FROM dashboard_cache WHERE form_id = :form_id"),
        {"form_id": form_id}
    )
    db.commit()

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


@router.get("/forms/{form_id}/dashboard", name="form_dashboard")
def form_dashboard(request: Request, form_id: int, debug: bool = False):
    """
    Page dashboard d'un formulaire avec graphiques et liste des questions
    """
    # Mode debug pour tester le cache PostgreSQL
    if debug:
        return test_cache_postgresql(form_id)
    
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

        # Cache PostgreSQL simple qui fonctionne
        cached_result = db.execute(
            text("""
                SELECT stats_json, updated_at 
                FROM dashboard_cache 
                WHERE form_id = :form_id 
                  AND updated_at > NOW() - INTERVAL '30 minutes'
            """),
            {"form_id": form_id}
        ).mappings().first()
        
        if cached_result:
            # Cache hit !
            questions_list = json.loads(cached_result["stats_json"])
        else:
            # Cache miss - calculer les stats
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
                
                # Stats pour single_choice
                if q["type"] == "single_choice":
                    try:
                        stats_rows = db.execute(text("""
                            SELECT 
                                o.label, COALESCE(COUNT(ao.option_id), 0) as count
                            FROM options o
                            LEFT JOIN answer_options ao ON ao.option_id = o.id
                            WHERE o.question_id = :qid
                            GROUP BY o.id, o.label, o.position
                            ORDER BY o.position LIMIT 10
                        """), {"qid": q["id"]}).mappings().all()
                        
                        if stats_rows and sum(row["count"] for row in stats_rows) > 0:
                            chart_data = {
                                "labels": [row["label"][:30] for row in stats_rows],
                                "datasets": [{"data": [row["count"] for row in stats_rows]}]
                            }
                            question_data["chart_data"] = chart_data
                    except:
                        pass
                
                questions_list.append(question_data)
            
            # Sauver dans le cache PostgreSQL
            try:
                db.execute(
                    text("""
                        INSERT INTO dashboard_cache (form_id, stats_json, updated_at)
                        VALUES (:form_id, :stats_json, NOW())
                        ON CONFLICT (form_id) 
                        DO UPDATE SET stats_json = :stats_json, updated_at = NOW()
                    """),
                    {"form_id": form_id, "stats_json": json.dumps(questions_list, ensure_ascii=False)}
                )
                db.commit()
            except Exception as e:
                # Pas grave si la sauvegarde cache échoue
                db.rollback()

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
