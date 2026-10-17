"""Persistance immuable et progression transactionnelle dans PostgreSQL RAG."""

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Connection, func, select, update
from sqlalchemy.dialects.postgresql import insert

from cahier_rag.contracts import CONTRACT_VERSION, TextUnit, UnitType, canonical_json
from cahier_rag.extraction import ExtractionError, ExtractionSpec
from cahier_rag.safety import DatabaseGuard, DatabaseIdentity
from cahier_rag.schema import checkpoints, manifests, memberships, units
from cahier_rag.sources.gdn import Cursor, DocumentBatch


class DocumentConflict(ExtractionError):
    """Même identité, contenu documentaire différent ; aucun écrasement autorisé."""


class ConcurrentProgress(ExtractionError):
    """Le checkpoint a changé depuis la lecture du consommateur."""


@dataclass(frozen=True)
class ExtractionState:
    extraction_id: UUID
    spec: ExtractionSpec
    source_identity: dict
    cursor: Cursor | None
    document_count: int
    source_row_count: int
    revision: int
    status: str
    completion_reason: str | None
    last_batch_hash: str | None

    def to_dict(self) -> dict:
        return {
            "extraction_id": str(self.extraction_id),
            "parameters": self.spec.to_dict(),
            "source_identity": self.source_identity,
            "cursor": self.cursor.to_dict() if self.cursor else None,
            "document_count": self.document_count,
            "source_row_count": self.source_row_count,
            "revision": self.revision,
            "status": self.status,
            "completion_reason": self.completion_reason,
        }


def _position(cursor: Cursor | None) -> tuple:
    if cursor is None:
        return (0, 0, 0)
    return (cursor.answer_id, cursor.unit_index is None, cursor.unit_index or 0)


def document_record(document: TextUnit) -> dict:
    payload = document.to_dict()
    context = dict(payload)
    for name in (
        "document_id",
        "corpus_id",
        "unit_type",
        "answer_id",
        "contribution_id",
        "question_id",
        "questionnaire_id",
        "unit_index",
        "text",
        "content_hash",
        "contract_version",
    ):
        context.pop(name)
    return {
        "document_id": document.document_id,
        "corpus_id": document.corpus_id,
        "unit_type": document.unit_type.value,
        "answer_id": document.answer_id,
        "contribution_id": document.contribution_id,
        "question_id": document.question_id,
        "questionnaire_id": document.questionnaire_id,
        "unit_index": document.unit_index,
        "text": document.text,
        "context": context,
        "content_hash": payload["content_hash"],
        "contract_version": CONTRACT_VERSION,
    }


def restore_document(record) -> TextUnit:
    if record["contract_version"] != CONTRACT_VERSION:
        raise ExtractionError("Version de document stocké incompatible.")
    context = dict(record["context"])
    if context["submitted_at"] is not None:
        context["submitted_at"] = datetime.fromisoformat(context["submitted_at"])
    document = TextUnit(
        corpus_id=record["corpus_id"],
        unit_type=UnitType(record["unit_type"]),
        answer_id=record["answer_id"],
        contribution_id=record["contribution_id"],
        question_id=record["question_id"],
        questionnaire_id=record["questionnaire_id"],
        unit_index=record["unit_index"],
        text=record["text"],
        **context,
    )
    if (
        document.document_id != record["document_id"]
        or document.content_hash != record["content_hash"]
    ):
        raise DocumentConflict("Identité ou empreinte du document stocké incohérente.")
    return document


class RagStore:
    def __init__(self, guard: DatabaseGuard):
        self.guard = guard

    def _load(self, connection: Connection, extraction_id: UUID, *, lock=False) -> ExtractionState:
        query = (
            select(manifests, checkpoints)
            .join(checkpoints)
            .where(manifests.c.extraction_id == extraction_id)
        )
        if lock:
            query = query.with_for_update(of=checkpoints)
        row = connection.execute(query).mappings().one_or_none()
        if row is None:
            raise ExtractionError("Extraction inconnue.")
        spec = ExtractionSpec.from_dict(row["parameters"])
        if spec.fingerprint != row["parameters_hash"]:
            raise ExtractionError("Empreinte du manifeste incohérente.")
        cursor = (
            Cursor(row["answer_id"], row["unit_index"]) if row["answer_id"] is not None else None
        )
        return ExtractionState(
            extraction_id=extraction_id,
            spec=spec,
            source_identity=row["source_identity"],
            cursor=cursor,
            document_count=row["document_count"],
            source_row_count=row["source_row_count"],
            revision=row["revision"],
            status=row["status"],
            completion_reason=row["completion_reason"],
            last_batch_hash=row["last_batch_hash"],
        )

    def create_extraction(self, spec: ExtractionSpec) -> ExtractionState:
        spec.ensure_current()
        identity = uuid4()
        with self.guard.transaction() as (connection, source):
            connection.execute(
                insert(manifests).values(
                    extraction_id=identity,
                    parameters=spec.to_dict(),
                    parameters_hash=spec.fingerprint,
                    source_identity=source.to_dict(),
                )
            )
            connection.execute(insert(checkpoints).values(extraction_id=identity))
            return self._load(connection, identity)

    def get_state(self, extraction_id: UUID) -> ExtractionState:
        with self.guard.transaction() as (connection, source):
            return self._load(connection, extraction_id)

    @staticmethod
    def validate_resume(
        state: ExtractionState, source: DatabaseIdentity, expected_spec: ExtractionSpec | None
    ):
        state.spec.ensure_current()
        if state.source_identity != source.to_dict():
            raise ExtractionError(
                "L'identité ou la révision de la source a changé ; reprise refusée."
            )
        if expected_spec is not None and state.spec != expected_spec:
            raise ExtractionError("Paramètres incompatibles avec le manifeste d'extraction.")

    def persist_batch(
        self,
        extraction_id: UUID,
        batch: DocumentBatch,
        *,
        expected_revision: int,
        expected_spec: ExtractionSpec,
    ) -> ExtractionState:
        records = [document_record(document) for document in batch.documents]
        signature = hashlib.sha256(
            canonical_json(
                {
                    "documents": [(item["document_id"], item["content_hash"]) for item in records],
                    "cursor": batch.next_cursor.to_dict() if batch.next_cursor else None,
                    "exhausted": batch.exhausted,
                    "expected_revision": expected_revision,
                    "source_rows": batch.source_rows,
                }
            ).encode()
        ).hexdigest()
        with self.guard.transaction() as (connection, source):
            state = self._load(connection, extraction_id, lock=True)
            self.validate_resume(state, source, expected_spec)
            # Réessai exact après perte de la réponse au COMMIT : aucun compteur n'avance.
            if state.revision == expected_revision + 1 and state.last_batch_hash == signature:
                return state
            if state.revision != expected_revision:
                raise ConcurrentProgress(
                    "Le checkpoint a changé ; relire l'état avant de reprendre."
                )
            if state.status == "completed":
                raise ExtractionError("Cette extraction est déjà terminée.")
            if _position(batch.next_cursor) < _position(state.cursor):
                raise ExtractionError("Le checkpoint ne peut pas reculer.")
            previous = _position(state.cursor)
            for document in batch.documents:
                position = _position(Cursor.after_document(document))
                if not previous < position <= _position(batch.next_cursor):
                    raise ExtractionError("Ordre des documents incompatible avec le checkpoint.")
                previous = position
                if (
                    document.corpus_id != state.spec.corpus_id
                    or (
                        state.spec.questionnaire_id is not None
                        and document.questionnaire_id != state.spec.questionnaire_id
                    )
                    or (
                        state.spec.contribution_id is not None
                        and document.contribution_id != state.spec.contribution_id
                    )
                    or (
                        state.spec.unit_type is not None
                        and document.unit_type != state.spec.unit_type
                    )
                ):
                    raise ExtractionError("Document hors du périmètre du manifeste.")
            count = state.document_count + len(records)
            if count > state.spec.limit:
                raise ExtractionError("Le lot dépasse la limite documentaire explicite.")
            source_count = state.source_row_count + batch.source_rows
            if (
                type(batch.source_rows) is not int
                or batch.source_rows < 0
                or source_count > state.spec.max_source_rows
            ):
                raise ExtractionError("Le lot dépasse le plafond de lignes sources.")
            if records:
                connection.execute(
                    insert(units)
                    .values(records)
                    .on_conflict_do_nothing(index_elements=[units.c.document_id])
                )
                hashes = dict(
                    connection.execute(
                        select(units.c.document_id, units.c.content_hash).where(
                            units.c.document_id.in_([item["document_id"] for item in records])
                        )
                    ).all()
                )
                if any(hashes.get(item["document_id"]) != item["content_hash"] for item in records):
                    raise DocumentConflict(
                        "Même identifiant documentaire, empreinte différente ; lot annulé."
                    )
                connection.execute(
                    insert(memberships).values(
                        [
                            {
                                "extraction_id": extraction_id,
                                "document_id": item["document_id"],
                                "ordinal": state.document_count + i + 1,
                            }
                            for i, item in enumerate(records)
                        ]
                    )
                )
            reason = (
                "document_limit"
                if count == state.spec.limit
                else "source_exhausted"
                if batch.exhausted
                else "source_row_limit"
                if source_count == state.spec.max_source_rows
                else None
            )
            connection.execute(
                update(checkpoints)
                .where(checkpoints.c.extraction_id == extraction_id)
                .values(
                    answer_id=batch.next_cursor.answer_id if batch.next_cursor else None,
                    unit_index=batch.next_cursor.unit_index if batch.next_cursor else None,
                    document_count=count,
                    source_row_count=source_count,
                    revision=state.revision + 1,
                    last_batch_hash=signature,
                    status="completed" if reason else "running",
                    completion_reason=reason,
                    updated_at=func.now(),
                )
            )
            return self._load(connection, extraction_id)

    def iter_documents(self, extraction_id: UUID, *, batch_size: int = 100) -> Iterator[TextUnit]:
        if type(batch_size) is not int or not 1 <= batch_size <= 5000:
            raise ExtractionError("Taille de lot de restitution invalide.")
        after = 0
        while True:
            with self.guard.transaction() as (connection, source):
                rows = (
                    connection.execute(
                        select(units, memberships.c.ordinal)
                        .join(memberships, memberships.c.document_id == units.c.document_id)
                        .where(
                            memberships.c.extraction_id == extraction_id,
                            memberships.c.ordinal > after,
                        )
                        .order_by(memberships.c.ordinal)
                        .limit(batch_size)
                    )
                    .mappings()
                    .all()
                )
            for row in rows:
                yield restore_document(row)
            if len(rows) < batch_size:
                return
            after = rows[-1]["ordinal"]
