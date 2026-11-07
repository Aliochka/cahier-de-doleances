"""Global ranking invariants and actual candidate SQL in a disposable cluster."""

import math
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from cahier_rag.search.service.control import Budget, SearchBusy
from sqlalchemy import text

from multicorpus.adapters import GdnAdapter
from multicorpus.core import MultiSearch, merge, rrf, score_expression
from tests.test_documentary import isolated_databases  # noqa: F401


def row(corpus, doc, score, unit=None):
    return dict(
        corpus=corpus,
        document_id=doc,
        unit_id=unit or doc,
        key=f"{corpus}:{doc}",
        score=score,
        branch="lexical",
    )


def test_global_scores_not_corpus_ranks_and_no_quota():
    a = [row("1789", str(i), 1 - i / 1000) for i in range(70)]
    b = [row("2019", str(i), 0.2 - i / 1000) for i in range(70)]
    result = merge([a, b], 50)
    assert len(result) == 50 and all(r["corpus"] == "1789" for r in result)
    assert [r["rank"] for r in result] == list(range(1, 51))
    assert all(r["corpus"] == "1789" for r in rrf(result, [], 50))
    with pytest.raises(ValueError, match="duplicate"):
        merge([[a[0], a[0]]], 50)


def test_single_rrf_stable_identity_and_both_witnesses():
    a, b = row("1789", "same", 0.9), row("2019", "same", 0.8)
    left = merge([[a, b]], 50)
    right = merge([[dict(b, score=0.99, branch="vector"), dict(a, score=0.8, branch="vector")]], 50)
    result = rrf(left, right)
    assert len(result) == 2
    assert result[0]["key"] == "1789:same"  # exact rational tie, stable namespace
    assert math.isclose(result[0]["score"], 1 / 61 + 1 / 62)
    assert result[0]["witness_origin"] == "both"


class Encoder:
    calls = 0

    def encode_queries(self, items):
        self.calls += 1
        yield SimpleNamespace(vectors=[[1.0] + [0.0] * 1023])


class Adapter:
    def __init__(self, corpus):
        self.corpus = corpus
        self.last_sql = {}
        self.calls = []

    def identity(self, budget):
        self.calls.append("identity")
        return {"publication_authorized": False}

    def parse(self, q, budget):
        return ["mot"], ["'mot'"]

    def statistics(self, terms, budget):
        self.calls.append("stats")
        return (100, {"mot": 10}) if self.corpus == "2019" else (10, {"mot": 2})

    def lexical(self, terms, weights, depth, filters, budget):
        self.calls.append(("lexical", weights[0]))
        return [row(self.corpus, "1", 0.9)], {}

    def vector(self, vector, depth, filters, budget):
        self.calls.append("vector")
        return [dict(row(self.corpus, "1", 0.8), branch="vector")], {}

    def hydrate(self, ranked, budget, query):
        return {r["key"]: {"title": "test"} for r in ranked}


def test_shared_statistics_one_encoding_and_single_corpus_isolation():
    a, b, encoder = Adapter("2019"), Adapter("1789"), Encoder()
    engine = MultiSearch([a, b], encoder)
    result = engine.search("mot")
    assert encoder.calls == 1
    assert result["statistics"] == {"population": 110, "frequencies": {"mot": 12}}
    expected = math.log(1 + (110 - 12 + 0.5) / (12 + 0.5))
    assert ("lexical", expected) in a.calls and ("lexical", expected) in b.calls
    assert len(result["items"]) == 2
    b.calls = []
    engine.search("mot", corpus="2019", mode="lexical")
    assert b.calls == [] and encoder.calls == 1
    for kwargs in [
        {"corpus": "tous", "question": 1},
        {"corpus": "2019", "place": "Agen"},
        {"corpus": "1789", "question": 1},
        {"corpus": "unknown"},
        {"depth": 51},
    ]:
        with pytest.raises(ValueError):
            engine.search("mot", **kwargs)
    engine.lock.acquire()
    try:
        with pytest.raises(SearchBusy):
            engine.search("mot")
    finally:
        engine.lock.release()


def test_shared_score_union_metadata_and_text():
    params = {}
    sql = score_expression(
        ["'agen'", "'agricultur'"], [2.0, 3.0], params, "u.search_vector", "d.metadata_vector"
    )
    assert "OR d.metadata_vector" in sql and "ts_rank(" in sql and "ts_rank_cd(" not in sql
    assert params["total_weight"] == 5 and params["query"] == "'agen' | 'agricultur'"


def test_gdn_sql_groups_complete_answers_before_limits(isolated_databases):  # noqa: F811
    # First fixture database is new, private and empty. Never a working database.
    engine = isolated_databases[0].engine
    with engine.begin() as c:
        c.execute(text("CREATE EXTENSION vector"))
        c.execute(text("CREATE SCHEMA rag_full"))
        c.execute(
            text("""CREATE TABLE rag_full.documents(space_id text,document_id text,
          answer_id bigint,record jsonb,search_vector tsvector,primary key(space_id,document_id))""")
        )
        c.execute(
            text("""CREATE TABLE rag_full.segments(space_id text,document_id text,
          segment_index int,representation_id text,start_offset int,end_offset int,embedding vector(1024))""")
        )
        for i, answer, value in [
            (1, 91, "agriculture agriculture"),
            (2, 91, "agriculture"),
            (3, 92, "agriculture"),
            (4, 93, "autre"),
        ]:
            c.execute(
                text(
                    "INSERT INTO rag_full.documents VALUES('full',:id,:answer,jsonb_build_object('question_id',1),to_tsvector('french',:value))"
                ),
                dict(id=str(i), answer=answer, value=value),
            )
            c.execute(
                text(
                    "INSERT INTO rag_full.segments VALUES('full',:id,0,:id,0,10,CAST(:v AS vector))"
                ),
                dict(id=str(i), v="[" + ",".join(["1"] + ["0"] * 1023) + "]"),
            )

    class TestAdapter(GdnAdapter):
        @contextmanager
        def connection(self, budget):
            with engine.connect() as c, c.begin():
                c.execute(text("SET TRANSACTION READ ONLY"))
                yield c

    adapter = TestAdapter(SimpleNamespace(source=engine))
    filters = dict(question=1)
    terms, quotes = adapter.parse("agriculture", Budget())
    results, trace = adapter.lexical(quotes, [1], 1, filters, Budget())
    assert len(results) == 1 and results[0]["document_id"] == "91"
    results, trace = adapter.lexical(quotes, [1], 50, filters, Budget())
    assert {r["document_id"] for r in results} == {"91", "92"}
    # Scope <=5000 uses existing exact-question protection, not an ANN reconstruction.
    results, trace = adapter.vector([1.0] + [0.0] * 1023, 50, filters, Budget())
    assert trace["mode"] == "exact-question" and len(results) == 3
    assert len({r["document_id"] for r in results}) == 3
    assert trace["retrieved_segments"] == 4
    # Source safety guard must now reject this test DB: it contains RAG structures.
    from documentary.safety import UnsafeDestination

    with pytest.raises(UnsafeDestination):
        with isolated_databases[0].transaction():
            pass


def test_local_endpoints_refuse_remote_before_connect(tmp_path):
    from multicorpus.adapters import DocumentaryAdapter
    from multicorpus.environment import hydration_engine, local_reader

    for url in [
        "postgresql://cahier_search_reader@production:5432/cahier_rag",
        "postgresql://cahier_search_reader@127.0.0.1:5432/cahier_rag?service=production",
        "postgresql://owner@127.0.0.1:5432/cahier_rag",
    ]:
        config = tmp_path / "reader.env"
        config.write_text("RAG_SOURCE_DATABASE_URL=" + url + "\nRAG_DATABASE_URL=" + url + "\n")
        with pytest.raises(ValueError):
            local_reader(config, {})
    with pytest.raises(ValueError):
        hydration_engine("postgresql+psycopg2://localhost/production", {"database_name": "local"})
    with pytest.raises(ValueError, match="validator"):
        DocumentaryAdapter(None, scope={"corpus": "future", "release": "unverified"})


def test_http_local_only_and_no_public_route():
    import json
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    from multicorpus.lab import Handler

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.search = MultiSearch([Adapter("2019"), Adapter("1789")], Encoder())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        for path, headers, status in [
            ("/", {"Host": "foreign.example"}, 403),
            ("/api/search?q=mot", {"Origin": "https://foreign.example"}, 403),
            ("/api/search?q=mot", {"Sec-Fetch-Site": "cross-site"}, 403),
            ("/api/v1/search?q=mot", {}, 404),
            ("/api/search?q=mot&corpus=2019&place=Agen", {}, 422),
        ]:
            with pytest.raises(HTTPError) as ex:
                urlopen(Request(url + path, headers=headers))
            assert ex.value.code == status
        with urlopen(url + "/api/search?q=mot&mode=compare") as response:
            result = json.load(response)
        assert len(result["items"]) == 2 and result["laboratory_only"]
        assert result["publication"]["1789"]["publication_authorized"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
