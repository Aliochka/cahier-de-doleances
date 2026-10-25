-- Run against the dedicated search database as its maintenance owner.
-- Additive index only: no source data, document records or embeddings change.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
DO $$
BEGIN
    IF to_regclass('public.answers') IS NOT NULL
       OR to_regclass('public.questions') IS NOT NULL
       OR to_regclass('rag_full.documents_full') IS NULL
       OR (SELECT version_num FROM public.rag_alembic_version) IS DISTINCT FROM 'rag_0007'
    THEN
        RAISE EXCEPTION 'Expected dedicated rag_0007 search database';
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS full_documents_question
    ON rag_full.documents (space_id, ((record->>'question_id')::bigint));
COMMIT;
