"""Search infra: extensions, FTS (tsvector), trigram, and core indexes

Revision ID: f839a0433a71
Revises: f9a8ff4a78dd
Create Date: 2025-08-26 19:24:07.111149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f839a0433a71'
down_revision: Union[str, Sequence[str], None] = 'f9a8ff4a78dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    # Extensions (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 1) Colonnes matérialisées pour FORMS
    op.add_column("forms", sa.Column("name_unaccent", sa.Text(), nullable=True))
    op.add_column("forms", sa.Column("tsv_name", sa.TEXT(), nullable=True))  # will store tsvector

    # 2) Colonnes matérialisées pour QUESTIONS
    op.add_column("questions", sa.Column("prompt_unaccent", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("tsv_prompt", sa.TEXT(), nullable=True))  # will store tsvector

    # 3) Backfill initial (idempotent)
    op.execute("""
        UPDATE forms
        SET name_unaccent = unaccent(COALESCE(name, '')),
            tsv_name = to_tsvector('french', unaccent(COALESCE(name, '')));
    """)
    op.execute("""
        UPDATE questions
        SET prompt_unaccent = unaccent(COALESCE(prompt, '')),
            tsv_prompt = to_tsvector('french', unaccent(COALESCE(prompt, '')));
    """)

    # 4) Fonctions TRIGGER pour maintenir les colonnes
    op.execute("""
    CREATE OR REPLACE FUNCTION trg_forms_update_search() RETURNS trigger AS $$
    BEGIN
        NEW.name_unaccent := unaccent(COALESCE(NEW.name, ''));
        NEW.tsv_name := to_tsvector('french', NEW.name_unaccent);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION trg_questions_update_search() RETURNS trigger AS $$
    BEGIN
        NEW.prompt_unaccent := unaccent(COALESCE(NEW.prompt, ''));
        NEW.tsv_prompt := to_tsvector('french', NEW.prompt_unaccent);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    # 5) Triggers ON INSERT/UPDATE
    op.execute("""
        DROP TRIGGER IF EXISTS trg_forms_update_search_row ON forms;
        CREATE TRIGGER trg_forms_update_search_row
        BEFORE INSERT OR UPDATE OF name ON forms
        FOR EACH ROW EXECUTE FUNCTION trg_forms_update_search();
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_questions_update_search_row ON questions;
        CREATE TRIGGER trg_questions_update_search_row
        BEFORE INSERT OR UPDATE OF prompt ON questions
        FOR EACH ROW EXECUTE FUNCTION trg_questions_update_search();
    """)

    # 6) Index (GIN sur tsv, trigram sur _unaccent)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_forms_tsv_name
        ON forms USING GIN ((tsv_name::tsvector));
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_forms_name_unaccent_trgm
        ON forms USING GIN (name_unaccent gin_trgm_ops);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_questions_tsv_prompt
        ON questions USING GIN ((tsv_prompt::tsvector));
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_questions_prompt_unaccent_trgm
        ON questions USING GIN (prompt_unaccent gin_trgm_ops);
    """)

    # 7) Index de perf annexes (ordre, jointures, navigation)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_questions_form_position
        ON questions(form_id, position);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_answers_question
        ON answers(question_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_answers_contribution_question
        ON answers(contribution_id, question_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_contributions_form_submit_id
        ON contributions(form_id, submitted_at, id);
    """)


def downgrade():
    # Drop perf indexes
    op.execute("DROP INDEX IF EXISTS ix_contributions_form_submit_id;")
    op.execute("DROP INDEX IF EXISTS ix_answers_contribution_question;")
    op.execute("DROP INDEX IF EXISTS ix_answers_question;")
    op.execute("DROP INDEX IF EXISTS ix_questions_form_position;")

    # Drop search indexes
    op.execute("DROP INDEX IF EXISTS ix_questions_prompt_unaccent_trgm;")
    op.execute("DROP INDEX IF EXISTS ix_questions_tsv_prompt;")
    op.execute("DROP INDEX IF EXISTS ix_forms_name_unaccent_trgm;")
    op.execute("DROP INDEX IF EXISTS ix_forms_tsv_name;")

    # Drop triggers & functions
    op.execute("DROP TRIGGER IF EXISTS trg_questions_update_search_row ON questions;")
    op.execute("DROP FUNCTION IF EXISTS trg_questions_update_search();")
    op.execute("DROP TRIGGER IF EXISTS trg_forms_update_search_row ON forms;")
    op.execute("DROP FUNCTION IF EXISTS trg_forms_update_search();")

    # Drop columns
    op.execute("ALTER TABLE questions DROP COLUMN IF EXISTS tsv_prompt;")
    op.execute("ALTER TABLE questions DROP COLUMN IF EXISTS prompt_unaccent;")
    op.execute("ALTER TABLE forms DROP COLUMN IF EXISTS tsv_name;")
    op.execute("ALTER TABLE forms DROP COLUMN IF EXISTS name_unaccent;")

    # (On laisse les extensions en place)
