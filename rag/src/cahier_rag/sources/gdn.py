"""Lecture PostgreSQL du Grand Débat, sans ORM applicatif ni transformation sémantique."""

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from sqlalchemy import Engine, bindparam, text

from cahier_rag.contracts import ContributionMetadata, TextUnit, UnitType, validate_id
from cahier_rag.db import source_connection


class SourceDataError(ValueError):
    """Anomalie source : message limité aux identifiants, jamais aux textes."""


@dataclass(frozen=True)
class Cursor:
    """Dernière réponse consommée ; indice None = réponse intégralement consommée."""

    answer_id: int
    unit_index: int | None = None

    def __post_init__(self) -> None:
        validate_id(self.answer_id, "answer_id")
        if self.unit_index is not None and (
            type(self.unit_index) is not int or self.unit_index < 0
        ):
            raise ValueError("unit_index doit être un entier positif ou nul, ou None.")

    @classmethod
    def after_document(cls, document: TextUnit) -> "Cursor":
        return cls(document.answer_id, document.unit_index)

    def to_dict(self) -> dict:
        return {"answer_id": str(self.answer_id), "unit_index": self.unit_index}

    @classmethod
    def from_dict(cls, value: Mapping) -> "Cursor":
        answer_id = value.get("answer_id")
        if set(value) != {"answer_id", "unit_index"} or not isinstance(answer_id, str):
            raise ValueError("Curseur invalide.")
        if not answer_id.isascii() or not answer_id.isdecimal():
            raise ValueError("Curseur invalide.")
        return cls(int(answer_id), value["unit_index"])


@dataclass(frozen=True)
class DocumentBatch:
    documents: tuple[TextUnit, ...]
    next_cursor: Cursor | None
    exhausted: bool
    source_rows: int


def row_to_documents(row: Mapping, corpus_id: str) -> tuple[TextUnit, ...]:
    """Une ligne normalisée devient zéro, une ou plusieurs unités, dans l'ordre source."""
    answer_id = row["answer_id"]
    if (
        row["contribution_id"] is None
        or row["questionnaire_id"] is None
        or row["question_form_id"] != row["contribution_form_id"]
    ):
        raise SourceDataError(f"Rattachement incohérent pour la réponse {answer_id}.")

    question_type = row["question_type"]
    if question_type == "text":
        values = (row["answer_text"],)
        unit_type = UnitType.OPEN_ANSWER
    elif question_type in {"single_choice", "multi_choice"}:
        raw = row["value_json"]
        if raw is None:
            return ()
        try:
            metadata = json.loads(raw)
        except (ValueError, TypeError, RecursionError):
            raise SourceDataError(f"value_json invalide pour la réponse {answer_id}.") from None
        if not isinstance(metadata, dict):
            raise SourceDataError(f"value_json non objet pour la réponse {answer_id}.")
        values = metadata.get("other_text", [])
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise SourceDataError(f"other_text non conforme pour la réponse {answer_id}.")
        unit_type = UnitType.OTHER_TEXT
    else:
        raise SourceDataError(f"Type de question non pris en charge pour la réponse {answer_id}.")

    documents = []
    for index, value in enumerate(values):
        if value is None or not value.strip():
            continue
        documents.append(
            TextUnit(
                corpus_id=corpus_id,
                unit_type=unit_type,
                unit_index=index,
                answer_id=answer_id,
                contribution_id=row["contribution_id"],
                question_id=row["question_id"],
                questionnaire_id=row["questionnaire_id"],
                text=value,
                question_text=row["question_text"],
                questionnaire_name=row["questionnaire_name"],
                contribution_title=row["contribution_title"],
                answer_position=row["answer_position"],
                question_position=row["question_position"],
                question_section=row["question_section"],
                question_type=question_type,
                question_code=row["question_code"],
                questionnaire_version=row["questionnaire_version"],
                questionnaire_source=row["questionnaire_source"],
                contribution_source=row["contribution_source"],
                external_contribution_id=row["external_contribution_id"],
                submitted_at=row["submitted_at"],
            )
        )
    return tuple(documents)


ANSWER_SELECT = """
SELECT a.id AS answer_id, a.text AS answer_text, a.value_json,
       a.position AS answer_position, a.question_id,
       c.id AS contribution_id, c.form_id AS contribution_form_id,
       c.title AS contribution_title, c.source AS contribution_source,
       c.source_contribution_id AS external_contribution_id, c.submitted_at,
       q.form_id AS question_form_id, q.prompt AS question_text,
       q.position AS question_position, q.section AS question_section,
       q.type AS question_type, q.question_code,
       f.id AS questionnaire_id, f.name AS questionnaire_name,
       f.version AS questionnaire_version, f.source AS questionnaire_source
FROM public.answers a
JOIN public.questions q ON q.id = a.question_id
LEFT JOIN public.contributions c ON c.id = a.contribution_id
LEFT JOIN public.forms f ON f.id = q.form_id
"""


class GdnReader:
    """Un moteur fourni explicitement ; chaque lot ferme sa transaction avant de retourner.

    batch_size borne le nombre de lignes answers, pas le nombre d'unités autres
    d'une ligne. Le corpus, les filtres et les règles doivent rester inchangés
    pour reprendre une extraction. L'appelant possède et libère le moteur.
    """

    def __init__(
        self,
        engine: Engine,
        *,
        corpus_id: str = "gdn-2019",
        batch_size: int = 500,
        questionnaire_id: int | None = None,
        contribution_id: int | None = None,
        unit_type: UnitType | None = None,
        contribution_ids: tuple[int, ...] | None = None,
    ):
        if not isinstance(corpus_id, str) or not corpus_id.strip():
            raise ValueError("corpus_id est requis.")
        if type(batch_size) is not int or batch_size < 1:
            raise ValueError("batch_size doit être un entier strictement positif.")
        for name, value in (
            ("questionnaire_id", questionnaire_id),
            ("contribution_id", contribution_id),
        ):
            if value is not None:
                validate_id(value, name)
        if unit_type is not None and not isinstance(unit_type, UnitType):
            raise ValueError("unit_type doit être un UnitType.")
        if contribution_ids is not None:
            from cahier_rag.extraction import ExtractionSpec

            ExtractionSpec(
                limit=1, contribution_id=contribution_id, contribution_ids=contribution_ids
            )
        self.contribution_ids = contribution_ids
        self.engine = engine
        self.corpus_id = corpus_id
        self.batch_size = batch_size
        self.questionnaire_id = questionnaire_id
        self.contribution_id = contribution_id
        self.unit_type = unit_type

    def _read_rows(self, after: Cursor | None) -> list[Mapping]:
        clauses = []
        params = {"batch_size": self.batch_size}
        types = {
            None: "q.type IN ('text', 'single_choice', 'multi_choice')",
            UnitType.OPEN_ANSWER: "q.type = 'text'",
            UnitType.OTHER_TEXT: "q.type IN ('single_choice', 'multi_choice')",
        }
        clauses.append(types[self.unit_type])
        if after is not None:
            operator = ">" if after.unit_index is None else ">="
            clauses.append(f"a.id {operator} :after_id")
            params["after_id"] = after.answer_id
        if self.questionnaire_id is not None:
            clauses.append("q.form_id = :questionnaire_id")
            params["questionnaire_id"] = self.questionnaire_id
        if self.contribution_id is not None:
            clauses.append("a.contribution_id = :contribution_id")
            params["contribution_id"] = self.contribution_id
        if self.contribution_ids is not None:
            clauses.append("a.contribution_id IN :contribution_ids")
            params["contribution_ids"] = self.contribution_ids
        query = text(
            ANSWER_SELECT
            + " WHERE "
            + " AND ".join(clauses)
            + " ORDER BY a.id ASC LIMIT :batch_size"
        )
        if self.contribution_ids is not None:
            query = query.bindparams(bindparam("contribution_ids", expanding=True))
        with source_connection(self.engine) as connection:
            with connection.execute(query, params) as result:
                return result.mappings().all()

    def read_batch(
        self, *, after: Cursor | None = None, max_documents: int | None = None
    ) -> DocumentBatch:
        if max_documents is not None and (type(max_documents) is not int or max_documents < 1):
            raise ValueError("max_documents doit être un entier strictement positif.")
        rows = self._read_rows(after)
        documents = []
        cursor = after
        for row in rows:
            for document in row_to_documents(row, self.corpus_id):
                if (
                    after is not None
                    and row["answer_id"] == after.answer_id
                    and after.unit_index is not None
                    and document.unit_index <= after.unit_index
                ):
                    continue
                documents.append(document)
                if max_documents is not None and len(documents) == max_documents:
                    return DocumentBatch(
                        tuple(documents), Cursor.after_document(document), False, len(rows)
                    )
            cursor = Cursor(row["answer_id"])
        return DocumentBatch(tuple(documents), cursor, len(rows) < self.batch_size, len(rows))

    def iter_batches(
        self, *, after: Cursor | None = None, limit: int | None = None
    ) -> Iterator[DocumentBatch]:
        if limit is not None and (type(limit) is not int or limit < 0):
            raise ValueError("limit doit être un entier positif ou nul.")
        remaining = limit
        while remaining is None or remaining > 0:
            batch = self.read_batch(after=after, max_documents=remaining)
            yield batch
            if batch.exhausted:
                return
            after = batch.next_cursor
            if remaining is not None:
                remaining -= len(batch.documents)

    def iter_documents(
        self, *, after: Cursor | None = None, limit: int | None = None
    ) -> Iterator[TextUnit]:
        for batch in self.iter_batches(after=after, limit=limit):
            yield from batch.documents

    def get_contribution(self, contribution_id: int) -> ContributionMetadata | None:
        """Lecture ciblée des métadonnées, y compris pour un titre sans réponse."""
        validate_id(contribution_id, "contribution_id")
        query = text("""
            SELECT c.id AS contribution_id, c.form_id AS questionnaire_id,
                   c.title, c.source, c.source_contribution_id AS external_id,
                   c.submitted_at, f.name AS questionnaire_name,
                   f.version AS questionnaire_version, f.source AS questionnaire_source
            FROM public.contributions c JOIN public.forms f ON f.id = c.form_id
            WHERE c.id = :contribution_id
        """)
        with source_connection(self.engine) as connection:
            with connection.execute(query, {"contribution_id": contribution_id}) as result:
                row = result.mappings().one_or_none()
        return ContributionMetadata(corpus_id=self.corpus_id, **row) if row is not None else None
