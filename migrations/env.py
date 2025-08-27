# migrations/env.py
from __future__ import annotations

import os
import sys
import pathlib
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- Charger .env sans override (prod Scalingo restera intacte)
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore
    load_dotenv(find_dotenv(), override=False)
except Exception:
    pass

# --- Config Alembic
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- PYTHONPATH du projet
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# --- Metadata du modèle
from app.models import Base  # noqa: E402

target_metadata = Base.metadata


def _get_url() -> str:
    """
    Résout l'URL DB selon une priorité stricte :
      1) -x db_url=... (ligne de commande Alembic)
      2) ALEMBIC_DATABASE_URL (si tu veux overrider en local)
      3) DATABASE_URL (par défaut, dev & prod Scalingo)
      4) sqlalchemy.url depuis alembic.ini (fallback)
    """
    xargs = context.get_x_argument(as_dictionary=True)
    url = (
        xargs.get("db_url")
        or os.getenv("ALEMBIC_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or config.get_main_option("sqlalchemy.url")
    )
    if not url:
        raise RuntimeError(
            "Aucune URL de base trouvée. "
            "Définis DATABASE_URL (ou ALEMBIC_DATABASE_URL), "
            "ou passe -x db_url=… "
            "ou renseigne sqlalchemy.url dans alembic.ini."
        )

    # Normaliser postgres:// vers psycopg2
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)

    return url


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
