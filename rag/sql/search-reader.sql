-- SEARCH-003, Hal9000 uniquement. Exécuter avec psql en administrateur local.
-- Aucun mot de passe dans ce fichier : utiliser ensuite \password cahier_search_reader.
-- Aucune table, donnée, structure d'index ou configuration du serveur modifiée.
\set ON_ERROR_STOP on
\connect cahier_rag

BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cahier_search_reader') THEN
        CREATE ROLE cahier_search_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 4;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cahier_search_reader'
               AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
       OR EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member
                  WHERE r.rolname='cahier_search_reader') THEN
        RAISE EXCEPTION 'Rôle préexistant privilégié : refus de le réutiliser';
    END IF;
END $$;
ALTER ROLE cahier_search_reader SET default_transaction_read_only=on;
ALTER ROLE cahier_search_reader SET statement_timeout='1s';
ALTER ROLE cahier_search_reader SET lock_timeout='500ms';
-- Les bases locales héritent d'un public appartenant à postgres avec CREATE
-- pour PUBLIC. Un REVOKE sur le seul lecteur ne supprime pas ce droit hérité.
-- Conserver la capacité de migration du propriétaire de base avant de le retirer.
DO $$
DECLARE owner_name text;
BEGIN
    SELECT pg_get_userbyid(datdba) INTO owner_name
    FROM pg_database WHERE datname=current_database();
    EXECUTE format('GRANT CREATE ON SCHEMA public TO %I', owner_name);
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE cahier_rag TO cahier_search_reader;
GRANT USAGE ON SCHEMA public,rag_full,rag_tuning TO cahier_search_reader;
GRANT SELECT ON rag_full.spaces,rag_full.documents,rag_full.documents_full,
    rag_full.segments,rag_full.segments_full,rag_tuning.statistics,
    rag_tuning.term_statistics,public.rag_alembic_version TO cahier_search_reader;
GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO cahier_search_reader;
COMMIT;

\connect cahier_doleances_local
BEGIN;
DO $$
DECLARE owner_name text;
BEGIN
    SELECT pg_get_userbyid(datdba) INTO owner_name
    FROM pg_database WHERE datname=current_database();
    EXECUTE format('GRANT CREATE ON SCHEMA public TO %I', owner_name);
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE cahier_doleances_local TO cahier_search_reader;
GRANT USAGE ON SCHEMA public TO cahier_search_reader;
GRANT SELECT ON public.alembic_version TO cahier_search_reader;
GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO cahier_search_reader;
COMMIT;

-- Ce login de recherche n'hydrate pas les résultats : SEARCH-004 utilisera
-- le pool applicatif pour les métadonnées publiques. Aucun droit d'écriture
-- ni droit d'import/migration RAG n'est attribué ici.
