# migrations/env.py
from __future__ import annotations

import os
import sys
import pathlib
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Config Alembic
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Ajouter le dossier racine du projet au PYTHONPATH
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]  # .../cahier-de-doleances
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Import du metadata de l’app
from app.models import Base  # noqa: E402

target_metadata = Base.metadata


def _get_url() -> str:
    """Récupère l’URL de base (env ou alembic.ini) et la normalise pour SQLAlchemy."""
    url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("DATABASE_URL non défini et sqlalchemy.url manquant")
    # Normaliser postgres:// vers le driver que tu utilises (ici psycopg2)
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
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
