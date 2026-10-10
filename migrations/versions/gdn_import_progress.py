"""Track resumable, verified imports of official source snapshots."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "gdn_import_progress"
down_revision = "restore_search_infra"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gdn_import_runs",
        sa.Column("source_key", sa.Text(), primary_key=True),
        sa.Column("file_sha256", sa.Text(), nullable=False),
        sa.Column("mapping_sha256", sa.Text(), nullable=False),
        sa.Column("rows_processed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stats", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade():
    op.drop_table("gdn_import_runs")
