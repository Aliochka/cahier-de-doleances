"""Cache personnel atomique, distinct des juges et des générations historiques."""

import json
import sqlite3
from pathlib import Path

from cahier_rag.contracts import canonical_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.personal.contracts import Input, schema, validate

PILOT = ("fiscalite-03", "fiscalite-05", "democratie-04", "democratie-05")


class Cache:
    def __init__(self, path, *, namespace="rag025"):
        path = Path(path).resolve()
        if (
            namespace not in {"rag025", "rag026", "rag027"}
            or namespace not in path.parts
            or path.suffix != ".sqlite3"
        ):
            raise ValueError("Cache personnel indépendant et namespace explicite requis.")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=10)
        path.chmod(0o600)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS results(key TEXT PRIMARY KEY,payload TEXT NOT NULL,hash TEXT NOT NULL)"
        )

    def get(self, key):
        row = self.connection.execute(
            "SELECT payload,hash FROM results WHERE key=?", (key,)
        ).fetchone()
        if row is None:
            return None
        value = json.loads(row[0])
        if digest(value) != row[1]:
            raise ValueError("Cache altéré.")
        return value

    def put(self, key, value):
        with self.connection:
            old = self.get(key)
            if old is not None and old != value:
                raise ValueError("Tentative existante préservée ; nouvelle recette requise.")
            self.connection.execute(
                "INSERT OR IGNORE INTO results VALUES(?,?,?)",
                (key, canonical_json(value), digest(value)),
            )

    def close(self):
        self.connection.close()


def execute(item, backend, cache):
    recipe = backend.recipe()
    key = digest(
        {
            "recipe": recipe,
            "input": item.input_hash,
            "schema": schema(item),
            "messages": item.messages(),
        }
    )
    old = cache.get(key)
    if old is not None:
        if (
            old["status"] == "valid"
            and validate(old["raw_output"], item, token_limit_reached=old["token_limit_reached"])
            != old["output"]
        ):
            raise ValueError("Validation du cache incompatible.")
        return old, True
    record = {
        "query_id": item.original.query_id,
        "stage": item.stage,
        "input_hash": item.input_hash,
        "original_input_hash": item.original.input_hash,
        "recipe": recipe,
        "messages": item.messages(),
        "schema": schema(item),
        "raw_output": None,
        "output": None,
        "status": "error",
        "error": None,
        "token_limit_reached": False,
    }
    try:
        record.update(backend.generate_one(item))
        try:
            record["output"] = validate(
                record["raw_output"], item, token_limit_reached=record["token_limit_reached"]
            )
            record["status"] = "valid"
        except (ValueError, TypeError, KeyError):
            record["status"] = "invalid"
            record["error"] = "deterministic_validation_failed"
    except (RuntimeError, MemoryError, ValueError):
        record["error"] = "local_inference_failed"
    cache.put(key, record)
    return record, False


def answer(original, backend, cache, *, method="direct"):
    if method not in {"direct", "two-step"}:
        raise ValueError("Méthode inconnue.")
    stages = []
    analysis = None
    if method == "two-step":
        record, reused = execute(Input(original, "analysis"), backend, cache)
        stages.append({"record": record, "reused": reused})
        if record["status"] != "valid":
            return {"status": "invalid_analysis", "stages": stages, "output": None}
        analysis = record["output"]
    record, reused = execute(
        Input(original, "direct" if method == "direct" else "synthesis", analysis), backend, cache
    )
    stages.append({"record": record, "reused": reused})
    return {"status": record["status"], "stages": stages, "output": record["output"]}
