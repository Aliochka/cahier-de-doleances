"""create question fts

Revision ID: cd95c6374600
Revises: 860df474248c
Create Date: 2025-08-19 22:08:51.108060

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd95c6374600'
down_revision: Union[str, Sequence[str], None] = '860df474248c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Virtual table FTS5 liée au contenu de questions(rowid=id)
    op.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS question_fts
    USING fts5(
        prompt,
        content='questions',
        content_rowid='id'
    );
    """)

    # Triggers de synchro (INSERT/UPDATE/DELETE)
    op.execute("""
    CREATE TRIGGER IF NOT EXISTS questions_ai AFTER INSERT ON questions BEGIN
        INSERT INTO question_fts(rowid, prompt) VALUES (new.id, new.prompt);
    END;
    """)
    op.execute("""
    CREATE TRIGGER IF NOT EXISTS questions_ad AFTER DELETE ON questions BEGIN
        INSERT INTO question_fts(question_fts, rowid, prompt) VALUES('delete', old.id, old.prompt);
    END;
    """)
    op.execute("""
    CREATE TRIGGER IF NOT EXISTS questions_au AFTER UPDATE ON questions BEGIN
        INSERT INTO question_fts(question_fts, rowid, prompt) VALUES('delete', old.id, old.prompt);
        INSERT INTO question_fts(rowid, prompt) VALUES (new.id, new.prompt);
    END;
    """)

    # (Re)construction initiale
    op.execute("INSERT INTO question_fts(question_fts) VALUES('rebuild');")

def downgrade():
    op.execute("DROP TRIGGER IF EXISTS questions_ai;")
    op.execute("DROP TRIGGER IF EXISTS questions_ad;")
    op.execute("DROP TRIGGER IF EXISTS questions_au;")
    op.execute("DROP TABLE IF EXISTS question_fts;")
