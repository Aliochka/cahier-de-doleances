"""remove_unused_trigram_index_answers_text_trgm

Revision ID: 4bd975b7a072
Revises: 1770ad98b7c6
Create Date: 2025-08-31 11:10:56.836800

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4bd975b7a072'
down_revision: Union[str, Sequence[str], None] = '1770ad98b7c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove unused trigram index on answers.text (10x slower than FTS)."""
    # This index is not used and much slower than FTS search
    op.execute("DROP INDEX IF EXISTS idx_answers_text_trgm")


def downgrade() -> None:
    """Recreate trigram index on answers.text."""
    # Note: Only recreate if pg_trgm extension is available
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_answers_text_trgm "
        "ON answers USING gin (text gin_trgm_ops)"
    )
