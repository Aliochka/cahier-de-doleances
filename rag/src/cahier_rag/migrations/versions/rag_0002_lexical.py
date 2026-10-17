"""Index lexical dérivé, limité à des manifestes explicites ; schéma figé."""

from alembic import op

revision = "rag_0002"
down_revision = "rag_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE rag.lexical_corpora (
        sample_hash VARCHAR(64) PRIMARY KEY,
        document_count INTEGER NOT NULL,
        configuration JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT lexical_bounded_size CHECK (document_count > 0 AND document_count <= 20000)
    )""")
    op.execute("""CREATE TABLE rag.lexical_members (
        sample_hash VARCHAR(64) NOT NULL REFERENCES rag.lexical_corpora(sample_hash) ON DELETE CASCADE,
        document_id TEXT NOT NULL REFERENCES rag.text_units(document_id),
        content_hash VARCHAR(64) NOT NULL,
        split VARCHAR(16) NOT NULL,
        PRIMARY KEY (sample_hash,document_id),
        CONSTRAINT lexical_known_split CHECK (split IN ('development','evaluation'))
    )""")
    op.execute("""CREATE TABLE rag.lexical_vectors (
        sample_hash VARCHAR(64) NOT NULL,
        strategy VARCHAR(32) NOT NULL,
        document_id TEXT NOT NULL,
        search_vector TSVECTOR NOT NULL,
        PRIMARY KEY (sample_hash,strategy,document_id),
        FOREIGN KEY (sample_hash,document_id) REFERENCES rag.lexical_members(sample_hash,document_id) ON DELETE CASCADE,
        CONSTRAINT lexical_known_strategy CHECK (strategy IN ('answer','question','title'))
    )""")
    op.execute(
        "CREATE INDEX ix_rag_lexical_vector_gin ON rag.lexical_vectors USING gin(search_vector)"
    )


def downgrade():
    op.execute("DROP TABLE rag.lexical_vectors")
    op.execute("DROP TABLE rag.lexical_members")
    op.execute("DROP TABLE rag.lexical_corpora")
