"""dashboard_cache_table_for_performance

Revision ID: 85d4c0e7c4c5
Revises: 4bd975b7a072
Create Date: 2025-08-31 11:35:23.687491

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85d4c0e7c4c5'
down_revision: Union[str, Sequence[str], None] = '4bd975b7a072'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create dashboard_cache table for performance optimization."""
    # Create dashboard cache table
    op.execute("""
        CREATE TABLE dashboard_cache (
            form_id INTEGER PRIMARY KEY,
            stats_json TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    
    # Index for cleanup of old cache entries
    op.execute("""
        CREATE INDEX idx_dashboard_cache_updated_at 
        ON dashboard_cache(updated_at)
    """)
    
    # Add performance indexes for dashboard queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_answer_options_question_id 
        ON answer_options(option_id, answer_id)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_answers_question_id_multi 
        ON answers(question_id) 
        WHERE text LIKE '%|%'
    """)


def downgrade() -> None:
    """Remove dashboard cache table and performance indexes."""
    op.execute("DROP TABLE IF EXISTS dashboard_cache")
    op.execute("DROP INDEX IF EXISTS idx_dashboard_cache_updated_at")
    op.execute("DROP INDEX IF EXISTS idx_answer_options_question_id")  
    op.execute("DROP INDEX IF EXISTS idx_answers_question_id_multi")
