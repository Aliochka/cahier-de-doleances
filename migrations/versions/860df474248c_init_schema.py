"""init schema

Revision ID: 860df474248c
Revises: 
Create Date: 2025-08-18 00:33:23.743137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '860df474248c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    # tables de base
    op.create_table("authors",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_author_id", sa.String),
        sa.Column("name", sa.String),
        sa.Column("email_hash", sa.String),
        sa.Column("zipcode", sa.String),
        sa.Column("city", sa.String),
        sa.Column("age_range", sa.String),
        sa.Column("gender", sa.String),
    )
    op.create_table("forms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("version", sa.String),
        sa.Column("source", sa.String),
    )
    op.create_table("questions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("form_id", sa.Integer, sa.ForeignKey("forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_code", sa.String, nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("section", sa.String),
        sa.Column("position", sa.Integer),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("options_json", sa.Text),
        sa.UniqueConstraint("form_id", "question_code"),
    )
    op.create_table("options",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String, nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("position", sa.Integer),
        sa.Column("meta_json", sa.Text),
        sa.UniqueConstraint("question_id", "code"),
    )
    op.create_table("contributions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_contribution_id", sa.String),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("authors.id")),
        sa.Column("form_id", sa.Integer, sa.ForeignKey("forms.id"), nullable=False),
        sa.Column("source", sa.String),
        sa.Column("theme_id", sa.Integer),
        sa.Column("submitted_at", sa.String),
        sa.Column("title", sa.String),
        sa.Column("import_batch_id", sa.String),
        sa.Column("raw_hash", sa.String),
        sa.Column("raw_json", sa.Text),
    )
    op.create_table("answers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("contribution_id", sa.Integer, sa.ForeignKey("contributions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="1"),
        sa.Column("text", sa.Text),
        sa.Column("value_json", sa.Text),
        sa.UniqueConstraint("contribution_id", "question_id", "position"),
    )
    op.create_table("answer_options",
        sa.Column("answer_id", sa.Integer, sa.ForeignKey("answers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("option_id", sa.Integer, sa.ForeignKey("options.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table("topics",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String, unique=True, nullable=False),
        sa.Column("label", sa.String, nullable=False),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("topics.id", ondelete="CASCADE")),
        sa.Column("depth", sa.Integer),
        sa.Column("sort_order", sa.Integer),
        sa.Column("meta_json", sa.Text),
    )
    op.create_table("topic_aliases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("topic_id", sa.Integer, sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String, nullable=False),
        sa.UniqueConstraint("topic_id", "alias"),
    )
    op.create_table("contribution_topics",
        sa.Column("contribution_id", sa.Integer, sa.ForeignKey("contributions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("topic_id", sa.Integer, sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
    )

    # Index utiles
    op.create_index("idx_contrib_author", "contributions", ["author_id"])
    op.create_index("idx_answers_qid", "answers", ["question_id"])
    op.create_index("idx_answers_contrib", "answers", ["contribution_id"])
    op.create_index("idx_ct_topic", "contribution_topics", ["topic_id"])

    # FTS5 (table virtuelle + triggers)
    op.execute("""
        CREATE VIRTUAL TABLE answers_fts USING fts5(
          text,
          content='answers',
          content_rowid='id',
          tokenize='unicode61 remove_diacritics 2'
        );
    """)
    op.execute("""
        CREATE TRIGGER answers_ai AFTER INSERT ON answers BEGIN
          INSERT INTO answers_fts(rowid, text) VALUES (new.id, new.text);
        END;
    """)
    op.execute("""
        CREATE TRIGGER answers_ad AFTER DELETE ON answers BEGIN
          INSERT INTO answers_fts(answers_fts, rowid, text) VALUES ('delete', old.id, old.text);
        END;
    """)
    op.execute("""
        CREATE TRIGGER answers_au AFTER UPDATE ON answers BEGIN
          INSERT INTO answers_fts(answers_fts, rowid, text) VALUES ('delete', old.id, old.text);
          INSERT INTO answers_fts(rowid, text) VALUES (new.id, new.text);
        END;
    """)

def downgrade():
    op.execute("DROP TRIGGER IF EXISTS answers_au;")
    op.execute("DROP TRIGGER IF EXISTS answers_ad;")
    op.execute("DROP TRIGGER IF EXISTS answers_ai;")
    op.execute("DROP TABLE IF EXISTS answers_fts;")
    for t in ["contribution_topics","topic_aliases","topics","answer_options","answers","contributions","options","questions","forms","authors"]:
        op.execute(f"DROP TABLE IF EXISTS {t};")
