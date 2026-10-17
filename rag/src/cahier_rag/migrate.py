"""Entrée Alembic autonome, installable hors du monorepo."""

from alembic import command
from alembic.config import Config

from cahier_rag.config import Settings


def upgrade_schema(settings: Settings) -> None:
    config = Config()
    config.set_main_option("script_location", "cahier_rag:migrations")
    config.attributes["rag_settings"] = settings
    command.upgrade(config, "head")
