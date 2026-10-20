"""Persistent, versioned public statistics and transactional corpus revision."""

from alembic import op

revision = "forms_statistics_v1"
down_revision = "remove_runtime_caches"
branch_labels = None
depends_on = None

SOURCES = (
    "forms",
    "questions",
    "options",
    "answers",
    "answer_options",
    "contributions",
    "question_stats",
)


def upgrade():
    op.execute("""
        CREATE TABLE statistics_source (
            id integer PRIMARY KEY CHECK (id=1),
            corpus_id uuid NOT NULL,
            revision bigint NOT NULL DEFAULT 0,
            published_generation uuid
        );
        INSERT INTO statistics_source(id,corpus_id) VALUES (1,gen_random_uuid());
        CREATE TABLE statistics_generations (
            id uuid PRIMARY KEY,
            corpus_id uuid NOT NULL,
            source_revision bigint NOT NULL,
            method_version text NOT NULL,
            calculated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            question_count integer NOT NULL CHECK(question_count>=0),
            form_count integer NOT NULL CHECK(form_count>=0),
            content_hash text NOT NULL
        );
        CREATE TABLE question_statistics_snapshots (
            generation_id uuid NOT NULL REFERENCES statistics_generations(id) ON DELETE CASCADE,
            question_id bigint NOT NULL,
            form_id bigint NOT NULL,
            answers_count bigint NOT NULL CHECK(answers_count>=0),
            statistics jsonb,
            content_hash text NOT NULL,
            PRIMARY KEY(generation_id,question_id)
        );
        CREATE INDEX question_statistics_form ON question_statistics_snapshots(generation_id,form_id);
        ALTER TABLE statistics_source ADD CONSTRAINT statistics_published_fk
            FOREIGN KEY(published_generation) REFERENCES statistics_generations(id);
        CREATE FUNCTION invalidate_public_statistics() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            UPDATE public.statistics_source SET revision=revision+1 WHERE id=1;
            RETURN NULL;
        END $$;
    """)
    for table in SOURCES:
        op.execute(f"""
            CREATE TRIGGER statistics_source_changed AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE
            ON {table} FOR EACH STATEMENT EXECUTE FUNCTION invalidate_public_statistics()
        """)


def downgrade():
    for table in SOURCES:
        op.execute(f"DROP TRIGGER statistics_source_changed ON {table}")
    op.execute("DROP FUNCTION invalidate_public_statistics()")
    op.execute("ALTER TABLE statistics_source DROP CONSTRAINT statistics_published_fk")
    op.drop_table("question_statistics_snapshots")
    op.drop_table("statistics_generations")
    op.drop_table("statistics_source")
