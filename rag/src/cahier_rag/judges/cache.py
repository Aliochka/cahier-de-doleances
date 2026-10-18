"""Cache SQLite local : résultats et tentatives atomiques, distincts des sessions humaines."""

import json
import sqlite3
from pathlib import Path

from cahier_rag.contracts import canonical_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.contracts import parse_output


class Cache:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.suffix not in {".sqlite3", ".db"}:
            raise ValueError("Le cache doit être un fichier SQLite distinct des sessions JSON.")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.connection = sqlite3.connect(self.path, timeout=5)
        self.path.chmod(0o600)
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS recipes(recipe_hash TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS results(recipe_hash TEXT NOT NULL REFERENCES recipes(recipe_hash),
                input_hash TEXT NOT NULL, payload TEXT NOT NULL, result_hash TEXT NOT NULL,
                PRIMARY KEY(recipe_hash,input_hash));
            CREATE TABLE IF NOT EXISTS attempts(recipe_hash TEXT NOT NULL, input_hash TEXT NOT NULL,
                attempt INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(recipe_hash,input_hash,attempt));
        """)

    def register(self, recipe):
        key = digest(recipe)
        payload = canonical_json(recipe)
        with self.connection:
            self.connection.execute("INSERT OR IGNORE INTO recipes VALUES(?,?)", (key, payload))
            old = self.connection.execute(
                "SELECT payload FROM recipes WHERE recipe_hash=?", (key,)
            ).fetchone()
            if old[0] != payload:
                raise ValueError("Recette de juge incompatible.")
        return key

    def get(self, recipe_hash, input_hash):
        row = self.connection.execute(
            "SELECT payload,result_hash FROM results WHERE recipe_hash=? AND input_hash=?",
            (recipe_hash, input_hash),
        ).fetchone()
        if row is None:
            return None
        value = json.loads(row[0])
        if digest(value) != row[1] or value.get("input_hash") != input_hash:
            raise ValueError("Jugement automatique modifié.")
        if value["status"] == "valid":
            parse_output(canonical_json(value["judgment"]))
        return value

    def commit(self, recipe_hash, records):
        with self.connection:
            for record in records:
                if record["status"] not in {"valid", "invalid", "too_long"}:
                    raise ValueError("Statut automatique invalide.")
                if record["status"] == "valid":
                    parse_output(canonical_json(record["judgment"]))
                elif record["judgment"] is not None:
                    raise ValueError("Échec de juge ne peut contenir une note.")
                key = record["input_hash"]
                old = self.get(recipe_hash, key)
                if old and old["status"] == "valid":
                    if (
                        old["judgment"] != record["judgment"]
                        or old["query_id"] != record["query_id"]
                        or old["document_id"] != record["document_id"]
                    ):
                        raise ValueError("Conflit de cache : résultat valide préservé.")
                    continue
                number = self.connection.execute(
                    "SELECT coalesce(max(attempt),0)+1 FROM attempts WHERE recipe_hash=? AND input_hash=?",
                    (recipe_hash, key),
                ).fetchone()[0]
                payload = canonical_json(record)
                self.connection.execute(
                    "INSERT INTO attempts VALUES(?,?,?,?)", (recipe_hash, key, number, payload)
                )
                self.connection.execute(
                    "INSERT INTO results VALUES(?,?,?,?) ON CONFLICT(recipe_hash,input_hash) DO UPDATE SET payload=excluded.payload,result_hash=excluded.result_hash",
                    (recipe_hash, key, payload, digest(record)),
                )

    def close(self):
        self.connection.close()
