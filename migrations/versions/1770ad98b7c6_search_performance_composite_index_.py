"""search_performance_composite_index_answers_tsv_id

Revision ID: 1770ad98b7c6
Revises: 193a3c9b0de7
Create Date: 2025-08-31 10:47:22.768713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1770ad98b7c6'
down_revision: Union[str, Sequence[str], None] = '193a3c9b0de7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add index on answers(id) ordered DESC for search performance cursor pagination."""
    # This helps with cursor-based pagination when combined with existing text_tsv index
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_answers_id_desc "
        "ON answers (id DESC)"
    )


def downgrade() -> None:
    """Remove index on answers(id DESC)."""
    op.execute("DROP INDEX IF EXISTS idx_answers_id_desc")
