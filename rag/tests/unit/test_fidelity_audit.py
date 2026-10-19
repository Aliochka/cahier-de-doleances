"""Garde-fous de la copie d'audit, uniquement sur données synthétiques."""

import copy
import runpy
from pathlib import Path

import pytest

from cahier_rag.context.contracts import ContextSource
from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType

AUDIT = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "scripts/extract_fidelity_audit.py")
)


def test_audit_preserves_exact_source_and_bigints():
    unit = TextUnit(
        "test",
        UnitType.OPEN_ANSWER,
        MAX_BIGINT,
        MAX_BIGINT - 1,
        101,
        4,
        "Non.\nOui, à condition de conserver un accueil.",
        "Numériser ?",
        "Services",
        0,
        "text",
        external_contribution_id="00001-A",
    )
    source = ContextSource(unit, "synthetic", 0, len(unit.text), "H1+R2", 1).to_dict()
    mapping = {"context_reference": source["reference"], "source": source}
    AUDIT["check_source"](mapping, unit)
    assert source["metadata"]["answer_id"] == str(MAX_BIGINT)
    assert source["metadata"]["external_contribution_id"] == "00001-A"
    for change in ("text", "id", "reference", "range"):
        altered = copy.deepcopy(mapping)
        if change == "text":
            altered["source"]["citizen_text"] = "Oui."
        elif change == "id":
            altered["source"]["metadata"]["answer_id"] = str(float(MAX_BIGINT))
        elif change == "reference":
            altered["context_reference"] = "another-source"
        else:
            altered["source"]["technical"]["excerpt"]["end"] -= 1
        with pytest.raises(ValueError):
            AUDIT["check_source"](altered, unit)


def test_length_signals_are_not_semantic_verdicts():
    text = "Une proposition. " + "a" * (600 - len("Une proposition. "))
    value = {"blocks": [{"text": text, "references": ["S01"]}]}
    signals = AUDIT["inspect_blocks"](value)
    assert signals[0]["at_600"] is True
    assert signals[0]["tail"] == text[-100:]
    assert "status" not in signals[0]
    assert AUDIT["STATUSES"] == ("Étayé", "Partiel", "Non étayé", "Contredit", "Incertain")
