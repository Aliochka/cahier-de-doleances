"""Read-only readiness check and explicit first publication of public statistics."""

import argparse
import json
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.services.statistics_generation import GenerationError, generate


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


def check_database(connection, env):
    actual = connection.execute(
        text("SELECT current_database(), current_user, current_setting('server_version_num')::int")
    ).one()
    database, user, version = actual
    if (database, user) != (env.get("EXPECTED_DB_NAME"), env.get("EXPECTED_DB_USER")):
        raise ValueError("Connected database/user differs from EXPECTED_DB_* values")
    major = int(env.get("EXPECTED_PG_MAJOR", "17"))
    if version // 10000 != major:
        raise ValueError(f"Expected PostgreSQL {major}")
    if connection.execute(text("SELECT to_regclass('public.statistics_source')")).scalar() is None:
        raise ValueError("Statistics migration is not installed")
    revision = connection.execute(
        text("SELECT version_num FROM public.alembic_version")
    ).scalar_one_or_none()
    target = env.get("EXPECTED_ALEMBIC_REVISION", "")
    if revision != target or target != "forms_statistics_v1":
        raise ValueError("Database is not at the configured forms_statistics_v1 revision")
    state = connection.execute(
        text("SELECT published_generation, revision FROM public.statistics_source WHERE id=1")
    ).one_or_none()
    if state is None:
        raise ValueError("Statistics source row is missing")
    return {
        "status": "ready",
        "database": database,
        "user": user,
        "postgres_major": version // 10000,
        "revision": revision,
        "published": state.published_generation is not None,
        "source_revision": state.revision,
    }


def run(env, *, publish=False):
    url = database_url(env)
    options = {
        "connect_args": {
            "connect_timeout": 5,
            "options": "-c statement_timeout=900000 -c lock_timeout=5000",
        },
    }
    if publish:
        options["isolation_level"] = "REPEATABLE READ"
    engine = create_engine(url, **options)
    try:
        if not publish:
            with engine.connect() as connection, connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                return check_database(connection, env)
        with Session(engine) as db, db.begin():
            check = check_database(db.connection(), env)
            result = generate(
                db,
                checkpoint=lambda phase: print(
                    "Statistics publication: " + phase, file=sys.stderr, flush=True
                ),
            )
            return {
                **check,
                "status": "published",
                "published": True,
                "generation_id": result["generation_id"],
                "questions": result["questions"],
                "forms": result["forms"],
                "seconds": result["seconds"],
            }
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Generate and atomically publish statistics after checking the configured production DB",
    )
    args = parser.parse_args()
    try:
        report = run(os.environ, publish=args.publish)
    except Exception as exc:
        report = {
            "status": "failed",
            "errors": [
                str(exc)
                if isinstance(exc, (ValueError, GenerationError))
                else f"Statistics operation failed ({type(exc).__name__})"
            ],
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"ready", "published"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
