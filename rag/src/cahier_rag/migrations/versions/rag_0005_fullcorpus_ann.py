"""HNSW cosinus RAG-026, partitions dédiées uniquement ; défauts pgvector documentés."""

from alembic import op

revision = "rag_0005"
down_revision = "rag_0004"
branch_labels = None
depends_on = None


def upgrade():
    # Pilote uniquement, après chargement. Le HNSW complet sera une étape
    # distincte conditionnée aux mesures et à la fin des embeddings complets.
    for name in ("pilot100k",):
        op.execute(
            f"CREATE INDEX segments_{name}_hnsw ON rag_full.segments_{name} "
            "USING hnsw(embedding public.vector_cosine_ops) WITH(m=16,ef_construction=64)"
        )


def downgrade():
    for name in ("pilot100k",):
        op.execute(f"DROP INDEX rag_full.segments_{name}_hnsw")
