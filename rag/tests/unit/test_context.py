"""Contextes synthétiques : fidélité, diversité, citations, budget et anti-fuite."""

import json
import subprocess
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

from cahier_rag.context.assembly import assemble, segment_text, similar
from cahier_rag.context.contracts import ContextConfig, ContextSource
from cahier_rag.context.experiments import configurations
from cahier_rag.context.repository import ContextRepository
from cahier_rag.context.validation import verify_context
from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.evaluation.sampling import describe, digest
from cahier_rag.search.lexical import CorpusScope


class Counter:
    description = {"tokenizer": "synthetic-character-counter"}

    def count(self, text):
        return len(text)


@pytest.fixture
def data(tmp_path):
    first = TextUnit(
        "test",
        UnitType.OPEN_ANSWER,
        MAX_BIGINT,
        MAX_BIGINT,
        101,
        4,
        "Oui.",
        "Supprimer le Sénat ?",
        "Démocratie",
        0,
        "text",
        external_contribution_id="000123-A",
        question_position=0,
    )
    docs = [
        first,
        replace(first, answer_id=MAX_BIGINT - 1, contribution_id=MAX_BIGINT - 1),
        replace(
            first,
            answer_id=MAX_BIGINT - 2,
            question_id=102,
            question_text="Pourquoi ?",
            text="Des bus entre villages et gares.",
            question_position=1,
        ),
        replace(
            first,
            answer_id=MAX_BIGINT - 3,
            contribution_id=MAX_BIGINT - 3,
            text="Une réponse longue.\n\n" * 500,
        ),
        replace(
            first,
            answer_id=MAX_BIGINT - 4,
            contribution_id=MAX_BIGINT - 4,
            text="École, impôts, « santé » !\nAccès.",
            contribution_title="Un titre",
        ),
    ]
    rows = [describe(d) | {"split": "development"} for d in docs]
    scope = CorpusScope(
        {"documents": rows, "selected_hash": digest(rows)},
        expected_hash=digest(rows),
        expected_size=len(docs),
    )
    repository = ContextRepository(tmp_path / "unused.sqlite3", scope)
    repository.documents = SimpleNamespace(
        fetch=lambda ids: {d.document_id: d for d in docs if d.document_id in ids}
    )
    return (
        docs,
        repository,
        {"query_id": "q1", "text": "Comment faire ?", "split": "development"},
        Counter(),
    )


def test_exact_citizen_text_bigints_citations_and_provenance(data):
    docs, repo, query, counter = data
    ids = [d.document_id for d in docs]
    context = assemble(
        query, ids, repo, counter, method="test", config=ContextConfig(selection="S1")
    )
    assert verify_context(context, query, ids, repo, counter) > 0
    for ref, source in context["citation_map"].items():
        u = next(d for d in docs if d.document_id == source["metadata"]["document_id"])
        span = source["technical"]["excerpt"]
        assert source["citizen_text"] == u.text[span["start"] : span["end"]]
        assert source["metadata"]["answer_id"] == str(u.answer_id)
        assert source["metadata"]["contribution_id"] == str(u.contribution_id)
        assert source["metadata"]["external_contribution_id"] == "000123-A"
        assert source["technical"]["public_url"] is None
        assert ref in context["model_document_payload"]
    assert (
        context["context_hash"]
        == assemble(query, ids, repo, counter, method="test", config=ContextConfig(selection="S1"))[
            "context_hash"
        ]
    )


def test_three_selection_policies_and_legitimate_occurrences(data):
    docs, repo, query, counter = data
    ids = [d.document_id for d in docs[:3]]
    outputs = {
        s: assemble(query, ids, repo, counter, method="test", config=ContextConfig(selection=s))
        for s in ("S1", "S2", "S3")
    }
    assert outputs["S1"]["statistics"]["primary_documents"] == 3
    assert outputs["S2"]["statistics"]["primary_documents"] == 2
    assert outputs["S3"]["statistics"]["primary_documents"] == 2
    assert outputs["S3"]["statistics"]["suppressed_repetitions"] == 1
    original = outputs["S3"]["citation_map"][next(iter(outputs["S3"]["citation_map"]))]
    assert original["metadata"]["contribution_id"] == str(MAX_BIGINT)
    assert (
        original["technical"]["observed_repetitions"]["contributions_including_representative"] == 2
    )
    assert len(repo.scope.documents) == len(docs)
    assert any(e["reason"] == "same_contribution" for e in outputs["S2"]["excluded"])


def test_near_duplicates_never_change_original_text_or_merge_questions(data):
    first = data[0][0]
    config = ContextConfig(selection="S3")
    assert similar(first, replace(first, text="oui !"), config) == "normalized_equal"
    assert similar(first, replace(first, question_id=999), config) is None
    text = "Nous voulons améliorer les transports publics pour tous les villages autour des gares"
    a = replace(first, text=text)
    assert similar(a, replace(a, text=text + " locales"), config) == "near"
    assert similar(a, replace(a, text=text + " sans"), config) is None
    assert similar(replace(a, text=text + " 10"), replace(a, text=text + " 20"), config) is None


@pytest.mark.parametrize("budget", [4096, 8192, 16384])
def test_budgets_and_long_answer_not_skipped_for_short_one(data, budget):
    docs, repo, query, counter = data
    ids = [docs[3].document_id, docs[0].document_id, docs[4].document_id]
    output = assemble(
        query, ids, repo, counter, method="test", config=ContextConfig(document_budget=budget)
    )
    payload = json.loads(output["model_document_payload"])
    first = output["citation_map"][payload["sources"][0]["reference"]]
    assert first["metadata"]["document_id"] == docs[3].document_id
    assert first["technical"]["omitted_ranges"]
    assert (
        output["budget"]["document_used"]
        == counter.count(output["model_document_payload"])
        <= budget
    )
    assert (
        output["budget"]["document_used"]
        == output["budget"]["metadata_reference_tokens"]
        + output["budget"]["citizen_incremental_tokens"]
    )
    assert output["budget"]["minimum_total_window"] == budget + 512 + 1024 + 128 + counter.count(
        query["text"]
    )
    spans = list(segment_text(docs[3].text, counter, budget=128))
    assert "".join(docs[3].text[a:b] for a, b in spans) == docs[3].text
    assert all(counter.count(docs[3].text[a:b]) <= 128 for a, b in spans)


def test_parent_modes_complementary_sources_and_budget(data):
    docs, repo, query, counter = data
    ids = [docs[0].document_id]
    outputs = {
        p: assemble(query, ids, repo, counter, method="test", config=ContextConfig(parent_mode=p))
        for p in ("P0", "P1", "P2")
    }
    assert "metadata" not in json.loads(outputs["P0"]["model_document_payload"])["sources"][0]
    assert (
        json.loads(outputs["P1"]["model_document_payload"])["sources"][0]["metadata"]["question"]
        == docs[0].question_text
    )
    assert outputs["P2"]["statistics"]["complementary_documents"] == 1
    assert outputs["P2"]["budget"]["expansion_incremental_tokens"] <= int(8192 * 0.2)
    for row in outputs["P2"]["citation_map"].values():
        assert row["metadata"]["contribution_id"] == str(docs[0].contribution_id)
        if row["technical"]["role"] == "complementary":
            assert row["technical"]["retrieval"]["rank"] is None
            assert row["technical"]["retrieval"]["direct"] is False
            assert row["technical"]["parent_document_id"] == docs[0].document_id
    assert verify_context(outputs["P2"], query, ids, repo, counter) == 2


def test_cross_contribution_expansion_is_rejected(data, monkeypatch):
    docs, repo, query, counter = data
    monkeypatch.setattr(repo, "neighbors", lambda primary, limit: [docs[1]])
    with pytest.raises(ValueError, match="autre contribution"):
        assemble(
            query,
            [docs[0].document_id],
            repo,
            counter,
            method="test",
            config=ContextConfig(parent_mode="P2"),
        )


def test_missing_altered_and_reserved_data_are_rejected(data):
    docs, repo, query, counter = data
    with pytest.raises(ValueError):
        assemble(
            dict(query, split="evaluation"), [docs[0].document_id], repo, counter, method="test"
        )
    with pytest.raises(ValueError):
        assemble(query, ["missing"], repo, counter, method="test")
    with pytest.raises(ValueError):
        repo.validate(replace(docs[0], text="Modified"))
    row = dict(repo.scope.documents[docs[0].document_id])
    row["split"] = "evaluation"
    repo.scope = SimpleNamespace(documents={docs[0].document_id: row}, sample_hash="test")
    with pytest.raises(ValueError):
        repo.fetch([docs[0].document_id])


def test_data_tampering_and_empty_results(data):
    docs, repo, query, counter = data
    context = assemble(query, [docs[0].document_id], repo, counter, method="test")
    context["citation_map"][next(iter(context["citation_map"]))]["citizen_text"] = "False quote"
    context["context_hash"] = digest({k: v for k, v in context.items() if k != "context_hash"})
    with pytest.raises(ValueError, match="modifié"):
        verify_context(context, query, [docs[0].document_id], repo, counter)
    empty = assemble(query, [], repo, counter, method="test")
    assert verify_context(empty, query, [], repo, counter) == 0


def test_reference_stable_across_methods_and_budget_modes(data):
    first = data[0][0]
    a = ContextSource(first, "scope", 0, len(first.text), "one", 1)
    b = ContextSource(first, "scope", 0, len(first.text), "two", 50)
    c = ContextSource(
        replace(first, answer_id=MAX_BIGINT - 1, contribution_id=MAX_BIGINT - 1),
        "scope",
        0,
        len(first.text),
        "one",
        1,
    )
    assert a.reference == b.reference != c.reference
    assert a.citizen_text == c.citizen_text
    with pytest.raises(ValueError):
        replace(a, end=len(first.text) + 1)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"selection": "bad"},
        {"document_budget": 255},
        {"document_budget": True},
        {"expansion_fraction": 0.5},
        {"max_neighbors": 100},
    ],
)
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        ContextConfig(**kwargs)


def test_staged_protocol_and_dependency_isolation():
    assert len(configurations()) == 7
    code = "import sys; import cahier_rag.context.assembly, cahier_rag.context.experiments; assert not any(m in sys.modules for m in ('torch','transformers','tokenizers','fastapi','app'))"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_missing_optional_context_is_not_invented(data):
    unit = replace(data[0][0], question_text="", contribution_title=None)
    value = ContextSource(unit, "scope", 0, len(unit.text), "test", 1).to_dict()
    assert value["metadata"]["question_text"] == ""
    assert value["metadata"]["contribution_title"] is None
    assert value["technical"]["parent_document_id"] is None


def test_budget_exhaustion_and_neighbor_already_selected(data):
    docs, repo, query, counter = data
    ids = [docs[0].document_id, docs[2].document_id]
    result = assemble(
        query, ids, repo, counter, method="test", config=ContextConfig(document_budget=256)
    )
    assert result["statistics"]["primary_documents"] == 0
    assert all(e["reason"] == "budget" for e in result["excluded"])
    result = assemble(
        query,
        ids,
        repo,
        counter,
        method="test",
        config=ContextConfig(selection="S1", parent_mode="P2"),
    )
    assert result["statistics"]["primary_documents"] == 2
    assert result["statistics"]["complementary_documents"] == 0
    assert len(result["citation_map"]) == 2
    assert all(e["status"] == "already_present" for e in result["expansion"])


def test_tokenizer_rejects_changed_file_without_importing_models(tmp_path):
    from cahier_rag.context.tokenization import LocalTokenizer

    path = tmp_path / "tokenizer.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="modifié"):
        LocalTokenizer(path, repository="test", revision="test", expected_sha256="wrong")


def test_invalid_parent_and_rendered_budget_tampering(data):
    docs, repo, query, counter = data
    result = assemble(query, [docs[0].document_id], repo, counter, method="test")
    result["budget"]["document_used"] += 1
    result["context_hash"] = digest({k: v for k, v in result.items() if k != "context_hash"})
    with pytest.raises(ValueError, match="Budget"):
        verify_context(result, query, [docs[0].document_id], repo, counter)
    with pytest.raises(ValueError):
        ContextSource(docs[0], "scope", 0, len(docs[0].text), "test", None, role="complementary")
