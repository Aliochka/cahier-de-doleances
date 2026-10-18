"""Préparation et candidats humains sans réseau, modèle ou jugement inventé."""

import pytest

from cahier_rag.search.experiments import pool_candidates
from cahier_rag.search.preparation import Preparation, tokenize
from tests.unit.test_evaluation import sample


def test_generic_removal_preserves_quoted_terms_and_accents():
    parsed = tokenize('Quelles contributions mentionnent "école publique" et la TVA ?')
    assert "Quelles" not in parsed["terms"] and "contributions" not in parsed["terms"]
    assert parsed["phrases"] == ["école publique"]
    assert "TVA" in parsed["terms"]
    assert "Quelles" in tokenize("Quelles taxes ?", Preparation(remove_generic=False))["terms"]


def test_empty_and_generic_queries_are_explicit():
    assert tokenize("")["terms"] == []
    assert tokenize("Quelles contributions réponses ?")["terms"] == []
    assert tokenize("« TVA »")["phrases"] == [" TVA "]
    assert tokenize("taxe -carbone")["excluded"] == ["carbone"]
    assert not tokenize("centre-ville")["excluded"]


@pytest.mark.parametrize("query", ['"unclosed', "x" * 1001, " ".join('"x"' for _ in range(9))])
def test_preparation_bounds(query):
    with pytest.raises(ValueError):
        tokenize(query)


def test_pool_is_deduplicated_keeps_methods_ranks_and_random_controls():
    selected = sample(size=30)
    dev = [d["document_id"] for d in selected["documents"] if d["split"] == "development"]
    queries = [
        {"query_id": "q", "split": "development"},
        {"query_id": "reserved", "split": "evaluation"},
    ]
    runs = {"a": {"q": dev[:25]}, "b": {"q": list(reversed(dev[:25]))}}
    rows = pool_candidates(queries, selected, runs, per_query=10, random_count=2)
    assert len(rows) == 10 and len({r["document_id"] for r in rows}) == 10
    assert all(r["query_id"] == "q" and r["grade"] is None for r in rows)
    assert sum(r["random_control"] for r in rows) == 2
    assert any(len(r["found_by"]) == 2 for r in rows)
    assert any(any(source["rank"] > 10 for source in row["found_by"]) for row in rows)
    assert rows == pool_candidates(queries, selected, runs, per_query=10, random_count=2)


def test_pool_refuses_evaluation_candidates():
    selected = sample(size=30)
    outside = next(d["document_id"] for d in selected["documents"] if d["split"] == "evaluation")
    with pytest.raises(ValueError):
        pool_candidates(
            [{"query_id": "q", "split": "development"}], selected, {"a": {"q": [outside]}}
        )


def test_freeze_and_single_heldout_claim(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from cahier_rag.evaluation.files import load_json, write_json
    from cahier_rag.evaluation.sampling import digest
    from cahier_rag.search import flexible_cli as cli
    from cahier_rag.search.flexible import Method, configuration
    from cahier_rag.search.lexical import Strategy

    queries = [
        {"query_id": "dev", "split": "development"},
        {"query_id": "eval", "split": "evaluation"},
    ]
    experiment = tmp_path / "development"
    experiment.mkdir()
    cfg = configuration(Method.WEIGHTED, Strategy.ANSWER, Preparation())
    write_json(
        experiment / "report.json",
        {
            "split": "development",
            "sample_hash": "scope",
            "queries_hash": digest(queries),
            "configuration": cfg,
            "limit": 10,
            "index_configuration": {"version": 1},
        },
    )
    monkeypatch.setattr(cli, "load_sample", lambda path: {})
    monkeypatch.setattr(cli, "CorpusScope", lambda sample: SimpleNamespace(sample_hash="scope"))
    monkeypatch.setattr(cli, "load_queries", lambda path: queries)
    monkeypatch.setattr(cli, "load_settings", lambda **kwargs: None)

    @contextmanager
    def opened(settings):
        yield SimpleNamespace(guard=None)

    monkeypatch.setattr(cli, "open_store", opened)
    monkeypatch.setattr(
        cli,
        "FlexibleEngine",
        lambda *args: SimpleNamespace(validate=lambda: {"configuration": {"version": 1}}),
    )
    calls = []

    def evaluate(*args, **kwargs):
        calls.append(kwargs["split"])
        return {"eval": []}, {"quality_metrics": None}

    monkeypatch.setattr(cli, "run_experiment", evaluate)
    frozen = tmp_path / "frozen.json"
    assert (
        cli.main(
            [
                "freeze",
                "--experiment-directory",
                str(experiment),
                "--reason",
                "Choix synthétique",
                "--output",
                str(frozen),
            ]
        )
        == 0
    )
    assert load_json(frozen)["configuration"] == cfg
    assert (
        cli.main(
            ["evaluate", "--frozen", str(frozen), "--output-directory", str(tmp_path / "eval1")]
        )
        == 0
    )
    assert (
        cli.main(
            ["evaluate", "--frozen", str(frozen), "--output-directory", str(tmp_path / "eval2")]
        )
        == 2
    )
    assert calls == ["evaluation"]


def test_blank_and_exclusion_only_query_components():
    assert not tokenize("   ?!")["terms"]
    assert not tokenize("-fiscalité")["terms"]
    with pytest.raises(ValueError):
        Preparation(remove_generic="yes")
