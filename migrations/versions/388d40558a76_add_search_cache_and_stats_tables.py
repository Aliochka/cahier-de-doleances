"""add_search_cache_and_stats_tables

Revision ID: 388d40558a76
Revises: 85d4c0e7c4c5
Create Date: 2025-08-31 16:41:07.228960

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '388d40558a76'
down_revision: Union[str, Sequence[str], None] = '85d4c0e7c4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add search cache and stats tables for intelligent query caching."""
    
    # Table pour tracker les statistiques de recherche
    op.execute("""
        CREATE TABLE search_stats (
            query_text VARCHAR(255) PRIMARY KEY,
            search_count INTEGER DEFAULT 1,
            last_searched TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    
    # Index pour optimiser les requêtes de stats
    op.execute("""
        CREATE INDEX idx_search_stats_count_desc 
        ON search_stats(search_count DESC, last_searched DESC)
    """)
    
    # Table pour cache des résultats de recherche
    op.execute("""
        CREATE TABLE search_cache (
            cache_key VARCHAR(100) PRIMARY KEY,
            results_json TEXT NOT NULL,
            search_count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    
    # Index pour nettoyage automatique du cache
    op.execute("""
        CREATE INDEX idx_search_cache_created_at 
        ON search_cache(created_at)
    """)


def downgrade() -> None:
    """Remove search cache and stats tables."""
    op.execute("DROP TABLE IF EXISTS search_cache")
    op.execute("DROP TABLE IF EXISTS search_stats")
    op.execute("DROP INDEX IF EXISTS idx_search_stats_count_desc")
    op.execute("DROP INDEX IF EXISTS idx_search_cache_created_at")
