"""add answer indexes for answers search

Revision ID: 2719d33cf3a4
Revises: 7eceb180a51a
Create Date: 2025-08-22 00:31:28.243087

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2719d33cf3a4'
down_revision: Union[str, Sequence[str], None] = '7eceb180a51a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index partiel : sous-ensemble "réponses valides" pour timeline + count
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_answers_nonempty_recent
        ON answers(id DESC)
        WHERE text IS NOT NULL AND length(text) >= 60 AND trim(text) <> '';
        """
    )

    # Index pour JOINs fréquents
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_answers_question_id
        ON answers(question_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_answers_contribution_id
        ON answers(contribution_id);
        """
    )


def downgrade() -> None:
    # Suppression des index (idempotent)
    op.execute("DROP INDEX IF EXISTS idx_answers_contribution_id;")
    op.execute("DROP INDEX IF EXISTS idx_answers_question_id;")
    op.execute("DROP INDEX IF EXISTS idx_answers_nonempty_recent;")
