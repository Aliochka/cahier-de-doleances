"""RAG-026 : espace dédié, sans modification des tables expérimentales."""

from alembic import op

revision = "rag_0004"
down_revision = "rag_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA rag_full")
    op.execute("""CREATE TABLE rag_full.spaces (
        space_id text PRIMARY KEY CHECK(space_id IN ('pilot100k','full')),
        manifest jsonb NOT NULL, recipe_hash text NOT NULL,
        expected_units bigint NOT NULL CHECK(expected_units>0),
        documents bigint NOT NULL DEFAULT 0, segments bigint NOT NULL DEFAULT 0,
        cursor jsonb, vector_cursor bigint NOT NULL DEFAULT 0,
        chain_hash text NOT NULL DEFAULT '',
        extraction_complete boolean NOT NULL DEFAULT false,
        vectors_complete boolean NOT NULL DEFAULT false,
        verified boolean NOT NULL DEFAULT false,
        updated_at timestamptz NOT NULL DEFAULT now())""")
    op.execute("""CREATE TABLE rag_full.documents (
        space_id text NOT NULL REFERENCES rag_full.spaces(space_id),
        document_id text NOT NULL, ordinal bigint NOT NULL CHECK(ordinal>0),
        answer_id bigint NOT NULL CHECK(answer_id>0),
        contribution_id bigint NOT NULL CHECK(contribution_id>0),
        questionnaire_id bigint NOT NULL CHECK(questionnaire_id>0),
        unit_type text NOT NULL CHECK(unit_type IN ('open_answer','other_text')),
        content_hash text NOT NULL, record jsonb NOT NULL,
        search_vector tsvector NOT NULL,
        historical_split text CHECK(historical_split IN ('development','evaluation')),
        PRIMARY KEY(space_id,document_id), UNIQUE(space_id,ordinal))
        PARTITION BY LIST(space_id)""")
    op.execute("""CREATE TABLE rag_full.segments (
        space_id text NOT NULL, document_id text NOT NULL,
        segment_index int NOT NULL CHECK(segment_index>=0), representation_id text NOT NULL,
        start_offset int NOT NULL CHECK(start_offset>=0), end_offset int NOT NULL,
        tokens int NOT NULL CHECK(tokens BETWEEN 1 AND 1024),
        content_hash text NOT NULL, vector_hash text NOT NULL,
        embedding public.vector(1024) NOT NULL,
        PRIMARY KEY(space_id,document_id,segment_index),
        UNIQUE(space_id,representation_id),
        FOREIGN KEY(space_id,document_id) REFERENCES rag_full.documents(space_id,document_id),
        CHECK(end_offset>start_offset),
        CHECK(abs(public.vector_norm(embedding)-1.0)<0.0001)) PARTITION BY LIST(space_id)""")
    for name in ("pilot100k", "full"):
        # Fixed identifiers only; never interpolated from user input.
        op.execute(
            f"CREATE TABLE rag_full.documents_{name} PARTITION OF rag_full.documents "
            f"FOR VALUES IN ('{name}')"
        )
        op.execute(
            f"CREATE TABLE rag_full.segments_{name} PARTITION OF rag_full.segments "
            f"FOR VALUES IN ('{name}')"
        )
    op.execute("CREATE INDEX full_lexical_gin ON rag_full.documents USING gin(search_vector)")
    op.execute(
        "CREATE INDEX full_documents_form ON rag_full.documents(space_id,questionnaire_id,unit_type)"
    )
    op.execute("CREATE INDEX full_documents_parent ON rag_full.documents(space_id,contribution_id)")


def downgrade():
    # Pas de CASCADE : aucune suppression implicite de données dépendantes.
    op.execute("DROP TABLE rag_full.segments")
    op.execute("DROP TABLE rag_full.documents")
    op.execute("DROP TABLE rag_full.spaces")
    op.execute("DROP SCHEMA rag_full")
