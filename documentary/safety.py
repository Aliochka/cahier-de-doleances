"""No .env, application URL, TCP connection, or implicit maintenance destination."""

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


class UnsafeDestination(ValueError):
    pass


class Destination:
    def __init__(self, url, expected_data_directory, expected_system_id):
        parsed = make_url(url)
        socket = Path(parsed.query.get("host", ""))
        data = Path(expected_data_directory)
        if (
            parsed.drivername != "postgresql+psycopg2"
            or parsed.host is not None
            or not (parsed.database or "").startswith("documentary_")
            or not (parsed.database or "").endswith("_test")
            or not socket.is_absolute()
            or not data.is_absolute()
            or not socket.resolve().is_relative_to(Path("/tmp"))
            or not data.resolve().is_relative_to(Path("/tmp"))
            or not socket.is_dir()
            or not data.is_dir()
            or socket.stat().st_uid != os.getuid()
            or data.stat().st_uid != os.getuid()
            or not str(expected_system_id).isdigit()
            or set(parsed.query) - {"host", "port"}
        ):
            raise UnsafeDestination(
                "Explicit private /tmp socket, cluster and documentary_*_test required"
            )
        self.expected_name = parsed.database
        self.data = data.resolve()
        self.system_id = str(expected_system_id)
        self.engine = create_engine(
            parsed, hide_parameters=True, connect_args={"connect_timeout": 3}
        )

    @contextmanager
    def transaction(self, *, readonly=False):
        with self.engine.connect() as c, c.begin():
            # Identity queries are read-only; absolutely no DDL before they pass.
            if readonly:
                c.execute(text("SET TRANSACTION READ ONLY"))
            row = c.execute(
                text("""SELECT current_database(), current_setting('data_directory'),
                (SELECT system_identifier::text FROM pg_control_system()), inet_server_addr()""")
            ).one()
            if (row[0], Path(row[1]).resolve(), row[2], row[3]) != (
                self.expected_name,
                self.data,
                self.system_id,
                None,
            ):
                raise UnsafeDestination(
                    "Physical PostgreSQL destination differs from explicit expectations"
                )
            forbidden = c.execute(
                text("""SELECT EXISTS (
                SELECT 1 FROM pg_namespace WHERE nspname IN ('rag','rag_full','rag_tuning'))
                OR to_regclass('public.answers') IS NOT NULL
                OR to_regclass('public.contributions') IS NOT NULL
                OR to_regclass('public.forms') IS NOT NULL
                OR to_regclass('public.questions') IS NOT NULL
                OR to_regclass('public.alembic_version') IS NOT NULL
                OR to_regclass('public.rag_alembic_version') IS NOT NULL""")
            ).scalar_one()
            if forbidden:
                raise UnsafeDestination(
                    "Use an isolated documentary database without GDN/RAG structures"
                )
            yield c

    def close(self):
        self.engine.dispose()
