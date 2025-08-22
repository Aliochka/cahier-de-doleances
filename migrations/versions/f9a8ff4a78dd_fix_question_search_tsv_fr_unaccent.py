"""fix question search tsv fr unaccent

Revision ID: f9a8ff4a78dd
Revises: post_import_timeline_counter
Create Date: 2025-08-22 19:57:46.526001

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f9a8ff4a78dd'
down_revision: Union[str, Sequence[str], None] = 'post_import_timeline_counter'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 0) config fr_unaccent (idempotent)
    op.execute("""
    CREATE EXTENSION IF NOT EXISTS unaccent;
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname='fr_unaccent') THEN
        CREATE TEXT SEARCH CONFIGURATION fr_unaccent ( COPY = french );
        ALTER TEXT SEARCH CONFIGURATION fr_unaccent
          ALTER MAPPING FOR hword, hword_part, word WITH unaccent, french_stem;
      END IF;
    END$$;
    """)

    # 1) drop l’index (si existant)
    op.execute("DROP INDEX IF EXISTS idx_questions_prompt_tsv;")

    # 2) remplace la colonne générée
    op.execute("ALTER TABLE questions DROP COLUMN IF EXISTS prompt_tsv;")
    op.execute("""
      ALTER TABLE questions
      ADD COLUMN prompt_tsv tsvector
      GENERATED ALWAYS AS ( to_tsvector('fr_unaccent', COALESCE(prompt,'')) ) STORED;
    """)

    # 3) index CONCURRENTLY (autocommit)
    with op.get_context().autocommit_block():
        op.execute("""
          CREATE INDEX CONCURRENTLY idx_questions_prompt_tsv
          ON questions USING GIN (prompt_tsv);
        """)

def downgrade():
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX IF EXISTS idx_questions_prompt_tsv;")
    op.execute("ALTER TABLE questions DROP COLUMN IF EXISTS prompt_tsv;")
