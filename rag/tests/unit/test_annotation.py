"""Sessions et parcours HTTP synthétiques, sans aucun jugement réel."""

import copy
import json
from pathlib import Path

import pytest

from cahier_rag.annotation.session import Session, atomic_json
from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.evaluation.files import load_judgments
from cahier_rag.evaluation.sampling import describe, digest


@pytest.fixture
def data():
    docs = [
        TextUnit(
            corpus_id="synthetic",
            unit_type=UnitType.OPEN_ANSWER,
            answer_id=MAX_BIGINT - i,
            contribution_id=MAX_BIGINT - i - 10,
            question_id=1,
            questionnaire_id=4,
            text="é <script>alert(1)</script>\n" + "long " * 10000,
            question_text="Pourquoi ?",
            questionnaire_name="Fiscalité",
            answer_position=0,
            question_type="text",
            contribution_title="Un titre",
        )
        for i in range(4)
    ]
    selected = [describe(d) | {"split": "development"} for d in docs]
    sample = {"documents": selected, "selected_hash": digest(selected)}
    queries = [
        {
            "query_id": f"q{i}",
            "text": f"Requête {i}",
            "split": "development",
            "version": "v1",
            "category": "thème",
            "domain": "fiscalité",
            "family": str(i),
        }
        for i in range(2)
    ]
    pool = [
        dict(
            d,
            query_id=q["query_id"],
            found_by=[{"method": "SECRET", "rank": 1}],
            score=999,
            random_control=True,
        )
        for q in queries
        for d in selected
    ]
    return pool, queries, sample, docs


def make(data, tmp_path, **kwargs):
    return Session(
        *data[:3],
        tmp_path / "session.json",
        evaluator="local",
        expected_count=len(data[0]),
        **kwargs,
    )


def test_order_reproducible_and_blind(data, tmp_path):
    a = make(data, tmp_path, seed=27)
    other = copy.deepcopy(data)
    other[0].reverse()
    b = make(other, tmp_path / "other", seed=27)
    assert a.order == b.order
    assert [p[0] for p in a.order] == sorted(p[0] for p in a.order)
    assert "SECRET" not in json.dumps(a.view())
    assert all(
        set(c) == {"query_id", "document_id", "content_hash", "corpus_id", "contribution_id"}
        for c in a.candidates.values()
    )
    assert make(data, tmp_path, seed=27).order == a.order
    with pytest.raises(ValueError):
        make(data, tmp_path, seed=28)


@pytest.mark.parametrize("grade", [0, 1, 2, 3])
def test_save_resume_modify_export(data, tmp_path, grade):
    session = make(data, tmp_path)
    session.change(revision=0, position=0, comment="é\ncommentaire", grade=grade)
    resumed = make(data, tmp_path)
    assert resumed.view()["position"] == 1
    assert resumed.view()["done"] == 1
    resumed.change(revision=1, position=1, comment="brouillon", destination=0)
    assert resumed.view()["draft"] == "é\ncommentaire"
    resumed.change(revision=2, position=0, comment="modifié", grade=3, destination=0)
    assert len(resumed.export()) == 1
    assert resumed.export()[0]["grade"] == 3
    resumed.change(revision=3, position=0, comment="commentaire seul")
    assert resumed.export()[0]["justification"] == "commentaire seul"
    output = tmp_path / "judgments.json"
    atomic_json(output, resumed.export())
    rows, _ = load_judgments(output, data[1], data[2])
    assert rows == resumed.export()
    assert rows[0]["document_id"] == session.order[0][1]
    assert int(rows[0]["document_id"].split(":")[-2]) > 2**53


@pytest.mark.parametrize("grade", [-1, 4, 1.2, True, "1"])
def test_invalid_grade(data, tmp_path, grade):
    session = make(data, tmp_path)
    with pytest.raises(ValueError):
        session.change(revision=0, position=0, comment="", grade=grade)
    assert session.export() == []


def test_atomic_failure_and_stale_tabs(data, tmp_path, monkeypatch):
    session = make(data, tmp_path)
    before = session.path.read_bytes()
    import cahier_rag.annotation.session as module

    def fail(*args):
        raise OSError("disk full secret")

    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError):
        session.change(revision=0, position=0, comment="comment", grade=2)
    assert session.path.read_bytes() == before
    assert session.export() == []
    assert not list(tmp_path.glob(".annotation-*"))
    monkeypatch.undo()
    session.change(revision=0, position=0, comment="brouillon", destination=2)
    assert make(data, tmp_path).state["drafts"]
    with pytest.raises(ValueError):
        session.change(revision=0, position=0, comment="", grade=0)


def test_reject_bad_candidates_and_corrupt_state(data, tmp_path):
    for transform in (
        lambda p: p.append(p[0]),
        lambda p: p[0].update(content_hash="bad"),
        lambda p: p[0].update(query_id="unknown"),
    ):
        bad = copy.deepcopy(data)
        transform(bad[0])
        with pytest.raises(ValueError):
            make(bad, tmp_path)
    a = make(data, tmp_path)
    a.state["judgments"] = [{"query_id": "unknown"}]
    atomic_json(a.path, a.state)
    with pytest.raises(ValueError):
        make(data, tmp_path)


@pytest.fixture
def client(data, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from cahier_rag.annotation.web import create_app

    session = make(data, tmp_path)

    class Reader:
        def get(self, pair, parent=False):
            return [next(d.to_dict() for d in data[3] if d.document_id == pair[1])]

    with TestClient(
        create_app(session, Reader()), base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)
    ) as client:
        yield client, session


def test_http_workflow_and_blindness(client):
    c, session = client
    state = c.get("/api/state").json()
    assert "SECRET" not in json.dumps(state)
    doc = c.get("/api/document?position=0").json()["documents"][0]
    assert len(doc["text"]) > 40000
    assert int(doc["answer_id"]) > 2**53
    assert c.get("/api/document?position=0&parent=true").status_code == 200
    headers = {"x-annotation-token": state["token"], "origin": "http://127.0.0.1:8765"}
    r = c.post(
        "/api/change",
        headers=headers,
        json={"position": 0, "revision": 0, "grade": 2, "comment": "oui"},
    )
    assert r.status_code == 200 and r.json()["position"] == 1
    assert c.get("/api/export").json() == session.export()
    assert c.get("/").headers["cache-control"] == "no-store"
    for path in ("/", "/ui.js", "/ui.css"):
        response = c.get(path)
        assert response.status_code == 200
        assert "SECRET" not in response.text and "found_by" not in response.text
    assert c.get("/api/document?position=-1").status_code == 409


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://evil.test"},
        {"host": "evil.test"},
        {"sec-fetch-site": "cross-site"},
        {"sec-fetch-site": "same-site"},
    ],
)
def test_origin_protection(client, headers):
    assert client[0].get("/api/state", headers=headers).status_code == 403


def test_csrf_invalid_grade_and_storage_failure(client, monkeypatch):
    c, session = client
    payload = {"position": 0, "revision": 0, "grade": 1, "comment": ""}
    assert c.post("/api/change", json=payload).status_code == 403
    token = c.get("/api/state").json()["token"]
    headers = {"x-annotation-token": token}
    assert c.post("/api/change", json=payload | {"grade": True}, headers=headers).status_code == 409

    def fail(*args):
        raise OSError("secret path password")

    monkeypatch.setattr("cahier_rag.annotation.session.atomic_json", fail)
    response = c.post("/api/change", json=payload, headers=headers)
    assert response.status_code == 503
    assert "secret" not in response.text
    assert session.export() == []


def test_database_failure(data, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from sqlalchemy.exc import OperationalError

    from cahier_rag.annotation.web import create_app

    class Broken:
        def get(self, *args, **kwargs):
            raise OperationalError("secret SQL", {}, Exception("password"))

    with TestClient(
        create_app(make(data, tmp_path), Broken()),
        base_url="http://127.0.0.1:8765",
        client=("127.0.0.1", 1),
    ) as c:
        response = c.get("/api/document?position=0")
        assert response.status_code == 503 and "secret" not in response.text


def test_real_pool_readonly_validation(tmp_path):
    from cahier_rag.evaluation.cli import load_sample
    from cahier_rag.evaluation.files import load_json, load_queries
    from cahier_rag.search.lexical import CorpusScope

    root = Path(__file__).resolve().parents[2]
    path = root / "evaluation/local/rag009/annotations/pool.json"
    if not path.exists():
        pytest.skip("Artefacts réels locaux absents")
    sample = load_sample(root / "evaluation/local/rag007/corpus.json")
    scope = CorpusScope(sample)
    pool = load_json(path)
    manifest = load_json(path.with_name("manifest.json"))
    assert digest(pool) == manifest["pool_hash"]
    assert scope.sample_hash == manifest["sample_hash"]
    queries = load_queries(root / "evaluation/queries.json")
    session = Session(pool, queries, sample, tmp_path / "synthetic-session.json", evaluator="test")
    assert len(session.order) == 400
    assert len({qid for qid, _ in session.order}) == 20
    assert all(g["total"] == 20 for g in session.view()["groups"])
    assert session.export() == []


def test_remote_client_is_refused(data, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from cahier_rag.annotation.web import create_app

    with TestClient(
        create_app(make(data, tmp_path), None),
        base_url="http://127.0.0.1:8765",
        client=("192.168.1.10", 1),
    ) as c:
        assert c.get("/").status_code == 403


def test_no_evaluation_candidates(data, tmp_path):
    changed = copy.deepcopy(data)
    changed[1][0]["split"] = "evaluation"
    with pytest.raises(ValueError):
        make(changed, tmp_path)
