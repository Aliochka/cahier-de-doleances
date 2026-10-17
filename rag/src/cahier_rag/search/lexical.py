"""Baseline française : périmètre immuable, vecteurs dérivés et résultats fidèles."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from sqlalchemy import bindparam, func, select, text

from cahier_rag.contracts import TextUnit, UnitType, validate_id
from cahier_rag.evaluation.sampling import digest
from cahier_rag.safety import DatabaseGuard
from cahier_rag.schema import lexical_corpora, lexical_members, lexical_vectors, units
from cahier_rag.storage import restore_document

RAG007_HASH = "d0173a371df7fc5d6b5d8ca393ea3f230349140b1cfb92a1ec4a2280200033cc"
CONFIGURATION = {
    "version": 1,
    "language": "pg_catalog.french",
    "parser": "websearch_to_tsquery",
    "ranking": "ts_rank_cd",
    "normalization": 32,
    "field_order": ["answer", "question", "title"],
    "rank_weights": [0.1, 0.2, 0.4, 1.0],
    "weights": {"answer": "A", "question": "B", "title": "C"},
    "strategies": ["answer", "question", "title"],
}


class Strategy(StrEnum):
    ANSWER = "answer"
    QUESTION = "question"
    TITLE = "title"


@dataclass(frozen=True)
class SearchResult:
    document: TextUnit
    score: float

    def to_dict(self):
        return {
            "document_id": self.document.document_id,
            "score": self.score,
            "document": self.document.to_dict(),
        }


@dataclass(frozen=True, init=False)
class CorpusScope:
    sample_hash: str
    documents: Mapping[str, Mapping]

    def __init__(self, sample, *, expected_hash=RAG007_HASH, expected_size=20000):
        documents = sample["documents"]
        if (
            len(documents) != expected_size
            or not 1 <= expected_size <= 20000
            or sample["selected_hash"] != expected_hash
            or digest(documents) != expected_hash
        ):
            raise ValueError("Le manifeste ne correspond pas au corpus lexical attendu.")
        object.__setattr__(self, "sample_hash", expected_hash)
        object.__setattr__(
            self,
            "documents",
            MappingProxyType({d["document_id"]: MappingProxyType(dict(d)) for d in documents}),
        )
        if len(self.documents) != expected_size:
            raise ValueError("Identifiants dupliqués dans le corpus.")
        links = {}
        for doc in documents:
            if doc["split"] not in {"development", "evaluation"}:
                raise ValueError("Partition inconnue.")
            for key in (
                ("parent", doc["corpus_id"], doc["contribution_id"]),
                ("text", doc["text_hash"]),
            ):
                if links.setdefault(key, doc["split"]) != doc["split"]:
                    raise ValueError("Fuite entre partitions.")


class LexicalEngine:
    def __init__(self, guard: DatabaseGuard, scope: CorpusScope):
        self.guard = guard
        self.scope = scope

    @staticmethod
    def _timeouts(connection):
        connection.execute(text("SET LOCAL statement_timeout = '5s'"))
        connection.execute(text("SET LOCAL lock_timeout = '2s'"))

    def rebuild(self):
        """Toute erreur annule la reconstruction ; l'ancien index reste utilisable."""
        expected = self.scope.documents
        with self.guard.transaction() as (connection, source):
            self._timeouts(connection)
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": self.scope.sample_hash},
            )
            connection.execute(
                lexical_corpora.delete().where(
                    lexical_corpora.c.sample_hash == self.scope.sample_hash
                )
            )
            config = dict(CONFIGURATION)
            config["server_version"] = connection.execute(text("SHOW server_version")).scalar_one()
            connection.execute(
                lexical_corpora.insert().values(
                    sample_hash=self.scope.sample_hash,
                    document_count=len(expected),
                    configuration=config,
                )
            )
            ids = sorted(expected)
            for offset in range(0, len(ids), 100):
                subset = ids[offset : offset + 100]
                records = (
                    connection.execute(select(units).where(units.c.document_id.in_(subset)))
                    .mappings()
                    .all()
                )
                if len(records) != len(subset):
                    raise ValueError("Document du manifeste absent de PostgreSQL.")
                for record in records:
                    doc = restore_document(record)
                    item = expected[doc.document_id]
                    if (
                        doc.content_hash != item["content_hash"]
                        or str(doc.contribution_id) != item["contribution_id"]
                        or doc.corpus_id != item["corpus_id"]
                    ):
                        raise ValueError("Provenance ou contenu incompatible avec le manifeste.")
                connection.execute(
                    lexical_members.insert(),
                    [
                        dict(
                            sample_hash=self.scope.sample_hash,
                            document_id=key,
                            content_hash=expected[key]["content_hash"],
                            split=expected[key]["split"],
                        )
                        for key in subset
                    ],
                )
                query = text("""
                    INSERT INTO rag.lexical_vectors(sample_hash,strategy,document_id,search_vector)
                    SELECT :sample_hash,s.strategy,u.document_id,
                      setweight(to_tsvector('pg_catalog.french',u.text),'A') ||
                      CASE WHEN s.strategy IN ('question','title') THEN
                        setweight(to_tsvector('pg_catalog.french',coalesce(u.context->>'question_text','')),'B')
                        ELSE ''::tsvector END ||
                      CASE WHEN s.strategy='title' THEN
                        setweight(to_tsvector('pg_catalog.french',coalesce(u.context->>'contribution_title','')),'C')
                        ELSE ''::tsvector END
                    FROM rag.text_units u CROSS JOIN (VALUES ('answer'),('question'),('title')) s(strategy)
                    WHERE u.document_id IN :ids
                """).bindparams(bindparam("ids", expanding=True))
                connection.execute(query, {"sample_hash": self.scope.sample_hash, "ids": subset})
        return {
            "sample_hash": self.scope.sample_hash,
            "documents": len(expected),
            "vectors": 3 * len(expected),
        }

    def _ready(self, connection, strategy):
        row = (
            connection.execute(
                select(lexical_corpora)
                .where(lexical_corpora.c.sample_hash == self.scope.sample_hash)
                .with_for_update(read=True)
            )
            .mappings()
            .one_or_none()
        )
        if row is None or row["document_count"] != len(self.scope.documents):
            raise ValueError("Index absent ou incomplet ; reconstruire explicitement.")
        if any(row["configuration"].get(key) != value for key, value in CONFIGURATION.items()):
            raise ValueError("Version d’index incompatible ; reconstruire explicitement.")
        if (
            row["configuration"].get("server_version")
            != connection.execute(text("SHOW server_version")).scalar_one()
        ):
            raise ValueError("Version PostgreSQL différente ; reconstruire explicitement.")
        for table, clauses in (
            (lexical_members, []),
            (lexical_vectors, [lexical_vectors.c.strategy == strategy]),
        ):
            count = connection.execute(
                select(func.count())
                .select_from(table)
                .where(table.c.sample_hash == self.scope.sample_hash, *clauses)
            ).scalar_one()
            if count != len(self.scope.documents):
                raise ValueError("Index incomplet ; reconstruire explicitement.")

    def validate(self):
        with self.guard.transaction() as (connection, source):
            self._timeouts(connection)
            for strategy in Strategy:
                self._ready(connection, strategy)
            records = (
                connection.execute(
                    select(lexical_members).where(
                        lexical_members.c.sample_hash == self.scope.sample_hash
                    )
                )
                .mappings()
                .all()
            )
            actual = {r["document_id"]: (r["content_hash"], r["split"]) for r in records}
            expected = {
                key: (d["content_hash"], d["split"]) for key, d in self.scope.documents.items()
            }
            if actual != expected:
                raise ValueError(
                    "Les membres indexés ne correspondent pas exactement au manifeste."
                )
            configuration = connection.execute(
                select(lexical_corpora.c.configuration).where(
                    lexical_corpora.c.sample_hash == self.scope.sample_hash
                )
            ).scalar_one()
        return {
            "documents": len(actual),
            "sample_hash": self.scope.sample_hash,
            "configuration": configuration,
        }

    def search(
        self,
        query: str,
        *,
        strategy: Strategy | str = Strategy.ANSWER,
        limit: int = 10,
        questionnaire_id: int | None = None,
        unit_type: UnitType | str | None = None,
        split: str | None = None,
    ) -> list[SearchResult]:
        strategy = Strategy(strategy)
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ValueError("Requête requise de 1 à 1000 caractères.")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Limite de résultats entre 1 et 1000.")
        if questionnaire_id is not None:
            validate_id(questionnaire_id, "questionnaire_id")
        if unit_type is not None:
            unit_type = UnitType(unit_type)
        if split is not None and split not in {"development", "evaluation"}:
            raise ValueError("Partition inconnue.")
        tsquery = func.websearch_to_tsquery("pg_catalog.french", query)
        score = func.ts_rank_cd(lexical_vectors.c.search_vector, tsquery, 32).label("score")
        statement = (
            select(units, score, lexical_members.c.content_hash.label("indexed_hash"))
            .join(lexical_vectors, units.c.document_id == lexical_vectors.c.document_id)
            .join(
                lexical_members,
                (lexical_members.c.document_id == lexical_vectors.c.document_id)
                & (lexical_members.c.sample_hash == lexical_vectors.c.sample_hash),
            )
            .where(
                lexical_vectors.c.sample_hash == self.scope.sample_hash,
                lexical_vectors.c.strategy == strategy,
                lexical_vectors.c.search_vector.op("@@")(tsquery),
            )
        )
        if questionnaire_id is not None:
            statement = statement.where(units.c.questionnaire_id == questionnaire_id)
        if unit_type is not None:
            statement = statement.where(units.c.unit_type == unit_type)
        if split is not None:
            statement = statement.where(lexical_members.c.split == split)
        statement = statement.order_by(score.desc(), units.c.document_id.collate("C").asc()).limit(
            limit
        )
        with self.guard.transaction() as (connection, source):
            self._timeouts(connection)
            self._ready(connection, strategy)
            records = connection.execute(statement).mappings().all()
        results = []
        for record in records:
            doc = restore_document(record)
            expected = self.scope.documents.get(doc.document_id)
            if (
                expected is None
                or doc.content_hash != expected["content_hash"]
                or record["indexed_hash"] != doc.content_hash
            ):
                raise ValueError("Résultat hors périmètre ou index périmé.")
            results.append(SearchResult(doc, float(record["score"])))
        return results
