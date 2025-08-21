from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool
from app.models import Base

# Charge .env si présent
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Alembic Config
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Métadonnées pour autogenerate
target_metadata = Base.metadata

# Priorité des sources d'URL: -x db_url=... > $DATABASE_URL > alembic.ini
x_args = context.get_x_argument(as_dictionary=True)
runtime_url = (x_args.get("db_url") or os.getenv("DATABASE_URL") or "").strip()

if runtime_url:
    config.set_main_option("sqlalchemy.url", runtime_url)

# Sanity check: on vérifie qu'on a bien une URL
final_url = config.get_main_option("sqlalchemy.url")
if not final_url:
    raise RuntimeError(
        "SQLAlchemy URL manquante. Fournis-la via `-x db_url=...`, "
        "ou définis DATABASE_URL, ou mets-la dans alembic.ini."
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
