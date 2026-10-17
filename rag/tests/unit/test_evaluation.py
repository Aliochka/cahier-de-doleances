"""Évaluation sur données synthétiques et valeurs de métriques connues."""

from pathlib import Path

import pytest

from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.evaluation.cli import load_sample, main
from cahier_rag.evaluation.files import candidates, load_judgments, load_queries, write_json
from cahier_rag.evaluation.metrics import aggregate, evaluate
from cahier_rag.evaluation.sampling import select_sample


def unit(i, **changes):
    values = dict(
        corpus_id="test",
        unit_type=UnitType.OPEN_ANSWER,
        answer_id=MAX_BIGINT - i,
        contribution_id=MAX_BIGINT - i,
        question_id=10,
        questionnaire_id=4,
        text=f"Texte {i}",
        question_text="Pourquoi ?",
        questionnaire_name="Test",
        answer_position=1,
        question_type="text",
    )
    return TextUnit(**(values | changes))


def sample(documents=None, **kw):
    return select_sample(
        documents if documents is not None else (unit(i) for i in range(30)),
        **(dict(size=10, seed=42, method="random", frame={"version": "test"}) | kw),
    )


def test_reproducible_deduplicated_order_independent():
    docs = [unit(i) for i in range(30)]
    a, b = sample(docs), sample(reversed(docs + docs))
    assert a["selected_hash"] == b["selected_hash"]
    assert a["frame_hash"] == b["frame_hash"]
    assert a["candidate_count"] == 30
    assert a["selected_hash"] != sample(seed=43)["selected_hash"]
    assert int(a["documents"][0]["contribution_id"]) > 2**53
    assert all("text" not in d for d in a["documents"])


def test_components_and_independent_split_seed():
    docs = [
        unit(1, text="identique"),
        unit(2, text="identique"),
        unit(3, contribution_id=unit(2).contribution_id),
    ]
    a = sample(docs, size=3)
    b = sample(docs, size=3, seed=123, method="stratified", quotas={"duplicate": 2})
    assert len({d["component_id"] for d in a["documents"]}) == 1
    assert len({d["split"] for d in a["documents"]}) == 1
    assert {d["document_id"]: d["split"] for d in a["documents"]} == {
        d["document_id"]: d["split"] for d in b["documents"]
    }
    assert a["frame_hash"] == b["frame_hash"]


def test_quotas_and_shortfalls():
    docs = [unit(1, text="x" * 3000), unit(2, unit_type=UnitType.OTHER_TEXT), unit(3)]
    result = sample(docs, size=3, method="stratified", quotas={"long": 1, "other": 1, "form:7": 1})
    assert result["shortfalls"] == {"form:7": 1}
    assert result["statistics"]["strata"]["long"] == 1
    assert result["statistics"]["strata"]["other"] == 1
    assert sample(docs, size=10)["size_shortfall"] == 7


def test_bounded_consumption():
    visited = []

    def source():
        for i in range(1000):
            visited.append(i)
            yield unit(i)

    with pytest.raises(ValueError):
        sample(source(), size=2, max_candidates=3)
    assert len(visited) == 4


def test_conflicting_document():
    with pytest.raises(ValueError):
        sample([unit(1), unit(1, text="autre")])


@pytest.mark.parametrize("size", [0, 20001, True])
def test_size_validation(size):
    with pytest.raises(ValueError):
        sample(size=size)


def test_known_metrics():
    score = evaluate(["b", "a", "c"], {"a": 3, "b": 0, "c": 2}, k=2, complete=True)
    assert score["precision_at_k"] == 0.5
    assert score["recall_at_k"] == 0.5
    assert score["mrr"] == 0.5
    assert score["ndcg_at_k"] == pytest.approx(0.4966392597)


def test_unjudged_and_incomplete_are_explicit():
    score = evaluate(["x", "a"], {"a": 3}, k=2)
    assert all(score[k] is None for k in ("precision_at_k", "recall_at_k", "mrr", "ndcg_at_k"))
    score = evaluate(["x", "a"], {"a": 3, "x": 0}, k=2)
    assert score["precision_at_k"] == 0.5 and score["mrr"] == 0.5
    assert score["recall_at_k"] is None


def test_empty_zero_and_short_ranking():
    assert evaluate([], {}, complete=True)["mrr"] is None
    score = evaluate(["a"], {"a": 0}, k=2, complete=True)
    assert score["precision_at_k"] == 0 and score["mrr"] == 0
    assert score["recall_at_k"] is None and score["ndcg_at_k"] is None
    assert evaluate(["a"], {"a": 3}, k=2, complete=True)["precision_at_k"] == 0.5


@pytest.mark.parametrize("grade", [True, -1, 4, 1.5])
def test_invalid_grade(grade):
    with pytest.raises(ValueError):
        evaluate(["a"], {"a": grade})


def test_duplicate_ranking():
    with pytest.raises(ValueError):
        evaluate(["a", "a"], {"a": 3})


def test_queries():
    queries = load_queries(Path(__file__).parents[2] / "evaluation/queries.json")
    assert len(queries) == 40
    assert sum(q["split"] == "development" for q in queries) == 20
    assert len({q["category"] for q in queries}) == 6


def test_human_judgments_roundtrip_and_candidates(tmp_path):
    selected = sample(size=30)
    doc = selected["documents"][0]
    queries = [dict(query_id="q", split=doc["split"], category="test")]
    assert all(r["grade"] is None for r in candidates(queries, selected, per_query=3))
    row = dict(
        query_id="q",
        document_id=doc["document_id"],
        grade=3,
        justification="Synthétique",
        judged_at="2026-10-17T12:00:00+02:00",
        version="v1",
        evaluator="humain-a",
    )
    path = tmp_path / "judgments.json"
    write_json(path, [row])
    assert load_judgments(path, queries, selected)[0] == [row]
    with pytest.raises(FileExistsError):
        write_json(path, [])
    with pytest.raises(ValueError):
        load_judgments(path, [queries[0] | {"split": "invalid"}], selected)


def test_sample_integrity_and_cli(tmp_path):
    value = sample()
    path = tmp_path / "sample.json"
    write_json(path, value)
    assert load_sample(path)["selected_hash"] == value["selected_hash"]
    queries = Path(__file__).parents[2] / "evaluation/queries.json"
    assert (
        main(
            [
                "candidates",
                "--sample",
                str(path),
                "--queries",
                str(queries),
                "--output",
                str(tmp_path / "candidates.json"),
            ]
        )
        == 0
    )
    value["documents"][0]["content_hash"] = "corrupt"
    path.unlink()
    write_json(path, value)
    with pytest.raises(ValueError):
        load_sample(path)


def test_aggregate_denominators():
    report = aggregate(
        [
            dict(query_id="a", category="c", split="development"),
            dict(query_id="b", category="c", split="evaluation"),
        ],
        {"a": ["d"]},
        {"a": {"d": 2}},
        k=1,
    )
    assert report["aggregates"]["all"]["precision_at_k"] == {
        "mean": 1,
        "defined_queries": 1,
        "total_queries": 2,
    }


def test_ten_thousand_units_without_bodies_in_sample():
    selected = sample((unit(i) for i in range(12000)), size=10000, max_candidates=12000)
    assert len(selected["documents"]) == 10000
    assert selected["size_shortfall"] == 0
    assert selected["statistics"]["splits"]["evaluation"] > 0


def test_duplicate_stratum_keeps_a_pair():
    docs = [unit(1, text="pair"), unit(2, text="pair"), unit(3)]
    selected = sample(docs, size=2, method="stratified", quotas={"duplicate": 1})
    assert len(selected["documents"]) == 2
    assert len({d["text_hash"] for d in selected["documents"]}) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"grade": None},
        {"grade": True},
        {"version": ""},
        {"evaluator": None},
        {"judged_at": "2026-10-17T12:00:00"},
        {"justification": 4},
        {"document_id": "absent"},
    ],
)
def test_invalid_judgments_are_not_silent(tmp_path, change):
    selected = sample()
    doc = selected["documents"][0]
    query = dict(query_id="q", split=doc["split"])
    row = (
        dict(
            query_id="q",
            document_id=doc["document_id"],
            grade=0,
            judged_at="2026-10-17T12:00:00Z",
            version="v1",
            evaluator="human",
        )
        | change
    )
    path = tmp_path / "judgments.json"
    write_json(path, [row])
    with pytest.raises(ValueError):
        load_judgments(path, [query], selected)


def test_complete_scoring_requires_exhaustive_judgments(tmp_path):
    selected = sample(size=3)
    doc = selected["documents"][0]
    queries = [
        dict(
            query_id="q",
            text="Question synthétique",
            category="test",
            domain="test",
            family="test",
            version="v1",
            split=doc["split"],
        )
    ]
    rows = [
        dict(
            query_id="q",
            document_id=d["document_id"],
            grade=2,
            judged_at="2026-10-17T12:00:00Z",
            version="v1",
            evaluator="human",
        )
        for d in selected["documents"]
        if d["split"] == doc["split"]
    ]
    for name, data in [
        ("sample", selected),
        ("queries", queries),
        ("judgments", rows),
        ("results", {"q": [doc["document_id"]]}),
    ]:
        write_json(tmp_path / (name + ".json"), data)
    args = [
        "score",
        "--sample",
        str(tmp_path / "sample.json"),
        "--queries",
        str(tmp_path / "queries.json"),
        "--judgments",
        str(tmp_path / "judgments.json"),
        "--results",
        str(tmp_path / "results.json"),
        "--output",
        str(tmp_path / "score.json"),
        "--k",
        "1",
        "--complete",
    ]
    assert main(args) == 0
    from cahier_rag.evaluation.files import load_json

    assert load_json(tmp_path / "score.json")["per_query"]["q"]["precision_at_k"] == 1
    (tmp_path / "judgments.json").unlink()
    write_json(tmp_path / "judgments.json", [])
    args[args.index("--output") + 1] = str(tmp_path / "invalid.json")
    assert main(args) == 2
    assert not (tmp_path / "invalid.json").exists()


def test_queries_reject_family_leakage_and_duplicate_json_keys(tmp_path):
    path = tmp_path / "queries.json"
    query = dict(
        query_id="a",
        text="Test",
        category="test",
        domain="test",
        family="same",
        version="v1",
        split="development",
    )
    write_json(path, [query, query | {"query_id": "b", "split": "evaluation"}])
    with pytest.raises(ValueError):
        load_queries(path)
    path.write_text('{"q":[],"q":[]}')
    from cahier_rag.evaluation.files import load_json

    with pytest.raises(ValueError):
        load_json(path)


def test_random_quotas_and_invalid_seed_rejected():
    with pytest.raises(ValueError):
        sample(quotas={"short": 1})
    with pytest.raises(ValueError):
        sample(split_seed=True)
