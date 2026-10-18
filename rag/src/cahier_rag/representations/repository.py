"""Lectures bornées du seul périmètre RAG-007, sans accès à la base source."""

from collections import defaultdict

from sqlalchemy import select, text

from cahier_rag.db import source_connection
from cahier_rag.representations.contracts import Strategy
from cahier_rag.representations.prepare import prepare_unit, structural_key
from cahier_rag.schema import units
from cahier_rag.storage import restore_document

LIMITS = {
    "max_batch_units": 5000,
    "max_batch_chars": 20000000,
    "max_parent_units": 256,
    "max_segments_per_unit": 1000,
}


class RepresentationRepository:
    def __init__(self, engine, scope):
        self.engine = engine
        self.scope = scope
        self.parents = defaultdict(list)
        for did, item in scope.documents.items():
            self.parents[item["corpus_id"], item["contribution_id"]].append(did)
        self.parents = {key: tuple(sorted(ids)) for key, ids in self.parents.items()}

    def parent_ids(self, document_id):
        item = self.scope.documents[document_id]
        ids = self.parents[item["corpus_id"], item["contribution_id"]]
        if len(ids) > LIMITS["max_parent_units"]:
            raise ValueError("Contribution dépassant le plafond de contexte (256 unités).")
        return ids

    def fetch(self, document_ids):
        ids = sorted(set(document_ids))
        if not ids or len(ids) > LIMITS["max_batch_units"]:
            raise ValueError("Lot vide ou supérieur au plafond de 5000 unités avec contexte.")
        if not set(ids) <= self.scope.documents.keys():
            raise ValueError("Unité extérieure au corpus RAG-007.")
        found = {}
        characters = 0
        with source_connection(self.engine) as connection:
            connection.execute(text("SET LOCAL statement_timeout = '5s'"))
            connection.execute(text("SET LOCAL lock_timeout = '2s'"))
            query = select(units).where(units.c.document_id.in_(ids)).order_by(units.c.document_id)
            with connection.execution_options(stream_results=True, yield_per=1).execute(
                query
            ) as result:
                for row in result.mappings():
                    unit = restore_document(row)
                    expected = self.scope.documents[unit.document_id]
                    if (
                        unit.content_hash != expected["content_hash"]
                        or str(unit.contribution_id) != expected["contribution_id"]
                        or unit.corpus_id != expected["corpus_id"]
                        or str(unit.questionnaire_id) != expected["questionnaire_id"]
                    ):
                        raise ValueError("Provenance ou empreinte différente du manifeste RAG-007.")
                    characters += sum(len(v) for v in unit.to_dict().values() if isinstance(v, str))
                    if characters > LIMITS["max_batch_chars"]:
                        raise ValueError(
                            "Lot supérieur à 20 millions de caractères ; réduire la taille du lot."
                        )
                    found[unit.document_id] = unit
        if len(found) != len(ids):
            raise ValueError("Unité du corpus absente de PostgreSQL.")
        return found

    def parent(self, document_id):
        """Récupération C à la demande, mêmes corpus/contribution et partition."""
        ids = self.parent_ids(document_id)
        docs = self.fetch(ids)
        primary = docs[document_id]
        for doc in docs.values():
            if doc.questionnaire_id != primary.questionnaire_id:
                raise ValueError("Questionnaires incompatibles dans la contribution parente.")
        return tuple(sorted(docs.values(), key=structural_key))

    def iter_prepared(self, target_ids, config, *, batch_size=50):
        if type(batch_size) is not int or not 1 <= batch_size <= 100:
            raise ValueError("Taille de lot entre 1 et 100 requise.")
        if (
            len(target_ids) != len(set(target_ids))
            or not set(target_ids) <= self.scope.documents.keys()
        ):
            raise ValueError("Cibles dupliquées ou hors corpus.")
        for offset in range(0, len(target_ids), batch_size):
            batch = target_ids[offset : offset + batch_size]
            needed = set(batch)
            if config.strategy == Strategy.D:
                for did in batch:
                    if self.scope.documents[did]["length"] < config.short_chars:
                        needed.update(self.parent_ids(did))
            documents = self.fetch(needed)
            # Toutes les connexions sont fermées avant le premier yield / écriture locale.
            for did in batch:
                ids = self.parent_ids(did)
                context = tuple(documents[key] for key in ids if key in documents)
                yield from prepare_unit(
                    documents[did],
                    config=config,
                    sample_hash=self.scope.sample_hash,
                    split=self.scope.documents[did]["split"],
                    parent=context if config.strategy == Strategy.D else (),
                    parent_unit_ids=ids,
                )
