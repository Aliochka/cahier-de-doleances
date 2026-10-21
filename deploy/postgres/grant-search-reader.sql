-- Run only AFTER restoring the new search database, as cluster administrator.
\set ON_ERROR_STOP on
\connect cahier_search
BEGIN;
DO $$
BEGIN
    IF (SELECT version_num FROM public.rag_alembic_version) IS DISTINCT FROM 'rag_0007'
       OR (SELECT extversion FROM pg_extension WHERE extname='vector') IS DISTINCT FROM '0.8.7' THEN
        RAISE EXCEPTION 'Unexpected restored schema';
    END IF;
END $$;
REVOKE CREATE ON SCHEMA public,rag,rag_full,rag_tuning FROM PUBLIC;
GRANT CONNECT ON DATABASE cahier_search TO cahier_search_reader;
GRANT USAGE ON SCHEMA public,rag_full,rag_tuning TO cahier_search_reader;
GRANT SELECT ON rag_full.spaces,rag_full.documents,rag_full.documents_full,
    rag_full.segments,rag_full.segments_full,rag_tuning.statistics,
    rag_tuning.term_statistics,public.rag_alembic_version TO cahier_search_reader;
GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO cahier_search_reader;
COMMIT;
\connect cahier_doleances
BEGIN;
-- Do not revoke existing application privileges to repair an unsafe reader.
-- Fail instead; inherited privileges require a separately reviewed intervention.
DO $$
BEGIN
    IF has_schema_privilege('cahier_search_reader','public','CREATE')
       OR has_database_privilege('cahier_search_reader',current_database(),'CREATE')
       OR EXISTS (
           SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND c.relkind IN ('r','p')
           AND (has_table_privilege('cahier_search_reader',c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER')
                OR pg_has_role('cahier_search_reader',c.relowner,'MEMBER'))
       ) THEN
        RAISE EXCEPTION 'Unsafe inherited source privileges: stop, preserve application ACLs';
    END IF;
END $$;
GRANT CONNECT ON DATABASE cahier_doleances TO cahier_search_reader;
GRANT USAGE ON SCHEMA public TO cahier_search_reader;
GRANT SELECT ON public.alembic_version TO cahier_search_reader;
GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO cahier_search_reader;
COMMIT;
