"""Lecture seule de la base RAG ; aucun accès au corpus source."""

from sqlalchemy import select, text

from cahier_rag.db import source_connection
from cahier_rag.schema import units
from cahier_rag.storage import restore_document


class Documents:
    def __init__(self, engine, candidates):
        self.engine = engine
        self.candidates = candidates

    def get(self, pair, *, parent=False):
        candidate = self.candidates[pair]
        with source_connection(self.engine) as connection:
            connection.execute(text("SET LOCAL statement_timeout = '5s'"))
            connection.execute(text("SET LOCAL lock_timeout = '2s'"))
            record = (
                connection.execute(select(units).where(units.c.document_id == pair[1]))
                .mappings()
                .one_or_none()
            )
            if record is None:
                raise ValueError("Document absent de la base RAG.")
            document = restore_document(record)
            if document.content_hash != candidate["content_hash"]:
                raise ValueError("Empreinte du document différente du candidat.")
            if not parent:
                return [document.to_dict()]
            # Unités stockées seulement, limitées à cette contribution et ce corpus.
            records = (
                connection.execute(
                    select(units)
                    .where(
                        units.c.corpus_id == document.corpus_id,
                        units.c.contribution_id == document.contribution_id,
                    )
                    .order_by(units.c.question_id, units.c.answer_id, units.c.unit_index)
                    .limit(501)
                )
                .mappings()
                .all()
            )
            if len(records) > 500:
                raise ValueError("Contribution trop volumineuse pour cet affichage (500 unités).")
            return [restore_document(row).to_dict() for row in records]
