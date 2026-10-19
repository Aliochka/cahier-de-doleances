"""Checkpoint atomique par lot de couples, recettes et scores validés par empreinte."""

import json
import sqlite3
from pathlib import Path

from cahier_rag.contracts import canonical_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.reranking.contracts import validate_scores


class Cache:
    def __init__(self, path, *, readonly=False):
        path = Path(path)
        if path.suffix != ".sqlite3":
            raise ValueError("Cache SQLite distinct des sessions d'annotation requis.")
        if not readonly:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(
            path.resolve().as_uri() + ("?mode=ro" if readonly else "?mode=rwc"), uri=True, timeout=5
        )
        if not readonly:
            path.chmod(0o600)
        self.connection.execute("PRAGMA foreign_keys=ON")
        if readonly:
            return
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS recipes(key TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS batches(recipe TEXT REFERENCES recipes(key),id TEXT,payload TEXT NOT NULL,hash TEXT NOT NULL,PRIMARY KEY(recipe,id));
            CREATE TABLE IF NOT EXISTS scores(recipe TEXT REFERENCES recipes(key),query_id TEXT,document_id TEXT,payload TEXT NOT NULL,hash TEXT NOT NULL,PRIMARY KEY(recipe,query_id,document_id));
        """)

    def register(self, recipe):
        key = digest(recipe)
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO recipes VALUES(?,?)", (key, canonical_json(recipe))
            )
            stored = json.loads(
                self.connection.execute(
                    "SELECT payload FROM recipes WHERE key=?", (key,)
                ).fetchone()[0]
            )
            if stored != recipe:
                raise ValueError("Recette de cache incompatible.")
        return key

    def get(self, recipe, qid, did):
        row = self.connection.execute(
            "SELECT payload,hash FROM scores WHERE recipe=? AND query_id=? AND document_id=?",
            (recipe, qid, did),
        ).fetchone()
        if row is None:
            return None
        value = json.loads(row[0])
        if digest(value) != row[1] or value["query_id"] != qid or value["document_id"] != did:
            raise ValueError("Score de reranking modifié.")
        validate_scores(
            [value["score"], *[v["score"] for v in value["segments"]]], 1 + len(value["segments"])
        )
        if not value["segments"] or value["score"] != max(v["score"] for v in value["segments"]):
            raise ValueError("Agrégation de segments incompatible.")
        return value

    def commit(self, recipe, batch, records):
        with self.connection:
            for value in records:
                validate_scores(
                    [value["score"], *[r["score"] for r in value["segments"]]],
                    1 + len(value["segments"]),
                )
                if not value["segments"] or value["score"] != max(
                    v["score"] for v in value["segments"]
                ):
                    raise ValueError("Agrégation incorrecte.")
                old = self.get(recipe, value["query_id"], value["document_id"])
                if old is not None and old != value:
                    raise ValueError("Conflit de cache : score valide préservé.")
                self.connection.execute(
                    "INSERT OR IGNORE INTO scores VALUES(?,?,?,?,?)",
                    (
                        recipe,
                        value["query_id"],
                        value["document_id"],
                        canonical_json(value),
                        digest(value),
                    ),
                )
            old = self.connection.execute(
                "SELECT payload FROM batches WHERE recipe=? AND id=?", (recipe, batch["batch_id"])
            ).fetchone()
            if old and json.loads(old[0]) != batch:
                raise ValueError("Conflit de métadonnées de lot.")
            self.connection.execute(
                "INSERT OR IGNORE INTO batches VALUES(?,?,?,?)",
                (recipe, batch["batch_id"], canonical_json(batch), digest(batch)),
            )

    def batches(self, recipe):
        result = []
        for raw, checksum in self.connection.execute(
            "SELECT payload,hash FROM batches WHERE recipe=? ORDER BY id", (recipe,)
        ):
            value = json.loads(raw)
            if digest(value) != checksum:
                raise ValueError("Mesure de lot modifiée.")
            result.append(value)
        return result

    def close(self):
        self.connection.close()
