"""Schéma documentaire v1 figé : aucune dépendance au modèle courant."""

from alembic import op
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData(schema="rag")

units = Table(
    "text_units",
    metadata,
    Column("document_id", Text, primary_key=True),
    Column("corpus_id", Text, nullable=False),
    Column("unit_type", String(32), nullable=False),
    Column("answer_id", BigInteger, nullable=False),
    Column("contribution_id", BigInteger, nullable=False),
    Column("question_id", BigInteger, nullable=False),
    Column("questionnaire_id", BigInteger, nullable=False),
    Column("unit_index", BigInteger, nullable=False),
    Column("text", Text, nullable=False),
    Column("context", JSONB, nullable=False),
    Column("content_hash", String(64), nullable=False),
    Column("contract_version", Integer, nullable=False),
    CheckConstraint(
        "answer_id > 0 AND contribution_id > 0 AND question_id > 0 AND questionnaire_id > 0",
        name="positive_source_ids",
    ),
    CheckConstraint("unit_index >= 0", name="nonnegative_unit_index"),
    CheckConstraint("contract_version > 0", name="positive_contract_version"),
    CheckConstraint("unit_type IN ('open_answer', 'other_text')", name="known_unit_type"),
    CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="sha256_content_hash"),
    CheckConstraint("jsonb_typeof(context) = 'object'", name="object_context"),
    UniqueConstraint(
        "corpus_id", "unit_type", "answer_id", "unit_index", name="unique_source_unit"
    ),
)
Index("ix_rag_units_questionnaire", units.c.corpus_id, units.c.questionnaire_id)
Index("ix_rag_units_contribution", units.c.corpus_id, units.c.contribution_id)
Index("ix_rag_units_question", units.c.corpus_id, units.c.question_id)

manifests = Table(
    "extractions",
    metadata,
    Column("extraction_id", UUID(as_uuid=True), primary_key=True),
    Column("parameters", JSONB, nullable=False),
    Column("parameters_hash", String(64), nullable=False),
    Column("source_identity", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(
        "jsonb_typeof(parameters) = 'object' AND jsonb_typeof(source_identity) = 'object'",
        name="manifest_objects",
    ),
    CheckConstraint("parameters_hash ~ '^[0-9a-f]{64}$'", name="sha256_parameters_hash"),
)

memberships = Table(
    "extraction_documents",
    metadata,
    Column(
        "extraction_id",
        UUID(as_uuid=True),
        ForeignKey("rag.extractions.extraction_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("document_id", Text, ForeignKey("rag.text_units.document_id"), primary_key=True),
    Column("ordinal", BigInteger, nullable=False),
    UniqueConstraint("extraction_id", "ordinal", name="unique_extraction_ordinal"),
    CheckConstraint("ordinal > 0", name="positive_ordinal"),
)
Index("ix_rag_membership_document", memberships.c.document_id)

checkpoints = Table(
    "checkpoints",
    metadata,
    Column(
        "extraction_id",
        UUID(as_uuid=True),
        ForeignKey("rag.extractions.extraction_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("answer_id", BigInteger),
    Column("unit_index", BigInteger),
    Column("document_count", BigInteger, nullable=False, server_default="0"),
    Column("source_row_count", BigInteger, nullable=False, server_default="0"),
    Column("revision", BigInteger, nullable=False, server_default="0"),
    Column("last_batch_hash", String(64)),
    Column("status", String(16), nullable=False, server_default="running"),
    Column("completion_reason", String(32)),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(
        "document_count >= 0 AND source_row_count >= 0 AND revision >= 0",
        name="nonnegative_progress",
    ),
    CheckConstraint("answer_id IS NULL OR answer_id > 0", name="positive_cursor_answer"),
    CheckConstraint(
        "unit_index IS NULL OR (answer_id IS NOT NULL AND unit_index >= 0)",
        name="valid_cursor_index",
    ),
    CheckConstraint(
        "(status = 'running' AND completion_reason IS NULL) OR (status = 'completed' AND completion_reason IN ('document_limit','source_exhausted','source_row_limit'))",
        name="valid_completion",
    ),
)

revision = "rag_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text("CREATE SCHEMA rag"))
    metadata.create_all(op.get_bind())


def downgrade():
    metadata.drop_all(op.get_bind())
    op.execute(text("DROP SCHEMA rag"))
