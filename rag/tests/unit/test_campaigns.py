"""Campagnes fictives isolées, aucun accès en écriture aux annotations réelles."""

import copy
import json

import pytest

from cahier_rag.annotation.campaigns import Catalogue
from cahier_rag.annotation.consolidation import consolidate
from cahier_rag.annotation.reporting import evaluate_report
from cahier_rag.annotation.session import Session
from cahier_rag.evaluation.files import validate_judgments
from cahier_rag.evaluation.sampling import digest
from tests.unit.test_annotation import data  # noqa: F401


@pytest.fixture
def catalogue(request, tmp_path):
    pool, queries, sample, docs = request.getfixturevalue("data")
    result = Catalogue(tmp_path, queries, sample, expected_count=len(pool))
    for spec in result.campaigns.values():
        spec.pool.parent.mkdir(parents=True, exist_ok=True)
        spec.pool.write_text(json.dumps(pool))
        spec.manifest.write_text(
            json.dumps(
                {
                    "pool_hash": digest(pool),
                    "candidate_count": len(pool),
                    "sample_hash": sample["selected_hash"],
                    "queries_hash": digest(queries),
                    "split": "development",
                }
            )
        )
    return result


def test_legacy_compatible_and_readonly(catalogue):
    cat = catalogue
    spec = cat.get("rag010")
    old = Session(
        cat.load_pool("rag010"),
        cat.queries,
        cat.sample,
        spec.session_path,
        evaluator="legacy",
        expected_count=cat.expected_count,
    )
    old.change(revision=0, position=0, comment="Commentaire existant é", grade=3)
    before = spec.session_path.read_bytes()
    snap = cat.snapshot("rag010")
    assert snap.identity == old.identity and "campaign_id" not in snap.identity
    assert snap.export() == old.export() and spec.session_path.read_bytes() == before
    with pytest.raises(ValueError, match="lecture seule"):
        snap.change(revision=1, position=1, comment="No", grade=0)
    assert spec.session_path.read_bytes() == before
    with pytest.raises(ValueError):
        cat.create("rag010", evaluator="different")
    assert spec.session_path.read_bytes() == before


def test_separate_creation_reprise_and_existing_session_preserved(catalogue):
    legacy = catalogue.create("rag010", evaluator="same", seed=17)
    legacy.change(revision=0, position=0, comment="ancien", grade=2)
    before = catalogue.get("rag010").session_path.read_bytes()
    second = catalogue.create("rag014", evaluator="other", seed=17)
    second.change(revision=0, position=0, comment="second", grade=1)
    resumed = catalogue.snapshot("rag014")
    assert resumed.state == second.state
    assert resumed.identity["campaign_id"] == "rag014"
    assert resumed.identity["evaluator"] == "other"
    assert catalogue.get("rag010").session_path.read_bytes() == before
    with pytest.raises(ValueError, match="existante"):
        catalogue.create("rag014", evaluator="other", seed=17)
    assert resumed.export()[0]["justification"] == "second"


def test_listing_and_consolidation_do_not_create_sessions(catalogue):
    assert all(not s.session_path.exists() for s in catalogue.campaigns.values())
    assert catalogue.status("rag014")["started"] is False
    reference = consolidate(catalogue)
    assert reference["judgments"] == [] and reference["conflicts"] == []
    assert all(not s.folder.exists() for s in catalogue.campaigns.values())
    with pytest.raises(ValueError):
        catalogue.session("rag014", evaluator="x")
    assert not catalogue.get("rag014").folder.exists()


def test_consolidation_deduplication_comments_provenance_and_conflicts(catalogue):
    a = catalogue.create("rag010", evaluator="first", seed=17)
    b = catalogue.create("rag014", evaluator="second", seed=17)
    a.change(revision=0, position=0, comment="premier commentaire", grade=3)
    b.change(revision=0, position=0, comment="second commentaire", grade=3)
    before = {name: spec.session_path.read_bytes() for name, spec in catalogue.campaigns.items()}
    reference = consolidate(catalogue)
    assert len(reference["judgments"]) == 1 and reference["observation_count"] == 2
    assert {r["justification"] for r in reference["provenance"][0]["observations"]} == {
        "premier commentaire",
        "second commentaire",
    }
    assert {r["campaign_id"] for r in reference["provenance"][0]["observations"]} == {
        "rag010",
        "rag014",
    }
    assert all(
        r["pool_hash"] and r["queries_hash"] for r in reference["provenance"][0]["observations"]
    )
    validate_judgments(reference["judgments"], catalogue.queries, catalogue.sample)
    assert all(
        spec.session_path.read_bytes() == before[name] for name, spec in catalogue.campaigns.items()
    )
    # Même couple, note différente : refus de choisir automatiquement un évaluateur.
    b.change(revision=1, position=1, comment="", destination=0)
    b.change(revision=2, position=0, comment="désaccord", grade=0)
    reference = consolidate(catalogue)
    assert not reference["judgments"] and len(reference["conflicts"]) == 1
    assert {r["grade"] for r in reference["conflicts"][0]["observations"]} == {0, 3}
    assert reference == consolidate(catalogue)


def test_failed_save_keeps_old_session_and_in_memory_state(catalogue, monkeypatch):
    session = catalogue.create("rag014", evaluator="test")
    before = session.path.read_bytes()
    state = copy.deepcopy(session.state)

    def fail(*args):
        raise OSError("synthetic full disk")

    monkeypatch.setattr("cahier_rag.annotation.session.atomic_json", fail)
    with pytest.raises(OSError):
        session.change(revision=0, position=0, comment="cannot save", grade=2)
    assert session.state == state and session.path.read_bytes() == before


def ranking_data(cat):
    ids = [d["document_id"] for d in cat.sample["documents"]]
    runs = {m: {q["query_id"]: ids for q in cat.queries} for m in ("lexical", "vector", "hybrid")}
    return runs, ids


def test_incomplete_metrics_do_not_assume_unknown_is_zero(catalogue):
    session = catalogue.create("rag010", evaluator="test")
    session.change(revision=0, position=0, comment="", grade=3)
    reference = consolidate(catalogue)
    runs, ids = ranking_data(catalogue)
    report = evaluate_report(reference, runs, catalogue.queries, catalogue.sample)
    assert report["final_ranking"] is None
    qid = session.order[0][0]
    row = report["methods"]["lexical"]["per_query"][qid]["5"]
    assert row["coverage"]["judged"] == 1 and row["coverage"]["unjudged"] == 3
    assert row["strict"]["precision_at_k"] is None
    assert row["strict"]["recall_at_k"] is None and row["strict"]["ndcg_at_k"] is None
    assert row["descriptive_judged_only"]["judged_relevant_fraction_in_original_top_k"] == 1
    assert row["descriptive_judged_only"]["condensed_ndcg"] == 1
    assert report == evaluate_report(reference, runs, catalogue.queries, catalogue.sample)


def test_conflict_not_zero_and_bigint_kept(catalogue):
    a = catalogue.create("rag010", evaluator="a", seed=17)
    b = catalogue.create("rag014", evaluator="b", seed=17)
    a.change(revision=0, position=0, comment="", grade=0)
    b.change(revision=0, position=0, comment="", grade=3)
    reference = consolidate(catalogue)
    runs, ids = ranking_data(catalogue)
    report = evaluate_report(reference, runs, catalogue.queries, catalogue.sample)
    qid = a.order[0][0]
    coverage = report["methods"]["hybrid"]["per_query"][qid]["5"]["coverage"]
    assert coverage["conflicts"] == 1 and coverage["judged"] == 0 and coverage["unjudged"] == 3
    assert int(catalogue.sample["documents"][0]["contribution_id"]) > 2**53


def test_exhaustive_synthetic_reference_makes_recall_and_ndcg_defined(catalogue):
    session = catalogue.create("rag010", evaluator="test")
    while session.view()["done"] < len(session.order):
        view = session.view()
        session.change(revision=view["revision"], position=view["position"], comment="", grade=3)
    reference = consolidate(catalogue)
    runs, ids = ranking_data(catalogue)
    report = evaluate_report(reference, runs, catalogue.queries, catalogue.sample)
    row = report["methods"]["lexical"]["per_query"][catalogue.queries[0]["query_id"]]["5"]
    assert row["strict"]["recall_at_k"] == 1 and row["strict"]["ndcg_at_k"] == 1
    assert report["matched_queries"]["5"]["precision_at_k"]["defined_queries"] == 2


def test_reject_cross_partition_and_pool_tampering(catalogue):
    spec = catalogue.get("rag014")
    rows = json.loads(spec.pool.read_text())
    rows[0]["content_hash"] = "changed"
    spec.pool.write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        catalogue.load_pool("rag014")
    assert not spec.session_path.exists()


def test_blind_second_campaign_web_state_and_export(catalogue):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from cahier_rag.annotation.web import create_app

    session = catalogue.create("rag014", evaluator="test")

    class Documents:
        def get(self, pair, *, parent=False):
            return [{"text": "Réponse citoyenne", "question_text": "Question ?"}]

    app = create_app(
        session, Documents(), campaign_id="rag014", campaign_label="Campagne complémentaire"
    )
    client = TestClient(app, base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000))
    view = client.get("/api/state").json()
    assert view["campaign_id"] == "rag014" and view["done"] == 0
    assert "SECRET" not in json.dumps(view) and "found_by" not in json.dumps(view)
    saved = client.post(
        "/api/change",
        json={"revision": 0, "position": 0, "comment": "Commentaire conservé", "grade": 2},
        headers={"x-annotation-token": view["token"]},
    )
    assert saved.status_code == 200 and saved.json()["campaign_id"] == "rag014"
    assert catalogue.snapshot("rag014").export()[0]["justification"] == "Commentaire conservé"
    assert client.get("/api/export").json()[0]["grade"] == 2
    assert "rag014" in client.get("/api/export").headers["content-disposition"]
    assert (
        client.get("/api/state", headers={"origin": "https://foreign.invalid"}).status_code == 403
    )


def test_mrr_unknown_before_relevant_and_empty_rankings(catalogue):
    session = catalogue.create("rag010", evaluator="test")
    session.change(revision=0, position=0, comment="", grade=3)
    reference = consolidate(catalogue)
    runs, ids = ranking_data(catalogue)
    qid, did = session.order[0]
    unknown = next(d for d in ids if d != did)
    for rankings in runs.values():
        rankings[qid] = [unknown, did]
    report = evaluate_report(reference, runs, catalogue.queries, catalogue.sample)
    row = report["methods"]["lexical"]["per_query"][qid]["5"]
    assert row["strict"]["mrr"] is None
    assert row["descriptive_judged_only"]["condensed_mrr"] == 1
    for rankings in runs.values():
        rankings[qid] = []
    row = evaluate_report(reference, runs, catalogue.queries, catalogue.sample)["methods"][
        "lexical"
    ]["per_query"][qid]["5"]
    assert row["coverage"]["returned"] == 0 and row["coverage"]["fraction"] is None


def test_reports_never_overwrite_existing_outputs(catalogue, tmp_path):
    from cahier_rag.annotation.campaign_cli import write_bundle

    output = tmp_path / "export"
    write_bundle(output, {"judgments.json": []})
    original = (output / "judgments.json").read_bytes()
    with pytest.raises(FileExistsError):
        write_bundle(output, {"judgments.json": [{"changed": True}]})
    assert (output / "judgments.json").read_bytes() == original


def test_cli_creation_export_consolidation_and_reports_preserve_sources(
    catalogue, tmp_path, monkeypatch, capsys
):
    import cahier_rag.annotation.campaign_cli as cli

    monkeypatch.setattr(cli, "load_queries", lambda *_: catalogue.queries)
    monkeypatch.setattr(cli, "load_sample", lambda *_: catalogue.sample)
    monkeypatch.setattr(cli, "CorpusScope", lambda *_: None)
    monkeypatch.setattr(cli, "Catalogue", lambda *_: catalogue)

    def run(*args):
        return cli.main(["--root", str(tmp_path), *args])

    assert run("list") == 0
    assert not catalogue.get("rag014").folder.exists()
    assert run("create", "--campaign", "rag014", "--evaluator", "test") == 0
    session = catalogue.session("rag014", evaluator="test")
    session.change(revision=0, position=0, comment="SHOULDNOTLOGCOMMENT", grade=2)
    before = session.path.read_bytes()
    assert run("create", "--campaign", "rag014", "--evaluator", "test") == 2
    assert run("export", "--campaign", "rag014", "--output", str(tmp_path / "export")) == 0
    assert run("consolidate", "--output", str(tmp_path / "reference")) == 0
    assert run("conflicts") == 0
    runs, _ = ranking_data(catalogue)
    monkeypatch.setattr(cli, "load_rankings", lambda *_: (runs, {}))
    assert run("report", "--output", str(tmp_path / "report")) == 0
    assert (tmp_path / "report/report.json").exists()
    assert session.path.read_bytes() == before
    assert "SHOULDNOTLOGCOMMENT" not in capsys.readouterr().out
    assert not catalogue.get("rag010").session_path.exists()


def test_campaign_report_chain_and_query_hash(catalogue):
    spec = catalogue.get("rag014")
    manifest = json.loads(spec.manifest.read_text())
    manifest.pop("queries_hash")
    runs = {"method": {"q0": []}}
    manifest["runs_hash"] = digest(runs)
    spec.manifest.write_text(json.dumps(manifest))
    folder = catalogue.root / "evaluation/local/rag014/development-replay"
    folder.mkdir()
    report = {
        "queries_hash": digest(catalogue.queries),
        "sample_hash": catalogue.sample["selected_hash"],
        "split": "development",
        "runs_hash": digest(runs),
    }
    (folder / "runs.json").write_text(json.dumps(runs))
    (folder / "report.json").write_text(json.dumps(report))
    assert catalogue.load_pool("rag014")
    report["queries_hash"] = "wrong"
    (folder / "report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="incompatible"):
        catalogue.load_pool("rag014")


def test_ranking_manifest_integrity_and_reserved_query_rejection(catalogue, tmp_path):
    from cahier_rag.annotation.reporting import load_rankings

    runs, _ = ranking_data(catalogue)
    folder = tmp_path / "rankings"
    folder.mkdir()
    report = {
        "runs_hash": digest(runs),
        "sample_hash": catalogue.sample["selected_hash"],
        "queries_hash": digest(catalogue.queries),
        "split": "development",
        "baselines": {},
        "configuration": {},
    }
    (folder / "runs.json").write_text(json.dumps(runs))
    (folder / "report.json").write_text(json.dumps(report))
    assert load_rankings(folder, catalogue.queries, catalogue.sample)[0] == runs
    runs["vector"]["reserved"] = []
    report["runs_hash"] = digest(runs)
    (folder / "runs.json").write_text(json.dumps(runs))
    (folder / "report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError):
        load_rankings(folder, catalogue.queries, catalogue.sample)


def test_judgment_never_propagates_to_another_query(catalogue):
    session = catalogue.create("rag010", evaluator="test")
    session.change(revision=0, position=0, comment="", grade=3)
    reference = consolidate(catalogue)
    runs, _ = ranking_data(catalogue)
    qid, did = session.order[0]
    other = next(q["query_id"] for q in catalogue.queries if q["query_id"] != qid)
    report = evaluate_report(reference, runs, catalogue.queries, catalogue.sample)
    row = report["methods"]["hybrid"]["per_query"][other]["5"]
    assert did in runs["hybrid"][other]
    assert row["coverage"]["judged"] == 0
    assert row["strict"]["mrr"] is None
