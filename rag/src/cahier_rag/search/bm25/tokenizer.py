"""Lexèmes français PostgreSQL sans plafonds de positions/fréquences tsvector."""

from sqlalchemy import text

from cahier_rag.db import source_connection
from cahier_rag.evaluation.sampling import digest
from cahier_rag.search.preparation import Preparation, tokenize


class FrenchTokenizer:
    def __init__(self, engine):
        self.engine = engine
        with source_connection(engine) as connection:
            version = connection.execute(text("SHOW server_version")).scalar_one()
        self.configuration = {
            "version": 1,
            "configuration": "pg_catalog.french",
            "postgresql": version,
            "parser": "ts_debug ordered lexemes; no tsvector",
            "probes": digest(
                self.encode(["L'école et les écoles rurales : transports, impôts, été."])
            ),
        }

    def encode(self, values):
        if not values or len(values) > 200 or sum(map(len, values)) > 20_000_000:
            raise ValueError("Lot tokenizer vide ou trop volumineux.")
        with source_connection(self.engine) as connection:
            connection.execute(text("SET LOCAL statement_timeout='5s'"))
            rows = (
                connection.execute(
                    text("""
                SELECT ARRAY(SELECT lex FROM
                    ts_debug('pg_catalog.french', input.value) WITH ORDINALITY AS d,
                    unnest(d.lexemes) WITH ORDINALITY AS l(lex,ord)
                    ORDER BY d.ordinality,l.ord)
                FROM unnest(CAST(:values AS text[])) WITH ORDINALITY AS input(value,ord)
                ORDER BY input.ord
            """),
                    {"values": values},
                )
                .scalars()
                .all()
            )
        return rows

    def query(self, value):
        parsed = tokenize(value)
        groups = self.encode([" ".join(parsed["terms"])] + parsed["phrases"] + parsed["excluded"])
        n = len(parsed["phrases"])
        phrases, excluded = groups[1 : 1 + n], groups[1 + n :]
        terms = sorted(set(groups[0] + [t for p in phrases for t in p]))
        if len(terms) > Preparation().max_terms:
            raise ValueError("Au plus 32 lexèmes significatifs.")
        return terms, phrases, excluded
