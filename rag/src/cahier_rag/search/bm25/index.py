"""Index inversé SQLite, BM25 explicite, lots atomiques et statistiques par partition."""

import hashlib
import json
import math
import sqlite3
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from cahier_rag.contracts import TextUnit, UnitType, canonical_json, validate_id
from cahier_rag.evaluation.sampling import digest
from cahier_rag.search.lexical import SearchResult
from cahier_rag.search.preparation import Preparation


@dataclass(frozen=True)
class Config:
    variant: str = "A"
    k1: float = 1.2
    b: float = 0.75

    def __post_init__(self):
        if self.variant not in {"A", "B"} or self.k1 != 1.2 or self.b != 0.75:
            raise ValueError("Recette RAG-018 figée : A/B, k1=1.2, b=0.75.")

    def to_dict(self):
        return asdict(self) | {
            "version": 1,
            "idf": "ln(1+(N-df+0.5)/(df+0.5))",
            "statistics": "per split before questionnaire/type filters",
            "query": Preparation().to_dict(),
            "question": "once, B only",
        }


def bm25(tf, df, n, dl, average, *, k1=1.2, b=0.75):
    if tf <= 0 or n <= 0 or average <= 0:
        return 0.0
    return (
        math.log1p((n - df + 0.5) / (df + 0.5))
        * tf
        * (k1 + 1)
        / (tf + k1 * (1 - b + b * dl / average))
    )


def restore(payload):
    value = json.loads(payload)
    original_id, checksum = value.pop("document_id"), value.pop("content_hash")
    if value.pop("contract_version") != 1:
        raise ValueError("Contrat documentaire incompatible.")
    for name in ("answer_id", "question_id", "questionnaire_id", "contribution_id"):
        value[name] = int(value[name])
    value["unit_type"] = UnitType(value["unit_type"])
    if value["submitted_at"]:
        value["submitted_at"] = datetime.fromisoformat(value["submitted_at"])
    unit = TextUnit(**value)
    if unit.document_id != original_id or unit.content_hash != checksum:
        raise ValueError("Document BM25 modifié.")
    return unit


def sequence(tokens):
    # Représentation non ambiguë pour vérifier les phrases de lexèmes.
    return " " + " ".join(t.encode().hex() for t in tokens) + " "


class BM25Index:
    def __init__(self, path, scope, tokenizer, config=Config(), *, writable=False):
        self.path, self.scope, self.tokenizer, self.config = Path(path), scope, tokenizer, config
        self.configuration = {
            "corpus": scope.sample_hash,
            "bm25": config.to_dict(),
            "tokenizer": tokenizer.configuration,
            "sqlite": sqlite3.sqlite_version,
        }
        self.key = digest(self.configuration)
        if writable:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        uri = self.path.resolve().as_uri() + ("?mode=rwc" if writable else "?mode=ro")
        self.db = sqlite3.connect(uri, uri=True, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA cache_size=-32768")
        self.db.execute("PRAGMA temp_store=FILE")
        self.writable = writable
        if writable:
            self.path.chmod(0o600)
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents(
                    id TEXT PRIMARY KEY,split TEXT NOT NULL,form TEXT NOT NULL,kind TEXT NOT NULL,
                    payload TEXT NOT NULL,length INTEGER NOT NULL,sequence TEXT NOT NULL,hash TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS document_filters ON documents(split,form,kind);
                CREATE TABLE IF NOT EXISTS postings(
                    split TEXT NOT NULL,term TEXT NOT NULL,id TEXT NOT NULL REFERENCES documents(id),
                    tf INTEGER NOT NULL CHECK(tf>0), PRIMARY KEY(split,term,id)) WITHOUT ROWID;
                CREATE INDEX IF NOT EXISTS postings_document ON postings(id,term);
                CREATE TABLE IF NOT EXISTS stats(split TEXT PRIMARY KEY,n INTEGER,total INTEGER);
                CREATE TABLE IF NOT EXISTS df(split TEXT,term TEXT,n INTEGER,PRIMARY KEY(split,term)) WITHOUT ROWID;
            """)
        row = self.db.execute("SELECT value FROM state WHERE key='configuration'").fetchone()
        if row is None and writable:
            with self.db:
                self.db.execute(
                    "INSERT INTO state VALUES('configuration',?)",
                    (canonical_json(self.configuration),),
                )
        elif row is None or json.loads(row[0]) != self.configuration:
            self.close()
            raise ValueError("Index, tokenizer ou recette incompatibles.")

    def close(self):
        self.db.close()

    def _ready(self):
        row = self.db.execute("SELECT value FROM state WHERE key='complete'").fetchone()
        if row is None or row[0] != self.key:
            raise ValueError("Index incomplet ; reprendre sa construction.")

    def build(self, repository, *, batch_size=50, stop_after=None):
        if not self.writable or type(batch_size) is not int or not 1 <= batch_size <= 100:
            raise ValueError("Index inscriptible et lots de 1 à 100 requis.")
        if stop_after is not None and (type(stop_after) is not int or stop_after <= 0):
            raise ValueError("Point d'arrêt positif requis.")
        started, added = time.perf_counter(), 0
        done = {r[0] for r in self.db.execute("SELECT id FROM documents")}
        ids = sorted(set(self.scope.documents) - done)
        for offset in range(0, len(ids), batch_size):
            subset = ids[offset : offset + batch_size]
            docs = repository.fetch(subset)
            texts = [
                docs[d].text + ("\n" + docs[d].question_text if self.config.variant == "B" else "")
                for d in subset
            ]
            tokens = self.tokenizer.encode(texts)
            if len(tokens) != len(subset):
                raise ValueError("Comptage tokenizer incompatible.")
            with self.db:
                for did, terms in zip(subset, tokens):
                    unit = docs[did]
                    expected = self.scope.documents[did]
                    if unit.document_id != did or unit.content_hash != expected["content_hash"]:
                        raise ValueError("Document hors manifeste ou modifié.")
                    split = expected["split"]
                    seq = sequence(terms)
                    payload = unit.to_json()
                    checksum = digest([payload, terms, split])
                    self.db.execute(
                        "INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)",
                        (
                            did,
                            split,
                            str(unit.questionnaire_id),
                            unit.unit_type.value,
                            payload,
                            len(terms),
                            seq,
                            checksum,
                        ),
                    )
                    self.db.executemany(
                        "INSERT INTO postings VALUES(?,?,?,?)",
                        [(split, t, did, tf) for t, tf in sorted(Counter(terms).items())],
                    )
            added += len(subset)
            if added % 1000 == 0:
                print(
                    f"BM25-{self.config.variant}: {len(done) + added}/{len(self.scope.documents)}",
                    flush=True,
                )
            if stop_after is not None and added >= stop_after:
                break
        if self.db.execute("SELECT count(*) FROM documents").fetchone()[0] == len(
            self.scope.documents
        ):
            with self.db:
                self.db.execute("DELETE FROM stats")
                self.db.execute("DELETE FROM df")
                self.db.execute(
                    "INSERT INTO stats SELECT split,count(*),sum(length) FROM documents GROUP BY split"
                )
                self.db.execute(
                    "INSERT INTO df SELECT split,term,count(*) FROM postings GROUP BY split,term"
                )
                self.db.execute("INSERT OR REPLACE INTO state VALUES('complete',?)", (self.key,))
        return {
            "added": added,
            "seconds": time.perf_counter() - started,
            "configuration": self.configuration,
        }

    def verify(self):
        self._ready()
        if self.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Intégrité SQLite invalide.")
        checksum, seen = hashlib.sha256(), set()
        for row in self.db.execute("SELECT * FROM documents ORDER BY id"):
            unit = restore(row["payload"])
            expected = self.scope.documents.get(row["id"])
            terms = [bytes.fromhex(t).decode() for t in row["sequence"].split()]
            actual = dict(
                self.db.execute(
                    "SELECT term,tf FROM postings WHERE id=? ORDER BY term", (row["id"],)
                ).fetchall()
            )
            if (
                expected is None
                or unit.document_id != row["id"]
                or unit.content_hash != expected["content_hash"]
                or row["split"] != expected["split"]
                or row["form"] != str(unit.questionnaire_id)
                or row["kind"] != unit.unit_type.value
                or row["length"] != len(terms)
                or actual != dict(Counter(terms))
                or row["hash"] != digest([row["payload"], terms, row["split"]])
            ):
                raise ValueError("Contenu, fréquences ou périmètre BM25 modifiés.")
            checksum.update(canonical_json([row["id"], row["hash"]]).encode())
            seen.add(row["id"])
        if seen != set(self.scope.documents):
            raise ValueError("Index extérieur ou incomplet.")
        if (
            self.db.execute(
                "SELECT split,term,n FROM df EXCEPT SELECT split,term,count(*) FROM postings GROUP BY split,term"
            ).fetchone()
            or self.db.execute(
                "SELECT split,term,count(*) FROM postings GROUP BY split,term EXCEPT SELECT split,term,n FROM df"
            ).fetchone()
        ):
            raise ValueError("Fréquences documentaires modifiées.")
        if (
            self.db.execute(
                "SELECT split,n,total FROM stats EXCEPT SELECT split,count(*),sum(length) FROM documents GROUP BY split"
            ).fetchone()
            or self.db.execute(
                "SELECT split,count(*),sum(length) FROM documents GROUP BY split EXCEPT SELECT split,n,total FROM stats"
            ).fetchone()
        ):
            raise ValueError("Statistiques de longueur modifiées.")
        return {
            "documents": len(seen),
            "index_hash": checksum.hexdigest(),
            "recipe_hash": self.key,
            "postings": self.db.execute("SELECT count(*) FROM postings").fetchone()[0],
            "partitions": [dict(r) for r in self.db.execute("SELECT * FROM stats ORDER BY split")],
            "bytes": self.path.stat().st_size,
            "configuration": self.configuration,
        }

    def search(
        self, query, *, limit=10, split="development", questionnaire_id=None, unit_type=None
    ):
        self._ready()
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or split not in {"development", "evaluation"}
        ):
            raise ValueError("Limite 1–100 et partition explicite requises.")
        if questionnaire_id is not None:
            validate_id(questionnaire_id, "questionnaire_id")
        if unit_type is not None:
            unit_type = UnitType(unit_type).value
        terms, phrases, excluded = self.tokenizer.query(query)
        if not terms or any(not p for p in phrases):
            return []
        stats = self.db.execute("SELECT n,total FROM stats WHERE split=?", (split,)).fetchone()
        if not stats or stats[1] == 0:
            return []
        n, total = stats
        parameters = {
            "split": split,
            "average": total / n,
            "k1": self.config.k1,
            "b": self.config.b,
            "limit": limit,
        }
        values = []
        for i, t in enumerate(terms):
            df = self.db.execute("SELECT n FROM df WHERE split=? AND term=?", (split, t)).fetchone()
            if df:
                values.append(f"(:term{i},:idf{i})")
                parameters[f"term{i}"] = t
                parameters[f"idf{i}"] = math.log1p((n - df[0] + 0.5) / (df[0] + 0.5))
        if not values:
            return []
        filters = []
        for column, value in (
            ("form", str(questionnaire_id) if questionnaire_id is not None else None),
            ("kind", unit_type),
        ):
            if value is not None:
                filters.append(f"d.{column}=:{column}")
                parameters[column] = value
        for i, p in enumerate(phrases):
            filters.append(f"instr(d.sequence,:phrase{i})>0")
            parameters[f"phrase{i}"] = sequence(p)
        for i, p in enumerate(excluded):
            if p:
                filters.append(f"instr(d.sequence,:excluded{i})=0")
                parameters[f"excluded{i}"] = sequence(p)
        sql = """WITH q(term,idf) AS (VALUES %s)
            SELECT d.id,SUM(q.idf*p.tf*(:k1+1)/(p.tf+:k1*(1-:b+:b*d.length/:average))) AS score
            FROM q JOIN postings p ON p.term=q.term AND p.split=:split
            JOIN documents d ON d.id=p.id WHERE d.split=:split %s
            GROUP BY d.id ORDER BY score DESC,d.id COLLATE BINARY LIMIT :limit
        """ % (",".join(values), "".join(" AND " + f for f in filters))
        start = time.monotonic()
        self.db.set_progress_handler(lambda: int(time.monotonic() - start > 5), 10000)
        try:
            rows = self.db.execute(sql, parameters).fetchall()
        finally:
            self.db.set_progress_handler(None, 0)
        results = []
        for did, score in rows:
            unit = restore(
                self.db.execute("SELECT payload FROM documents WHERE id=?", (did,)).fetchone()[0]
            )
            if unit.content_hash != self.scope.documents[did]["content_hash"] or not math.isfinite(
                score
            ):
                raise ValueError("Résultat BM25 incompatible.")
            results.append(SearchResult(unit, score))
        return results
