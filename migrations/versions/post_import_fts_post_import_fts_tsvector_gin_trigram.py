"""post_import_fts (tsvector + GIN + trigram)

Revision ID: post_import_fts
Revises: post_import_fks_idx
Create Date: 2025-08-22 15:37:49.576957

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'post_import_fts'
down_revision: Union[str, Sequence[str], None] = 'post_import_fks_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    # 1) Extensions nécessaires
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2) Config de recherche 'fr_unaccent' (une seule fois)
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_ts_config WHERE cfgname = 'fr_unaccent'
      ) THEN
        CREATE TEXT SEARCH CONFIGURATION fr_unaccent ( COPY = french );
        ALTER TEXT SEARCH CONFIGURATION fr_unaccent
          ALTER MAPPING FOR hword, hword_part, word
          WITH unaccent, french_stem;
      END IF;
    END
    $$;
    """)

    # 3) Colonnes tsvector GENERATEES (sans appeler unaccent() directement)
    op.execute("""
        ALTER TABLE questions
        ADD COLUMN IF NOT EXISTS prompt_tsv tsvector
        GENERATED ALWAYS AS (
            to_tsvector('fr_unaccent'::regconfig, coalesce(prompt,''))
        ) STORED;
    """)

    op.execute("""
        ALTER TABLE answers
        ADD COLUMN IF NOT EXISTS text_tsv tsvector
        GENERATED ALWAYS AS (
            to_tsvector('fr_unaccent'::regconfig, coalesce(text,''))
        ) STORED;
    """)

    # 4) Index GIN sur ces colonnes
    op.execute("CREATE INDEX IF NOT EXISTS idx_questions_prompt_tsv ON questions USING GIN (prompt_tsv);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_answers_text_tsv   ON answers   USING GIN (text_tsv);")

    # 5) (Optionnel) Fuzzy / 'contient' : trigram sur le texte brut
    op.execute("CREATE INDEX IF NOT EXISTS idx_answers_text_trgm ON answers USING GIN (text gin_trgm_ops);")


def downgrade():
    # Index
    for name in [
        "idx_answers_text_trgm",
        "idx_answers_text_tsv",
        "idx_questions_prompt_tsv",
    ]:
        op.execute(f"DROP INDEX IF EXISTS {name};")

    # Colonnes
    op.execute("ALTER TABLE answers   DROP COLUMN IF EXISTS text_tsv;")
    op.execute("ALTER TABLE questions DROP COLUMN IF EXISTS prompt_tsv;")

    # Optionnel : retirer la config (souvent on la garde)
    # op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS fr_unaccent;")
    # op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
    # op.execute("DROP EXTENSION IF EXISTS unaccent;")
