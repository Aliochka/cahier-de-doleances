#!/usr/bin/env python3
"""
Script pour nettoyer le cache de recherche et afficher des statistiques
Usage: python scripts/clean_search_cache.py [--dry-run] [--older-than=HOURS] [--stats]
"""

import argparse
import sys
from pathlib import Path
import datetime

# Ajouter le répertoire parent au PYTHONPATH pour importer l'app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import SessionLocal
from sqlalchemy import text

def show_cache_stats(db):
    """Affiche les statistiques du cache de recherche"""
    print("📊 Statistiques du cache de recherche")
    print("=" * 50)
    
    # Stats générales
    cache_stats = db.execute(text("""
        SELECT 
            COUNT(*) as total_entries,
            SUM(LENGTH(results_json)) as total_size_bytes,
            AVG(search_count) as avg_popularity,
            MIN(created_at) as oldest_entry,
            MAX(created_at) as newest_entry
        FROM search_cache
    """)).mappings().first()
    
    if cache_stats and cache_stats["total_entries"]:
        total_mb = cache_stats["total_size_bytes"] / (1024 * 1024)
        print(f"Total des entrées: {cache_stats['total_entries']}")
        print(f"Taille totale: {total_mb:.2f} MB")
        print(f"Popularité moyenne: {cache_stats['avg_popularity']:.1f}")
        print(f"Plus ancienne entrée: {cache_stats['oldest_entry']}")
        print(f"Plus récente entrée: {cache_stats['newest_entry']}")
        
        # Top 10 des caches les plus populaires
        print("\n🔥 Top 10 des caches les plus populaires:")
        top_caches = db.execute(text("""
            SELECT cache_key, search_count, created_at,
                   LENGTH(results_json) as size_bytes
            FROM search_cache
            ORDER BY search_count DESC
            LIMIT 10
        """)).mappings().all()
        
        for cache in top_caches:
            key = cache["cache_key"]
            if len(key) > 40:
                key = key[:37] + "..."
            print(f"  {key:<40} | {cache['search_count']:>4} hits | {cache['size_bytes']:>6} bytes")
    else:
        print("Cache vide")
    
    print("\n📈 Statistiques des recherches populaires")
    print("=" * 50)
    
    # Stats des recherches
    search_stats = db.execute(text("""
        SELECT 
            COUNT(*) as total_queries,
            SUM(search_count) as total_searches,
            AVG(search_count) as avg_searches_per_query,
            MAX(search_count) as max_searches
        FROM search_stats
    """)).mappings().first()
    
    if search_stats and search_stats["total_queries"]:
        print(f"Requêtes uniques trackées: {search_stats['total_queries']}")
        print(f"Total des recherches: {search_stats['total_searches']}")
        print(f"Moyenne par requête: {search_stats['avg_searches_per_query']:.1f}")
        print(f"Maximum pour une requête: {search_stats['max_searches']}")
        
        # Top 10 des recherches
        print("\n🔍 Top 10 des requêtes les plus populaires:")
        top_searches = db.execute(text("""
            SELECT query_text, search_count, last_searched
            FROM search_stats
            ORDER BY search_count DESC
            LIMIT 10
        """)).mappings().all()
        
        for search in top_searches:
            query = search["query_text"]
            if len(query) > 35:
                query = query[:32] + "..."
            print(f"  '{query:<35}' | {search['search_count']:>4} fois | {search['last_searched']}")
    else:
        print("Aucune statistique de recherche")

def clean_expired_cache(db, hours_old: int, dry_run: bool = False):
    """Nettoie le cache expiré"""
    print(f"\n🧹 Nettoyage du cache (entrées > {hours_old}h)")
    print("=" * 50)
    
    # Compter les entrées à supprimer
    count_result = db.execute(text("""
        SELECT COUNT(*) as expired_count,
               SUM(LENGTH(results_json)) as expired_size_bytes
        FROM search_cache
        WHERE created_at < NOW() - INTERVAL '%s hours'
    """ % hours_old)).mappings().first()
    
    expired_count = count_result["expired_count"] if count_result else 0
    expired_size_mb = (count_result["expired_size_bytes"] or 0) / (1024 * 1024)
    
    if expired_count == 0:
        print("✅ Aucune entrée expirée à nettoyer")
        return
    
    print(f"Entrées expirées trouvées: {expired_count}")
    print(f"Espace à libérer: {expired_size_mb:.2f} MB")
    
    if dry_run:
        print("🔍 Mode dry-run: simulation seulement, aucune suppression")
        return
    
    # Supprimer les entrées expirées
    try:
        result = db.execute(text("""
            DELETE FROM search_cache
            WHERE created_at < NOW() - INTERVAL '%s hours'
        """ % hours_old))
        
        deleted_count = result.rowcount
        db.commit()
        
        print(f"✅ {deleted_count} entrées supprimées avec succès")
        
    except Exception as e:
        print(f"❌ Erreur lors de la suppression: {e}")
        db.rollback()

def clean_old_search_stats(db, days_old: int = 90, dry_run: bool = False):
    """Nettoie les anciennes statistiques de recherche"""
    print(f"\n🗑️  Nettoyage des stats de recherche (> {days_old} jours sans activité)")
    print("=" * 50)
    
    count_result = db.execute(text("""
        SELECT COUNT(*) as old_count
        FROM search_stats
        WHERE last_searched < NOW() - INTERVAL '%s days'
    """ % days_old)).mappings().first()
    
    old_count = count_result["old_count"] if count_result else 0
    
    if old_count == 0:
        print("✅ Aucune ancienne statistique à nettoyer")
        return
    
    print(f"Anciennes statistiques trouvées: {old_count}")
    
    if dry_run:
        print("🔍 Mode dry-run: simulation seulement, aucune suppression")
        return
    
    try:
        result = db.execute(text("""
            DELETE FROM search_stats
            WHERE last_searched < NOW() - INTERVAL '%s days'
        """ % days_old))
        
        deleted_count = result.rowcount
        db.commit()
        
        print(f"✅ {deleted_count} statistiques supprimées avec succès")
        
    except Exception as e:
        print(f"❌ Erreur lors de la suppression: {e}")
        db.rollback()

def main():
    parser = argparse.ArgumentParser(description="Gestion du cache de recherche")
    parser.add_argument("--dry-run", action="store_true", help="Simulation sans suppression")
    parser.add_argument("--older-than", type=int, default=48, help="Heures d'ancienneté pour le nettoyage (défaut: 48h)")
    parser.add_argument("--stats", action="store_true", help="Afficher seulement les statistiques")
    parser.add_argument("--clean-old-stats", type=int, metavar="DAYS", help="Nettoyer les stats inactives depuis X jours")
    
    args = parser.parse_args()
    
    try:
        with SessionLocal() as db:
            if args.stats:
                show_cache_stats(db)
            else:
                show_cache_stats(db)
                clean_expired_cache(db, args.older_than, args.dry_run)
                
                if args.clean_old_stats:
                    clean_old_search_stats(db, args.clean_old_stats, args.dry_run)
                    
        print("\n✅ Opération terminée")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()