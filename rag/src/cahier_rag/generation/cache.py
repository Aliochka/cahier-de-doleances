"""Cache de génération indépendant, tentatives et checkpoints atomiques immuables."""

import json
import sqlite3
from pathlib import Path

from cahier_rag.contracts import canonical_json
from cahier_rag.evaluation.sampling import digest


class Cache:
    def __init__(self, path, *, readonly=False):
        self.path = Path(path)
        if self.path.suffix != ".sqlite3" or "rag022" not in self.path.resolve().parts:
            raise ValueError("Cache de génération rag022 indépendant requis.")
        if not readonly:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(
            self.path.resolve().as_uri() + ("?mode=ro" if readonly else "?mode=rwc"),
            uri=True,
            timeout=5,
        )
        if readonly:
            return
        self.path.chmod(0o600)
        self.connection.executescript("""CREATE TABLE IF NOT EXISTS generation_recipes(key TEXT PRIMARY KEY,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS generation_attempts(recipe TEXT,input_hash TEXT,attempt INTEGER,payload TEXT,hash TEXT,PRIMARY KEY(recipe,input_hash,attempt));
CREATE TABLE IF NOT EXISTS generation_checkpoints(recipe TEXT,input_hash TEXT,attempt INTEGER,PRIMARY KEY(recipe,input_hash));""")

    def register(self, value):
        key = digest(value)
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO generation_recipes VALUES(?,?)", (key, canonical_json(value))
            )
            stored = self.connection.execute(
                "SELECT payload FROM generation_recipes WHERE key=?", (key,)
            ).fetchone()[0]
            if json.loads(stored) != value:
                raise ValueError("Recette incompatible.")
        return key

    def get(self, recipe, input_hash):
        row = self.connection.execute(
            "SELECT a.payload,a.hash FROM generation_attempts a JOIN generation_checkpoints c ON a.recipe=c.recipe AND a.input_hash=c.input_hash AND a.attempt=c.attempt WHERE a.recipe=? AND a.input_hash=?",
            (recipe, input_hash),
        ).fetchone()
        if row is None:
            return None
        value = json.loads(row[0])
        if digest(value) != row[1] or value["input_hash"] != input_hash:
            raise ValueError("Résultat de génération modifié.")
        return value

    def commit(self, recipe, record, *, retry_invalid=False):
        with self.connection:
            old = self.get(recipe, record["input_hash"])
            if old:
                if old == record:
                    return
                if old["status"] == "valid" or not retry_invalid:
                    raise ValueError("Tentative existante préservée.")
            if record["status"] not in {"valid", "invalid", "error", "too_long"} or (
                record["status"] == "valid"
            ) != (record["output"] is not None):
                raise ValueError("Statut incompatible.")
            n = self.connection.execute(
                "SELECT coalesce(max(attempt),0)+1 FROM generation_attempts WHERE recipe=? AND input_hash=?",
                (recipe, record["input_hash"]),
            ).fetchone()[0]
            self.connection.execute(
                "INSERT INTO generation_attempts VALUES(?,?,?,?,?)",
                (recipe, record["input_hash"], n, canonical_json(record), digest(record)),
            )
            self.connection.execute(
                "INSERT INTO generation_checkpoints VALUES(?,?,?) ON CONFLICT(recipe,input_hash) DO UPDATE SET attempt=excluded.attempt",
                (recipe, record["input_hash"], n),
            )

    def close(self):
        self.connection.close()
