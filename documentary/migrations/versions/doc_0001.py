"""Documentary phase 1; independent of public.rag_alembic_version."""

from pathlib import Path

from alembic import op

revision = "doc_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text())


def downgrade():
    raise RuntimeError("No destructive downgrade: retain the inactive documentary schema")
