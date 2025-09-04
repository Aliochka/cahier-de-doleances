"""add_composite_indexes_for_search_performance

Revision ID: performance_fix_001
Revises: 388d40558a76
Create Date: 2025-09-04 09:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'performance_fix_001'
down_revision: Union[str, Sequence[str], None] = '388d40558a76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes to fix search timeouts."""
    
    # 1. Index sur questions.type pour éviter les scans sur les JOIN
    # Très utile car on filtre souvent par type
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_questions_type
        ON questions (type)
    """)
    
    # 2. Index composite sur contributions pour les JOINs
    # Optimise les JOINs contributions -> authors  
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_contributions_author_submitted
        ON contributions (author_id, submitted_at)
    """)
    
    # 3. Index partiel pour les réponses longues (condition fréquente)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_answers_long_text
        ON answers (id DESC)
        WHERE char_length(btrim(text)) >= 60
    """)


def downgrade() -> None:
    """Remove composite indexes."""
    op.execute("DROP INDEX IF EXISTS idx_questions_type")
    op.execute("DROP INDEX IF EXISTS idx_contributions_author_submitted") 
    op.execute("DROP INDEX IF EXISTS idx_answers_long_text")