from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---- Importe tes modèles pour l'autogénération ----
# Assure-toi que app.models:Base est importable depuis ici
from app.models import Base

# Optionnel : charger .env en local
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Alembic Config
config = context.config

# Logging Alembic
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Métadonnées pour 'alembic revision --autogenerate'
target_metadata = Base.metadata

# Priorité des sources d'URL : -x db_url=... > $DATABASE_URL > $SCALINGO_POSTGRESQL_URL > alembic.ini
x_args = context.get_x_argument(as_dictionary=True)
runtime_url = (
    x_args.get("db_url")
    or os.getenv("DATABASE_URL")
    or os.getenv("SCALINGO_POSTGRESQL_URL")
    or ""
).strip()

# Normalisation pour psycopg2 : convertir postgres://* ou postgresql://* en postgresql+psycopg2://*
def _normalize_psycopg2(url: str) -> str:
    if not url:
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://") and "+psycopg2" not in url and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url

runtime_url = _normalize_psycopg2(runtime_url)
if runtime_url:
    config.set_main_option("sqlalchemy.url", runtime_url)

# Sanity check
final_url = config.get_main_option("sqlalchemy.url")
if not final_url:
    raise RuntimeError(
        "SQLAlchemy URL manquante. Fournis-la via `-x db_url=...`, "
        "ou définis DATABASE_URL/SCALINGO_POSTGRESQL_URL, ou mets-la dans alembic.ini."
    )

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
