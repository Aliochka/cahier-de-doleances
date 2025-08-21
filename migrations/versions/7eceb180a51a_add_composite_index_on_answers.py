"""add composite index on answers

Revision ID: 7eceb180a51a
Revises: cd95c6374600
Create Date: 2025-08-21 17:30:20.727406

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '7eceb180a51a'
down_revision: Union[str, Sequence[str], None] = 'cd95c6374600'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_answers_qid_id_desc_nonempty
        ON answers(question_id, id DESC)
        WHERE text IS NOT NULL AND trim(text) <> '';
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS idx_answers_qid_id_desc_nonempty;
    """)