#!/usr/bin/env python3
"""
Script de correction des types de questions mal typées
Détecte automatiquement les questions 'text' qui sont en réalité des choix multiples
et corrige leur type dans la base de données.

Usage: python scripts/fix_question_types.py [--dry-run] [--min-answers=100] [--min-percentage=50]
"""

import argparse
import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH pour importer l'app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal
from sqlalchemy import text

def analyze_question_responses(db, question_id: int, min_answers: int = 100, min_percentage: int = 30) -> dict:
    """
    Analyse les réponses d'une question pour déterminer son vrai type
    
    Returns:
        dict avec 'total_answers', 'pipe_answers', 'percentage', 'suggested_type', 'confidence', 'unique_answers'
    """
    # Compter le total de réponses, celles avec des pipes, et les réponses uniques
    result = db.execute(text("""
        SELECT 
            COUNT(*) as total_answers,
            COUNT(CASE WHEN a.text LIKE '%|%' THEN 1 END) as pipe_answers,
            COUNT(DISTINCT a.text) as unique_answers
        FROM answers a
        WHERE a.question_id = :qid
          AND a.text IS NOT NULL 
          AND TRIM(a.text) != ''
    """), {"qid": question_id}).mappings().first()
    
    total = result["total_answers"]
    pipes = result["pipe_answers"]
    unique = result["unique_answers"]
    pipe_percentage = (pipes / total * 100) if total > 0 else 0
    uniqueness_ratio = (unique / total * 100) if total > 0 else 0
    
    # Déterminer le type suggéré
    suggested_type = None
    confidence = "low"
    
    # Cas 1: Questions à choix multiples (avec pipes)
    if total >= min_answers and pipes >= 1000:  # Au moins 1000 réponses avec pipes
        if pipe_percentage >= 40:  # 40%+ = très probable
            suggested_type = "multi_choice"
            confidence = "high"
        elif pipe_percentage >= 20 and pipes >= 10000:  # 20%+ avec beaucoup de données
            suggested_type = "multi_choice" 
            confidence = "medium"
        elif pipe_percentage >= min_percentage:  # Seuil personnalisé
            suggested_type = "multi_choice"
            confidence = "medium"
    elif pipes >= 500 and pipe_percentage >= 50:  # Moins de données mais % élevé
        suggested_type = "multi_choice"
        confidence = "medium"
    
    # Cas 2: Questions à choix unique (très peu de réponses distinctes)
    elif (total >= 10000 and  # Beaucoup de réponses au total
          unique <= 10 and    # Très peu de réponses distinctes  
          uniqueness_ratio <= 0.1):  # Moins de 0.1% d'unicité
        suggested_type = "single_choice"
        confidence = "high" if unique <= 5 else "medium"
    
    return {
        "total_answers": total,
        "pipe_answers": pipes, 
        "unique_answers": unique,
        "pipe_percentage": pipe_percentage,
        "uniqueness_ratio": uniqueness_ratio,
        "suggested_type": suggested_type,
        "confidence": confidence
    }

def find_mistyped_questions(db, min_answers: int = 100, min_percentage: int = 30) -> list:
    """
    Trouve toutes les questions 'text' qui semblent être des choix multiples
    """
    print(f"🔍 Recherche des questions mal typées...")
    print(f"   Critères: min {min_answers} réponses, min {min_percentage}% avec '|'")
    
    # Récupérer toutes les questions de type 'text'
    questions = db.execute(text("""
        SELECT q.id, q.prompt, q.type
        FROM questions q
        WHERE q.type = 'text'
        ORDER BY q.id
    """)).mappings().all()
    
    mistyped = []
    
    for q in questions:
        analysis = analyze_question_responses(db, q["id"], min_answers, min_percentage)
        
        if analysis["suggested_type"] in ("multi_choice", "single_choice"):
            mistyped.append({
                "id": q["id"],
                "prompt": q["prompt"],
                "current_type": q["type"],
                "suggested_type": analysis["suggested_type"],
                "total_answers": analysis["total_answers"],
                "pipe_answers": analysis["pipe_answers"],
                "unique_answers": analysis["unique_answers"],
                "pipe_percentage": analysis["pipe_percentage"],
                "uniqueness_ratio": analysis["uniqueness_ratio"],
                "confidence": analysis["confidence"]
            })
    
    return mistyped

def show_analysis_report(mistyped_questions: list):
    """
    Affiche un rapport détaillé des questions à corriger
    """
    print(f"\n📊 RAPPORT D'ANALYSE")
    print(f"=" * 50)
    print(f"Questions à corriger: {len(mistyped_questions)}")
    
    if not mistyped_questions:
        print("✅ Aucune question mal typée trouvée!")
        return
        
    print(f"\nDétail des questions à corriger:")
    print(f"{'ID':<5} {'Type':<12} {'Nouveau':<12} {'Réponses':<10} {'Uniques':<8} {'%Uniq':<6} {'Pipes':<8} {'%Pip':<6} {'Conf':<6} {'Prompt':<30}")
    print(f"{'-' * 5} {'-' * 12} {'-' * 12} {'-' * 10} {'-' * 8} {'-' * 6} {'-' * 8} {'-' * 6} {'-' * 6} {'-' * 30}")
    
    for q in mistyped_questions:
        prompt_preview = q["prompt"][:27] + "..." if len(q["prompt"]) > 30 else q["prompt"]
        print(f"{q['id']:<5} "
              f"{q['current_type']:<12} "
              f"{q['suggested_type']:<12} "
              f"{q['total_answers']:<10} "
              f"{q['unique_answers']:<8} "
              f"{q['uniqueness_ratio']:<6.2f} "
              f"{q['pipe_answers']:<8} "
              f"{q['pipe_percentage']:<6.1f} "
              f"{q['confidence']:<6} "
              f"{prompt_preview:<30}")

def create_options_for_single_choice(db, question_id: int) -> dict:
    """
    Crée les options pour une question single_choice à partir des réponses existantes
    Utilise des IDs explicites élevés pour éviter les problèmes de séquence
    """
    # Récupérer les réponses les plus fréquentes
    responses = db.execute(text("""
        SELECT a.text, COUNT(*) as count
        FROM answers a
        JOIN contributions c ON c.id = a.contribution_id
        WHERE a.question_id = :qid 
          AND a.text IS NOT NULL 
          AND trim(a.text) != ''
        GROUP BY a.text
        ORDER BY count DESC
        LIMIT 15
    """), {"qid": question_id}).mappings().all()
    
    if not responses:
        return {"options_created": 0, "responses_migrated": 0}
    
    # Utiliser des IDs élevés basés sur l'ID de la question pour éviter les conflits
    base_id = 900000 + (question_id * 100)
    option_ids = {}
    
    print(f"      Création de {len(responses)} options...")
    
    for i, response in enumerate(responses, 1):
        option_id = base_id + i
        option_code = f"opt{i}"
        
        # Créer l'option avec ID explicite
        db.execute(text("""
            INSERT INTO options (id, question_id, code, label, position)
            VALUES (:opt_id, :qid, :code, :label, :pos)
        """), {
            "opt_id": option_id,
            "qid": question_id,
            "code": option_code,
            "label": response["text"], 
            "pos": i
        })
        
        option_ids[response["text"]] = option_id
        print(f"        Option {i}: {response['text'][:50]}...")
    
    # Migrer les réponses vers answer_options en utilisant LIKE pour les caractères spéciaux
    total_migrated = 0
    print(f"      Migration des réponses...")
    
    for response_text, option_id in option_ids.items():
        # Échapper les caractères spéciaux pour LIKE
        like_pattern = response_text.replace("'", "_").replace("'", "_")[:50] + "%"
        
        migrated = db.execute(text("""
            INSERT INTO answer_options (answer_id, option_id)
            SELECT a.id, :opt_id
            FROM answers a
            JOIN contributions c ON c.id = a.contribution_id
            WHERE a.question_id = :qid 
              AND a.text LIKE :pattern
              AND a.id NOT IN (
                  SELECT ao2.answer_id 
                  FROM answer_options ao2 
                  JOIN answers a2 ON a2.id = ao2.answer_id 
                  WHERE a2.question_id = :qid
              )
        """), {
            "opt_id": option_id, 
            "qid": question_id, 
            "pattern": like_pattern
        }).rowcount
        
        total_migrated += migrated
        print(f"        {migrated} réponses migrées pour option {option_id}")
    
    return {"options_created": len(option_ids), "responses_migrated": total_migrated}

def apply_corrections(db, mistyped_questions: list, dry_run: bool = True):
    """
    Applique les corrections de type dans la base de données
    """
    if not mistyped_questions:
        return
        
    print(f"\n🔧 APPLICATION DES CORRECTIONS")
    print(f"=" * 50)
    
    if dry_run:
        print("🔍 MODE DRY-RUN - Aucune modification ne sera appliquée")
    else:
        print("⚠️  MODE PRODUCTION - Les modifications vont être appliquées!")
    
    corrections_made = 0
    
    for q in mistyped_questions:
        if dry_run:
            if q['suggested_type'] == 'single_choice':
                print(f"  [DRY-RUN] Question {q['id']}: {q['current_type']} → {q['suggested_type']} (créerait ~{q['unique_answers']} options)")
            else:
                print(f"  [DRY-RUN] Question {q['id']}: {q['current_type']} → {q['suggested_type']}")
        else:
            try:
                # Pour single_choice, créer les options d'abord
                if q['suggested_type'] == 'single_choice':
                    print(f"  🔧 Question {q['id']}: Création des options...")
                    migration_result = create_options_for_single_choice(db, q['id'])
                    print(f"      {migration_result['options_created']} options créées")
                    print(f"      {migration_result['responses_migrated']} réponses migrées")
                
                # Changer le type de la question
                db.execute(text("""
                    UPDATE questions 
                    SET type = :new_type 
                    WHERE id = :qid
                """), {
                    "new_type": q['suggested_type'],
                    "qid": q['id']
                })
                print(f"  ✅ Question {q['id']}: {q['current_type']} → {q['suggested_type']}")
                corrections_made += 1
            except Exception as e:
                print(f"  ❌ Erreur question {q['id']}: {e}")
                # Continuer avec les autres questions
    
    if not dry_run and corrections_made > 0:
        db.commit()
        print(f"\n✅ {corrections_made} corrections appliquées avec succès!")
    elif dry_run:
        print(f"\n💡 Pour appliquer les corrections, relancez avec --apply")

def main():
    parser = argparse.ArgumentParser(description="Correction des types de questions")
    parser.add_argument("--dry-run", action="store_true", default=True, 
                       help="Mode aperçu sans modifications (défaut)")
    parser.add_argument("--apply", action="store_true", 
                       help="Appliquer réellement les corrections")
    parser.add_argument("--min-answers", type=int, default=100,
                       help="Nombre minimum de réponses pour analyser (défaut: 100)")
    parser.add_argument("--min-percentage", type=int, default=30,
                       help="Pourcentage minimum de réponses avec '|' (défaut: 30)")
    
    args = parser.parse_args()
    
    # Si --apply est utilisé, désactiver dry-run
    if args.apply:
        args.dry_run = False
    
    print(f"🚀 SCRIPT DE CORRECTION DES TYPES DE QUESTIONS")
    print(f"=" * 60)
    print(f"Mode: {'DRY-RUN (aperçu)' if args.dry_run else 'PRODUCTION (modifications)'}")
    print(f"Paramètres: min {args.min_answers} réponses, {args.min_percentage}% avec pipes")
    
    try:
        with SessionLocal() as db:
            # 1. Analyser et trouver les questions mal typées
            mistyped_questions = find_mistyped_questions(
                db, args.min_answers, args.min_percentage
            )
            
            # 2. Afficher le rapport
            show_analysis_report(mistyped_questions)
            
            # 3. Appliquer les corrections si demandé
            if mistyped_questions:
                apply_corrections(db, mistyped_questions, args.dry_run)
            
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()