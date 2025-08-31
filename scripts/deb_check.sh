# ⬇️ adapte USER/DB et PGPASSWORD si besoin
PGPASSWORD="$PGPASSWORD_SCALINGO" psql -h 127.0.0.1 -p 10000 -U cahier_de_d_9133 -d cahier_de_d_9133 -v ON_ERROR_STOP=1 -f - <<'SQL'
\pset pager off
\pset border 2
\pset format aligned
\timing off

-- Seuils "warning"
\set warn_conn 200
\set warn_cache 95.0

SELECT now() AS now,
       current_setting('server_version') AS server_version,
       current_setting('max_connections') AS max_connections;

-- Connexions
WITH s AS (
  SELECT COUNT(*) AS total,
         SUM(CASE WHEN state='active' THEN 1 ELSE 0 END) AS active,
         SUM(CASE WHEN wait_event IS NOT NULL THEN 1 ELSE 0 END) AS waiting
  FROM pg_stat_activity
  WHERE datname = current_database()
)
SELECT total AS conns_total, active AS conns_active, waiting AS conns_waiting FROM s;
SELECT COUNT(*) AS conns_idle_in_tx
FROM pg_stat_activity
WHERE datname = current_database() AND state = 'idle in transaction';

-- Cache hit
SELECT blks_hit, blks_read,
       ROUND(100.0*blks_hit/GREATEST(blks_hit+blks_read,1),2) AS cache_hit_pct
FROM pg_stat_database WHERE datname = current_database()\gset

-- Warnings lisibles
SELECT CASE WHEN :cache_hit_pct < :warn_cache
            THEN '⚠️  Cache hit ' || :cache_hit_pct || '% < ' || :warn_cache || '%'
            ELSE '✅ Cache hit ' || :cache_hit_pct || '%' END AS cache_hit_status;

WITH s AS (
  SELECT COUNT(*) AS total FROM pg_stat_activity WHERE datname=current_database()
) SELECT CASE WHEN total > :warn_conn
              THEN '⚠️  Connections ' || total || ' > ' || :warn_conn
              ELSE '✅ Connections ' || total || ' / ' || :warn_conn END AS connections_status
FROM s;

-- Tailles
SELECT pg_size_pretty(pg_database_size(current_database())) AS db_size;

-- Top relations (taille)
SELECT relkind,
       relname,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total,
       pg_size_pretty(pg_relation_size(c.oid))       AS table_size,
       pg_size_pretty(pg_total_relation_size(c.oid)-pg_relation_size(c.oid)) AS idx_toast
FROM pg_class c
JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND relkind IN ('r','i')
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 10;

-- Index usage + taille (answers/questions)
SELECT indexrelid::regclass AS index,
       idx_scan,
       pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE relname IN ('answers','questions')
ORDER BY relname, idx_scan DESC;

-- Santé VACUUM/ANALYZE (tables clés)
SELECT relname,
       n_live_tup, n_dead_tup,
       to_char(last_vacuum,      'YYYY-MM-DD HH24:MI') AS last_vacuum,
       to_char(last_autovacuum,  'YYYY-MM-DD HH24:MI') AS last_autovacuum,
       to_char(last_analyze,     'YYYY-MM-DD HH24:MI') AS last_analyze,
       to_char(last_autoanalyze, 'YYYY-MM-DD HH24:MI') AS last_autoanalyze
FROM pg_stat_all_tables
WHERE schemaname='public' AND relname IN ('answers','questions','contributions')
ORDER BY n_dead_tup DESC;

-- FTS: présence & taille index principaux
SELECT 'idx_answers_text_tsv'   AS index, pg_size_pretty(pg_relation_size('idx_answers_text_tsv'::regclass)) AS size
UNION ALL
SELECT 'idx_questions_prompt_tsv', pg_size_pretty(pg_relation_size('idx_questions_prompt_tsv'::regclass));

SQL
