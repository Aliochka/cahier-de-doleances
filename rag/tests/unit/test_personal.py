"""Recette personnelle, reprises et interface sur données synthétiques uniquement."""

import json
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.evaluation.sampling import describe, digest
from cahier_rag.generation.contracts import GenerationInput
from cahier_rag.personal.campaign import Cache, answer
from cahier_rag.personal.contracts import Input, schema, validate
from cahier_rag.personal.live import live_context, merge_vector_partitions
from cahier_rag.search.lexical import CorpusScope, SearchResult


def original():
    source = {
        "reference": "S01",
        "answer": "Non. Garder un accueil humain.",
        "question": "Tout numériser ?",
        "questionnaire": "Services",
        "incomplete": False,
    }
    return GenerationInput(
        "synthetic", "Une question libre et nouvelle ?", {"sources": [source], "citation_map": {}}
    )


def output():
    return {
        "blocks": [
            {
                "kind": "reported_opinion",
                "text": "Une réponse demande de garder un accueil humain.",
                "references": ["S01"],
                "quotes": [],
            }
        ],
        "limits": [],
        "insufficient_sources": False,
    }


def test_sentence_ends_and_no_600_ceiling():
    item = Input(original())
    v = output()
    v["blocks"][0]["text"] = "Une proposition. " * 50
    assert validate(json.dumps(v), item) == v
    assert (
        schema(item)["properties"]["blocks"]["items"]["properties"]["text"].get("maxLength") is None
    )
    v["blocks"][0]["text"] = "Une proposition coupée au"
    with pytest.raises(ValueError, match="unfinished_sentence"):
        validate(json.dumps(v), item)
    with pytest.raises(ValueError, match="output_token_limit"):
        validate(json.dumps(output()), item, token_limit_reached=True)


@pytest.mark.parametrize("refs", [["S99"], ["S01", "S01"], []])
def test_final_references_remain_strict(refs):
    value = output()
    value["blocks"][0]["references"] = refs
    with pytest.raises(ValueError):
        validate(json.dumps(value), Input(original()))


def test_analysis_references_and_original_sources():
    item = Input(original(), "analysis")
    value = {
        "items": [
            {
                "reference": "S01",
                "stance": "opposition",
                "statement": "Refus de tout numériser.",
                "conditions": "",
            }
        ]
    }
    assert validate(json.dumps(value), item) == value
    messages = Input(original(), "synthesis", value).messages()
    payload = json.loads(messages[1]["content"])
    assert payload["sources"] == original().document["sources"]
    assert payload["fallible_analysis_verify_against_original_sources"] == value
    value["items"][0]["reference"] = "S99"
    with pytest.raises(ValueError, match="invalid_analysis_reference"):
        validate(json.dumps(value), item)


def test_cache_resume_and_two_steps(tmp_path):
    class Backend:
        calls = []

        def recipe(self):
            return {"version": "synthetic"}

        def generate_one(self, item):
            self.calls.append(item.stage)
            v = (
                {
                    "items": [
                        {
                            "reference": "S01",
                            "stance": "opposition",
                            "statement": "Garder un accueil.",
                            "conditions": "",
                        }
                    ]
                }
                if item.stage == "analysis"
                else output()
            )
            return {"raw_output": json.dumps(v), "token_limit_reached": False}

    backend = Backend()
    path = tmp_path / "rag025/results.sqlite3"
    cache = Cache(path)
    result = answer(original(), backend, cache, method="two-step")
    cache.close()
    assert result["status"] == "valid" and backend.calls == ["analysis", "synthesis"]
    cache = Cache(path)
    resumed = answer(original(), backend, cache, method="two-step")
    cache.close()
    assert all(s["reused"] for s in resumed["stages"]) and backend.calls == [
        "analysis",
        "synthesis",
    ]
    with pytest.raises(ValueError):
        Cache(tmp_path / "rag023/cache.sqlite3")


def test_invalid_output_preserved_and_not_repaired(tmp_path):
    class Broken:
        calls = 0

        def recipe(self):
            return {"version": "invalid-test"}

        def generate_one(self, item):
            self.calls += 1
            return {"raw_output": '{"blocks":[', "token_limit_reached": True}

    backend = Broken()
    cache = Cache(tmp_path / "rag025/results.sqlite3")
    try:
        first = answer(original(), backend, cache)
        assert (
            first["status"] == "invalid"
            and first["stages"][0]["record"]["raw_output"] == '{"blocks":['
        )
        assert answer(original(), backend, cache)["stages"][0]["reused"] and backend.calls == 1
    finally:
        cache.close()


def unit():
    return TextUnit(
        "test",
        UnitType.OPEN_ANSWER,
        MAX_BIGINT,
        MAX_BIGINT - 1,
        101,
        4,
        "Non. Garder un accueil humain.",
        "Tout numériser ?",
        "Services",
        0,
        "text",
    )


def test_free_context_accepts_both_document_partitions_without_query_catalog():
    a = unit()
    b = replace(
        a,
        answer_id=MAX_BIGINT - 2,
        contribution_id=MAX_BIGINT - 3,
        text="Oui, avec un guichet maintenu.",
    )
    rows = [describe(a) | {"split": "development"}, describe(b) | {"split": "evaluation"}]
    scope = CorpusScope(
        {"documents": rows, "selected_hash": digest(rows)},
        expected_size=2,
        expected_hash=digest(rows),
    )
    counter = SimpleNamespace(count=lambda text: len(text) // 4, description={"synthetic": True})
    document, context = live_context(
        "Question personnelle absente de tout catalogue.",
        [SearchResult(a, 2), SearchResult(b, 1)],
        scope,
        counter,
    )
    assert context["query_partition"] is None and context["purpose"] == "personal-free-query"
    assert len(document["sources"]) == 2
    assert document["sources"][0]["answer"] == a.text
    assert document["citation_map"]["S01"]["source"]["metadata"]["answer_id"] == str(MAX_BIGINT)
    merged = merge_vector_partitions([[SearchResult(a, 0.5)], [SearchResult(b, 0.8)]])
    assert merged[0].document == b
    with pytest.raises(ValueError):
        merge_vector_partitions([[SearchResult(a, 0.5)], [SearchResult(a, 0.5)]])


def test_local_ui_free_question_and_security():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from cahier_rag.personal.web import create_app

    called = []

    def service(query, progress):
        called.append(query)
        progress("Synthèse")
        return {
            "answer": output(),
            "sources": [],
            "citation_map": {},
            "timings": {"total_seconds": 0.1},
        }

    app = create_app(service)
    with TestClient(app, base_url="http://127.0.0.1:8770", client=("127.0.0.1", 1234)) as client:
        assert client.get("/").status_code == 200
        token = client.get("/api/state").json()["token"]
        headers = {"X-Rag-Token": token}
        assert client.post("/api/ask", json={"query": "libre"}).status_code == 403
        assert (
            client.post(
                "/api/ask",
                json={"query": "libre"},
                headers={**headers, "Origin": "http://evil.example"},
            ).status_code
            == 403
        )
        assert client.get("/api/state", headers={"Host": "evil.example"}).status_code == 403
        assert client.post("/api/ask", json={"query": ""}, headers=headers).status_code == 400
        result = client.post(
            "/api/ask", json={"query": "Question libre nouvelle."}, headers=headers
        )
        assert result.status_code == 202
        job = result.json()["job_id"]
        for _ in range(100):
            state = client.get("/api/jobs/" + job).json()
            if state["status"] != "running":
                break
            time.sleep(0.005)
        assert state["status"] == "complete" and called == ["Question libre nouvelle."]
        assert "textContent" in client.get("/ui.js").text
        assert "innerHTML" not in client.get("/ui.js").text


def test_local_ui_reports_failure_without_secret():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from cahier_rag.personal.web import create_app

    def fail(query, progress):
        raise ValueError("postgresql://secret:password@server")

    with TestClient(
        create_app(fail), base_url="http://127.0.0.1:8770", client=("127.0.0.1", 1234)
    ) as client:
        headers = {"X-Rag-Token": client.get("/api/state").json()["token"]}
        job = client.post("/api/ask", json={"query": "libre"}, headers=headers).json()["job_id"]
        for _ in range(100):
            response = client.get("/api/jobs/" + job)
            if response.json()["status"] != "running":
                break
            time.sleep(0.005)
        assert response.json()["status"] == "error" and "password" not in response.text
