"""post_import_fks_idx

Revision ID: post_import_fks_idx
Revises: init_pg
Create Date: 2025-08-22 14:37:35.213550

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'post_import_fks_idx'
down_revision: Union[str, Sequence[str], None] = 'init_pg'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # -----------------------
    # 1) Uniques & indexes
    # -----------------------
    # authors
    op.create_unique_constraint("uq_authors_email_hash", "authors", ["email_hash"])
    op.create_unique_constraint("uq_authors_source_author_id", "authors", ["source_author_id"])

    # questions
    op.create_unique_constraint("uq_questions_form_code", "questions", ["form_id", "question_code"])
    op.create_index("idx_questions_form_id", "questions", ["form_id"])

    # options
    op.create_unique_constraint("uq_options_qid_code", "options", ["question_id", "code"])
    op.create_index("idx_options_question_id", "options", ["question_id"])

    # contributions
    op.create_unique_constraint("uq_contributions_source_id", "contributions", ["source_contribution_id"])
    op.create_unique_constraint("uq_contributions_raw_hash", "contributions", ["raw_hash"])
    op.create_index("idx_contrib_author_id", "contributions", ["author_id"])
    op.create_index("idx_contrib_form_id", "contributions", ["form_id"])

    # answers
    op.create_unique_constraint(
        "uq_answers_cid_qid_pos", "answers", ["contribution_id", "question_id", "position"]
    )
    op.create_index("idx_answers_contribution_id", "answers", ["contribution_id"])
    op.create_index("idx_answers_question_id", "answers", ["question_id"])

    # answer_options
    op.create_index("idx_answer_options_option_id", "answer_options", ["option_id"])

    # topics
    op.create_unique_constraint("uq_topics_slug", "topics", ["slug"])
    op.create_index("idx_topics_parent_id", "topics", ["parent_id"])

    # topic_aliases
    op.create_unique_constraint("uq_topic_aliases_tid_alias", "topic_aliases", ["topic_id", "alias"])
    op.create_index("idx_topic_aliases_topic_id", "topic_aliases", ["topic_id"])

    # contribution_topics
    op.create_index("idx_ct_topic_id", "contribution_topics", ["topic_id"])

    # -----------------------------------------
    # 2) Foreign keys (NOT VALID -> VALIDATE)
    # -----------------------------------------
    stmts = [
        # questions → forms
        "ALTER TABLE questions ADD CONSTRAINT fk_questions_form_id "
        "FOREIGN KEY (form_id) REFERENCES forms(id) ON DELETE CASCADE NOT VALID;",

        # options → questions
        "ALTER TABLE options ADD CONSTRAINT fk_options_question_id "
        "FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE NOT VALID;",

        # contributions → authors (nullable)
        "ALTER TABLE contributions ADD CONSTRAINT fk_contributions_author_id "
        "FOREIGN KEY (author_id) REFERENCES authors(id) NOT VALID;",

        # contributions → forms
        "ALTER TABLE contributions ADD CONSTRAINT fk_contributions_form_id "
        "FOREIGN KEY (form_id) REFERENCES forms(id) NOT VALID;",

        # answers → contributions
        "ALTER TABLE answers ADD CONSTRAINT fk_answers_contribution_id "
        "FOREIGN KEY (contribution_id) REFERENCES contributions(id) ON DELETE CASCADE NOT VALID;",

        # answers → questions
        "ALTER TABLE answers ADD CONSTRAINT fk_answers_question_id "
        "FOREIGN KEY (question_id) REFERENCES questions(id) NOT VALID;",

        # answer_options → answers
        "ALTER TABLE answer_options ADD CONSTRAINT fk_answer_options_answer_id "
        "FOREIGN KEY (answer_id) REFERENCES answers(id) ON DELETE CASCADE NOT VALID;",

        # answer_options → options
        "ALTER TABLE answer_options ADD CONSTRAINT fk_answer_options_option_id "
        "FOREIGN KEY (option_id) REFERENCES options(id) ON DELETE CASCADE NOT VALID;",

        # topics(parent_id) → topics(id)
        "ALTER TABLE topics ADD CONSTRAINT fk_topics_parent_id "
        "FOREIGN KEY (parent_id) REFERENCES topics(id) ON DELETE CASCADE NOT VALID;",

        # topic_aliases → topics
        "ALTER TABLE topic_aliases ADD CONSTRAINT fk_topic_aliases_topic_id "
        "FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE NOT VALID;",

        # contribution_topics → contributions
        "ALTER TABLE contribution_topics ADD CONSTRAINT fk_contribution_topics_contribution_id "
        "FOREIGN KEY (contribution_id) REFERENCES contributions(id) ON DELETE CASCADE NOT VALID;",

        # contribution_topics → topics
        "ALTER TABLE contribution_topics ADD CONSTRAINT fk_contribution_topics_topic_id "
        "FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE NOT VALID;",
    ]
    for s in stmts:
        op.execute(s)

    validates = [
        "ALTER TABLE questions           VALIDATE CONSTRAINT fk_questions_form_id;",
        "ALTER TABLE options             VALIDATE CONSTRAINT fk_options_question_id;",
        "ALTER TABLE contributions       VALIDATE CONSTRAINT fk_contributions_author_id;",
        "ALTER TABLE contributions       VALIDATE CONSTRAINT fk_contributions_form_id;",
        "ALTER TABLE answers             VALIDATE CONSTRAINT fk_answers_contribution_id;",
        "ALTER TABLE answers             VALIDATE CONSTRAINT fk_answers_question_id;",
        "ALTER TABLE answer_options      VALIDATE CONSTRAINT fk_answer_options_answer_id;",
        "ALTER TABLE answer_options      VALIDATE CONSTRAINT fk_answer_options_option_id;",
        "ALTER TABLE topics              VALIDATE CONSTRAINT fk_topics_parent_id;",
        "ALTER TABLE topic_aliases       VALIDATE CONSTRAINT fk_topic_aliases_topic_id;",
        "ALTER TABLE contribution_topics VALIDATE CONSTRAINT fk_contribution_topics_contribution_id;",
        "ALTER TABLE contribution_topics VALIDATE CONSTRAINT fk_contribution_topics_topic_id;",
    ]
    for v in validates:
        op.execute(v)


def downgrade():
    drops = [
        "ALTER TABLE contribution_topics DROP CONSTRAINT IF EXISTS fk_contribution_topics_topic_id;",
        "ALTER TABLE contribution_topics DROP CONSTRAINT IF EXISTS fk_contribution_topics_contribution_id;",
        "ALTER TABLE topic_aliases       DROP CONSTRAINT IF EXISTS fk_topic_aliases_topic_id;",
        "ALTER TABLE topics              DROP CONSTRAINT IF EXISTS fk_topics_parent_id;",
        "ALTER TABLE answer_options      DROP CONSTRAINT IF EXISTS fk_answer_options_option_id;",
        "ALTER TABLE answer_options      DROP CONSTRAINT IF EXISTS fk_answer_options_answer_id;",
        "ALTER TABLE answers             DROP CONSTRAINT IF EXISTS fk_answers_question_id;",
        "ALTER TABLE answers             DROP CONSTRAINT IF EXISTS fk_answers_contribution_id;",
        "ALTER TABLE contributions       DROP CONSTRAINT IF EXISTS fk_contributions_form_id;",
        "ALTER TABLE contributions       DROP CONSTRAINT IF EXISTS fk_contributions_author_id;",
        "ALTER TABLE options             DROP CONSTRAINT IF EXISTS fk_options_question_id;",
        "ALTER TABLE questions           DROP CONSTRAINT IF EXISTS fk_questions_form_id;",
    ]
    for d in drops:
        op.execute(d)

    for name in [
        "idx_ct_topic_id",
        "idx_topic_aliases_topic_id",
        "idx_topics_parent_id",
        "idx_answer_options_option_id",
        "idx_answers_question_id",
        "idx_answers_contribution_id",
        "idx_contrib_form_id",
        "idx_contrib_author_id",
        "idx_options_question_id",
        "idx_questions_form_id",
    ]:
        op.drop_index(name, table_name=None)

    for tbl, name in [
        ("topic_aliases", "uq_topic_aliases_tid_alias"),
        ("topics", "uq_topics_slug"),
        ("answers", "uq_answers_cid_qid_pos"),
        ("contributions", "uq_contributions_raw_hash"),
        ("contributions", "uq_contributions_source_id"),
        ("options", "uq_options_qid_code"),
        ("questions", "uq_questions_form_code"),
        ("authors", "uq_authors_source_author_id"),
        ("authors", "uq_authors_email_hash"),
    ]:
        op.drop_constraint(name, tbl, type_="unique")
