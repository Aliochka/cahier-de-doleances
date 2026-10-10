"""Bounded, read-only deployment checks. Never imports the FastAPI entry point."""

import argparse
import json
import os
import socket
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.models import Base

REQUIRED_TABLES = (
    "authors",
    "forms",
    "questions",
    "options",
    "contributions",
    "answers",
    "answer_options",
    "users",
    "bookmarks",
    "question_stats",
    "answer_valid_stats",
)
# Names, target tables and access methods from the existing migrations.
CRITICAL_INDEXES = {
    "idx_answers_text_tsv": ("answers", "gin"),
    "idx_answers_fts_length_id_critical": ("answers", "gin"),
    "idx_questions_prompt_tsv": ("questions", "gin"),
    "ix_forms_tsv_name": ("forms", "gin"),
    "ix_questions_prompt_unaccent_trgm": ("questions", "gin"),
    "ix_forms_name_unaccent_trgm": ("forms", "gin"),
    "idx_answers_qid_id_desc_nonempty": ("answers", "btree"),
    "idx_answers_id_desc_long_text": ("answers", "btree"),
    "idx_answers_contribution_id": ("answers", "btree"),
    "idx_contrib_author_id": ("contributions", "btree"),
    "idx_contrib_form_id": ("contributions", "btree"),
    "idx_bookmarks_user_type": ("bookmarks", "btree"),
    "ix_users_email": ("users", "btree"),
    "unique_user_bookmark": ("bookmarks", "btree"),
}
INDEX_COLUMNS = {
    "idx_answers_text_tsv": ("text_tsv",),
    "idx_answers_fts_length_id_critical": ("text_tsv",),
    "idx_questions_prompt_tsv": ("prompt_tsv",),
    "ix_forms_tsv_name": ("tsv_name",),
    "ix_questions_prompt_unaccent_trgm": ("prompt_unaccent",),
    "ix_forms_name_unaccent_trgm": ("name_unaccent",),
    "idx_answers_qid_id_desc_nonempty": ("question_id", "id"),
    "idx_answers_id_desc_long_text": ("id",),
    "idx_answers_contribution_id": ("contribution_id",),
    "idx_contrib_author_id": ("author_id",),
    "idx_contrib_form_id": ("form_id",),
    "idx_bookmarks_user_type": ("user_id", "page_type"),
    "ix_users_email": ("email",),
    "unique_user_bookmark": ("user_id", "page_type", "page_id"),
}


def inspect_schema(connection, expected_revision):
    errors = []
    heads = ScriptDirectory(str(Path(__file__).resolve().parents[1] / "migrations")).get_heads()
    if heads != [expected_revision]:
        errors.append(f"Repository Alembic heads differ: {heads}")
    if connection.execute(text("SELECT to_regclass('public.alembic_version')")).scalar() is None:
        revisions = []
    else:
        revisions = list(
            connection.execute(text("SELECT version_num FROM public.alembic_version")).scalars()
        )
    if revisions != [expected_revision]:
        errors.append(f"Database Alembic revisions differ: {revisions}")

    columns = {}
    for table, column in connection.execute(
        text("""
        SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema='public'
    """)
    ):
        columns.setdefault(table, set()).add(column)
    for table in REQUIRED_TABLES:
        required = {column.name for column in Base.metadata.tables[table].columns}
        if table == "questions":
            required |= {"prompt_tsv", "prompt_unaccent", "tsv_prompt"}
        if table == "answers":
            required.add("text_tsv")
        missing = required - columns.get(table, set())
        if missing:
            errors.append(f"Missing table/columns public.{table}: {sorted(missing)}")
        if table in columns:
            allowed = connection.execute(
                text("SELECT has_table_privilege(current_user, :table, 'SELECT')"),
                {"table": f"public.{table}"},
            ).scalar()
            if not allowed:
                errors.append(f"Missing SELECT privilege on public.{table}")

    for table, privileges in {
        "users": ("INSERT", "UPDATE"),
        "authors": ("INSERT", "UPDATE"),
        "bookmarks": ("INSERT", "DELETE"),
    }.items():
        if table not in columns:
            continue
        for privilege in privileges:
            allowed = connection.execute(
                text("SELECT has_table_privilege(current_user, :table, :privilege)"),
                {"table": f"public.{table}", "privilege": privilege},
            ).scalar()
            if not allowed:
                errors.append(f"Missing {privilege} privilege on public.{table}")
        sequence_usage = connection.execute(
            text(
                "SELECT has_sequence_privilege(current_user, pg_get_serial_sequence(:table, 'id'), 'USAGE')"
            ),
            {"table": f"public.{table}"},
        ).scalar()
        if not sequence_usage:
            errors.append(f"Missing identity sequence/USAGE privilege for public.{table}.id")

    extensions = set(connection.execute(text("SELECT extname FROM pg_extension")).scalars())
    if missing := {"unaccent", "pg_trgm"} - extensions:
        errors.append(f"Missing extensions: {sorted(missing)}")
    config = connection.execute(
        text("""
        SELECT cfg.cfgname FROM pg_ts_config cfg
        JOIN pg_namespace ns ON ns.oid=cfg.cfgnamespace
        WHERE ns.nspname='public' AND cfg.cfgname='fr_unaccent'
    """)
    ).scalar()
    if config is None:
        errors.append("Missing text search configuration public.fr_unaccent")
    elif "unaccent" in extensions:
        matches = connection.execute(
            text("""
            SELECT to_tsvector('public.fr_unaccent', 'éducation')
                   @@ websearch_to_tsquery('public.fr_unaccent', 'education')
        """)
        ).scalar()
        if not matches:
            errors.append("fr_unaccent does not match accented/unaccented search terms")

    indexes = {
        row[0]: row[1:]
        for row in connection.execute(
            text("""
            SELECT idx.relname, tbl.relname, am.amname, i.indisvalid, i.indisready,
                   ARRAY(SELECT pg_get_indexdef(i.indexrelid, n, true)
                         FROM generate_series(1, i.indnkeyatts) n),
                   i.indisunique
            FROM pg_index i JOIN pg_class idx ON idx.oid=i.indexrelid
            JOIN pg_class tbl ON tbl.oid=i.indrelid
            JOIN pg_namespace ns ON ns.oid=tbl.relnamespace
            JOIN pg_am am ON am.oid=idx.relam WHERE ns.nspname='public'
        """)
        )
    }
    for index, (table, method) in CRITICAL_INDEXES.items():
        actual = indexes.get(index)
        if actual is None or actual[:4] != (table, method, True, True):
            errors.append(f"Critical index missing, invalid or unexpected: {index}")
            continue
        keys, unique = actual[4:]
        expected_columns = INDEX_COLUMNS[index]
        if len(keys) != len(expected_columns) or any(
            column
            not in key.replace('"', "").split("::")[0].replace("(", "").replace(")", "").split()
            for key, column in zip(keys, expected_columns)
        ):
            errors.append(f"Unexpected columns in critical index: {index}")
        if index in {"ix_users_email", "unique_user_bookmark"} and not unique:
            errors.append(f"Expected unique index: {index}")
    return {
        "alembic_heads": heads,
        "alembic_current": revisions,
        "extensions": sorted(extensions),
        "errors": errors,
    }


def check_deployment(env, *, connection_only=False, count_contributions=False):
    raw = env.get("DATABASE_URL", "")
    if not raw or "REPLACE_WITH" in raw:
        raise ValueError("Configure DATABASE_URL with the existing database password")
    if any(
        env.get(key)
        for key in ("TEST_DATABASE_URL", "ALEMBIC_DATABASE_URL", "SCALINGO_POSTGRESQL_URL")
    ):
        raise ValueError("Remove alternate database URL variables")
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    url = make_url(raw)
    if url.get_backend_name() != "postgresql":
        raise ValueError("DATABASE_URL must use PostgreSQL")
    url = url.set(drivername="postgresql+psycopg2")
    expected_host = env.get("EXPECTED_DB_HOST", "cahier-postgres")
    expected_db = env.get("EXPECTED_DB_NAME", "cahier_doleances")
    expected_user = env.get("EXPECTED_DB_USER", "cahier")
    if (url.host, url.database, url.username) != (expected_host, expected_db, expected_user):
        raise ValueError("DATABASE_URL host/database/user differs from EXPECTED_DB_* values")
    addresses = sorted(
        {
            entry[4][0]
            for entry in socket.getaddrinfo(
                expected_host, url.port or 5432, type=socket.SOCK_STREAM
            )
        }
    )
    engine = create_engine(
        url,
        connect_args={
            "connect_timeout": 5,
            "options": "-c default_transaction_read_only=on -c statement_timeout=5000 -c lock_timeout=2000",
        },
    )
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            database, user, version, read_only = connection.execute(
                text("""
                SELECT current_database(), current_user,
                       current_setting('server_version_num')::int,
                       current_setting('transaction_read_only')
            """)
            ).one()
            errors = []
            if (database, user) != (expected_db, expected_user):
                errors.append("Connected database/user differs from expectations")
            if version // 10000 != int(env.get("EXPECTED_PG_MAJOR", "17")):
                errors.append(f"Unexpected PostgreSQL version: {version}")
            if read_only != "on":
                errors.append("Read-only transaction is not active")
            report = {
                "host": expected_host,
                "resolved_addresses": addresses,
                "database": database,
                "user": user,
                "server_version_num": version,
                "transaction_read_only": read_only,
                "errors": errors,
            }
            if not connection_only:
                schema = inspect_schema(
                    connection, env.get("EXPECTED_ALEMBIC_REVISION", "remove_runtime_caches")
                )
                report["errors"].extend(schema.pop("errors"))
                report.update(schema)
            if count_contributions and not report["errors"]:
                connection.execute(text("SET LOCAL statement_timeout = '30000'"))
                count = connection.execute(
                    text("SELECT count(*) FROM public.contributions")
                ).scalar_one()
                report["contributions"] = count
                if count != 1589285:
                    report["errors"].append(
                        f"Unexpected contributions count: {count} (expected 1589285)"
                    )
            report["status"] = "ok" if not report["errors"] else "failed"
            return report
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-only", action="store_true")
    parser.add_argument(
        "--count-contributions",
        action="store_true",
        help="Optional bounded full count; not a healthcheck",
    )
    args = parser.parse_args()
    try:
        report = check_deployment(
            os.environ,
            connection_only=args.connection_only,
            count_contributions=args.count_contributions,
        )
    except Exception as exc:
        # Never print SQLAlchemy exceptions: they can contain credentials or URLs.
        report = {
            "status": "failed",
            "errors": [
                f"Check failed ({type(exc).__name__}); verify DNS, credentials and configuration"
            ],
        }
        if isinstance(exc, ValueError):
            report["errors"] = [str(exc)]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
