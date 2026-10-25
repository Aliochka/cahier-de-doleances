"""H1 corpus complet : lexical historique, cosinus exact/ANN explicite, RRF 60."""

import time

from sqlalchemy import text

from cahier_rag.contracts import UnitType, validate_id
from cahier_rag.search.flexible import WEIGHTS
from cahier_rag.search.hybrid.core import fuse
from cahier_rag.search.lexical import SearchResult
from cahier_rag.search.preparation import normalize, tokenize
from cahier_rag.storage import restore_document

FILTERS = """d.space_id=:space AND (:form IS NULL OR d.questionnaire_id=:form)
 AND (:kind IS NULL OR d.unit_type=:kind)
 AND (:split IS NULL OR d.historical_split=:split)
 AND (:question IS NULL OR CAST(d.record->>'question_id' AS bigint)=:question)"""


class FullSearch:
    def __init__(self, store):
        self.store = store

    def parameters(self, limit, questionnaire_id, unit_type, split, question_id=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Limite entre 1 et 100.")
        if questionnaire_id is not None:
            validate_id(questionnaire_id, "questionnaire_id")
        if question_id is not None:
            validate_id(question_id, "question_id")
        if split not in (None, "development", "evaluation"):
            raise ValueError("Partition inconnue.")
        state = self.store.state()
        if not state["verified"]:
            raise ValueError("Index complet et vérifié requis pour la recherche.")
        return dict(
            space=self.store.space,
            form=questionnaire_id,
            question=question_id,
            kind=UnitType(unit_type).value if unit_type else None,
            split=split,
            limit=limit,
            n=state["documents"],
        )

    @staticmethod
    def _results(c, ids):
        if not ids:
            return []
        rows = (
            c.execute(
                text(
                    "SELECT document_id,record FROM rag_full.documents "
                    "WHERE space_id=:space AND document_id=ANY(:ids)"
                ),
                dict(space=ids[0][2], ids=[r[0] for r in ids]),
            )
            .mappings()
            .all()
        )
        documents = {r["document_id"]: restore_document(r["record"]) for r in rows}
        return [SearchResult(documents[did], float(score)) for did, score, _ in ids]

    def lexical(self, query, *, limit=50, questionnaire_id=None, unit_type=None, split=None):
        params = self.parameters(limit, questionnaire_id, unit_type, split)
        tokens = tokenize(query)
        with self.store.guard.transaction() as (c, _):
            c.execute(text("SET LOCAL statement_timeout='30s'"))
            parsed = normalize(c, tokens)
            if not parsed["query"]:
                return []
            params.update(parsed, **WEIGHTS)
            pop = "SELECT CAST(:n AS float8) AS n"
            if any(params[k] is not None for k in ("form", "kind", "split")):
                pop = f"SELECT count(*)::float8 AS n FROM rag_full.documents d WHERE {FILTERS}"
            sql = f"""WITH population AS MATERIALIZED ({pop}),
             term_stats AS MATERIALIZED (
               SELECT term,ln(1.0+(p.n-v.df+0.5)/(v.df+0.5)) AS idf
               FROM unnest(CAST(:terms AS text[])) term CROSS JOIN population p
               CROSS JOIN LATERAL (SELECT count(*)::float8 AS df FROM rag_full.documents d
                 WHERE {FILTERS} AND d.search_vector @@ CAST(quote_literal(term) AS tsquery)) v)
             SELECT d.document_id,
               (SELECT :idf_coverage*coalesce(sum(t.idf) FILTER(WHERE d.search_vector @@ CAST(quote_literal(t.term) AS tsquery)),0)/sum(t.idf)
                 + :term_coverage*count(*) FILTER(WHERE d.search_vector @@ CAST(quote_literal(t.term) AS tsquery))::float8/count(*)
                FROM term_stats t)
                + :frequency_proximity*ts_rank_cd(d.search_vector,CAST(:query AS tsquery),32)::float8 AS score
             FROM rag_full.documents d WHERE {FILTERS}
               AND d.search_vector @@ CAST(:query AS tsquery)
             ORDER BY score DESC,d.document_id COLLATE "C" LIMIT :limit"""
            rows = c.execute(text(sql), params).all()
            return self._results(c, [(r[0], r[1], self.store.space) for r in rows])

    def vector(
        self,
        vector,
        *,
        limit=50,
        questionnaire_id=None,
        unit_type=None,
        split=None,
        ann=False,
        ef_search=400,
    ):
        from cahier_rag.embeddings.core import validate_vectors

        values = validate_vectors([vector], expected_rows=1, dimension=1024, normalize=False)[0]
        params = self.parameters(limit, questionnaire_id, unit_type, split)
        params["vector"] = "[" + ",".join(str(x) for x in values) + "]"
        if type(ef_search) is not int or not 40 <= ef_search <= 1000:
            raise ValueError("ef_search entre 40 et 1000.")
        with self.store.guard.transaction() as (c, _):
            c.execute(text("SET LOCAL statement_timeout='30s'"))
            if ann:
                # Explicit opt-in; a missing index must not masquerade as ANN.
                name = f"segments_{self.store.space}_hnsw"
                exists = c.execute(
                    text("SELECT to_regclass(:name)"), {"name": "rag_full." + name}
                ).scalar_one()
                if not exists:
                    raise ValueError("Index HNSW absent.")
                c.execute(
                    text("SELECT set_config('hnsw.ef_search',:ef,true)"), {"ef": str(ef_search)}
                )
                c.execute(text("SET LOCAL hnsw.iterative_scan='strict_order'"))
                c.execute(text("SET LOCAL enable_seqscan=off"))
                params["candidates"] = min(50000, limit * 8)
                while True:
                    rows = c.execute(
                        text(f"""WITH nearest AS MATERIALIZED (
                      SELECT s.document_id,s.embedding <=> CAST(:vector AS public.vector) AS distance
                      FROM rag_full.segments s JOIN rag_full.documents d USING(space_id,document_id)
                      WHERE {FILTERS} ORDER BY s.embedding <=> CAST(:vector AS public.vector)
                      LIMIT :candidates)
                      SELECT document_id,1-min(distance) AS score FROM nearest GROUP BY document_id
                      ORDER BY score DESC,document_id COLLATE "C" LIMIT :limit"""),
                        params,
                    ).all()
                    if len(rows) >= limit or params["candidates"] >= 50000:
                        break
                    params["candidates"] = min(50000, params["candidates"] * 2)
            else:
                c.execute(text("SET LOCAL enable_indexscan=off"))
                c.execute(text("SET LOCAL enable_bitmapscan=off"))
                # Exact segment top-N first: no GROUP BY of five million units.
                # Once >=k distinct units are present, all unit top-k maxima
                # are included. Distance/document/segment order resolves ties.
                joins = ""
                filters = "s.space_id=:space"
                if any(params[key] is not None for key in ("form", "kind", "split")):
                    joins = "JOIN rag_full.documents d USING(space_id,document_id)"
                    filters = FILTERS
                params["candidates"] = limit * 8
                while True:
                    rows = c.execute(
                        text(f"""WITH nearest AS MATERIALIZED (
                        SELECT s.document_id,s.embedding <=> CAST(:vector AS public.vector) AS distance
                        FROM rag_full.segments s {joins} WHERE {filters}
                        ORDER BY distance,s.document_id COLLATE "C",s.segment_index LIMIT :candidates)
                        SELECT document_id,1-min(distance) AS score,
                        (SELECT count(*) FROM nearest) AS segment_count
                        FROM nearest GROUP BY document_id
                        ORDER BY score DESC,document_id COLLATE "C" LIMIT :limit"""),
                        params,
                    ).all()
                    if not rows or len(rows) >= limit or rows[0][2] < params["candidates"]:
                        break
                    params["candidates"] *= 2
            return self._results(c, [(r[0], r[1], self.store.space) for r in rows])

    def hybrid(self, query, vector, *, depth=50, ann=False, **filters):
        started = time.perf_counter()
        lexical = self.lexical(query, limit=depth, **filters)
        middle = time.perf_counter()
        dense = self.vector(vector, limit=depth, ann=ann, **filters)
        end = time.perf_counter()
        results, traces = fuse({"lexical": lexical, "vector": dense}, k=60)
        return (
            results,
            traces,
            dict(
                lexical_seconds=middle - started,
                vector_seconds=end - middle,
                fusion_seconds=time.perf_counter() - end,
                total_seconds=time.perf_counter() - started,
                common=len(
                    {r.document.document_id for r in lexical}
                    & {r.document.document_id for r in dense}
                ),
            ),
        )
