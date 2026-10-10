"""Remove retired search and dashboard caches and query popularity tracking."""

from alembic import op

revision = "remove_runtime_caches"
down_revision = "gdn_bulk_counters"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("search_cache")
    op.drop_table("search_stats")
    op.drop_table("dashboard_cache")


def downgrade():
    op.execute("""
        CREATE TABLE dashboard_cache (
            form_id INTEGER PRIMARY KEY, stats_json TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX idx_dashboard_cache_updated_at ON dashboard_cache(updated_at);
        CREATE TABLE search_stats (
            query_text VARCHAR(255) PRIMARY KEY, search_count INTEGER DEFAULT 1,
            last_searched TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX idx_search_stats_count_desc ON search_stats(search_count DESC,last_searched DESC);
        CREATE TABLE search_cache (
            cache_key VARCHAR(100) PRIMARY KEY, results_json TEXT NOT NULL,
            search_count INTEGER DEFAULT 0, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX idx_search_cache_created_at ON search_cache(created_at);
    """)
