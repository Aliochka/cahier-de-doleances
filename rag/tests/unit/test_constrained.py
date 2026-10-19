"""Schéma et décodage LMFE réels sur textes synthétiques, sans poids/GPU."""

import json
from types import SimpleNamespace

import pytest

from cahier_rag.contracts import canonical_json
from cahier_rag.generation.constrained.schema import accepts
from cahier_rag.generation.contracts import parse_output


@pytest.fixture
def item():
    pytest.importorskip(
        "lmformatenforcer", reason="Extra constrained requis pour les tests du parseur réel"
    )
    return SimpleNamespace(
        query="École ?",
        document={
            "sources": [
                {"reference": "S01", "answer": "École, cœur, santé ! 😀"},
                {"reference": "S02", "answer": "Non."},
            ]
        },
    )


def output():
    return {
        "blocks": [
            {
                "kind": "reported_opinion",
                "text": "École et santé.",
                "references": ["S01"],
                "quotes": [],
            }
        ],
        "limits": [],
        "insufficient_sources": False,
    }


def test_real_parser_unicode_required_fields_and_empty_lists(item):
    value = output()
    assert accepts(canonical_json(value), item)
    assert parse_output(canonical_json(value), item) == value
    value["blocks"][0]["text"] = "École, cœur 😀."
    assert accepts(canonical_json(value), item)
    value["blocks"][0].pop("quotes")
    assert not accepts(canonical_json(value), item)


@pytest.mark.parametrize(
    "change",
    [
        lambda v: v.update(insufficient_sources="false"),
        lambda v: v.update(blocks=[]),
        lambda v: v["blocks"][0].update(kind="unknown"),
        lambda v: v["blocks"][0].update(references=["S99"]),
        lambda v: v["blocks"][0].update(references=[]),
        lambda v: v["blocks"][0].update(text=""),
        lambda v: v["blocks"][0].update(extra=True),
        lambda v: v.update(extra=True),
    ],
)
def test_invalid_structure_impossible_for_parser(item, change):
    value = output()
    change(value)
    assert not accepts(canonical_json(value), item)


def test_limit_and_interruptions(item):
    value = output()
    assert not accepts(canonical_json(value)[:-1], item)
    value["blocks"][0]["text"] = "x" * 601
    assert not accepts(canonical_json(value), item)
    value = output()
    value["limits"] = ["x" * 301]
    assert not accepts(canonical_json(value), item)
    value = output()
    value["blocks"] *= 9
    assert not accepts(canonical_json(value), item)


def test_refs_depend_on_query_and_no_sources(item):
    other = SimpleNamespace(document={"sources": [{"reference": "S02", "answer": "Non."}]})
    assert not accepts(canonical_json(output()), other)
    value = output()
    value["blocks"][0].update(kind="limitation", references=[])
    assert accepts(canonical_json(value), item)
    empty = SimpleNamespace(document={"sources": []})
    value["insufficient_sources"] = True
    assert accepts(canonical_json(value), empty)
    assert parse_output(canonical_json(value), empty) == value


def test_unsupported_unique_items_still_refused_by_original_validator(item):
    value = output()
    value["blocks"][0]["references"] = ["S01", "S01"]
    assert accepts(canonical_json(value), item)  # uniqueItems is ignored by LMFE 0.11.3.
    with pytest.raises(ValueError, match="duplicate_reference"):
        parse_output(canonical_json(value), item)


def test_quotes_exactness_and_semantics_stay_post_validation(item):
    value = output()
    value["blocks"][0]["quotes"] = [{"reference": "S01", "text": "Inventé."}]
    assert accepts(canonical_json(value), item)
    with pytest.raises(ValueError, match="inexact_quote"):
        parse_output(canonical_json(value), item)
    value["blocks"][0]["quotes"][0]["text"] = "École"
    assert parse_output(canonical_json(value), item)
    value["blocks"][0]["text"] = "Une affirmation non étayée."
    assert accepts(canonical_json(value), item)
    assert parse_output(canonical_json(value), item)


def test_token_filter_with_toy_vocabulary(item):
    from lmformatenforcer import TokenEnforcer, TokenEnforcerTokenizerData

    from cahier_rag.generation.constrained.schema import parser_for

    text = canonical_json(output())
    characters = sorted(set(text + "?"))
    regular = [(i, c, False) for i, c in enumerate(characters)]
    eos = len(characters)
    data = TokenEnforcerTokenizerData(
        regular, lambda ids: "".join(characters[i] for i in ids), eos, False, eos + 1
    )
    enforcer = TokenEnforcer(data, parser_for(item))
    seq = [eos]
    for c in text:
        allowed = enforcer.get_allowed_tokens(seq).allowed_tokens
        token = characters.index(c)
        assert token in allowed
        seq.append(token)
    assert eos in enforcer.get_allowed_tokens(seq).allowed_tokens


def test_source_newlines_do_not_allow_unescaped_json_controls(item):
    item.document["sources"][0]["answer"] += "\n\tAutre ligne."
    value = output()
    value["limits"] = ["École.\nAutre ligne."]
    encoded = canonical_json(value)
    assert accepts(encoded, item)
    assert not accepts(encoded.replace("\\n", "\n"), item)


@pytest.fixture
def simulated_pipeline(tmp_path, monkeypatch):
    from cahier_rag.evaluation.sampling import digest
    from cahier_rag.generation.constrained import pipeline
    from cahier_rag.generation.constrained.planning import PILOT
    from cahier_rag.generation.contracts import GenerationInput, InferenceConfig

    directory = tmp_path / "rag023/plan"
    directory.mkdir(parents=True)
    doc = {
        "context_hash": "synthetic",
        "sources": [{"reference": "S01", "answer": "École !"}],
        "citation_map": {
            "S01": {
                "source": {
                    "metadata": {"corpus_id": "synthetic", "contribution_id": str(2**63 - 1)}
                }
            }
        },
    }
    items = [GenerationInput(q, "École ?", doc) for q in (*PILOT, "extra-development")]
    entries = []
    with (directory / "inputs.jsonl").open("w") as f:
        for item in items:
            prompt = canonical_json(item.messages())
            value = {
                "query_id": item.query_id,
                "query": item.query,
                "document": item.document,
                "input_hash": item.input_hash,
                "prompt": prompt,
                "prompt_hash": digest(prompt),
                "prompt_tokens": len(prompt),
            }
            entries.append(
                {k: value[k] for k in ("query_id", "input_hash", "prompt_hash", "prompt_tokens")}
            )
            f.write(canonical_json(value) + "\n")

    class Backend:
        config = InferenceConfig()
        torch = None
        load_seconds = 0.1
        last_metrics = {"grammar_seconds": 0.001}
        last_output_tokens = 50
        invalid = False

        def __init__(self):
            self.calls = []

        def recipe(self):
            return {"fake": True}

        def prompt(self, item):
            return canonical_json(item.messages())

        def token_counts(self, items):
            return [len(self.prompt(i)) for i in items]

        def load(self):
            pass

        def generate(self, items):
            self.calls.extend(i.input_hash for i in items)
            return ['{"blocks":' if self.invalid else canonical_json(output()) for i in items]

        def close(self):
            pass

    backend = Backend()
    plan = {"plan_hash": "synthetic", "backend": backend.recipe(), "entries": entries}
    monkeypatch.setattr(pipeline, "load_plan", lambda *a: plan)

    class Memory:
        peak = 100

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(pipeline, "MemorySampler", Memory)
    return directory, backend, pipeline


def test_transactional_resume_and_historical_failure_pilot(simulated_pipeline):
    from cahier_rag.generation.constrained.cache import Cache

    directory, backend, module = simulated_pipeline
    cache = Cache(directory.parent / "generation.sqlite3")
    with pytest.raises(ValueError, match="Pilote"):
        module.run(directory, backend, cache, stage="development")
    assert module.run(directory, backend, cache, stop_after=1)["new"] == 1
    resumed = module.run(directory, backend, cache)
    assert resumed["new"] == 2 and resumed["reused"] == 1
    full = module.run(directory, backend, cache, stage="development")
    assert full["new"] == 1 and full["reused"] == 3
    assert len(backend.calls) == len(set(backend.calls)) == 4
    cache.close()


def test_incomplete_raw_and_cache_isolation(simulated_pipeline, tmp_path):
    from cahier_rag.generation.constrained.cache import Cache

    directory, backend, module = simulated_pipeline
    backend.invalid = True
    cache = Cache(directory.parent / "generation.sqlite3")
    assert module.run(directory, backend, cache)["valid"] == 0
    payloads = [
        json.loads(r[0])
        for r in cache.connection.execute("SELECT payload FROM generation_attempts")
    ]
    assert len(payloads) == 3 and all(r["raw_output"] == '{"blocks":' for r in payloads)
    assert all(r["validation_seconds"] >= 0 for r in payloads)
    module.run(directory, backend, cache)
    assert len(backend.calls) == 3
    cache.close()
    with pytest.raises(ValueError):
        Cache(tmp_path / "rag022/generation.sqlite3")


def test_comparison_is_reproducible_and_readonly(tmp_path, monkeypatch, item):
    from cahier_rag.embeddings.snapshots import sha256_file
    from cahier_rag.generation.cache import Cache as BaselineCache
    from cahier_rag.generation.constrained import reporting
    from cahier_rag.generation.constrained.cache import Cache
    from cahier_rag.generation.contracts import GenerationInput

    doc = item.document | {
        "context_hash": "synthetic",
        "citation_map": {
            r: {"source": {"metadata": {"corpus_id": "test", "contribution_id": str(2**63 - 1)}}}
            for r in ("S01", "S02")
        },
    }
    entry = GenerationInput("development", "École ?", doc)
    old = {"plan_hash": "old", "backend": {"version": "v2"}}
    new = {"plan_hash": "new", "backend": {"version": "v3"}}
    baseline = tmp_path / "evaluation/local/rag022/v2/plan"
    baseline.mkdir(parents=True)
    (baseline / "manifest.json").write_text(canonical_json(old))
    directory = tmp_path / "evaluation/local/rag023/plan"
    directory.mkdir(parents=True)
    for spec, cls, path in (
        (old, BaselineCache, baseline.parent / "generation.sqlite3"),
        (new, Cache, directory.parent / "generation.sqlite3"),
    ):
        cache = cls(path)
        key = cache.register(
            {"version": 1, "plan_hash": spec["plan_hash"], "backend": spec["backend"]}
        )
        cache.commit(
            key,
            {
                "query_id": entry.query_id,
                "input_hash": entry.input_hash,
                "status": "valid",
                "raw_output": canonical_json(output()),
                "output": output(),
                "validation_error": None,
                "output_tokens": 50,
                "prompt_tokens": 100,
                "seconds": 1.0,
                "finish_reason": "eos",
            },
        )
        cache.close()
    before = sha256_file(baseline.parent / "generation.sqlite3")
    monkeypatch.setattr(reporting, "load_plan", lambda *a: new)
    monkeypatch.setattr(reporting, "iter_inputs", lambda *a: iter([(entry, {})]))
    a = reporting.report(tmp_path, directory)
    b = reporting.report(tmp_path, directory)
    assert a == b and a["valid"] == 1
    assert sha256_file(baseline.parent / "generation.sqlite3") == before


def test_output_token_filter():
    from cahier_rag.generation.constrained.backend import safe_token_ids

    tokens = [
        (1, "bonjour", False),
        (2, "\\", False),
        (3, "«", False),
        (4, '"', False),
        (5, "école", False),
        (6, "“avis”", False),
    ]
    assert safe_token_ids(tokens) == {1, 4, 5}
