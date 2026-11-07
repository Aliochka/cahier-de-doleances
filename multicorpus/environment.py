"""Explicit local endpoints and physical identities; no production fallback."""

import ipaddress
from pathlib import Path

from cahier_rag.safety import inspect_database
from cahier_rag.search.service.reader import SearchReader
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


def local_engine(url):
    # Existing reader role allows only four concurrent connections. No idle leases
    # in this optional laboratory; H1 SQL/guards remain unchanged.
    return create_engine(
        url,
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 1,
            "options": "-c default_transaction_read_only=on -c statement_timeout=1000 -c lock_timeout=500",
        },
        execution_options={"postgresql_readonly": True},
    )


class LocalReader(SearchReader):
    def __init__(self, source, target, expected):
        self.expected = expected
        super().__init__(source, target)

    def validate(self, budget):
        for key, engine in [("source", self.source), ("target", self.target)]:
            budget.check()
            with engine.connect() as c, c.begin():
                c.execute(text("SET TRANSACTION READ ONLY"))
                identity = inspect_database(c, source=key == "source").to_dict()
                address = c.execute(text("SELECT inet_server_addr()::text")).scalar_one()
                if identity != self.expected[key] or (
                    address is not None and not ipaddress.ip_interface(address).ip.is_loopback
                ):
                    raise ValueError("Local physical database identity mismatch")
        budget.check()
        return super().validate(budget)


def local_reader(path, expected):
    # Only an explicitly named reader file; never import application config/.env.
    path = Path(path)
    values = dotenv_values(path, interpolate=False)
    engines = []
    for key in ["RAG_SOURCE_DATABASE_URL", "RAG_DATABASE_URL"]:
        url = make_url(values[key])
        if url.drivername not in {"postgresql", "postgresql+psycopg2"}:
            raise ValueError("Synchronous PostgreSQL reader required")
        if url.host not in {"127.0.0.1", "::1"} or url.query or url.port != 5432:
            raise ValueError(
                "Explicit loopback PostgreSQL port 5432 required; remote/service options refused"
            )
        if (
            url.database not in {"cahier_doleances_local", "cahier_rag"}
            or url.username != "cahier_search_reader"
        ):
            raise ValueError("Only the known local reader endpoints are accepted")
        engines.append(local_engine(url))
    return LocalReader(*engines, expected)


def hydration_engine(url, expected):
    parsed = make_url(url)
    if (
        parsed.drivername != "postgresql+psycopg2"
        or parsed.host is not None
        or parsed.database != expected["database_name"]
        or set(parsed.query) != {"host"}
        or parsed.query["host"] != "/var/run/postgresql"
    ):
        raise ValueError("Explicit local application Unix socket required for hydration")
    engine = local_engine(parsed)
    try:
        with engine.connect() as c, c.begin():
            if inspect_database(c, source=True).to_dict() != expected:
                raise ValueError("Hydration/source physical identity mismatch")
        return engine
    except Exception:
        engine.dispose()
        raise
