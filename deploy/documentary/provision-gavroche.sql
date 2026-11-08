-- PREPARED ONLY. Run AFTER approved full backups and isolated restore verification.
-- No change to GDN schemas, ownership, privileges or publication flags.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout='2s';
SET LOCAL statement_timeout='10s';
DO $$
BEGIN
  IF current_database()<>'cahier_search'
     OR (SELECT oid FROM pg_database WHERE datname=current_database())<>634726
     OR (SELECT system_identifier::text FROM pg_control_system())<>'7695026423032606758'
     OR current_user<>'cahier'
     OR (SELECT version_num FROM public.rag_alembic_version) IS DISTINCT FROM 'rag_0007'
     OR (SELECT extversion FROM pg_extension WHERE extname='vector') IS DISTINCT FROM '0.8.7' THEN
    RAISE EXCEPTION 'Physical production destination, role or revision mismatch';
  END IF;
  IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='cahier_documentary_owner') THEN
    CREATE ROLE cahier_documentary_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
  END IF;
  IF EXISTS(SELECT FROM pg_roles WHERE rolname='cahier_documentary_owner'
            AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls))
     OR EXISTS(SELECT FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='cahier_documentary_owner')) THEN
    RAISE EXCEPTION 'Documentary owner must have no privileged attributes or inherited roles';
  END IF;
  IF to_regnamespace('documentary') IS NULL THEN
    CREATE SCHEMA documentary AUTHORIZATION cahier_documentary_owner;
  END IF;
  IF (SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='documentary')<>'cahier_documentary_owner' THEN
    RAISE EXCEPTION 'Existing documentary schema has an unexpected owner';
  END IF;
END $$;
GRANT cahier_documentary_owner TO cahier_search_maintenance;
COMMIT;
