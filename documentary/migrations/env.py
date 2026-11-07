"""Only the explicitly guarded maintenance connection may run these migrations."""

from alembic import context

connection = context.config.attributes.get("connection")
if connection is None or not context.config.attributes.get("documentary_guarded"):
    raise RuntimeError("Use python -m documentary migrate with an explicit isolated destination")
context.configure(
    connection=connection,
    version_table="alembic_version",
    version_table_schema="documentary",
)
with context.begin_transaction():
    context.run_migrations()
