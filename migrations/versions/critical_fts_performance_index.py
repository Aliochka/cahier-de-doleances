"""critical_fts_performance_index

Revision ID: critical_fts_fix
Revises: performance_fix_001
Create Date: 2025-09-04 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'critical_fts_fix'
down_revision: Union[str, Sequence[str], None] = 'performance_fix_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add critical FTS performance index for search queries."""
    
    # Index composite critique pour la recherche FTS avec filtrage de longueur
    # Cet index permet de faire la recherche FTS ET le filtrage de longueur en une seule passe
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_answers_fts_length_id_critical
        ON answers USING GIN (text_tsv)
        WHERE char_length(btrim(text)) >= 60
    """)
    
    # Index partiel sur les ID pour les résultats FTS (pour ORDER BY id DESC optimisé)  
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_answers_id_desc_long_text
        ON answers (id DESC)
        WHERE char_length(btrim(text)) >= 60
    """)
    
    # Supprimer l'ancien index moins efficace s'il existe
    op.execute("DROP INDEX IF EXISTS idx_answers_long_text")


def downgrade() -> None:
    """Remove critical FTS performance indexes."""
    op.execute("DROP INDEX IF EXISTS idx_answers_fts_length_id_critical")
    op.execute("DROP INDEX IF EXISTS idx_answers_id_desc_long_text")