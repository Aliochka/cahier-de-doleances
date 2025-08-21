"""add incremental counter and index for answers timeline

Revision ID: 03de7138a7d6
Revises: 2719d33cf3a4
Create Date: 2025-08-22 00:47:26.340030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03de7138a7d6'
down_revision: Union[str, Sequence[str], None] = '2719d33cf3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Table de stats (1 seule ligne)
    op.execute("""
        CREATE TABLE IF NOT EXISTS answer_valid_stats (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            valid_count INTEGER NOT NULL DEFAULT 0
        );
    """)
    # Seed si vide
    op.execute("""
        INSERT INTO answer_valid_stats (id, valid_count)
        SELECT 1, 0
        WHERE NOT EXISTS (SELECT 1 FROM answer_valid_stats WHERE id = 1);
    """)

    # 2) Fonction de validité (inline via CASE dans triggers)
    # valid = text IS NOT NULL AND trim(text) <> '' AND length(text) >= 60

    # 3) Triggers INSERT / UPDATE / DELETE
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_answers_valid_ins
        AFTER INSERT ON answers
        WHEN NEW.text IS NOT NULL AND length(trim(NEW.text)) > 0 AND length(NEW.text) >= 60
        BEGIN
            UPDATE answer_valid_stats SET valid_count = valid_count + 1 WHERE id = 1;
        END;
    """)

    op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_answers_valid_del
        AFTER DELETE ON answers
        WHEN OLD.text IS NOT NULL AND length(trim(OLD.text)) > 0 AND length(OLD.text) >= 60
        BEGIN
            UPDATE answer_valid_stats SET valid_count = valid_count - 1 WHERE id = 1;
        END;
    """)

    # UPDATE : comparer ancien et nouveau état de validité
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_answers_valid_upd
        AFTER UPDATE OF text ON answers
        BEGIN
            -- OLD valide et NEW non valide => -1
            UPDATE answer_valid_stats
            SET valid_count = valid_count - 1
            WHERE id = 1
              AND (OLD.text IS NOT NULL AND length(trim(OLD.text)) > 0 AND length(OLD.text) >= 60)
              AND NOT (NEW.text IS NOT NULL AND length(trim(NEW.text)) > 0 AND length(NEW.text) >= 60);

            -- OLD non valide et NEW valide => +1
            UPDATE answer_valid_stats
            SET valid_count = valid_count + 1
            WHERE id = 1
              AND NOT (OLD.text IS NOT NULL AND length(trim(OLD.text)) > 0 AND length(OLD.text) >= 60)
              AND (NEW.text IS NOT NULL AND length(trim(NEW.text)) > 0 AND length(NEW.text) >= 60);
        END;
    """)

    # 4) Backfill initial (une seule fois)
    op.execute("""
        WITH c AS (
            SELECT COUNT(*) AS n
            FROM answers
            WHERE text IS NOT NULL
              AND length(trim(text)) > 0
              AND length(text) >= 60
        )
        UPDATE answer_valid_stats
        SET valid_count = (SELECT n FROM c)
        WHERE id = 1;
    """)

    # 5) Index (rappel) pour ORDER BY + scans rapides
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_answers_nonempty_recent
        ON answers(id DESC)
        WHERE text IS NOT NULL AND length(text) >= 60 AND length(trim(text)) > 0;
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_answers_question_id ON answers(question_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_answers_contribution_id ON answers(contribution_id);")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_answers_valid_upd;")
    op.execute("DROP TRIGGER IF EXISTS trg_answers_valid_del;")
    op.execute("DROP TRIGGER IF EXISTS trg_answers_valid_ins;")
    op.execute("DROP TABLE IF EXISTS answer_valid_stats;")
    # on peut laisser les index en place, sinon :
    op.execute("DROP INDEX IF EXISTS idx_answers_contribution_id;")
    op.execute("DROP INDEX IF EXISTS idx_answers_question_id;")
    op.execute("DROP INDEX IF EXISTS idx_answers_nonempty_recent;")
