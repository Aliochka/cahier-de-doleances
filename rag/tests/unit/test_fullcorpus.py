"""Précontrôles et segmentation RAG-026 sans base, modèle ou GPU."""

from dataclasses import replace

import pytest

from cahier_rag.contracts import TextUnit, UnitType
from cahier_rag.fullcorpus.audit import WHITESPACE, fingerprint, resource_estimate
from cahier_rag.fullcorpus.pipeline import prepare_unit, require_disk
from cahier_rag.fullcorpus.store import chain, require_space, vector_hash
from cahier_rag.vector.preparation import TokenConfig, segments


def unit(text="Non"):
    return TextUnit(
        "gdn-2019",
        UnitType.OPEN_ANSWER,
        2**63 - 2,
        2**53 + 3,
        1,
        4,
        text,
        "Pourquoi ?",
        "Questionnaire",
        1,
        "text",
    )


class Tokenizer:
    def __call__(self, value, *, add_special_tokens=True, return_offsets_mapping=False, **kw):
        return {
            "input_ids": list(range(len(value) + (2 if add_special_tokens else 0))),
            "offset_mapping": [(i, i + 1) for i in range(len(value))],
        }


def test_exact_inventory_blanks():
    assert "\u00a0" in WHITESPACE and "\x1c" in WHITESPACE
    assert all(c.isspace() for c in WHITESPACE)


def test_resources_and_refusal(monkeypatch, tmp_path):
    assert not resource_estimate(5_200_000, 1.01, 3000, 1_000_000)["sufficient"]
    assert resource_estimate(5_200_000, 1.01, 3000, 10**12)["sufficient"]
    monkeypatch.setattr("shutil.disk_usage", lambda p: type("D", (), {"free": 10})())
    with pytest.raises(ValueError, match="disque"):
        require_disk(tmp_path)


@pytest.mark.parametrize("value", ["Non", "école\n", "phrase. " * 200])
def test_same_historical_segmentation(value):
    doc = unit(value)
    tokenizer = Tokenizer()
    config = TokenConfig(budget=128, overlap=16)
    assert prepare_unit(doc, tokenizer, config, "scope") == list(
        segments(doc, tokenizer, config, "scope", "full")
    )


def test_bigint_chain_and_legitimate_duplicates():
    a = unit()
    b = replace(a, answer_id=a.answer_id - 1)
    assert a.to_dict()["answer_id"] == str(2**63 - 2)
    assert chain("", [a, b]) == chain(chain("", [a]), [b])
    assert chain("", [a, b]) != chain("", [b, a])
    assert fingerprint({"b": 1, "a": "é"}) == fingerprint({"a": "é", "b": 1})


def test_spaces_and_vector_fingerprint():
    with pytest.raises(ValueError):
        require_space("rag007")
    assert vector_hash([1.0] + [0.0] * 1023) == vector_hash([1] + [0] * 1023)
    with pytest.raises(Exception):
        vector_hash([0.0])


def test_vector_binary_preserves_signed_zero():
    import json
    import struct

    from cahier_rag.fullcorpus.store import decode_vector_binary

    values = [1.0, -0.0] + [0.0] * 1022
    raw = struct.pack("!HH1024f", 1024, 0, *values)
    assert vector_hash(decode_vector_binary(raw)) == vector_hash(values)
    assert vector_hash(json.loads("[1,-0," + ",".join(["0"] * 1022) + "]")) != vector_hash(values)
    for corrupt in (
        raw[:20],
        struct.pack("!HH", 1023, 0) + raw[4:],
        struct.pack("!HH", 1024, 1) + raw[4:],
    ):
        with pytest.raises(ValueError, match="Protocole"):
            decode_vector_binary(corrupt)


def test_vector_transport_rounds_once_and_preserves_zero_sign():
    import json

    from cahier_rag.fullcorpus.store import vector_literal

    values = [0.0012148848618380725, -0.0] + [0.0] * 1022
    literal = vector_literal(values)
    # Chiffres float32 exacts avant le passage à strtof PostgreSQL ; la chaîne
    # traverse JSONB sans conversion de ses nombres ou du signe de zéro.
    assert literal.startswith("[0.0012148849200457335,-0.0,")
    assert vector_hash(json.loads(literal, parse_int=float)) == vector_hash(values)
