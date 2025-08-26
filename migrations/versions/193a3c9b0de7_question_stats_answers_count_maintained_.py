"""Question stats: answers_count maintained by triggers

Revision ID: 193a3c9b0de7
Revises: f839a0433a71
Create Date: 2025-08-26 19:25:17.711284

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '193a3c9b0de7'
down_revision: Union[str, Sequence[str], None] = 'f839a0433a71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS question_stats (
            question_id INTEGER PRIMARY KEY REFERENCES questions(id) ON DELETE CASCADE,
            answers_count INTEGER NOT NULL DEFAULT 0
        );
    """)

    op.execute("""
        INSERT INTO question_stats (question_id, answers_count)
        SELECT q.id, COALESCE(a.cnt, 0)::int
        FROM questions q
        LEFT JOIN (
            SELECT question_id, COUNT(*) AS cnt
            FROM answers
            GROUP BY question_id
        ) a ON a.question_id = q.id
        ON CONFLICT (question_id) DO UPDATE
        SET answers_count = EXCLUDED.answers_count;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION trg_answers_inc() RETURNS trigger AS $$
    BEGIN
        INSERT INTO question_stats (question_id, answers_count)
        VALUES (NEW.question_id, 1)
        ON CONFLICT (question_id) DO UPDATE
        SET answers_count = question_stats.answers_count + 1;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION trg_answers_dec() RETURNS trigger AS $$
    BEGIN
        UPDATE question_stats
        SET answers_count = GREATEST(answers_count - 1, 0)
        WHERE question_id = OLD.question_id;
        RETURN OLD;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION trg_answers_upd() RETURNS trigger AS $$
    BEGIN
        IF NEW.question_id <> OLD.question_id THEN
            UPDATE question_stats
            SET answers_count = GREATEST(answers_count - 1, 0)
            WHERE question_id = OLD.question_id;

            INSERT INTO question_stats (question_id, answers_count)
            VALUES (NEW.question_id, 1)
            ON CONFLICT (question_id) DO UPDATE
            SET answers_count = question_stats.answers_count + 1;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trg_answers_after_insert ON answers;
        CREATE TRIGGER trg_answers_after_insert
        AFTER INSERT ON answers
        FOR EACH ROW EXECUTE FUNCTION trg_answers_inc();
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_answers_after_delete ON answers;
        CREATE TRIGGER trg_answers_after_delete
        AFTER DELETE ON answers
        FOR EACH ROW EXECUTE FUNCTION trg_answers_dec();
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_answers_after_update ON answers;
        CREATE TRIGGER trg_answers_after_update
        AFTER UPDATE OF question_id ON answers
        FOR EACH ROW EXECUTE FUNCTION trg_answers_upd();
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_question_stats_question
        ON question_stats(question_id);
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_question_stats_question;")
    op.execute("DROP TRIGGER IF EXISTS trg_answers_after_update ON answers;")
    op.execute("DROP TRIGGER IF EXISTS trg_answers_after_delete ON answers;")
    op.execute("DROP TRIGGER IF EXISTS trg_answers_after_insert ON answers;")
    op.execute("DROP FUNCTION IF EXISTS trg_answers_upd();")
    op.execute("DROP FUNCTION IF EXISTS trg_answers_dec();")
    op.execute("DROP FUNCTION IF EXISTS trg_answers_inc();")
    op.execute("DROP TABLE IF EXISTS question_stats;")
