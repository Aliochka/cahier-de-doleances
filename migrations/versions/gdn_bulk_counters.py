"""Maintain answer counters per SQL statement for efficient bulk imports."""
from alembic import op

revision = "gdn_bulk_counters"
down_revision = "gdn_import_progress"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("trg_answers_after_insert", "trg_answers_after_delete", "trg_answers_after_update", "trg_answers_valid_all"):
        op.execute(f"DROP TRIGGER IF EXISTS {name} ON answers")
    op.execute("""
        CREATE FUNCTION gdn_answer_stats_insert() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE delta bigint;
        BEGIN
            INSERT INTO question_stats(question_id,answers_count)
            SELECT question_id,count(*)::int FROM gdn_new_answers GROUP BY question_id
            ON CONFLICT(question_id) DO UPDATE
              SET answers_count=question_stats.answers_count+EXCLUDED.answers_count;
            SELECT count(*) INTO delta FROM gdn_new_answers
              WHERE text IS NOT NULL AND char_length(btrim(text))>=60;
            IF delta<>0 THEN
                UPDATE answer_valid_stats SET valid_count=valid_count+delta WHERE id=1;
            END IF;
            RETURN NULL;
        END $$;
        CREATE FUNCTION gdn_answer_stats_delete() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE delta bigint;
        BEGIN
            UPDATE question_stats s SET answers_count=GREATEST(0,s.answers_count-d.n)
            FROM (SELECT question_id,count(*)::int n FROM gdn_old_answers GROUP BY question_id) d
            WHERE s.question_id=d.question_id;
            SELECT count(*) INTO delta FROM gdn_old_answers
              WHERE text IS NOT NULL AND char_length(btrim(text))>=60;
            IF delta<>0 THEN
                UPDATE answer_valid_stats SET valid_count=valid_count-delta WHERE id=1;
            END IF;
            RETURN NULL;
        END $$;
        CREATE FUNCTION gdn_answer_stats_update() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE delta bigint;
        BEGIN
            WITH changes AS (
                SELECT question_id,count(*)::int n FROM gdn_new_answers GROUP BY question_id
                UNION ALL
                SELECT question_id,-count(*)::int n FROM gdn_old_answers GROUP BY question_id
            ), differences AS (
                SELECT question_id,sum(n)::int n FROM changes GROUP BY question_id HAVING sum(n)<>0
            )
            INSERT INTO question_stats(question_id,answers_count)
            SELECT question_id,n FROM differences
            ON CONFLICT(question_id) DO UPDATE
              SET answers_count=GREATEST(0,question_stats.answers_count+EXCLUDED.answers_count);
            SELECT
                (SELECT count(*) FROM gdn_new_answers WHERE text IS NOT NULL AND char_length(btrim(text))>=60)
                - (SELECT count(*) FROM gdn_old_answers WHERE text IS NOT NULL AND char_length(btrim(text))>=60)
            INTO delta;
            IF delta<>0 THEN
                UPDATE answer_valid_stats SET valid_count=valid_count+delta WHERE id=1;
            END IF;
            RETURN NULL;
        END $$;
        CREATE TRIGGER gdn_stats_insert AFTER INSERT ON answers
          REFERENCING NEW TABLE AS gdn_new_answers FOR EACH STATEMENT EXECUTE FUNCTION gdn_answer_stats_insert();
        CREATE TRIGGER gdn_stats_delete AFTER DELETE ON answers
          REFERENCING OLD TABLE AS gdn_old_answers FOR EACH STATEMENT EXECUTE FUNCTION gdn_answer_stats_delete();
        CREATE TRIGGER gdn_stats_update AFTER UPDATE ON answers
          REFERENCING OLD TABLE AS gdn_old_answers NEW TABLE AS gdn_new_answers
          FOR EACH STATEMENT EXECUTE FUNCTION gdn_answer_stats_update();
    """)


def downgrade():
    for name in ("insert", "delete", "update"):
        op.execute(f"DROP TRIGGER gdn_stats_{name} ON answers")
        op.execute(f"DROP FUNCTION gdn_answer_stats_{name}()")
    op.execute("""
        CREATE TRIGGER trg_answers_after_insert AFTER INSERT ON answers
          FOR EACH ROW EXECUTE FUNCTION trg_answers_inc();
        CREATE TRIGGER trg_answers_after_delete AFTER DELETE ON answers
          FOR EACH ROW EXECUTE FUNCTION trg_answers_dec();
        CREATE TRIGGER trg_answers_after_update AFTER UPDATE OF question_id ON answers
          FOR EACH ROW EXECUTE FUNCTION trg_answers_upd();
        CREATE TRIGGER trg_answers_valid_all AFTER INSERT OR DELETE OR UPDATE OF text ON answers
          FOR EACH ROW EXECUTE FUNCTION answers_valid_stats_upd();
    """)
