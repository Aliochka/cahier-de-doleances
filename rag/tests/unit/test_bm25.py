"""Formule indépendante et index synthétique sans PostgreSQL ou modèles."""

import json
import math
import re
from dataclasses import replace

import pytest

from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.evaluation.sampling import describe, digest
from cahier_rag.search.bm25.experiments import complement_pairs, validate_runs
from cahier_rag.search.bm25.index import BM25Index, Config, bm25
from cahier_rag.search.lexical import CorpusScope


class Tokens:
    configuration = {"synthetic": 1}

    def encode(self, values):
        return [re.findall(r"\w+", v.lower()) for v in values]

    def query(self, value):
        return sorted(set(self.encode([value])[0])), [], []


@pytest.fixture
def corpus():
    base = TextUnit(
        corpus_id="test",
        unit_type=UnitType.OPEN_ANSWER,
        answer_id=MAX_BIGINT,
        contribution_id=MAX_BIGINT,
        question_id=1,
        questionnaire_id=4,
        text="bus rural",
        question_text="écologie transport",
        questionnaire_name="Questionnaire",
        answer_position=0,
        question_type="text",
    )
    docs = [
        base,
        replace(base, answer_id=MAX_BIGINT - 1, contribution_id=MAX_BIGINT - 1),
        replace(
            base,
            answer_id=MAX_BIGINT - 2,
            contribution_id=MAX_BIGINT - 2,
            text="bus " * 1000,
            questionnaire_id=5,
        ),
        replace(
            base,
            answer_id=MAX_BIGINT - 3,
            contribution_id=MAX_BIGINT - 3,
            text="oui",
            unit_type=UnitType.OTHER_TEXT,
        ),
        replace(
            base, answer_id=MAX_BIGINT - 4, contribution_id=MAX_BIGINT - 4, text="autre évaluation"
        ),
    ]
    rows = [
        describe(d) | {"split": "development" if i < 4 else "evaluation"}
        for i, d in enumerate(docs)
    ]
    scope = CorpusScope(
        {"documents": rows, "selected_hash": digest(rows)},
        expected_hash=digest(rows),
        expected_size=5,
    )

    class Repo:
        def fetch(self, ids):
            assert len(ids) <= 100
            return {d.document_id: d for d in docs if d.document_id in ids}

    return docs, scope, Repo()


def test_formula_known_and_limits():
    assert bm25(2, 3, 10, 8, 5) == pytest.approx(
        math.log1p(7.5 / 3.5) * 4.4 / (2 + 1.2 * (0.25 + 0.75 * 8 / 5))
    )
    assert bm25(0, 1, 10, 1, 1) == 0 and bm25(1, 1, 0, 0, 0) == 0
    assert bm25(1, 9, 10, 10, 10) > 0
    assert bm25(2, 1, 10, 10, 10) > bm25(1, 1, 10, 10, 10)
    assert bm25(1, 1, 10, 100, 10) < bm25(1, 1, 10, 1, 10)
    with pytest.raises(ValueError):
        Config(k1=2)


@pytest.mark.parametrize("variant", ["A", "B"])
def test_index_formula_reprise_determinism_filters(corpus, tmp_path, variant):
    docs, scope, repo = corpus
    index = BM25Index(tmp_path / "index.sqlite3", scope, Tokens(), Config(variant), writable=True)
    try:
        index.build(repo, batch_size=1, stop_after=1)
        with pytest.raises(ValueError, match="incomplet"):
            index.search("bus")
        index.build(repo, batch_size=2)
        manifest = index.verify()
        assert manifest["documents"] == 5
        found = index.search("bus", limit=100)
        assert len(found) == 3 and found == index.search("bus", limit=100)
        tied = index.search("bus", questionnaire_id=4)
        assert [r.document.document_id for r in tied] == sorted(
            d.document_id for d in docs[:2]
        )
        tokens = Tokens().encode(
            [d.text + ("\n" + d.question_text if variant == "B" else "") for d in docs[:4]]
        )
        for result in found:
            ts = tokens[docs.index(result.document)]
            assert result.score == pytest.approx(
                bm25(ts.count("bus"), 3, 4, len(ts), sum(map(len, tokens)) / 4)
            )
        assert len(index.search("bus", questionnaire_id=5)) == 1
        assert index.search("bus", unit_type="other_text") == []
        assert len(index.search("oui", unit_type="other_text")) == 1
        assert len(index.search("autre", split="evaluation")) == 1
        assert index.search("autre") == [] and index.search("") == []
        assert len(index.search("transport")) == (4 if variant == "B" else 0)
        assert str(MAX_BIGINT) in json.dumps([r.to_dict() for r in found])
        before = manifest["index_hash"]
        assert index.build(repo)["added"] == 0 and index.verify()["index_hash"] == before
    finally:
        index.close()
    readonly = BM25Index(tmp_path / "index.sqlite3", scope, Tokens(), Config(variant))
    assert readonly.verify()["index_hash"] == before
    readonly.close()


def test_integrity_scope_recipe_and_frequencies(corpus, tmp_path):
    docs, scope, repo = corpus
    path = tmp_path / "index.sqlite3"
    index = BM25Index(path, scope, Tokens(), writable=True)
    index.build(repo)
    with pytest.raises(ValueError, match="incompatibles"):
        BM25Index(path, scope, Tokens(), Config("B"))
    index.db.execute("UPDATE postings SET tf=tf+1 WHERE id=?", (docs[0].document_id,))
    index.db.commit()
    with pytest.raises(ValueError, match="modifiés"):
        index.verify()
    index.close()


def test_failure_batch_is_atomic(corpus, tmp_path):
    docs, scope, repo = corpus

    class Bad:
        def fetch(self, ids):
            values = repo.fetch(ids)
            key = sorted(values)[-1]
            values[key] = replace(values[key], text="modifié")
            return values

    index = BM25Index(tmp_path / "index.sqlite3", scope, Tokens(), writable=True)
    with pytest.raises(ValueError):
        index.build(Bad(), batch_size=100)
    assert index.db.execute("SELECT count(*) FROM documents").fetchone()[0] == 0
    index.close()


def test_pool_reuses_known_invalid_without_repair_and_deduplicates():
    runs = {"bm25-A": {"q": ["a", "b", "c"]}, "bm25-B": {"q": ["b", "d", "c"]}}
    old = {
        "entries": [{"query_id": "q", "document_id": "a"}, {"query_id": "q", "document_id": "b"}]
    }
    rows, counts = complement_pairs(runs, old)
    assert [(r["query_id"], r["document_id"]) for r in rows] == [("q", "c"), ("q", "d")]
    assert len(rows[0]["origins"]) == 2 and counts["historical_pairs_reused"] == 2
    assert complement_pairs(runs, old) == (rows, counts)


def test_reserved_query_or_document_refused(corpus):
    docs, scope, _ = corpus
    runs = {m: {"q": [docs[-1].document_id]} for m in ("lexical", "vector", "bm25-A", "bm25-B")}
    with pytest.raises(ValueError):
        validate_runs(runs, scope, [{"query_id": "q", "split": "development"}])
