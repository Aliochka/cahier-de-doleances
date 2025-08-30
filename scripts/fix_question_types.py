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
        dict avec 'total_answers', 'pipe_answers', 'percentage', 'suggested_type', 'confidence'
    """
    # Compter le total de réponses et celles avec des pipes
    result = db.execute(text("""
        SELECT 
            COUNT(*) as total_answers,
            COUNT(CASE WHEN a.text LIKE '%|%' THEN 1 END) as pipe_answers
        FROM answers a
        WHERE a.question_id = :qid
          AND a.text IS NOT NULL 
          AND TRIM(a.text) != ''
    """), {"qid": question_id}).mappings().first()
    
    total = result["total_answers"]
    pipes = result["pipe_answers"]
    percentage = (pipes / total * 100) if total > 0 else 0
    
    # Déterminer le type suggéré avec logique plus souple
    suggested_type = None
    confidence = "low"
    
    if total >= min_answers and pipes >= 1000:  # Au moins 1000 réponses avec pipes
        if percentage >= 40:  # 40%+ = très probable
            suggested_type = "multi_choice"
            confidence = "high"
        elif percentage >= 20 and pipes >= 10000:  # 20%+ avec beaucoup de données
            suggested_type = "multi_choice" 
            confidence = "medium"
        elif percentage >= min_percentage:  # Seuil personnalisé
            suggested_type = "multi_choice"
            confidence = "medium"
    elif pipes >= 500 and percentage >= 50:  # Moins de données mais % élevé
        suggested_type = "multi_choice"
        confidence = "medium"
    
    return {
        "total_answers": total,
        "pipe_answers": pipes, 
        "percentage": percentage,
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
        
        if analysis["suggested_type"] == "multi_choice":
            mistyped.append({
                "id": q["id"],
                "prompt": q["prompt"],
                "current_type": q["type"],
                "suggested_type": analysis["suggested_type"],
                "total_answers": analysis["total_answers"],
                "pipe_answers": analysis["pipe_answers"],
                "percentage": analysis["percentage"],
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
    print(f"{'ID':<5} {'Type':<12} {'Réponses':<10} {'Pipes':<10} {'%':<6} {'Conf':<6} {'Prompt':<40}")
    print(f"{'-' * 5} {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 6} {'-' * 6} {'-' * 40}")
    
    for q in mistyped_questions:
        prompt_preview = q["prompt"][:37] + "..." if len(q["prompt"]) > 40 else q["prompt"]
        print(f"{q['id']:<5} "
              f"{q['current_type']:<12} "
              f"{q['total_answers']:<10} "
              f"{q['pipe_answers']:<10} "
              f"{q['percentage']:<6.1f} "
              f"{q['confidence']:<6} "
              f"{prompt_preview:<40}")

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
            print(f"  [DRY-RUN] Question {q['id']}: {q['current_type']} → {q['suggested_type']}")
        else:
            try:
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