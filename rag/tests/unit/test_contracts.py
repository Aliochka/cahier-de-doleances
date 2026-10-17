"""Identité, empreintes, types et JSON sans pertes ni normalisation du texte."""

import json
from dataclasses import replace
from datetime import datetime

import pytest

from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType


def unit(**kwargs):
    values = dict(
        corpus_id="gdn:2019/consultation",
        unit_type=UnitType.OPEN_ANSWER,
        answer_id=MAX_BIGINT,
        contribution_id=MAX_BIGINT - 1,
        question_id=2**53 + 1,
        questionnaire_id=MAX_BIGINT - 2,
        text=" Non. Égalité, l'école et « l'autre »\n\"Oui\"\t ",
        question_text="Quelle proposition ?",
        questionnaire_name="Démocratie",
        answer_position=1,
        question_type="text",
    )
    return TextUnit(**(values | kwargs))


def test_json_preserves_all_bigints_and_external_ids():
    document = unit(external_contribution_id="001:QW5zd2Vy:é")
    payload = json.loads(document.to_json())
    assert payload["answer_id"] == str(MAX_BIGINT)
    assert payload["contribution_id"] == str(MAX_BIGINT - 1)
    assert payload["question_id"] == str(2**53 + 1)
    assert payload["questionnaire_id"] == str(MAX_BIGINT - 2)
    assert payload["external_contribution_id"] == "001:QW5zd2Vy:é"
    assert payload["text"] == document.text
    assert document.to_json() == document.to_json()
    assert "Égalité" in document.to_json()


@pytest.mark.parametrize("value", [True, 1.0, str(MAX_BIGINT), 0, -1, MAX_BIGINT + 1])
def test_ids_must_be_exact_bigint_integers(value):
    with pytest.raises(ValueError, match="BIGINT"):
        unit(answer_id=value)


@pytest.mark.parametrize("value", ["", " \t\n", "\u2003"])
def test_empty_units_are_explicitly_invalid(value):
    with pytest.raises(ValueError, match="non blanc"):
        unit(text=value)


@pytest.mark.parametrize("value", ["N", "Non", "École\nOù ?", "é" * 350_874])
def test_short_and_long_texts_are_preserved(value):
    document = unit(text=value)
    assert json.loads(document.to_json())["text"] == value


def test_identity_does_not_depend_on_content_or_extraction_order():
    document = unit()
    assert document.document_id == replace(document, text="Autre texte").document_id
    identities = {
        document.document_id,
        replace(document, answer_id=MAX_BIGINT - 10).document_id,
        replace(document, corpus_id="autre").document_id,
        replace(document, unit_type=UnitType.OTHER_TEXT).document_id,
        replace(document, unit_type=UnitType.OTHER_TEXT, unit_index=1).document_id,
    }
    assert len(identities) == 5
    assert "gdn%3A2019%2Fconsultation" in document.document_id


def test_fingerprint_tracks_text_context_provenance_and_optional_fields():
    document = unit()
    assert len(document.content_hash) == 64
    assert document.content_hash == replace(document).content_hash
    variants = [
        replace(document, text="Autre"),
        replace(document, contribution_title="Titre"),
        replace(document, question_text="Autre question"),
        replace(document, external_contribution_id="external"),
        replace(document, question_position=4, question_section="Section", question_code="Q4"),
        replace(document, submitted_at=datetime(2019, 1, 1, 12)),
    ]
    assert all(item.content_hash != document.content_hash for item in variants)
    payload = json.loads(document.to_json())
    assert payload["contract_version"] == 1
    assert payload["contribution_title"] is None
    assert payload["submitted_at"] is None
    assert payload["document_id"] == document.document_id
    assert payload["content_hash"] == document.content_hash


def test_unicode_is_not_normalized():
    assert unit(text="é").content_hash != unit(text="e\u0301").content_hash


@pytest.mark.parametrize(
    "changes",
    [
        {"external_contribution_id": 123},
        {"answer_position": 1.0},
        {"question_position": True},
        {"submitted_at": "2019-01-01"},
        {"question_text": None},
    ],
)
def test_context_types_are_not_silently_coerced(changes):
    with pytest.raises(ValueError):
        unit(**changes)
