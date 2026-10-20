"""RAG-027 : statistiques de lexèmes indépendantes, aucune modification d'index existant."""

from alembic import op

revision = "rag_0007"
down_revision = "rag_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA rag_tuning")
    op.execute("""CREATE TABLE rag_tuning.statistics (
        space_id text PRIMARY KEY REFERENCES rag_full.spaces(space_id),
        corpus_hash text NOT NULL, documents bigint NOT NULL CHECK(documents>0),
        lexemes bigint NOT NULL, version int NOT NULL CHECK(version=1),
        created_at timestamptz NOT NULL DEFAULT now())""")
    op.execute("""CREATE TABLE rag_tuning.term_statistics (
        space_id text NOT NULL REFERENCES rag_tuning.statistics(space_id),term text NOT NULL,
        documents bigint NOT NULL CHECK(documents>0),PRIMARY KEY(space_id,term))""")


def downgrade():
    op.execute("DROP TABLE rag_tuning.term_statistics")
    op.execute("DROP TABLE rag_tuning.statistics")
    op.execute("DROP SCHEMA rag_tuning")
