"""Segmentation, intégrité et isolation sans modèle ni connexion PostgreSQL."""

import importlib
import json
import math
import subprocess
import sys
from dataclasses import replace

import pytest

from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.evaluation.sampling import describe, digest
from cahier_rag.search.lexical import CorpusScope
from cahier_rag.vector.preparation import (
    TokenConfig,
    atomic_json,
    contextualize,
    iter_units,
    load_prepared,
    segments,
)
from cahier_rag.vector.store import float32_vector, recipe


class CharacterTokenizer:
    def __call__(self, text, *, add_special_tokens=True, **kwargs):
        value = {"input_ids": list(range(len(text) + (2 if add_special_tokens else 0)))}
        if kwargs.get("return_offsets_mapping"):
            value["offset_mapping"] = [(i, i + 1) for i in range(len(text))]
        return value


@pytest.fixture
def unit():
    return TextUnit(
        "synthetic",
        UnitType.OPEN_ANSWER,
        MAX_BIGINT,
        MAX_BIGINT - 1,
        MAX_BIGINT - 2,
        4,
        "École !\n\n" * 100,
        "Pourquoi ?",
        "Test",
        0,
        "text",
    )


def test_token_segmentation_offsets_overlap_fidelity(unit):
    config = TokenConfig(128, 12)
    items = list(segments(unit, CharacterTokenizer(), config, "sample", "development"))
    assert len(items) > 1
    assert items[0]["start"] == 0 and items[-1]["end"] == len(unit.text)
    for previous, item in zip(items, items[1:]):
        assert previous["start"] < item["start"] < previous["end"]
    for item in items:
        assert item["tokens"] <= config.budget
        assert item["text"] == contextualize(
            unit.question_text, unit.text[item["start"] : item["end"]]
        )
        assert item["contribution_id"] == str(MAX_BIGINT - 1)
        assert item["source_hash"] == unit.content_hash
    assert items == list(segments(unit, CharacterTokenizer(), config, "sample", "development"))
    assert len({i["representation_id"] for i in items}) == len(items)


def test_short_unicode_and_other_kept(unit):
    short = replace(unit, text="Non", unit_type=UnitType.OTHER_TEXT)
    (item,) = segments(short, CharacterTokenizer(), TokenConfig(128, 0), "s", "development")
    assert item["text"].endswith("Non") and item["unit_type"] == "other_text"
    assert item["start"] == 0 and item["end"] == 3
    (changed,) = segments(
        replace(short, answer_id=7), CharacterTokenizer(), TokenConfig(128, 0), "s", "development"
    )
    assert changed["representation_id"] != item["representation_id"]


@pytest.mark.parametrize("budget,overlap", [(0, 0), (8193, 0), (True, 0), (128, 64), (128, -1)])
def test_invalid_config(budget, overlap):
    with pytest.raises(ValueError):
        TokenConfig(budget, overlap)


def test_question_too_long_is_explicit(unit):
    with pytest.raises(ValueError, match="Question trop longue"):
        list(
            segments(
                replace(unit, question_text="x" * 200),
                CharacterTokenizer(),
                TokenConfig(128, 8),
                "s",
                "development",
            )
        )


def test_no_overlap_and_full_reconstruction(unit):
    items = list(segments(unit, CharacterTokenizer(), TokenConfig(128, 0), "s", "development"))
    assert "".join(unit.text[i["start"] : i["end"]] for i in items) == unit.text


@pytest.mark.parametrize(
    "vector", [[1.0] * 1023, [float("nan")] * 1024, [0.0] * 1024, [1.0] * 1024]
)
def test_invalid_vectors(vector):
    with pytest.raises(ValueError):
        float32_vector(vector)


def test_float32_vector_hash_stability():
    vector = [1 / math.sqrt(1024)] * 1024
    literal, checksum = float32_vector(vector)
    assert len(json.loads(literal)) == 1024
    assert float32_vector(json.loads(literal)) == (literal, checksum)


def test_artifact_iteration_partition_and_tampering(tmp_path, unit):
    metadata = [describe(unit) | {"split": "development"}]
    scope = CorpusScope(
        {"documents": metadata, "selected_hash": digest(metadata)},
        expected_hash=digest(metadata),
        expected_size=1,
    )
    rows = list(
        segments(unit, CharacterTokenizer(), TokenConfig(128, 12), scope.sample_hash, "development")
    )
    path = tmp_path / "representations.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert list(iter_units(tmp_path, scope)) == [rows]
    rows[0]["split"] = "evaluation"
    rows[0]["content_hash"] = digest({k: v for k, v in rows[0].items() if k != "content_hash"})
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(ValueError):
        list(iter_units(tmp_path, scope))


def test_incomplete_and_empty_artifact(tmp_path, unit):
    metadata = [describe(unit) | {"split": "development"}]
    scope = CorpusScope(
        {"documents": metadata, "selected_hash": digest(metadata)},
        expected_hash=digest(metadata),
        expected_size=1,
    )
    (tmp_path / "representations.jsonl").write_text("")
    with pytest.raises(ValueError):
        list(iter_units(tmp_path, scope))


def test_recipe_model_revision_and_normalization():
    config = recipe({"sample_hash": "s"})
    assert config["dimension"] == 1024 and config["normalization"] == "L2"
    assert config["model"]["revision"] == "5617a9f61b028005a4858fdac845db406aefb181"
    with pytest.raises(ValueError):
        recipe({}, precision="float16")


def test_manifest_tampering(tmp_path):
    atomic_json(tmp_path / "manifest.json", {"manifest_hash": "wrong"})
    with pytest.raises(ValueError):
        load_prepared(tmp_path, None)


def test_imports_do_not_load_backend_gpu_or_create_engine():
    code = """
import sys
import sqlalchemy
sqlalchemy.create_engine=lambda *a,**k: (_ for _ in ()).throw(AssertionError('engine'))
import cahier_rag.vector.cli
assert not any(m in sys.modules for m in ('torch','transformers','app','fastapi','numpy'))
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert importlib.import_module("cahier_rag.vector")


def test_cache_float32_roundtrip_and_rejection(tmp_path):
    from cahier_rag.embeddings.core import EmbeddingInput
    from cahier_rag.vector.cache import cached, save_cache

    inputs = [EmbeddingInput("stable", "Texte", "source")]
    configuration = {"version": 1}
    vectors = [[1.0] + [0.0] * 1023]
    assert cached(tmp_path, 0, inputs, configuration) is None
    save_cache(tmp_path, 0, inputs, configuration, vectors)
    assert cached(tmp_path, 0, inputs, configuration) == [tuple(vectors[0])]
    with pytest.raises(ValueError):
        cached(tmp_path, 0, inputs, {"version": 2})
    with pytest.raises(ValueError):
        cached(tmp_path, 0, [EmbeddingInput("changed", "Texte", "source")], configuration)
    path = tmp_path / "encoded" / "00000.f32"
    content = bytearray(path.read_bytes())
    content[0] ^= 1
    path.write_bytes(content)
    with pytest.raises(ValueError):
        cached(tmp_path, 0, inputs, configuration)


def test_missing_binary_cache_is_not_success(tmp_path):
    from cahier_rag.vector.cache import cached

    root = tmp_path / "encoded"
    root.mkdir()
    (root / "00000.json").write_text("{}")
    with pytest.raises(OSError):
        cached(tmp_path, 0, [], {})


def test_atomic_json_leaves_previous_on_failure(tmp_path, monkeypatch):
    import os

    target = tmp_path / "manifest.json"
    atomic_json(target, {"checkpoint": 1})

    def fail(_):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError):
        atomic_json(target, {"checkpoint": 2})
    assert json.loads(target.read_text()) == {"checkpoint": 1}


def test_query_engine_rejects_incompatible_model_before_loading():
    from types import SimpleNamespace

    from cahier_rag.embeddings.core import EmbeddingEngine
    from cahier_rag.embeddings.registry import MODELS
    from cahier_rag.vector.engine import VectorEngine

    class FakeBackend:
        dimension = 1024
        precision = "bfloat16"
        spec = MODELS["qwen3-0.6b"]

        def load_tokenizer(self):
            pytest.fail("Incompatible model must not load")

    store = SimpleNamespace(configuration=recipe({"snapshot_hash": "snapshot"}))
    with pytest.raises(ValueError, match="incompatible"):
        VectorEngine(store, EmbeddingEngine(FakeBackend())).load()


def test_query_engine_requires_explicit_loading():
    from cahier_rag.vector.engine import VectorEngine

    with pytest.raises(ValueError, match="explicitement"):
        VectorEngine(None, None).search("école")


def test_migration_refuses_missing_extension_before_ddl(monkeypatch):
    module = importlib.import_module("cahier_rag.migrations.versions.rag_0003_vectors")

    class Result:
        def scalar_one(self):
            return False

    class Connection:
        def execute(self, statement):
            assert "pg_available_extensions" in str(statement)
            return Result()

    monkeypatch.setattr(module.op, "get_bind", lambda: Connection())
    monkeypatch.setattr(module.op, "execute", lambda *_: pytest.fail("No DDL without pgvector"))
    with pytest.raises(ValueError, match="indisponible"):
        module.upgrade()
