"""Préparations et artefacts synthétiques, sans modèle, réseau ni jugements."""

import json
import random
from dataclasses import replace

import pytest

from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.evaluation.sampling import describe, digest
from cahier_rag.representations.artifacts import generate, inspect_artifact, select_targets
from cahier_rag.representations.cli import config_from_dict, verify_replay
from cahier_rag.representations.contracts import PreparationConfig, Strategy
from cahier_rag.representations.prepare import prepare_unit
from cahier_rag.representations.repository import RepresentationRepository
from cahier_rag.representations.segmentation import segment_offsets
from cahier_rag.search.lexical import CorpusScope


def unit(i=0, **kwargs):
    value = TextUnit(
        corpus_id="synthetic",
        unit_type=UnitType.OPEN_ANSWER,
        answer_id=MAX_BIGINT - i,
        contribution_id=MAX_BIGINT - 100,
        question_id=10 + i,
        questionnaire_id=4,
        text="Oui !",
        question_text=f"Question {i} ?",
        questionnaire_name="Fiscalité",
        question_position=i,
        answer_position=0,
        question_type="text",
        external_contribution_id="000:synthétique",
    )
    return replace(value, **kwargs)


@pytest.fixture
def corpus():
    docs = [
        unit(),
        unit(1, text="Une proposition précise.\n\n" * 30),
        unit(2, text="école", unit_type=UnitType.OTHER_TEXT, question_type="single_choice"),
        unit(3, contribution_id=MAX_BIGINT - 101, text="Autre contribution"),
        unit(4, contribution_id=MAX_BIGINT - 102, text="Partition réservée"),
    ]
    rows = [
        describe(d) | {"split": "evaluation" if i == 4 else "development"}
        for i, d in enumerate(docs)
    ]
    sample = {"documents": rows, "selected_hash": digest(rows)}
    scope = CorpusScope(sample, expected_size=len(rows), expected_hash=sample["selected_hash"])

    class Memory(RepresentationRepository):
        def __init__(self):
            super().__init__(None, scope)
            self.calls = []

        def fetch(self, ids):
            self.calls.append(set(ids))
            return {d.document_id: d for d in docs if d.document_id in ids}

    return docs, sample, Memory()


@pytest.mark.parametrize("strategy", list(Strategy))
def test_four_strategies_fidelity_and_provenance(corpus, strategy):
    docs, _, repository = corpus
    original = [d.to_json() for d in docs]
    config = PreparationConfig(
        strategy=strategy, segment_chars=80, overlap_chars=12, max_neighbors=2, neighbor_chars=50
    )
    rows = list(repository.iter_prepared([docs[0].document_id], config))
    assert len(rows) == 1
    row = rows[0]
    assert row.context.question_text == docs[0].question_text
    assert row.context.contribution_title is None
    assert row.primary.contribution_id > 2**53
    assert row.primary.to_dict()["answer_id"] == str(MAX_BIGINT)
    source_index = {d.document_id: d for d in docs}
    for span in row.spans:
        assert (
            row.embedding_text[span.output_start : span.output_end]
            == getattr(source_index[span.document_id], span.field)[
                span.source_start : span.source_end
            ]
        )
    if strategy == Strategy.A:
        assert row.embedding_text == docs[0].text
    else:
        assert row.embedding_text.startswith("Question :\nQuestion 0 ?\n\nRéponse :\nOui !")
    if strategy == Strategy.D:
        assert row.enriched
        assert len(row.sources) == 3
        assert {s.document_id for s in row.sources} == {d.document_id for d in docs[:3]}
        assert all(s.contribution_id == docs[0].contribution_id for s in row.sources)
    else:
        assert not row.enriched and len(row.sources) == 1
    assert [d.to_json() for d in docs] == original
    assert row.to_dict() == json.loads(row.to_json())
    assert row.content_hash == digest(row._payload())


def test_B_C_same_text_and_parent_mechanism(corpus):
    docs, _, repository = corpus
    rows = [
        list(repository.iter_prepared([docs[0].document_id], PreparationConfig(s)))[0]
        for s in (Strategy.B, Strategy.C)
    ]
    assert rows[0].embedding_text == rows[1].embedding_text
    assert rows[0].representation_id != rows[1].representation_id
    assert set(rows[1].parent_unit_ids) == {d.document_id for d in docs[:3]}
    parent = repository.parent(docs[0].document_id)
    assert {d.document_id for d in parent} == set(rows[1].parent_unit_ids)
    assert all(d.contribution_id == docs[0].contribution_id for d in parent)


def test_short_threshold_and_neighbor_prefixes(corpus):
    docs, _, repository = corpus
    config = PreparationConfig(Strategy.D, max_neighbors=1, neighbor_chars=12)
    first = list(repository.iter_prepared([docs[0].document_id], config))[0]
    assert first.sources[1].document_id == docs[1].document_id
    span = first.spans[-1]
    assert (span.source_start, span.source_end) == (0, 12)
    assert first.embedding_text[span.output_start : span.output_end] == docs[1].text[:12]
    singleton = list(repository.iter_prepared([docs[3].document_id], config))[0]
    assert not singleton.enriched
    exact = unit(text="x" * 60)
    assert not list(
        prepare_unit(
            exact, config=config, sample_hash="s", split="development", parent=(exact, docs[1])
        )
    )[0].enriched
    assert not list(
        repository.iter_prepared([docs[0].document_id], replace(config, max_neighbors=0))
    )[0].enriched


def test_no_cross_contribution_or_questionnaire(corpus):
    docs, _, _ = corpus
    for wrong in (docs[3], replace(docs[1], questionnaire_id=5)):
        with pytest.raises(ValueError):
            list(
                prepare_unit(
                    docs[0],
                    config=PreparationConfig(Strategy.D),
                    sample_hash="s",
                    split="development",
                    parent=(wrong,),
                )
            )


@pytest.mark.parametrize("size,overlap", [(8, 0), (8, 4), (20, 3), (100, 0), (100, 50)])
def test_offsets_unicode_boundaries_and_reconstruction(size, overlap):
    rng = random.Random(33)
    texts = [
        "Oui",
        "école 👩🏽‍💻 e\u0301\n\nBonjour. Est-ce juste ?\n" * 40,
        "x" * 444,
        "".join(rng.choice("abc.?!\n é😀") for _ in range(1600)),
    ]
    for text in texts:
        offsets = list(segment_offsets(text, size=size, overlap=overlap))
        assert offsets == list(segment_offsets(text, size=size, overlap=overlap))
        assert offsets[0][0] == 0 and offsets[-1][1] == len(text)
        rebuilt = text[offsets[0][0] : offsets[0][1]]
        for (previous_start, previous_end), (start, end) in zip(offsets, offsets[1:]):
            assert previous_end - start == overlap
            assert start > previous_start
            rebuilt += text[previous_end:end]
        assert rebuilt == text
        assert all(0 < end - start <= size for start, end in offsets)


def test_sentence_and_paragraph_priority():
    text = "x" * 12 + "\n\n" + "y" * 30
    assert list(segment_offsets(text, size=20, overlap=2))[0] == (0, 14)
    text = "x" * 12 + ". " + "y" * 30
    assert list(segment_offsets(text, size=20, overlap=2))[0] == (0, 14)


def test_identity_content_versions_and_config(corpus):
    docs, _, _ = corpus
    config = PreparationConfig(Strategy.B)

    def render(doc, configuration=config):
        return list(prepare_unit(doc, config=configuration, sample_hash="s", split="development"))[
            0
        ]

    first = render(docs[0])
    changed = render(replace(docs[0], text="Non !"))
    assert first.representation_id == changed.representation_id  # même unité et offsets
    assert first.content_hash != changed.content_hash
    assert (
        render(replace(docs[0], answer_id=MAX_BIGINT - 50)).representation_id
        != first.representation_id
    )
    assert (
        render(docs[0], replace(config, short_chars=61)).representation_id
        != first.representation_id
    )
    assert config_from_dict(config.to_dict()) == config
    with pytest.raises(ValueError):
        config_from_dict(config.to_dict() | {"strategy_version": 2})
    with pytest.raises(ValueError):
        replace(first, segment_end=-1)


@pytest.mark.parametrize(
    "parameters",
    [
        dict(segment_chars=7),
        dict(overlap_chars=1001),
        dict(short_chars=0),
        dict(max_neighbors=9),
        dict(neighbor_chars=0),
        dict(segment_chars=True),
    ],
)
def test_invalid_parameters(parameters):
    with pytest.raises(ValueError):
        PreparationConfig(Strategy.A, **parameters)


def test_batched_lazy_preparation_and_determinism(corpus):
    docs, _, repository = corpus
    ids = [d.document_id for d in docs]
    config = PreparationConfig(Strategy.B, segment_chars=100, overlap_chars=10)
    iterator = repository.iter_prepared(ids, config, batch_size=1)
    assert repository.calls == []
    first = next(iterator)
    assert len(repository.calls) == 1 and len(repository.calls[0]) == 1
    iterator.close()
    a = [p.to_json() for p in repository.iter_prepared(ids, config, batch_size=1)]
    b = [p.to_json() for p in repository.iter_prepared(ids, config, batch_size=4)]
    assert a == b and first.to_json() == a[0]
    d = PreparationConfig(Strategy.D)
    assert [p.to_json() for p in repository.iter_prepared(ids, d, batch_size=1)] == [
        p.to_json() for p in repository.iter_prepared(ids, d, batch_size=4)
    ]
    with pytest.raises(ValueError):
        list(repository.iter_prepared(ids + ids[:1], config))
    with pytest.raises(ValueError):
        list(repository.iter_prepared(["outside"], config))


@pytest.mark.parametrize("strategy", list(Strategy))
def test_artifact_roundtrip_replay_tampering_and_no_overwrite(corpus, tmp_path, strategy):
    docs, _, repository = corpus
    config = PreparationConfig(strategy, segment_chars=120, overlap_chars=12)
    ids = [d.document_id for d in docs]
    path = tmp_path / strategy
    manifest = generate(repository, config, ids, path, selection={"seed": 42}, batch_size=1)
    assert inspect_artifact(path, scope=repository.scope) == manifest
    assert verify_replay(repository, path, batch_size=3)["reproducible"]
    other = tmp_path / (strategy + "-repeat")
    second = generate(repository, config, ids, other, selection={"seed": 42}, batch_size=4)
    assert second["data_sha256"] == manifest["data_sha256"]
    assert second["representations_hash"] == manifest["representations_hash"]
    assert second["target_ids_hash"] == manifest["target_ids_hash"]
    assert manifest["external_context_units"] == 0
    assert manifest["statistics"]["target_units"] == len(ids)
    with pytest.raises(FileExistsError):
        generate(repository, config, ids, path, selection={})
    with (path / "representations.jsonl").open("ab") as stream:
        stream.write(b"{}\n")
    with pytest.raises((ValueError, KeyError)):
        inspect_artifact(path, scope=repository.scope)


def test_select_targets_is_fixed_and_split_isolation(corpus):
    docs, sample, repository = corpus
    ids = select_targets(repository.scope, limit=4, seed=42)
    assert ids == select_targets(repository.scope, limit=4, seed=42)
    assert docs[-1].document_id not in ids
    assert select_targets(repository.scope, limit=1, split="evaluation") == [docs[-1].document_id]
    with pytest.raises(ValueError):
        select_targets(repository.scope, limit=5)
    for problem in ("parent", "text"):
        bad = [dict(r) for r in sample["documents"]]
        if problem == "parent":
            bad[4]["contribution_id"] = bad[0]["contribution_id"]
        else:
            bad[4]["text_hash"] = bad[0]["text_hash"]
        with pytest.raises(ValueError):
            CorpusScope(
                {"documents": bad, "selected_hash": digest(bad)},
                expected_size=len(bad),
                expected_hash=digest(bad),
            )


def test_imports_without_backend_gpu_web_or_connection(tmp_path):
    import subprocess
    import sys

    script = """
import importlib.abc
import sys
import sqlalchemy
import psycopg2
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'app','fastapi','torch','transformers','pgvector','sentence_transformers'}:
            raise AssertionError(fullname)
sys.meta_path.insert(0, Block())
def forbidden(*args, **kwargs):
    raise AssertionError('connection or engine created')
sqlalchemy.create_engine = forbidden
psycopg2.connect = forbidden
import cahier_rag.representations.contracts
import cahier_rag.representations.segmentation
import cahier_rag.representations.prepare
import cahier_rag.representations.repository
import cahier_rag.representations.artifacts
import cahier_rag.representations.cli
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_incomplete_run_has_no_success_manifest(corpus, tmp_path):
    docs, _, repository = corpus

    def broken(*args, **kwargs):
        yield next(
            RepresentationRepository.iter_prepared(
                repository, [docs[0].document_id], PreparationConfig(Strategy.A)
            )
        )
        raise ValueError("interruption synthétique")

    repository.iter_prepared = broken
    path = tmp_path / "interrupted"
    with pytest.raises(ValueError):
        generate(
            repository, PreparationConfig(Strategy.A), [docs[0].document_id], path, selection={}
        )
    assert (path / "representations.jsonl").exists()
    assert not (path / "manifest.json").exists()
    with pytest.raises(OSError):
        inspect_artifact(path)


def test_cli_requires_limit_and_refuses_foreign_output(corpus, tmp_path, monkeypatch):
    import cahier_rag.representations.cli as cli
    from cahier_rag.representations.cli import main

    with pytest.raises(SystemExit):
        main(["generate", "--strategy", "A", "--output", str(tmp_path)])
    monkeypatch.setattr(cli, "load_sample", lambda _: corpus[1])
    monkeypatch.setattr(cli, "CorpusScope", lambda _: corpus[2].scope)

    def forbidden(*args, **kwargs):
        pytest.fail("Connexion ne doit pas être créée")

    monkeypatch.setattr(cli, "create_rag_engine", forbidden)
    assert main(["generate", "--strategy", "A", "--limit", "1", "--output", str(tmp_path)]) == 2
    path = tmp_path / "valid"
    generate(
        corpus[2], PreparationConfig(Strategy.A), [corpus[0][0].document_id], path, selection={}
    )
    assert main(["inspect", str(path)]) == 0


def test_very_long_original_reconstructed_without_normalization():
    original = "Été e\u0301 👩🏽‍💻 — citation « oui ».\n\n" * 20000
    source = unit(text=original)
    config = PreparationConfig(Strategy.B)
    count, end, pieces = 0, 0, []
    for representation in prepare_unit(source, config=config, sample_hash="s", split="development"):
        span = next(s for s in representation.spans if s.role == "primary-answer")
        fragment = representation.embedding_text[span.output_start : span.output_end]
        assert fragment == original[span.source_start : span.source_end]
        pieces.append(fragment[max(0, end - span.source_start) :])
        end = span.source_end
        count += 1
    assert count > 100
    assert "".join(pieces) == original and end == len(original)


def test_empty_selection_is_rejected_before_writing(corpus, tmp_path):
    path = tmp_path / "empty"
    with pytest.raises(ValueError):
        generate(corpus[2], PreparationConfig(Strategy.A), [], path, selection={})
    assert not path.exists()
