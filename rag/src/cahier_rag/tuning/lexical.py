"""RAG-027 : formule conservée, statistiques figées et expressions sans sous-plan par ligne."""

import time

from sqlalchemy import text

from cahier_rag.fullcorpus.search import FILTERS, FullSearch
from cahier_rag.search.flexible import WEIGHTS
from cahier_rag.search.preparation import normalize, tokenize


class TunedSearch(FullSearch):
    """Recette distincte ; FullSearch reste la référence RAG-026."""

    def __init__(self, store, *, statistics=True, prefilter=None):
        super().__init__(store)
        if prefilter is not None and (type(prefilter) is not int or not 100 <= prefilter <= 100000):
            raise ValueError("Préfiltrage expérimental entre 100 et 100000.")
        self.statistics = statistics
        self.prefilter = prefilter
        self.last_lexical_timings = {}

    def _terms(self, c, params):
        if self.statistics and all(params[k] is None for k in ("form", "kind", "split")):
            state = self.store.state()
            manifest = (
                c.execute(
                    text("""SELECT documents,corpus_hash FROM rag_tuning.statistics
                WHERE space_id=:space"""),
                    params,
                )
                .mappings()
                .one_or_none()
            )
            if (
                manifest is None
                or manifest["documents"] != params["n"]
                or manifest["corpus_hash"] != state["chain_hash"]
            ):
                raise ValueError("Statistiques lexicales absentes ou incompatibles.")
            sql = """WITH term_stats AS (
                SELECT t.term,t.ord,ln(1.0+(:n-coalesce(s.documents,0)+0.5)::float8/
                    (coalesce(s.documents,0)+0.5)::float8) AS idf
                FROM unnest(CAST(:terms AS text[])) WITH ORDINALITY t(term,ord) LEFT JOIN rag_tuning.term_statistics s
                ON s.space_id=:space AND s.term=t.term)
                SELECT term,quote_literal(term) AS query,idf,sum(idf) OVER(ORDER BY ord ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS total FROM term_stats ORDER BY ord"""
        else:
            population = "SELECT CAST(:n AS float8) AS n"
            if any(params[k] is not None for k in ("form", "kind", "split")):
                population = (
                    f"SELECT count(*)::float8 AS n FROM rag_full.documents d WHERE {FILTERS}"
                )
            sql = f"""WITH population AS ({population}),term_stats AS MATERIALIZED (
                SELECT term,ord,ln(1.0+(p.n-v.df+0.5)/(v.df+0.5)) AS idf
                FROM unnest(CAST(:terms AS text[])) WITH ORDINALITY t(term,ord) CROSS JOIN population p
                CROSS JOIN LATERAL(SELECT count(*)::float8 AS df FROM rag_full.documents d
                 WHERE {FILTERS} AND d.search_vector @@ CAST(quote_literal(term) AS tsquery)) v)
                SELECT term,quote_literal(term) AS query,idf,sum(idf) OVER(ORDER BY ord ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS total FROM term_stats ORDER BY ord"""
        return c.execute(text(sql), params).mappings().all()

    @staticmethod
    def score_expression(terms, params):
        idfs, counts = [], []
        for i, term in enumerate(terms):
            params[f"t{i}"] = term["query"]
            params[f"w{i}"] = term["idf"]
            match = f"d.search_vector @@ CAST(:t{i} AS tsquery)"
            idfs.append(f"CASE WHEN {match} THEN CAST(:w{i} AS float8) ELSE 0::float8 END")
            counts.append(f"CASE WHEN {match} THEN 1 ELSE 0 END")
        params.update(total_idf=terms[0]["total"], term_count=len(terms), **WEIGHTS)
        return f""":idf_coverage*({" + ".join(idfs)})/CAST(:total_idf AS float8)
            + :term_coverage*CAST(({" + ".join(counts)}) AS float8)/:term_count
            + :frequency_proximity*ts_rank_cd(d.search_vector,CAST(:query AS tsquery),32)::float8"""

    def lexical(self, query, *, limit=50, questionnaire_id=None, unit_type=None, split=None):
        started = time.perf_counter()
        params = self.parameters(limit, questionnaire_id, unit_type, split)
        tokens = tokenize(query)
        with self.store.guard.transaction() as (c, _):
            c.execute(text("SET LOCAL statement_timeout='30s'"))
            parsed = normalize(c, tokens)
            if not parsed["query"]:
                self.last_lexical_timings = dict(total_seconds=time.perf_counter() - started)
                return []
            params.update(parsed)
            normalized = time.perf_counter()
            terms = self._terms(c, params)
            stats = time.perf_counter()
            score = self.score_expression(terms, params)
            candidate = ""
            table = "rag_full.documents"
            if self.prefilter is not None:
                # Explicitly approximate: ts_rank is NOT an upper bound on weighted score.
                params["prefilter"] = self.prefilter
                candidate = f"""WITH candidates AS MATERIALIZED(SELECT d.document_id,d.search_vector,d.space_id,d.questionnaire_id,d.unit_type,d.historical_split FROM rag_full.documents d
                   WHERE {FILTERS} AND d.search_vector @@ CAST(:query AS tsquery)
                   ORDER BY ts_rank_cd(d.search_vector,CAST(:query AS tsquery),32) DESC,
                   d.document_id COLLATE "C" LIMIT :prefilter) """
                table = "candidates"
            sql = f"""{candidate}SELECT d.document_id,{score} AS score FROM {table} d
                WHERE {FILTERS} AND d.search_vector @@ CAST(:query AS tsquery)
                ORDER BY score DESC,d.document_id COLLATE "C" LIMIT :limit"""
            rows = c.execute(text(sql), params).all()
            sql_end = time.perf_counter()
            results = self._results(c, [(r[0], r[1], self.store.space) for r in rows])
        self.last_lexical_timings = dict(
            preparation_seconds=normalized - started,
            statistics_seconds=stats - normalized,
            sql_seconds=sql_end - stats,
            total_seconds=time.perf_counter() - started,
            recipe="unrolled-v1",
            approximate=self.prefilter is not None,
            prefilter=self.prefilter,
        )
        return results
