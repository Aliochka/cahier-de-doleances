"""init_pg (postgres + bigint ids)

Revision ID: init_pg
Revises: 
Create Date: 2025-08-22 13:56:00.666071

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'init_pg'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # --- authors ---
    op.create_table(
        "authors",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source_author_id", sa.String),
        sa.Column("name", sa.String),
        sa.Column("email_hash", sa.String),
        sa.Column("zipcode", sa.String),
        sa.Column("city", sa.String),
        sa.Column("age_range", sa.String),
        sa.Column("gender", sa.String),
    )

    # --- forms ---
    op.create_table(
        "forms",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("version", sa.String),
        sa.Column("source", sa.String),
    )

    # --- questions ---
    op.create_table(
        "questions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("form_id", sa.BigInteger, nullable=False),
        sa.Column("question_code", sa.String, nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("section", sa.String),
        sa.Column("position", sa.Integer),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("options_json", sa.Text),
    )

    # --- options ---
    op.create_table(
        "options",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("question_id", sa.BigInteger, nullable=False),
        sa.Column("code", sa.String, nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("position", sa.Integer),
        sa.Column("meta_json", sa.Text),
    )

    # --- contributions ---
    op.create_table(
        "contributions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source_contribution_id", sa.String),
        sa.Column("author_id", sa.BigInteger),
        sa.Column("form_id", sa.BigInteger, nullable=False),
        sa.Column("source", sa.String),
        sa.Column("theme_id", sa.BigInteger),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=False)),
        sa.Column("title", sa.String),
        sa.Column("import_batch_id", sa.String),
        sa.Column("raw_hash", sa.String),
        sa.Column("raw_json", sa.Text),
    )

    # --- answers ---
    op.create_table(
        "answers",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("contribution_id", sa.BigInteger, nullable=False),
        sa.Column("question_id", sa.BigInteger, nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("text", sa.Text),
        sa.Column("value_json", sa.Text),
    )

    # --- answer_options (PK composite) ---
    op.create_table(
        "answer_options",
        sa.Column("answer_id", sa.BigInteger, primary_key=True),
        sa.Column("option_id", sa.BigInteger, primary_key=True),
    )

    # --- topics ---
    op.create_table(
        "topics",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("slug", sa.String, nullable=False),
        sa.Column("label", sa.String, nullable=False),
        sa.Column("parent_id", sa.BigInteger),
        sa.Column("depth", sa.Integer),
        sa.Column("sort_order", sa.Integer),
        sa.Column("meta_json", sa.Text),
    )

    # --- topic_aliases ---
    op.create_table(
        "topic_aliases",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("topic_id", sa.BigInteger, nullable=False),
        sa.Column("alias", sa.String, nullable=False),
    )

    # --- contribution_topics (PK composite) ---
    op.create_table(
        "contribution_topics",
        sa.Column("contribution_id", sa.BigInteger, primary_key=True),
        sa.Column("topic_id", sa.BigInteger, primary_key=True),
    )


def downgrade():
    # drop in reverse logical order
    for name in [
        "contribution_topics",
        "topic_aliases",
        "topics",
        "answer_options",
        "answers",
        "contributions",
        "options",
        "questions",
        "forms",
        "authors",
    ]:
        op.execute(f'DROP TABLE IF EXISTS "{name}" CASCADE;')
