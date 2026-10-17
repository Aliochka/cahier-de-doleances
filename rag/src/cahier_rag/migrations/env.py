"""Aucune migration, y compris Alembic direct, sans vérification des deux bases."""

from alembic import context

from cahier_rag.config import load_settings
from cahier_rag.db import create_rag_engine, create_source_engine
from cahier_rag.safety import DatabaseGuard, DatabaseSafetyError
from cahier_rag.schema import metadata

if context.is_offline_mode():
    raise DatabaseSafetyError(
        "Les migrations hors connexion sont refusées : identité des bases invérifiable."
    )

settings = context.config.attributes.get("rag_settings")
if settings is None:
    settings = load_settings(env_file=context.get_x_argument(as_dictionary=True).get("env_file"))
source = create_source_engine(settings)
target = create_rag_engine(settings)
try:
    with DatabaseGuard(source, target).transaction() as (connection, identity):
        context.configure(
            connection=connection,
            target_metadata=metadata,
            version_table="rag_alembic_version",
            version_table_schema="public",
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()
finally:
    source.dispose()
    target.dispose()
