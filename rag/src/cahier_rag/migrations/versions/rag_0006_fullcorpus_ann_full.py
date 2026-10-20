"""HNSW complet après encodage validé ; aucun index historique modifié."""

from alembic import op
from sqlalchemy import text

revision = "rag_0006"
down_revision = "rag_0005"
branch_labels = None
depends_on = None


def upgrade():
    c = op.get_bind()
    state = c.execute(
        text("SELECT verified FROM rag_full.spaces WHERE space_id='full'")
    ).scalar_one_or_none()
    if state is False:
        raise ValueError("Indexation complète non vérifiée : construction ANN refusée.")
    # Base de test vide : construction sans mémoire exceptionnelle. Sur la vraie
    # base, limite par transaction uniquement, sous réserve du précontrôle RAM.
    if state is True:
        c.execute(text("SET LOCAL maintenance_work_mem='40GB'"))
        c.execute(text("SET LOCAL max_parallel_maintenance_workers=2"))
        c.execute(text("SET LOCAL statement_timeout='2h'"))
        c.execute(text("SET LOCAL lock_timeout='2s'"))
    op.execute(
        "CREATE INDEX IF NOT EXISTS segments_full_hnsw ON rag_full.segments_full "
        "USING hnsw(embedding public.vector_cosine_ops) WITH(m=16,ef_construction=64)"
    )


def downgrade():
    op.execute("DROP INDEX rag_full.segments_full_hnsw")
