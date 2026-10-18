"""Juges simulés, garanties d'aveuglement et reprise sans modèle ni base."""

import json
from types import SimpleNamespace

import pytest

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.cache import Cache
from cahier_rag.judges.comparison import agreement
from cahier_rag.judges.contracts import InferenceConfig, JudgeInput, parse_output
from cahier_rag.judges.models import MODELS
from cahier_rag.judges.pipeline import run
from cahier_rag.judges.planning import grouped_split, prepare
from cahier_rag.search.lexical import CorpusScope
from tests.unit.test_annotation import data  # noqa: F401


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "```json\n{}\n```",
        "{}",
        '{"grade":true,"justification":"a","uncertain":false}',
        '{"grade":"2","justification":"a","uncertain":false}',
        '{"grade":4,"justification":"a","uncertain":false}',
        '{"grade":2,"justification":"","uncertain":false}',
        '{"grade":2,"grade":3,"justification":"a","uncertain":false}',
        '{"grade":2,"justification":"a","uncertain":0}',
        '{"grade":2,"justification":"a","uncertain":false,"human_grade":3}',
    ],
)
def test_invalid_outputs(raw):
    with pytest.raises(ValueError):
        parse_output(raw)


def test_contract_and_messages_are_blind():
    item = JudgeInput(
        "q",
        "answer:9223372036854775807",
        "hash",
        "Requête",
        "Non",
        "Voulez-vous changer ?",
        "Titre",
    )
    assert (
        parse_output('{"grade":0,"justification":"Sans rapport.","uncertain":true}')["grade"] == 0
    )
    payload = json.loads(item.messages()[1]["content"].split("\n", 1)[1])
    assert set(payload) == {"requete", "reponse", "question_originale", "titre"}
    assert "9223372036854775807" not in json.dumps(item.messages())
    assert item.input_hash == digest(item.to_dict())
    with pytest.raises(TypeError):
        JudgeInput(**dict(item.to_dict(), human_grade=3))


def valid(key="input", grade=2):
    return {
        "input_hash": key,
        "query_id": "q",
        "document_id": "doc",
        "status": "valid",
        "judgment": {"grade": grade, "justification": "Pertinent.", "uncertain": False},
    }


def test_cache_idempotence_conflicts_isolation_and_atomicity(tmp_path):
    cache = Cache(tmp_path / "auto.sqlite3")
    try:
        a = cache.register({"model": "one"})
        b = cache.register({"model": "two"})
        cache.commit(a, [valid()])
        cache.commit(a, [valid()])
        assert cache.get(a, "input")["judgment"]["grade"] == 2
        assert cache.get(b, "input") is None
        with pytest.raises(ValueError, match="Conflit"):
            cache.commit(a, [valid(grade=3)])
        with pytest.raises(ValueError):
            cache.commit(b, [valid("first"), dict(valid("second"), status="invalid")])
        assert cache.get(b, "first") is None
    finally:
        cache.close()
    resumed = Cache(tmp_path / "auto.sqlite3")
    assert resumed.get(a, "input")["judgment"]["grade"] == 2
    resumed.close()


def test_agreements_and_linear_kappa():
    values = agreement([(0, 0), (1, 1), (2, 2), (3, 3)])
    assert values["exact"] == values["binary"] == values["weighted_kappa"] == 1
    values = agreement([(0, 1), (1, 0), (2, 3), (3, 2)])
    assert values["exact"] == 0 and values["within_one"] == values["binary"] == 1
    assert values["weighted_kappa"] == pytest.approx(0.2)
    assert agreement([])["weighted_kappa"] is None
    assert agreement([(0, 0)])["weighted_kappa"] is None


@pytest.fixture
def small_plan(request, tmp_path):
    pool, queries, sample, docs = request.getfixturevalue("data")
    scope = CorpusScope(sample, expected_hash=sample["selected_hash"], expected_size=len(docs))
    byid = {d.document_id: d for d in docs}
    repository = SimpleNamespace(
        scope=scope, fetch=lambda ids: {did: byid[did] for did in set(ids)}
    )
    directory = tmp_path / "plan"
    manifest = prepare(
        directory,
        [(r["query_id"], r["document_id"]) for r in pool],
        repository,
        queries,
        kind="human60",
        source_hashes={"human": "only hash"},
    )
    return directory, manifest, scope


class Fake:
    spec = MODELS["qwen3-8b"]
    snapshot_hash = "snapshot"
    load_seconds = 0
    torch = None

    def __init__(self):
        self.calls = 0

    def load_tokenizer(self):
        pass

    def load(self):
        pass

    def close(self):
        pass

    def token_counts(self, inputs):
        return [100] * len(inputs)

    def generate(self, inputs):
        self.calls += len(inputs)
        return ['{"grade":2,"justification":"Pertinent.","uncertain":false}'] * len(inputs)


@pytest.fixture
def lightweight(monkeypatch):
    import cahier_rag.embeddings.benchmark as benchmark
    import cahier_rag.judges.pipeline as pipeline

    monkeypatch.setattr(pipeline, "version", lambda _: "test")

    class Sampler:
        peak = 1

        def __enter__(self):
            pass

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(benchmark, "MemorySampler", Sampler)


def test_resume_reuse_and_invalid_outputs(small_plan, lightweight, tmp_path):
    directory, manifest, _ = small_plan
    cache = Cache(tmp_path / "cache.db")
    backend = Fake()
    config = InferenceConfig()
    try:
        first = run(directory, backend, config, cache, limit=8, stop_after=2)
        assert first["counts"]["valid"] == 2 and not first["complete"]
        second = run(directory, backend, config, cache, limit=8)
        assert (
            second["complete"]
            and second["counts"]["valid"] == 8
            and second["counts"]["reused"] == 2
        )
        assert backend.calls == 8
        repeated = run(directory, backend, config, cache, limit=8)
        assert repeated["counts"]["reused"] == 8 and backend.calls == 8
        with pytest.raises(ValueError):
            run(directory, backend, config, cache, limit=800)
    finally:
        cache.close()


def test_no_silent_truncation_and_full_campaign_guard(small_plan, lightweight, tmp_path):
    directory, manifest, _ = small_plan
    backend = Fake()
    backend.token_counts = lambda batch: [100000] * len(batch)
    cache = Cache(tmp_path / "cache.db")
    try:
        result = run(directory, backend, InferenceConfig(), cache, limit=8)
        assert result["counts"]["too_long"] == 8 and backend.calls == 0
        manifest["kind"] = "pools800"
        manifest.pop("manifest_hash")
        manifest["manifest_hash"] = digest(manifest)
        atomic_json(directory / "manifest.json", manifest)
        with pytest.raises(ValueError, match="allow-full"):
            run(directory, backend, InferenceConfig(), cache, limit=8)
    finally:
        cache.close()


def test_split_groups_same_parent_and_text(small_plan):
    _, manifest, scope = small_plan
    pairs = [(e["query_id"], e["document_id"]) for e in manifest["entries"]]
    assert grouped_split(pairs, scope) == grouped_split(pairs, scope)
    mapping = grouped_split(pairs, scope)
    for a in pairs:
        for b in pairs:
            da, db = scope.documents[a[1]], scope.documents[b[1]]
            if da["contribution_id"] == db["contribution_id"] or da["text_hash"] == db["text_hash"]:
                assert mapping[a] == mapping[b]


def test_invalid_generation_never_becomes_grade(small_plan, lightweight, tmp_path):
    directory, _, _ = small_plan
    backend = Fake()
    backend.generate = lambda batch: ['{"grade":4}'] * len(batch)
    cache = Cache(tmp_path / "cache.db")
    try:
        result = run(directory, backend, InferenceConfig(), cache, limit=8)
        assert result["counts"]["invalid"] == 8
        assert all(
            r["judgment"] is None
            for r in json.loads((directory / "qwen3-8b-results.json").read_text())["results"]
        )
        backend.generate = lambda batch: (
            ['{"grade":1,"justification":"Partiel.","uncertain":true}'] * len(batch)
        )
        retried = run(directory, backend, InferenceConfig(), cache, limit=8, retry_failed=True)
        assert retried["counts"]["valid"] == 8
    finally:
        cache.close()


def test_two_judges_do_not_share_cached_grades(small_plan, lightweight, tmp_path):
    directory, _, _ = small_plan
    cache = Cache(tmp_path / "cache.db")
    try:
        first, second = Fake(), Fake()
        second.spec = MODELS["qwen3-14b"]
        a = run(directory, first, InferenceConfig(), cache, limit=8)
        b = run(directory, second, InferenceConfig(), cache, limit=8)
        assert first.calls == second.calls == 8
        assert a["recipe_hash"] != b["recipe_hash"]
        assert b["counts"]["reused"] == 0
    finally:
        cache.close()


def test_comparison_missing_and_major_disagreements(small_plan):
    from cahier_rag.judges.comparison import report

    _, manifest, _ = small_plan
    entry = manifest["entries"][0]
    key = entry["input_hash"]
    results = {
        "first": {
            key: {
                "status": "valid",
                "judgment": {"grade": 0, "justification": "Hors sujet.", "uncertain": False},
            }
        },
        "second": {
            key: {
                "status": "valid",
                "judgment": {"grade": 3, "justification": "Direct.", "uncertain": False},
            }
        },
    }
    results["first"][manifest["entries"][1]["input_hash"]] = None
    output = report(manifest, results, {(entry["query_id"], entry["document_id"]): 0})
    assert output["disagreements"]["major"] == 1
    assert output["inter_judge"]["binary_disagreements"] == 1
    assert len(output["review"]) == len(manifest["entries"])
    assert "major_human_disagreement" in output["review"][0]["reasons"]


def test_cli_inference_does_not_load_human_reference(monkeypatch, tmp_path):
    from cahier_rag.judges import cli

    def forbidden(*args, **kwargs):
        pytest.fail("Inference accessed human data")

    monkeypatch.setattr(cli, "load_queries", forbidden)
    monkeypatch.setattr(cli, "Catalogue", forbidden)
    monkeypatch.setattr(cli, "TransformersJudge", lambda *args: object())
    monkeypatch.setattr(
        cli,
        "run",
        lambda *args, **kwargs: {
            "recipe_hash": "test",
            "counts": {},
            "seconds": 0,
            "complete": True,
        },
    )
    assert (
        cli.main(
            [
                "--cache",
                str(tmp_path / "cache.db"),
                "run",
                "--plan",
                "absent",
                "--judge",
                "qwen3-8b",
                "--limit",
                "60",
            ]
        )
        == 0
    )


def test_cache_cannot_open_human_session(tmp_path):
    session = tmp_path / "session.json"
    session.write_text('{"judgments": []}', encoding="utf-8")
    previous = session.read_bytes()
    with pytest.raises(ValueError, match="distinct"):
        Cache(session)
    assert session.read_bytes() == previous


def test_frozen_human_reference_preserves_sources_and_hides_comments(small_plan):
    from copy import deepcopy

    from cahier_rag.judges.reference import freeze, grades

    _, manifest, _ = small_plan
    reference = {
        "sources": "original",
        "conflicts": [],
        "judgments": [
            {
                "query_id": e["query_id"],
                "document_id": e["document_id"],
                "grade": 2,
                "evaluator": "human",
                "judged_at": "2026-10-18",
                "version": "v1",
                "justification": "Commentaire strictement personnel",
            }
            for e in manifest["entries"]
        ],
    }
    manifest = deepcopy(manifest)
    manifest["source_hashes"] = {"human_sources": "original"}
    before = deepcopy(reference)
    frozen = freeze(manifest, reference)
    assert reference == before
    assert "Commentaire" not in json.dumps(frozen)
    assert len(grades(manifest, frozen)) == len(manifest["entries"])
    reference["judgments"][0]["grade"] = 0
    assert set(grades(manifest, frozen).values()) == {2}
    tampered = deepcopy(frozen)
    tampered["judgments"][0]["grade"] = 0
    with pytest.raises(ValueError):
        grades(manifest, tampered)
    tampered = deepcopy(frozen)
    tampered["judgments"].append(tampered["judgments"][0])
    tampered.pop("reference_hash")
    tampered["reference_hash"] = digest(tampered)
    with pytest.raises(ValueError):
        grades(manifest, tampered)


@pytest.mark.parametrize("stop", [0, -1, 9, True])
def test_invalid_stop_cannot_launch_unintended_campaign(small_plan, tmp_path, stop):
    directory, _, _ = small_plan
    cache = Cache(tmp_path / "cache.db")
    try:
        with pytest.raises(ValueError, match="arrêt"):
            run(directory, Fake(), InferenceConfig(), cache, limit=8, stop_after=stop)
    finally:
        cache.close()


def test_gpu_failure_keeps_committed_batches_and_closes_backend(small_plan, lightweight, tmp_path):
    directory, _, _ = small_plan
    backend = Fake()
    original = backend.generate
    closed = []

    def interrupted(batch):
        if backend.calls >= 2:
            raise ValueError("GPU interrompu")
        return original(batch)

    backend.generate = interrupted
    backend.close = lambda: closed.append(True)
    cache = Cache(tmp_path / "cache.db")
    try:
        with pytest.raises(ValueError, match="GPU"):
            run(directory, backend, InferenceConfig(), cache, limit=8)
        assert closed == [True]
        resumed = run(directory, Fake(), InferenceConfig(), cache, limit=8)
        assert resumed["complete"] and resumed["counts"]["reused"] == 2
        assert cache.connection.execute("SELECT count(*) FROM results").fetchone()[0] == 8
    finally:
        cache.close()
