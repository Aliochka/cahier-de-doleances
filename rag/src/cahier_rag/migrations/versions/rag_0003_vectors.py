"""Espaces denses exacts et checkpoints atomiques, extension locale uniquement."""

from alembic import op
from sqlalchemy import text

revision = "rag_0003"
down_revision = "rag_0002"
branch_labels = None
depends_on = None


def upgrade():
    # env.py a déjà vérifié l'identité physique et l'absence du schéma source.
    connection = op.get_bind()
    if not connection.execute(
        text("SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name='vector')")
    ).scalar_one():
        raise ValueError("pgvector indisponible ; installation système manuelle nécessaire.")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
    namespace = connection.execute(
        text("""
        SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace
        WHERE e.extname='vector'
    """)
    ).scalar_one()
    if namespace != "public":
        raise ValueError("pgvector doit être disponible dans le schéma public.")
    compatible = connection.execute(
        text("""
        SELECT to_regprocedure('public.vector_norm(public.vector)') IS NOT NULL
           AND to_regprocedure('public.cosine_distance(public.vector,public.vector)') IS NOT NULL
    """)
    ).scalar_one()
    if not compatible:
        raise ValueError("Version pgvector incompatible ; fonctions de norme/cosinus requises.")
    op.execute("""CREATE TABLE rag.vector_spaces (
        space_id VARCHAR(64) PRIMARY KEY,
        sample_hash VARCHAR(64) NOT NULL,
        manifest JSONB NOT NULL,
        expected_units INTEGER NOT NULL CHECK(expected_units BETWEEN 1 AND 20000),
        expected_segments INTEGER NOT NULL CHECK(expected_segments > 0),
        completed_units INTEGER NOT NULL DEFAULT 0 CHECK(completed_units >= 0),
        completed_segments INTEGER NOT NULL DEFAULT 0 CHECK(completed_segments >= 0),
        state TEXT NOT NULL DEFAULT 'building' CHECK(state IN ('building','complete')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK(completed_units <= expected_units),
        CHECK(completed_segments <= expected_segments)
    )""")
    op.execute("""CREATE TABLE rag.vector_representations (
        space_id VARCHAR(64) NOT NULL REFERENCES rag.vector_spaces(space_id) ON DELETE CASCADE,
        representation_id TEXT NOT NULL,
        document_id TEXT NOT NULL REFERENCES rag.text_units(document_id),
        source_hash VARCHAR(64) NOT NULL,
        content_hash VARCHAR(64) NOT NULL,
        split TEXT NOT NULL CHECK(split IN ('development','evaluation')),
        segment_index INTEGER NOT NULL CHECK(segment_index >= 0),
        start_offset INTEGER NOT NULL CHECK(start_offset >= 0),
        end_offset INTEGER NOT NULL CHECK(end_offset > start_offset),
        payload JSONB NOT NULL,
        embedding public.vector(1024) NOT NULL,
        vector_hash VARCHAR(64) NOT NULL,
        PRIMARY KEY(space_id, representation_id),
        UNIQUE(space_id, document_id, segment_index),
        CHECK(abs(public.vector_norm(embedding) - 1.0) < 0.0001)
    )""")
    op.execute(
        "CREATE INDEX ix_vector_document ON rag.vector_representations(space_id,document_id)"
    )
    op.execute("CREATE INDEX ix_vector_split ON rag.vector_representations(space_id,split)")


def downgrade():
    op.execute("DROP TABLE rag.vector_representations")
    op.execute("DROP TABLE rag.vector_spaces")
    # Extension potentiellement partagée avec d'autres schémas : ne pas la supprimer.
