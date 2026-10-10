#!/usr/bin/env python3
"""
Tests de performance sur la recherche pour diagnostiquer les timeouts
"""

import time

from sqlalchemy import text

from app.db import SessionLocal


def test_search_performance():
    """Test les performances de différentes requêtes de recherche"""

    # Requêtes de test qui ont causé des timeouts
    test_queries = [
        "financement",  # 507ms dans les logs
        "psychiatrie",  # 94ms dans les logs
        "lapin",  # 21ms dans les logs
        "économie",  # nouveau test
        "santé",  # nouveau test
        "éducation",  # nouveau test
    ]

    with SessionLocal() as db:
        print("=== TEST PERFORMANCES RECHERCHE ===\n")

        # Vérifier que les nouveaux index sont présents
        print("1. VÉRIFICATION DES INDEX:")

        new_indexes = (
            db.execute(
                text("""
            SELECT indexname, indexdef
            FROM pg_indexes 
            WHERE tablename IN ('questions', 'contributions', 'answers')
              AND (indexname LIKE '%type%' 
                   OR indexname LIKE '%author_submitted%'
                   OR indexname LIKE '%long_text%')
            ORDER BY indexname
        """)
            )
            .mappings()
            .all()
        )

        for idx in new_indexes:
            print(f"  ✅ {idx['indexname']}")

        if not new_indexes:
            print("  ❌ AUCUN NOUVEL INDEX TROUVÉ !")
            return

        print("\n2. TEST DES REQUÊTES:")

        for query in test_queries:
            print(f"\n🔍 Test: '{query}'")

            # Configuration pour ce test
            db.execute(text("SET work_mem = '32MB'"))

            start_time = time.time()

            try:
                # Utiliser la même requête que dans search.py
                result = (
                    db.execute(
                        text("""
                    SELECT
                        a.id                AS answer_id,
                        a.question_id       AS question_id,
                        q.prompt            AS question_prompt,
                        c.author_id         AS author_id,
                        c.submitted_at      AS submitted_at,
                        au.name             AS author_name,
                        LEFT(a.text, 1000) AS answer_text
                    FROM answers a
                    JOIN questions q ON q.id = a.question_id
                    JOIN contributions c ON c.id = a.contribution_id
                    LEFT JOIN authors au ON au.id = c.author_id
                    WHERE a.text_tsv @@ websearch_to_tsquery('fr_unaccent', :q)
                      AND char_length(btrim(a.text)) >= 60
                      AND q.type NOT IN ('single_choice', 'multi_choice')
                    ORDER BY a.id DESC
                    LIMIT 21
                """),
                        {"q": query},
                    )
                    .mappings()
                    .all()
                )

                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000

                print(f"  ⏱️  {duration_ms:.1f}ms - {len(result)} résultats")

                if duration_ms > 500:
                    print(f"  🔴 TIMEOUT PROBABLE (>{500}ms)")
                elif duration_ms > 100:
                    print(f"  ⚠️  LENT (>{100}ms)")
                else:
                    print(f"  ✅ RAPIDE (<{100}ms)")

            except Exception as e:
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                print(f"  💥 ERREUR après {duration_ms:.1f}ms: {e}")

        print("\n3. ANALYSE EXPLAIN:")

        # Analyser la requête la plus lente
        print("\n📊 EXPLAIN pour 'financement':")

        try:
            explain_result = (
                db.execute(
                    text("""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT
                    a.id, q.prompt, c.author_id
                FROM answers a
                JOIN questions q ON q.id = a.question_id
                JOIN contributions c ON c.id = a.contribution_id
                WHERE a.text_tsv @@ websearch_to_tsquery('fr_unaccent', :q)
                  AND char_length(btrim(a.text)) >= 60
                  AND q.type NOT IN ('single_choice', 'multi_choice')
                ORDER BY a.id DESC
                LIMIT 21
            """),
                    {"q": "financement"},
                )
                .mappings()
                .all()
            )

            for row in explain_result:
                line = row["QUERY PLAN"]
                if "Seq Scan" in line:
                    print(f"  🔴 {line}")
                elif "cost=" in line and "actual time=" in line:
                    print(f"  📈 {line}")
                elif "Nested Loop" in line or "Hash Join" in line or "Index" in line:
                    print(f"  🔧 {line}")

        except Exception as e:
            print(f"  ❌ Erreur EXPLAIN: {e}")

        print("\n4. STATISTIQUES TABLES:")

        # Vérifier les stats des tables
        stats = (
            db.execute(
                text("""
            SELECT 
                schemaname||'.'||tablename as table_name,
                n_tup_ins - n_tup_del as row_count,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                last_vacuum,
                last_analyze
            FROM pg_stat_user_tables 
            WHERE tablename IN ('answers', 'questions', 'contributions', 'authors')
            ORDER BY n_tup_ins - n_tup_del DESC
        """)
            )
            .mappings()
            .all()
        )

        for stat in stats:
            print(f"  📊 {stat['table_name']}: {stat['row_count']} rows ({stat['size']})")
            if stat["last_analyze"] is None:
                print("    ⚠️  Jamais analysée ! Exécuter ANALYZE")


if __name__ == "__main__":
    test_search_performance()
