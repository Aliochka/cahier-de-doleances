#!/usr/bin/env python3
"""
Analyser les performances de la requête de recherche
"""

from sqlalchemy import text

from app.db import SessionLocal


def analyze_search_query():
    """Analyse les performances de la requête FTS"""

    with SessionLocal() as db:
        print("=== ANALYSE PERFORMANCE REQUÊTE FTS ===\n")

        # 1. Vérifier les index existants
        print("1. INDEX EXISTANTS SUR LES TABLES CRITIQUES:")

        indexes = (
            db.execute(
                text("""
            SELECT schemaname, tablename, indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename IN ('answers', 'questions', 'contributions', 'authors')
              AND indexname LIKE '%tsv%' OR indexname LIKE '%id%' OR indexname LIKE '%question%'
            ORDER BY tablename, indexname
        """)
            )
            .mappings()
            .all()
        )

        for idx in indexes:
            print(f"  {idx['tablename']}.{idx['indexname']}")

        print(f"\nTotal index pertinents: {len(indexes)}")

        # 2. Test avec une requête simple
        test_queries = [
            "lapin",
            "psychiatrie",
            "financement",
            "",  # Timeline
        ]

        for query in test_queries:
            print(f"\n2. TEST QUERY: '{query}'")

            if not query:
                print("   -> Timeline query (pas de FTS)")
                continue

            try:
                # Set work_mem pour cette session
                db.execute(text("SET work_mem = '32MB'"))

                # EXPLAIN ANALYZE
                explain = (
                    db.execute(
                        text("""
                    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                    WITH s AS (SELECT websearch_to_tsquery('fr_unaccent', :q) AS tsq)
                    SELECT a.id, a.question_id 
                    FROM answers a, s
                    WHERE a.text_tsv @@ s.tsq
                      AND char_length(btrim(a.text)) >= 60
                    ORDER BY a.id DESC
                    LIMIT 100
                """),
                        {"q": query},
                    )
                    .mappings()
                    .first()
                )

                plan = explain["QUERY PLAN"][0]
                exec_time = plan["Execution Time"]
                total_cost = plan["Plan"]["Total Cost"]

                print(f"   Execution Time: {exec_time:.2f}ms")
                print(f"   Total Cost: {total_cost:.2f}")

                # Chercher les Sequential Scans
                def find_seq_scans(node, depth=0):
                    if node.get("Node Type") == "Seq Scan":
                        print(
                            f"   {'  ' * depth}⚠️  SEQ SCAN sur {node.get('Relation Name', 'unknown')}"
                        )

                    for child in node.get("Plans", []):
                        find_seq_scans(child, depth + 1)

                find_seq_scans(plan["Plan"])

            except Exception as e:
                print(f"   ❌ Erreur: {e}")

        # 3. Statistiques tables
        print("\n3. TAILLE DES TABLES:")

        stats = (
            db.execute(
                text("""
            SELECT 
                schemaname,
                tablename, 
                n_tup_ins - n_tup_del as estimated_count,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_stat_user_tables 
            WHERE tablename IN ('answers', 'questions', 'contributions', 'authors')
            ORDER BY estimated_count DESC
        """)
            )
            .mappings()
            .all()
        )

        for stat in stats:
            print(f"  {stat['tablename']}: {stat['estimated_count']} rows ({stat['size']})")

        # 4. Questions les plus lentes
        print("\n4. RECOMMANDATIONS:")

        # Vérifier si on a l'index composite nécessaire
        composite_idx = (
            db.execute(
                text("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'answers' 
              AND indexdef LIKE '%text_tsv%id%'
        """)
            )
            .mappings()
            .all()
        )

        if not composite_idx:
            print("  🚨 INDEX MANQUANT: answers(text_tsv, id DESC)")
            print(
                "     → Créer: CREATE INDEX CONCURRENTLY idx_answers_tsv_id_desc ON answers USING GIN (text_tsv) WITH (id DESC);"
            )

        # Vérifier l'index sur contributions
        contrib_idx = (
            db.execute(
                text("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'contributions' 
              AND indexdef LIKE '%question_id%'
        """)
            )
            .mappings()
            .all()
        )

        print(f"  📊 Index sur contributions: {len(contrib_idx)} trouvé(s)")

        # Vérifier l'index sur questions.type
        type_idx = (
            db.execute(
                text("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'questions' 
              AND indexdef LIKE '%type%'
        """)
            )
            .mappings()
            .all()
        )

        if not type_idx:
            print("  🚨 INDEX MANQUANT: questions(type)")
            print("     → Créer: CREATE INDEX CONCURRENTLY idx_questions_type ON questions (type);")


if __name__ == "__main__":
    analyze_search_query()
