"""Génération simulée et sorties synthétiques uniquement, aucun jugement humain."""

from dataclasses import replace

import pytest

from cahier_rag.context.contracts import ContextSource
from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType, canonical_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.generation.cache import Cache
from cahier_rag.generation.contracts import (
    GenerationInput,
    InferenceConfig,
    answer_text,
    compact,
    parse_output,
)


@pytest.fixture
def item():
    unit = TextUnit(
        "test",
        UnitType.OPEN_ANSWER,
        MAX_BIGINT,
        MAX_BIGINT,
        99,
        4,
        "École, santé !\nDes bus.",
        "Pourquoi ?",
        "Test",
        0,
        "text",
    )
    sources = [
        ContextSource(unit, "scope", 0, 13, "method", 1),
        ContextSource(
            replace(unit, answer_id=MAX_BIGINT - 1, contribution_id=MAX_BIGINT - 1),
            "scope",
            0,
            13,
            "method",
            2,
        ),
    ]
    context = {
        "citation_map": {s.reference: s.to_dict() for s in sources},
        "model_document_payload": canonical_json(
            {
                "sources": [
                    {"reference": s.reference, "citizen_text": s.citizen_text} for s in sources
                ]
            }
        ),
    }
    context["context_hash"] = digest(context)
    return GenerationInput("q", "Des propositions ?", compact(context))


def valid():
    return {
        "blocks": [
            {
                "kind": "reported_opinion",
                "text": "Une réponse consultée évoque les services publics.",
                "references": ["S01"],
                "quotes": [],
            }
        ],
        "limits": ["Sous-ensemble sélectionné, non représentatif."],
        "insufficient_sources": False,
    }


def test_compact_exact_text_mapping_bigint_and_incomplete(item):
    assert len(item.document["citation_map"]) == 2
    assert all(s["incomplete"] for s in item.document["sources"])
    a = item.document["citation_map"]["S01"]
    b = item.document["citation_map"]["S02"]
    assert a["source"]["metadata"]["answer_id"] == str(MAX_BIGINT)
    assert a["context_reference"] != b["context_reference"]
    assert (
        a["source"]["citizen_text"]
        == b["source"]["citizen_text"]
        == item.document["sources"][0]["answer"]
    )
    assert "sha256" not in item.messages()[1]["content"]
    assert str(MAX_BIGINT) not in item.messages()[1]["content"]
    assert item.input_hash == replace(item).input_hash


def test_valid_output_and_literal_quote(item):
    output = valid()
    output["blocks"][0]["quotes"] = [
        {"reference": "S01", "text": item.document["sources"][0]["answer"]}
    ]
    parsed = parse_output(canonical_json(output), item)
    assert "[S01]" in answer_text(parsed)
    assert item.document["sources"][0]["answer"] in answer_text(parsed)


@pytest.mark.parametrize(
    "mutation,error",
    [
        (lambda o: o["blocks"][0].update(references=["S99"]), "reference"),
        (lambda o: o["blocks"][0].update(references=[]), "unsupported"),
        (lambda o: o["blocks"][0].update(references=["S01", "S01"]), "reference"),
        (
            lambda o: o["blocks"][0].update(
                quotes=[{"reference": "S01", "text": "Une citation inventée"}]
            ),
            "inexact",
        ),
        (lambda o: o["blocks"][0].update(text="Il affirme « oui »."), "unstructured"),
        (lambda o: o.update(insufficient_sources="false"), "limits"),
    ],
)
def test_invalid_outputs_not_repaired(item, mutation, error):
    value = valid()
    mutation(value)
    with pytest.raises(ValueError, match=error):
        parse_output(canonical_json(value), item)


@pytest.mark.parametrize(
    "raw", ["```json\n{}\n```", "not json", '{"blocks":[],"blocks":[]}', '{"a":NaN}']
)
def test_invalid_json(item, raw):
    with pytest.raises(ValueError):
        parse_output(raw, item)


def test_insufficiency_without_sources_and_not_semantic_validator(item):
    output = valid()
    output["blocks"][0].update(
        kind="limitation", references=[], text="Les sources ne suffisent pas."
    )
    output["insufficient_sources"] = True
    assert parse_output(canonical_json(output), item)["insufficient_sources"]
    output = valid()
    output["blocks"][0]["text"] = "Une affirmation sans rapport avec la source."
    assert parse_output(
        canonical_json(output), item
    )  # Known limitation: reference existence is not semantic support.


def test_generation_cache_preserves_invalid_attempts_and_valid_results(tmp_path, item):
    cache = Cache(tmp_path / "rag022/cache.sqlite3")
    key = cache.register({"v": 1})
    bad = {"input_hash": item.input_hash, "status": "invalid", "raw_output": "bad", "output": None}
    cache.commit(key, bad)
    good = {
        "input_hash": item.input_hash,
        "status": "valid",
        "raw_output": canonical_json(valid()),
        "output": valid(),
    }
    with pytest.raises(ValueError):
        cache.commit(key, good)
    cache.commit(key, good, retry_invalid=True)
    assert cache.get(key, item.input_hash) == good
    assert cache.connection.execute("SELECT count(*) FROM generation_attempts").fetchone()[0] == 2
    with pytest.raises(ValueError):
        cache.commit(key, bad, retry_invalid=True)
    cache.close()
    cache = Cache(tmp_path / "rag022/cache.sqlite3", readonly=True)
    assert cache.get(key, item.input_hash) == good
    cache.close()


def test_cache_rejects_judge_path(tmp_path):
    with pytest.raises(ValueError):
        Cache(tmp_path / "judges/cache.sqlite3")


def test_generation_configuration():
    assert InferenceConfig().thinking is False
    with pytest.raises(ValueError):
        InferenceConfig(thinking=True)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda o: o["blocks"][0].update(kind={}),
        lambda o: o["blocks"][0].update(quotes=[{"reference": {}, "text": "x"}]),
        lambda o: o.update(blocks=[None]),
    ],
)
def test_arbitrary_json_types_are_invalid_not_crashes(item, mutation):
    output = valid()
    mutation(output)
    with pytest.raises(ValueError):
        parse_output(canonical_json(output), item)


def test_context_window_refused_before_model_execution(item, tmp_path):
    from cahier_rag.generation.backend import LocalGenerator

    backend = LocalGenerator(tmp_path, InferenceConfig())
    backend.model = object()
    backend.token_counts = lambda inputs: [32768]
    with pytest.raises(ValueError, match="Contexte trop long"):
        backend.generate([item])
    backend.model = None


@pytest.fixture
def fake_pipeline(item, tmp_path, monkeypatch):
    import cahier_rag.generation.pipeline as module
    from cahier_rag.generation.planning import PILOT

    directory = tmp_path / "rag022/plan"
    directory.mkdir(parents=True)
    items = [replace(item, query_id=q) for q in (*PILOT, "other-development")]
    entries = []
    with (directory / "inputs.jsonl").open("w") as f:
        for i in items:
            prompt = canonical_json(i.messages())
            row = {
                "query_id": i.query_id,
                "query": i.query,
                "document": i.document,
                "input_hash": i.input_hash,
                "prompt": prompt,
                "prompt_hash": digest(prompt),
                "prompt_tokens": len(prompt),
                "compact_tokens": 100,
            }
            f.write(canonical_json(row) + "\n")
            entries.append(
                {
                    k: row[k]
                    for k in (
                        "query_id",
                        "input_hash",
                        "prompt_hash",
                        "prompt_tokens",
                        "compact_tokens",
                    )
                }
            )

    class Backend:
        config = InferenceConfig()
        torch = None
        load_seconds = 0.1
        last_output_tokens = 12
        calls = []
        invalid = False

        def recipe(self):
            return {"fake": True}

        def prompt(self, i):
            return canonical_json(i.messages())

        def token_counts(self, inputs):
            return [len(self.prompt(i)) for i in inputs]

        def load(self):
            pass

        def generate(self, inputs):
            self.calls.extend(i.input_hash for i in inputs)
            return ["bad" if self.invalid else canonical_json(valid()) for i in inputs]

        def close(self):
            pass

    backend = Backend()
    backend.calls = []
    plan = {"plan_hash": "frozen", "backend": backend.recipe(), "entries": entries}
    monkeypatch.setattr(module, "load_plan", lambda *a: plan)

    class Memory:
        peak = 100

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(module, "MemorySampler", Memory)
    return directory, backend, module


def test_interrupt_resume_and_pilot_gate(fake_pipeline):
    directory, backend, module = fake_pipeline
    cache = Cache(directory.parent / "generation.sqlite3")
    with pytest.raises(ValueError, match="Pilote"):
        module.run(directory, backend, cache, stage="development")
    stopped = module.run(directory, backend, cache, stop_after=1)
    assert not stopped["complete"] and stopped["new"] == 1
    resumed = module.run(directory, backend, cache)
    assert resumed["complete"] and resumed["reused"] == 1 and resumed["new"] == 2
    full = module.run(directory, backend, cache, stage="development")
    assert full["complete"] and full["new"] == 1 and full["reused"] == 3
    assert len(backend.calls) == len(set(backend.calls)) == 4
    cache.close()


def test_invalid_raw_retained_no_silent_retry(fake_pipeline):
    directory, backend, module = fake_pipeline
    backend.invalid = True
    cache = Cache(directory.parent / "generation.sqlite3")
    result = module.run(directory, backend, cache)
    assert result["valid"] == 0
    assert (
        cache.connection.execute(
            "SELECT count(*) FROM generation_attempts WHERE payload LIKE '%bad%'"
        ).fetchone()[0]
        == 3
    )
    module.run(directory, backend, cache)
    assert len(backend.calls) == 3
    with pytest.raises(ValueError, match="Pilote"):
        module.run(directory, backend, cache, stage="development")
    cache.close()


def test_checkpoint_and_attempt_are_atomic(tmp_path, item):
    cache = Cache(tmp_path / "rag022/cache.sqlite3")
    key = cache.register({"version": 1})
    cache.connection.execute(
        "CREATE TRIGGER simulated_error BEFORE INSERT ON generation_checkpoints BEGIN SELECT RAISE(ABORT,'simulated'); END"
    )
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        cache.commit(
            key,
            {
                "input_hash": item.input_hash,
                "status": "invalid",
                "raw_output": "bad",
                "output": None,
            },
        )
    assert cache.connection.execute("SELECT count(*) FROM generation_attempts").fetchone()[0] == 0
    cache.close()


def test_prompt_versions_are_distinct_and_explicit(item):
    from cahier_rag.generation.contracts import resolve_prompt

    first = resolve_prompt("generation-fr-v1")
    second = resolve_prompt("generation-fr-v2")
    assert first != second and "220 mots" in second and "quotes doit être []" in second
    assert item.messages("generation-fr-v1")[0]["content"] == first
    with pytest.raises(ValueError):
        resolve_prompt("unknown")


def test_generation_imports_are_lightweight():
    import subprocess
    import sys

    code = "import sys; import cahier_rag.generation.contracts, cahier_rag.generation.cache, cahier_rag.generation.planning; assert not any(m in sys.modules for m in ('torch','transformers','fastapi','app'))"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
