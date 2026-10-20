"""Guarded, explicitly invoked Alembic migration for the deployment release."""

import argparse
import json
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_SOURCE_TABLES = (
    "forms",
    "questions",
    "options",
    "answers",
    "answer_options",
    "contributions",
    "question_stats",
)


def migration_plan(env):
    source = env.get("MIGRATION_FROM_REVISION", "")
    target = env.get("MIGRATION_TARGET_REVISION", "")
    scripts = ScriptDirectory(str(ROOT / "migrations"))
    target_script = scripts.get_revision(target) if target else None
    if not source or not target_script:
        raise ValueError("Set MIGRATION_FROM_REVISION and MIGRATION_TARGET_REVISION")
    if scripts.get_heads() != [target]:
        raise ValueError("Migration target must be the repository's single Alembic head")
    if target_script.down_revision != source:
        raise ValueError("Migration target is not a direct child of the planned source revision")
    if scripts.get_revision(source) is None:
        raise ValueError("Planned source revision is not present in this repository")
    return source, target


def inspect_database(connection, env):
    source, target = migration_plan(env)
    expected_host = env.get("EXPECTED_DB_HOST", "")
    expected_name = env.get("EXPECTED_DB_NAME", "")
    expected_user = env.get("EXPECTED_DB_USER", "")
    actual = connection.execute(
        text("SELECT current_database(), current_user, current_setting('server_version_num')::int")
    ).one()
    database, user, version = actual
    if (database, user) != (expected_name, expected_user):
        raise ValueError("Connected database/user differs from EXPECTED_DB_* values")
    major = int(env.get("EXPECTED_PG_MAJOR", "17"))
    if version // 10000 != major:
        raise ValueError(f"Expected PostgreSQL {major}")
    if not expected_host:
        raise ValueError("EXPECTED_DB_HOST is required")
    if not connection.execute(
        text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
    ).scalar_one():
        raise ValueError("Database role needs CREATE privilege on schema public")
    for table in MIGRATION_SOURCE_TABLES:
        if connection.execute(
            text("SELECT to_regclass(:table)"), {"table": f"public.{table}"}
        ).scalar() is None:
            raise ValueError(f"Migration source table is missing: public.{table}")
        if not connection.execute(
            text("SELECT has_table_privilege(current_user, :table, 'TRIGGER')"),
            {"table": f"public.{table}"},
        ).scalar_one():
            raise ValueError(f"Database role needs TRIGGER privilege on public.{table}")
    if connection.execute(text("SELECT to_regclass('public.alembic_version')")).scalar() is None:
        revisions = []
    else:
        revisions = list(
            connection.execute(text("SELECT version_num FROM public.alembic_version")).scalars()
        )
    if revisions != [source]:
        raise ValueError(
            f"Database revision does not match planned source {source}; observed {revisions}"
        )
    return {
        "status": "ready",
        "database": database,
        "user": user,
        "postgres_major": version // 10000,
        "current_revision": source,
        "target_revision": target,
    }


def database_url(env):
    raw = env.get("DATABASE_URL", "")
    if not raw or "REPLACE_WITH" in raw:
        raise ValueError("Configure DATABASE_URL privately")
    if any(env.get(key) for key in ("TEST_DATABASE_URL", "ALEMBIC_DATABASE_URL", "SCALINGO_POSTGRESQL_URL")):
        raise ValueError("Remove alternate database URL variables")
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    url = make_url(raw)
    if url.get_backend_name() != "postgresql":
        raise ValueError("DATABASE_URL must use PostgreSQL")
    if (url.host, url.database, url.username) != (
        env.get("EXPECTED_DB_HOST"),
        env.get("EXPECTED_DB_NAME"),
        env.get("EXPECTED_DB_USER"),
    ):
        raise ValueError("DATABASE_URL host/database/user differs from EXPECTED_DB_* values")
    return url.set(drivername="postgresql+psycopg2")


def run(env, apply=False):
    url = database_url(env)
    engine = create_engine(
        url,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=60000 -c lock_timeout=5000"},
    )
    try:
        with engine.connect() as connection:
            with connection.begin():
                if not apply:
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                report = inspect_database(connection, env)
                if not apply:
                    report["status"] = "ready"
                else:
                    config = Config(str(ROOT / "alembic.ini"))
                    config.attributes["connection"] = connection
                    command.upgrade(config, report["target_revision"])
                    report["status"] = "applied"
                    report["current_revision"] = report["target_revision"]
                return report
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the single explicitly configured migration after the guarded revision check",
    )
    args = parser.parse_args()
    try:
        report = run(os.environ, apply=args.apply)
    except Exception as exc:
        report = {
            "status": "failed",
            "errors": [str(exc) if isinstance(exc, ValueError) else f"Migration check failed ({type(exc).__name__})"],
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"ready", "applied"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
