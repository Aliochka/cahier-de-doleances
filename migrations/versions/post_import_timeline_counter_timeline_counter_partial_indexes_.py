"""timeline counter + partial indexes (postgres)

Revision ID: post_import_timeline_counter
Revises: post_import_fts
Create Date: 2025-08-22 18:18:56.413240

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'post_import_timeline_counter'
down_revision: Union[str, Sequence[str], None] = 'post_import_fts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1) Table de stats (1 seule ligne, id=1)
    op.execute("""
        CREATE TABLE IF NOT EXISTS answer_valid_stats (
            id          integer PRIMARY KEY CHECK (id = 1),
            valid_count bigint  NOT NULL DEFAULT 0
        );
    """)
    op.execute("""
        INSERT INTO answer_valid_stats (id, valid_count)
        VALUES (1, 0)
        ON CONFLICT (id) DO NOTHING;
    """)

    # 2) Fonction de trigger (Postgres)
    # valid si: text non NULL et longueur après trim >= 60
    op.execute("""
    CREATE OR REPLACE FUNCTION answers_valid_stats_upd()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE
        old_valid boolean := false;
        new_valid boolean := false;
    BEGIN
        IF TG_OP = 'INSERT' THEN
            new_valid := (NEW.text IS NOT NULL AND char_length(btrim(NEW.text)) >= 60);
            IF new_valid THEN
                UPDATE answer_valid_stats SET valid_count = valid_count + 1 WHERE id = 1;
            END IF;
            RETURN NULL;

        ELSIF TG_OP = 'DELETE' THEN
            old_valid := (OLD.text IS NOT NULL AND char_length(btrim(OLD.text)) >= 60);
            IF old_valid THEN
                UPDATE answer_valid_stats SET valid_count = valid_count - 1 WHERE id = 1;
            END IF;
            RETURN NULL;

        ELSIF TG_OP = 'UPDATE' THEN
            -- on ne s'intéresse qu'aux changements de NEW.text / OLD.text
            old_valid := (OLD.text IS NOT NULL AND char_length(btrim(OLD.text)) >= 60);
            new_valid := (NEW.text IS NOT NULL AND char_length(btrim(NEW.text)) >= 60);

            IF old_valid AND NOT new_valid THEN
                UPDATE answer_valid_stats SET valid_count = valid_count - 1 WHERE id = 1;
            ELSIF NOT old_valid AND new_valid THEN
                UPDATE answer_valid_stats SET valid_count = valid_count + 1 WHERE id = 1;
            END IF;
            RETURN NULL;
        END IF;

        RETURN NULL;
    END;
    $$;
    """)

    # 3) Triggers (une seule fonction pour INSERT/UPDATE/DELETE)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_answers_valid_all ON answers;
        CREATE TRIGGER trg_answers_valid_all
        AFTER INSERT OR UPDATE OF text OR DELETE ON answers
        FOR EACH ROW
        EXECUTE FUNCTION answers_valid_stats_upd();
    """)

    # 4) Backfill initial (une seule fois)
    op.execute("""
        WITH c AS (
            SELECT COUNT(*) AS n
            FROM answers
            WHERE text IS NOT NULL
              AND char_length(btrim(text)) >= 60
        )
        UPDATE answer_valid_stats
        SET valid_count = (SELECT n FROM c)
        WHERE id = 1;
    """)

    # 5) Index partiels utiles
    # -- timeline récente (ORDER BY id DESC) filtrée sur textes valides
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_answers_nonempty_recent
        ON answers (id DESC)
        WHERE text IS NOT NULL AND char_length(btrim(text)) >= 60;
    """)

    # -- aperçus par question: top 3 récents par question
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_answers_qid_id_desc_nonempty
        ON answers (question_id, id DESC)
        WHERE text IS NOT NULL AND char_length(btrim(text)) >= 60;
    """)


def downgrade():
    # Index
    op.execute("DROP INDEX IF EXISTS idx_answers_qid_id_desc_nonempty;")
    op.execute("DROP INDEX IF EXISTS idx_answers_nonempty_recent;")

    # Trigger + function
    op.execute("DROP TRIGGER IF EXISTS trg_answers_valid_all ON answers;")
    op.execute("DROP FUNCTION IF EXISTS answers_valid_stats_upd();")

    # Table de stats
    op.execute("DROP TABLE IF EXISTS answer_valid_stats;")
