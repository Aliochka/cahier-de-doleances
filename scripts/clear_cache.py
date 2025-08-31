#!/usr/bin/env python3
"""
Script pour vider le cache dashboard en production
Usage: python scripts/clear_cache.py [--form-id=X]
"""

import argparse
import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH pour importer l'app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal
from sqlalchemy import text

def clear_all_cache():
    """Vide tout le cache dashboard"""
    with SessionLocal() as db:
        result = db.execute(text("DELETE FROM dashboard_cache")).rowcount
        db.commit()
        print(f"✅ Cache vidé: {result} entrées supprimées")

def clear_form_cache(form_id: int):
    """Vide le cache d'un formulaire spécifique"""
    with SessionLocal() as db:
        result = db.execute(
            text("DELETE FROM dashboard_cache WHERE form_id = :form_id"),
            {"form_id": form_id}
        ).rowcount
        db.commit()
        print(f"✅ Cache vidé pour formulaire {form_id}: {result} entrée(s) supprimée(s)")

def show_cache_status():
    """Affiche le statut du cache"""
    with SessionLocal() as db:
        result = db.execute(text("""
            SELECT form_id, 
                   LENGTH(stats_json) as size_bytes,
                   updated_at,
                   EXTRACT(EPOCH FROM (NOW() - updated_at))/60 as age_minutes
            FROM dashboard_cache 
            ORDER BY form_id
        """)).mappings().all()
        
        if not result:
            print("📊 Cache vide")
        else:
            print(f"📊 Cache status ({len(result)} entrées):")
            print(f"{'Form':<6} {'Taille':<8} {'Âge (min)':<10} {'Mis à jour':<20}")
            print("-" * 50)
            for row in result:
                age = f"{row['age_minutes']:.1f}" if row['age_minutes'] else "0"
                print(f"{row['form_id']:<6} {row['size_bytes']:<8} {age:<10} {row['updated_at']}")

def main():
    parser = argparse.ArgumentParser(description="Gestion du cache dashboard")
    parser.add_argument("--form-id", type=int, help="Vider le cache d'un formulaire spécifique")
    parser.add_argument("--status", action="store_true", help="Afficher le statut du cache")
    parser.add_argument("--clear-all", action="store_true", help="Vider tout le cache")
    
    args = parser.parse_args()
    
    try:
        if args.status:
            show_cache_status()
        elif args.clear_all:
            clear_all_cache()
        elif args.form_id:
            clear_form_cache(args.form_id)
        else:
            print("Usage:")
            print("  python scripts/clear_cache.py --status")
            print("  python scripts/clear_cache.py --clear-all")
            print("  python scripts/clear_cache.py --form-id=1")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()