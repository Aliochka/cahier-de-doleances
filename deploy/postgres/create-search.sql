-- Explicit administrative operation, after backups/image checks; NEVER at startup.
-- Run with psql -X -v ON_ERROR_STOP=1 as the existing cluster administrator.
\set ON_ERROR_STOP on
DO $$
BEGIN
    IF current_setting('server_version_num')::int NOT BETWEEN 170011 AND 179999 THEN
        RAISE EXCEPTION 'PostgreSQL 17.11+ required';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_available_extension_versions
                   WHERE name='vector' AND version='0.8.7') THEN
        RAISE EXCEPTION 'pgvector 0.8.7 binaries unavailable';
    END IF;
    IF EXISTS (SELECT FROM pg_database WHERE datname='cahier_search')
       OR EXISTS (SELECT FROM pg_roles WHERE rolname IN
                   ('cahier_search_owner','cahier_search_reader')) THEN
        RAISE EXCEPTION 'Existing search database/roles: stop and inspect, no overwrite';
    END IF;
END $$;
CREATE ROLE cahier_search_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
CREATE ROLE cahier_search_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 4;
ALTER ROLE cahier_search_reader SET default_transaction_read_only=on;
ALTER ROLE cahier_search_reader SET statement_timeout='1s';
ALTER ROLE cahier_search_reader SET lock_timeout='500ms';
CREATE DATABASE cahier_search OWNER cahier_search_owner TEMPLATE template0
    ENCODING 'UTF8' LC_COLLATE 'fr_FR.UTF-8' LC_CTYPE 'fr_FR.UTF-8';
REVOKE ALL ON DATABASE cahier_search FROM PUBLIC;
\connect cahier_search
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE EXTENSION vector VERSION '0.8.7';
-- Set reader password interactively with \password; no password in scripts/logs.
-- A partial administrative failure requires inspection, never DROP/retry blindly.
