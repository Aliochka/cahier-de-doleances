"""Ordre aveugle et état unique atomique (jugements, brouillons, curseur)."""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from cahier_rag.contracts import canonical_json
from cahier_rag.evaluation.files import load_json, validate_judgments
from cahier_rag.evaluation.sampling import digest


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".annotation-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(canonical_json(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Session:
    def __init__(
        self, pool, queries, sample, path, *, evaluator, seed=20261020, expected_count=400
    ):
        if not evaluator.strip() or len(evaluator) > 100:
            raise ValueError("Identifiant d’évaluateur requis (100 caractères maximum).")
        if len(pool) != expected_count or not pool:
            raise ValueError("Nombre de candidats inattendu.")
        self.queries = {q["query_id"]: q for q in queries}
        docs = {d["document_id"]: d for d in sample["documents"]}
        pairs = set()
        self.candidates = {}
        for row in pool:
            qid, did = row["query_id"], row["document_id"]
            pair = (qid, did)
            if pair in pairs or qid not in self.queries or did not in docs:
                raise ValueError("Candidat dupliqué ou référence inconnue.")
            if self.queries[qid]["split"] != "development" or docs[did]["split"] != "development":
                raise ValueError("Seuls les candidats de développement sont autorisés.")
            if row["content_hash"] != docs[did]["content_hash"]:
                raise ValueError("Empreinte documentaire différente du corpus.")
            for key in ("corpus_id", "contribution_id"):
                if row[key] != docs[did][key]:
                    raise ValueError("Provenance incompatible.")
            pairs.add(pair)
            # Whitelist : aucun rang, score, méthode ni indicateur de contrôle aléatoire.
            self.candidates[pair] = {
                k: row[k]
                for k in ("query_id", "document_id", "content_hash", "corpus_id", "contribution_id")
            }
        self.order = sorted(pairs, key=lambda p: (p[0], digest([seed, *p])))
        self.path = Path(path)
        self.sample = sample
        self.lock = RLock()
        self.identity = {
            "pool_hash": digest(pool),
            "sample_hash": sample["selected_hash"],
            "queries_hash": digest(queries),
            "seed": seed,
            "evaluator": evaluator,
            "version": "rag010-v1",
            "order_hash": digest(self.order),
        }
        if self.path.exists():
            self.state = load_json(self.path)
            if self.state.get("identity") != self.identity:
                raise ValueError(
                    "Session incompatible : candidats, paramètres ou évaluateur modifiés."
                )
            self._validate_state()
        else:
            self.state = {
                "identity": self.identity,
                "position": 0,
                "revision": 0,
                "judgments": [],
                "drafts": {},
            }
            atomic_json(self.path, self.state)

    def _validate_state(self):
        state = self.state
        if type(state["position"]) is not int or not 0 <= state["position"] < len(self.order):
            raise ValueError("Position de session invalide.")
        if type(state["revision"]) is not int or state["revision"] < 0:
            raise ValueError("Révision invalide.")
        # Réutiliser strictement le validateur RAG-006, sans fichier temporaire sur disque.
        validate_judgments(state["judgments"], list(self.queries.values()), self.sample)
        for row in state["judgments"]:
            if (row["query_id"], row["document_id"]) not in self.candidates:
                raise ValueError("Jugement extérieur aux candidats.")
            if (
                row["evaluator"] != self.identity["evaluator"]
                or row["version"] != self.identity["version"]
            ):
                raise ValueError("Évaluateur ou version incompatible.")
        if not isinstance(state["drafts"], dict) or any(
            key not in {self.key(p) for p in self.order}
            or not isinstance(value, str)
            or len(value) > 10000
            for key, value in state["drafts"].items()
        ):
            raise ValueError("Brouillons invalides.")

    @staticmethod
    def key(pair):
        return canonical_json(list(pair))

    def view(self):
        with self.lock:
            judged = {(r["query_id"], r["document_id"]): r for r in self.state["judgments"]}
            qid, did = self.order[self.state["position"]]
            groups = []
            for query in sorted({p[0] for p in self.order}):
                indices = [i for i, p in enumerate(self.order) if p[0] == query]
                groups.append(
                    {
                        "query_id": query,
                        "text": self.queries[query]["text"],
                        "position": indices[0],
                        "total": len(indices),
                        "done": sum(self.order[i] in judged for i in indices),
                    }
                )
            return {
                "position": self.state["position"],
                "revision": self.state["revision"],
                "total": len(self.order),
                "done": len(judged),
                "groups": groups,
                "query_id": qid,
                "query": self.queries[qid]["text"],
                "document_id": did,
                "judgment": judged.get((qid, did)),
                "draft": self.state["drafts"].get(
                    self.key((qid, did)), judged.get((qid, did), {}).get("justification") or ""
                ),
            }

    def change(self, *, revision, position, comment, grade=None, destination=None):
        with self.lock:
            if type(revision) is not int or revision != self.state["revision"]:
                raise ValueError("Session modifiée dans un autre onglet ; recharger.")
            if type(position) is not int or position != self.state["position"]:
                raise ValueError("Position obsolète.")
            if not isinstance(comment, str) or len(comment) > 10000:
                raise ValueError("Commentaire limité à 10 000 caractères.")
            if grade is not None and (type(grade) is not int or not 0 <= grade <= 3):
                raise ValueError("Note entière de 0 à 3 requise.")
            if destination is None:
                destination = (
                    min(position + 1, len(self.order) - 1) if grade is not None else position
                )
            if type(destination) is not int or not 0 <= destination < len(self.order):
                raise ValueError("Destination invalide.")
            # Copy-on-write : aucune mutation mémoire si la persistance échoue.
            import copy

            state = copy.deepcopy(self.state)
            pair = self.order[position]
            state["drafts"][self.key(pair)] = comment
            existing = next(
                (r for r in state["judgments"] if (r["query_id"], r["document_id"]) == pair), None
            )
            if grade is None and existing and comment != (existing["justification"] or ""):
                grade = existing["grade"]
            if grade is not None:
                state["judgments"] = [
                    r for r in state["judgments"] if (r["query_id"], r["document_id"]) != pair
                ]
                state["judgments"].append(
                    {
                        "query_id": pair[0],
                        "document_id": pair[1],
                        "grade": grade,
                        "justification": comment or None,
                        "evaluator": self.identity["evaluator"],
                        "judged_at": datetime.now(timezone.utc).isoformat(),
                        "version": self.identity["version"],
                    }
                )
                state["judgments"].sort(key=lambda r: (r["query_id"], r["document_id"]))
                state["drafts"].pop(self.key(pair), None)
            state["position"] = destination
            state["revision"] += 1
            atomic_json(self.path, state)
            self.state = state
            return self.view()

    def export(self):
        with self.lock:
            import copy

            return copy.deepcopy(self.state["judgments"])
