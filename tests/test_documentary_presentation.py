"""Presentation only: exact source coverage and codepoint-based highlighting."""

import gzip
import json
from pathlib import Path

import pytest

from app.documentary_presentation import reading_paragraphs


def fragments(paragraphs):
    return [f for p in paragraphs for f in p["fragments"]]


TEXT = "  TITRE\n \n  Premier 😀 paragraphe\n   séné- chaussée.\n\nDeuxième e\u0301  paragraphe.  "
BREAK = TEXT.index("Deuxième")
METADATA = dict(
    source_start=100,
    xml_blocks=[
        dict(start=102, end=107, tag="head"),
        dict(start=111, end=100 + BREAK - 2, tag="p", role="body"),
        dict(start=100 + BREAK, end=100 + len(TEXT) - 2, tag="p", role="body"),
    ],
)


@pytest.mark.parametrize(
    "a,z",
    [
        (15, 25),  # Wholly within one paragraph; includes supplementary Unicode.
        (20, len(TEXT) - 5),  # Crosses a paragraph boundary.
        (TEXT.index("paragraphe"), BREAK + 4),  # Newlines and indentation.
        (0, 18),  # First passage, including source prefix.
        (BREAK, len(TEXT)),  # Last passage, including source suffix.
        (0, len(TEXT)),
    ],
)
def test_source_and_selected_offsets_survive_paragraph_projection(a, z):
    paragraphs = reading_paragraphs(
        TEXT, METADATA, dict(unit_id="stable-id", start_offset=a, end_offset=z)
    )
    parts = fragments(paragraphs)
    assert "".join(f["text"] for f in parts) == TEXT
    assert "".join(f["text"] for f in parts if f["selected"]) == TEXT[a:z]
    assert [f["anchor"] for f in parts if f["anchor"]] == ["passage-stable-id"]
    assert paragraphs[0]["kind"] == "heading"
    for p in paragraphs:
        assert (
            "".join(f["text"] for f in p["fragments"]) == TEXT[p["start_offset"] : p["end_offset"]]
        )


@pytest.mark.parametrize(
    "metadata",
    [{}, {"source_start": 0, "xml_blocks": [dict(start="bad", end=10)]}],
)
def test_conservative_fallback_preserves_blank_lines_not_internal_linebreaks(metadata):
    value = "  Art. 1. Un texte\n    continu.\n \nUn second paragraphe.\n\n"
    p = reading_paragraphs(value, metadata)
    assert len(p) == 2
    assert all(x["kind"] == "paragraph" for x in p)  # No inferred articles.
    assert "".join(f["text"] for f in fragments(p)) == value


def test_xml_page_milestones_and_nonxml_text_are_not_lost():
    value = "Préface\n  Rubrique\nTexte\n  fin hors bloc"
    metadata = dict(
        source_start=0,
        xml_blocks=[
            dict(start=10, end=18, role="section_heading", tag="p"),
            dict(start=19, end=19, tag="pb"),
            dict(start=19, end=24, tag="p"),
        ],
    )
    p = reading_paragraphs(value, metadata)
    assert "".join(f["text"] for f in fragments(p)) == value
    assert any(x["kind"] == "heading" for x in p)


COLLECTION = Path("1789/data/documents/reference-documents-2-7cbcaea79991")


@pytest.mark.skipif(not COLLECTION.exists(), reason="Immutable local artefacts unavailable")
def test_real_collection_and_every_agen_passage_keep_exact_canonical_coverage():
    with gzip.open(COLLECTION / "passages.jsonl.gz", "rt") as stream:
        units = [json.loads(line) for line in stream]
    agen_id = "ap1789-registry-p1:arcpa_0000-0000_1879_num_1_1_1531"
    checked = 0
    with gzip.open(COLLECTION / "documents.jsonl.gz", "rt") as stream:
        for line in stream:
            d = json.loads(line)
            full = d["full_text"]
            p = reading_paragraphs(full, d)
            assert "".join(f["text"] for f in fragments(p)) == full, d["id"]
            checked += 1
            if d["id"] == agen_id:
                assert len(p) > 80
                assert any(x["kind"] == "heading" for x in p)
                agen_units = [u for u in units if u["document_id"] == agen_id]
                assert len(agen_units) == 18
                for u in agen_units:
                    selected = reading_paragraphs(
                        full,
                        d,
                        dict(
                            unit_id=u["id"],
                            start_offset=u["start_in_document"],
                            end_offset=u["end_in_document"],
                        ),
                    )
                    assert (
                        "".join(f["text"] for f in fragments(selected) if f["selected"])
                        == u["text"]
                    )
    assert checked == 1267
