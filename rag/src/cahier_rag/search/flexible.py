"""Méthodes RAG-009 sur les index RAG-008 inchangés : aucune migration."""

from enum import StrEnum

from sqlalchemy import text

from cahier_rag.contracts import UnitType, validate_id
from cahier_rag.search.lexical import LexicalEngine, SearchResult, Strategy
from cahier_rag.search.preparation import Preparation, normalize, tokenize
from cahier_rag.storage import restore_document


class Method(StrEnum):
    STRICT = "strict"
    PARTIAL = "partial"
    WEIGHTED = "weighted"


WEIGHTS = {"idf_coverage": 0.5, "term_coverage": 0.3, "frequency_proximity": 0.2}


def configuration(method, strategy, preparation):
    return {
        "version": 1,
        "method": Method(method).value,
        "representation": Strategy(strategy).value,
        "preparation": None if method == Method.STRICT else preparation.to_dict(),
        "weights": dict(WEIGHTS) if method == Method.WEIGHTED else None,
        "idf": "ln(1 + (N-df+0.5)/(df+0.5))" if method == Method.WEIGHTED else None,
        "statistics_scope": "same filters and partition" if method == Method.WEIGHTED else None,
        "phrase_policy": "RAG008 unchanged"
        if method == Method.STRICT
        else "all quoted phrases required",
        "tie_break": "document_id COLLATE C",
    }


class FlexibleEngine(LexicalEngine):
    def search(
        self,
        query,
        *,
        method=Method.WEIGHTED,
        strategy=Strategy.ANSWER,
        preparation=Preparation(),
        limit=10,
        questionnaire_id=None,
        unit_type=None,
        split=None,
    ):
        method = Method(method)
        if method == Method.STRICT:
            return super().search(
                query,
                strategy=strategy,
                limit=limit,
                questionnaire_id=questionnaire_id,
                unit_type=unit_type,
                split=split,
            )
        strategy = Strategy(strategy)
        if not isinstance(preparation, Preparation):
            raise ValueError("Configuration de préparation requise.")
        tokens = tokenize(query, preparation)
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Limite entre 1 et 1000.")
        if questionnaire_id is not None:
            validate_id(questionnaire_id, "questionnaire_id")
        if unit_type is not None:
            unit_type = UnitType(unit_type)
        if split is not None and split not in {"development", "evaluation"}:
            raise ValueError("Partition inconnue.")
        params = {
            "hash": self.scope.sample_hash,
            "strategy": strategy.value,
            "limit": limit,
            "split": split,
            "form": questionnaire_id,
            "kind": unit_type.value if unit_type else None,
        }
        # SQL fragments are fixed constants; all input values, lexemes and tsquery are bound.
        filters = """m.sample_hash=:hash AND (:split IS NULL OR m.split=:split)
          AND (:form IS NULL OR u.questionnaire_id=:form)
          AND (:kind IS NULL OR u.unit_type=:kind)"""
        joins = """JOIN rag.lexical_members m ON m.sample_hash=v.sample_hash AND m.document_id=v.document_id
          JOIN rag.text_units u ON u.document_id=v.document_id"""
        with self.guard.transaction() as (connection, source):
            self._timeouts(connection)
            self._ready(connection, strategy)
            parsed = normalize(connection, tokens, preparation)
            if not parsed["query"]:
                return []
            params.update(query=parsed["query"], terms=parsed["terms"], **WEIGHTS)
            if method == Method.PARTIAL:
                ctes = ""
                score = "ts_rank_cd(v.search_vector,CAST(:query AS tsquery),32)::float8"
            else:
                # Per-term DF uses existing GIN; no persistent statistics and no evaluation leakage.
                ctes = f"""population AS MATERIALIZED (
                  SELECT count(*)::float8 AS n FROM rag.lexical_members m
                  JOIN rag.text_units u ON u.document_id=m.document_id WHERE {filters}),
                term_stats AS MATERIALIZED (
                  SELECT term, ln(1.0 + (p.n-d.df+0.5)/(d.df+0.5)) AS idf
                  FROM unnest(CAST(:terms AS text[])) AS term CROSS JOIN population p
                  CROSS JOIN LATERAL (
                    SELECT count(*)::float8 AS df FROM rag.lexical_vectors v {joins}
                    WHERE {filters} AND v.strategy=:strategy
                      AND v.search_vector @@ CAST(quote_literal(term) AS tsquery)
                  ) d),
                """
                score = """(SELECT :idf_coverage*coalesce(sum(t.idf) FILTER(WHERE v.search_vector @@ CAST(quote_literal(t.term) AS tsquery)),0)/sum(t.idf)
                  + :term_coverage*count(*) FILTER(WHERE v.search_vector @@ CAST(quote_literal(t.term) AS tsquery))::float8/count(*)
                  FROM term_stats t) + :frequency_proximity*ts_rank_cd(v.search_vector,CAST(:query AS tsquery),32)::float8"""
            sql = f"""WITH {ctes} ranked AS MATERIALIZED (
              SELECT v.document_id, {score} AS score FROM rag.lexical_vectors v {joins}
              WHERE {filters} AND v.strategy=:strategy
                AND v.search_vector @@ CAST(:query AS tsquery)
              ORDER BY score DESC,v.document_id COLLATE "C" ASC LIMIT :limit)
              SELECT u.*, r.score,m.content_hash AS indexed_hash FROM ranked r
              JOIN rag.text_units u ON u.document_id=r.document_id
              JOIN rag.lexical_members m ON m.document_id=r.document_id AND m.sample_hash=:hash
              ORDER BY r.score DESC,r.document_id COLLATE "C" ASC"""
            records = connection.execute(text(sql), params).mappings().all()
        results = []
        for row in records:
            doc = restore_document(row)
            item = self.scope.documents.get(doc.document_id)
            if (
                item is None
                or item["content_hash"] != doc.content_hash
                or row["indexed_hash"] != doc.content_hash
            ):
                raise ValueError("Résultat hors périmètre ou périmé.")
            results.append(SearchResult(doc, float(row["score"])))
        return results
