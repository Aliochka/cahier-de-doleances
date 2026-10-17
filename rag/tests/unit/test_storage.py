"""Types, fidélité et sécurité de stockage sans PostgreSQL."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.extraction import ExtractionError, ExtractionSpec
from cahier_rag.storage import DocumentConflict, document_record, restore_document


def document(**changes):
    values = dict(
        corpus_id="test:rag005",
        unit_type=UnitType.OPEN_ANSWER,
        answer_id=MAX_BIGINT,
        contribution_id=MAX_BIGINT - 1,
        question_id=MAX_BIGINT - 2,
        questionnaire_id=MAX_BIGINT - 3,
        text=" Égalité\n« L'école » " * 30_000,
        question_text="Pourquoi ?",
        questionnaire_name="Enquête",
        answer_position=1,
        question_type="text",
        contribution_title="Titre séparé",
        external_contribution_id="000:external",
    )
    return TextUnit(**(values | changes))


@pytest.mark.parametrize(
    "date", [None, datetime(2019, 1, 1), datetime(2019, 1, 1, tzinfo=timezone.utc)]
)
def test_storage_record_roundtrip_and_no_duplicate_content(date):
    unit = document(submitted_at=date)
    record = document_record(unit)
    assert record["answer_id"] == MAX_BIGINT
    assert "text" not in record["context"]
    assert "answer_id" not in record["context"]
    assert restore_document(record).to_json() == unit.to_json()


def test_restitution_detects_corruption_without_disclosing_text():
    record = document_record(document(text="PRIVATE"))
    record["text"] = "MODIFIED"
    with pytest.raises(DocumentConflict) as error:
        restore_document(record)
    assert "PRIVATE" not in str(error.value)
    assert "MODIFIED" not in str(error.value)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, 10001])
def test_explicit_small_limit_is_mandatory(limit):
    with pytest.raises(ExtractionError):
        ExtractionSpec(limit=limit)


def test_offline_migration_is_refused_before_connecting():
    from alembic import command
    from alembic.config import Config

    from cahier_rag.safety import DatabaseSafetyError

    config = Config()
    config.set_main_option("script_location", "cahier_rag:migrations")
    with pytest.raises(DatabaseSafetyError, match="hors connexion"):
        command.upgrade(config, "head", sql=True)


def test_parameters_roundtrip_hash_and_versions():
    spec = ExtractionSpec(limit=5, contribution_id=MAX_BIGINT, unit_type=UnitType.OTHER_TEXT)
    assert ExtractionSpec.from_dict(spec.to_dict()) == spec
    assert spec.to_dict()["contribution_id"] == str(MAX_BIGINT)
    assert replace(spec).fingerprint == spec.fingerprint
    assert replace(spec, limit=6).fingerprint != spec.fingerprint
    for changed in (
        replace(spec, contract_version=2),
        replace(spec, reader_version="future"),
        replace(spec, pipeline_version=2),
    ):
        with pytest.raises(ExtractionError, match="Versions"):
            changed.ensure_current()
