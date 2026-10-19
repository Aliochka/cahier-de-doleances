"""Parents sélectionnés RAG-007 exclusivement, copie SQLite contrôlée en lecture seule."""

from collections import defaultdict

from cahier_rag.representations.prepare import structural_key
from cahier_rag.search.hybrid.multi.artifacts import LocalDocuments


class ContextRepository:
    def __init__(self, path, scope):
        self.scope = scope
        self.documents = LocalDocuments(path, scope)
        self.parents = defaultdict(list)
        for did, item in scope.documents.items():
            self.parents[item["corpus_id"], item["contribution_id"]].append(did)
        for ids in self.parents.values():
            ids.sort()

    def validate(self, unit):
        item = self.scope.documents.get(unit.document_id)
        if (
            item is None
            or item["split"] != "development"
            or item["content_hash"] != unit.content_hash
            or item["corpus_id"] != unit.corpus_id
            or item["contribution_id"] != str(unit.contribution_id)
            or item["questionnaire_id"] != str(unit.questionnaire_id)
        ):
            raise ValueError("Document absent, modifié ou extérieur au développement.")
        return unit

    def fetch(self, ids):
        ids = list(ids)
        if (
            not ids
            or len(ids) > 500
            or any(
                d not in self.scope.documents or self.scope.documents[d]["split"] != "development"
                for d in ids
            )
        ):
            raise ValueError("Lot hors périmètre de développement.")
        values = self.documents.fetch(ids)
        if sum(len(u.text) for u in values.values()) > 20000000:
            raise ValueError("Lot supérieur à 20 millions de caractères.")
        return {d: self.validate(u) for d, u in values.items()}

    def neighbors(self, primary, limit):
        self.validate(primary)
        ids = self.parents[primary.corpus_id, str(primary.contribution_id)]
        if len(ids) > 256:
            raise ValueError("Contribution dépassant le plafond de 256 unités sélectionnées.")
        docs = self.fetch(ids)
        if any(
            (u.corpus_id, u.contribution_id, u.questionnaire_id)
            != (primary.corpus_id, primary.contribution_id, primary.questionnaire_id)
            for u in docs.values()
        ):
            raise ValueError("Relations parentales incohérentes.")
        ordered = sorted(docs.values(), key=structural_key)
        pos = next(i for i, u in enumerate(ordered) if u.document_id == primary.document_id)
        candidates = sorted(
            (abs(i - pos), i, u.document_id, u) for i, u in enumerate(ordered) if i != pos
        )
        return [entry[-1] for entry in candidates[:limit]]
