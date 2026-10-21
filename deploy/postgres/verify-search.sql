-- Explicit post-restore maintenance validation; full counts may take minutes.
-- Never run on the application database. No writes, ANALYZE or index rebuilds.
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='30min';
SET LOCAL lock_timeout='500ms';
DO $$
DECLARE documents_count bigint; segments_count bigint;
BEGIN
    IF current_database()<>'cahier_search'
       OR (SELECT version_num FROM public.rag_alembic_version) IS DISTINCT FROM 'rag_0007'
       OR (SELECT extversion FROM pg_extension WHERE extname='vector') IS DISTINCT FROM '0.8.7' THEN
        RAISE EXCEPTION 'Wrong database, revision or extension';
    END IF;
    SELECT count(*) INTO documents_count FROM rag_full.documents_full;
    SELECT count(*) INTO segments_count FROM rag_full.segments_full;
    IF documents_count<>5172356 OR segments_count<>5187190
       OR NOT EXISTS (SELECT FROM rag_full.spaces WHERE space_id='full'
         AND documents=documents_count AND segments=segments_count
         AND expected_units=documents_count AND vector_cursor=documents_count
         AND verified AND extraction_complete AND vectors_complete) THEN
        RAISE EXCEPTION 'Restored counts differ from approved SEARCH-DEPLOY-001 corpus';
    END IF;
    IF EXISTS (SELECT FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('rag','rag_full','rag_tuning')
          AND (NOT i.indisvalid OR NOT i.indisready))
       OR EXISTS (SELECT FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
         WHERE n.nspname IN ('rag','rag_full','rag_tuning') AND NOT c.convalidated) THEN
        RAISE EXCEPTION 'Invalid index or unvalidated constraint';
    END IF;
    IF (SELECT count(*) FROM pg_inherits WHERE inhparent IN
        ('rag_full.documents'::regclass,'rag_full.segments'::regclass))<>4 THEN
        RAISE EXCEPTION 'Missing full/pilot partition';
    END IF;
END $$;
COMMIT;
