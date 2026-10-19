"""Gel avant jugements, références immuables et chargement local des candidats."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.files import load_queries
from cahier_rag.evaluation.sampling import digest
from cahier_rag.search.bm25.experiments import load_experiment
from cahier_rag.search.bm25.index import restore
from cahier_rag.search.hybrid.multi.core import configuration
from cahier_rag.search.lexical import CorpusScope, SearchResult

FROZEN_INPUTS = (
    "evaluation/queries.json",
    "evaluation/local/rag007/corpus.json",
    "evaluation/local/rag014/development-replay/runs.json",
    "evaluation/local/rag014/development-replay/report.json",
    "evaluation/local/rag018/development/runs.json",
    "evaluation/local/rag018/development/report.json",
    "evaluation/local/rag018/bm25-A.sqlite3",
    "evaluation/local/rag018/bm25-B.sqlite3",
    "evaluation/local/rag018/frozen-bm25.json",
    "src/cahier_rag/search/hybrid/multi/core.py",
)


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def load_context(root):
    sample = json.loads((root / "evaluation/local/rag007/corpus.json").read_text())
    return CorpusScope(sample), load_queries(root / "evaluation/queries.json")


def freeze(root, directory):
    scope, queries = load_context(root)
    paths = [
        "evaluation/queries.json",
        "evaluation/local/rag007/corpus.json",
        "evaluation/local/rag014/development-replay/runs.json",
        "evaluation/local/rag014/development-replay/report.json",
        "evaluation/local/rag018/development/runs.json",
        "evaluation/local/rag018/development/report.json",
        "evaluation/local/rag018/bm25-A.sqlite3",
        "evaluation/local/rag018/bm25-B.sqlite3",
        "evaluation/local/rag018/frozen-bm25.json",
        "src/cahier_rag/search/hybrid/multi/core.py",
    ]
    manifest = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "configuration": configuration(),
        "sample_hash": scope.sample_hash,
        "queries_hash": digest(queries),
        "development_queries_hash": digest([q for q in queries if q["split"] == "development"]),
        "inputs": {p: file_hash(root / p) for p in paths},
        "judgments_used_for_tuning": False,
    }
    manifest["frozen_hash"] = digest(manifest)
    directory.mkdir(parents=True, exist_ok=False)
    atomic_json(directory / "frozen.json", manifest)
    return manifest


def load_frozen(root, directory):
    manifest = json.loads((directory / "frozen.json").read_text())
    body = {k: v for k, v in manifest.items() if k != "frozen_hash"}
    scope, queries = load_context(root)
    if (
        digest(body) != manifest["frozen_hash"]
        or manifest["configuration"] != configuration()
        or manifest["sample_hash"] != scope.sample_hash
        or manifest["queries_hash"] != digest(queries)
        or set(manifest["inputs"]) != set(FROZEN_INPUTS)
        or any(file_hash(root / p) != h for p, h in manifest["inputs"].items())
    ):
        raise ValueError("Configuration ou référence gelée modifiée.")
    return manifest, scope, queries


def validate_bundle(bundle, scope, queries, frozen):
    report = bundle["report"]
    body = {k: v for k, v in report.items() if k != "manifest_hash"}
    expected = {q["query_id"] for q in queries if q["split"] == "development"}
    if (
        digest(body) != report["manifest_hash"]
        or report["frozen_hash"] != frozen["frozen_hash"]
        or report["sample_hash"] != scope.sample_hash
        or report["queries_hash"] != digest(queries)
        or report["configuration"] != configuration()
        or report["split"] != "development"
    ):
        raise ValueError("Expérience multi-moteurs incompatible.")
    for name in ("runs", "sources", "traces", "measurements", "statistics"):
        if digest(bundle[name]) != report[name + "_hash"]:
            raise ValueError("Artefact de comparaison modifié.")
    if set(bundle["runs"]) != {
        "H1",
        "H2",
        "H3",
        "H4",
        "H5",
        "lexical",
        "vector",
        "bm25-A",
        "bm25-B",
    }:
        raise ValueError("Configurations ou références incomplètes.")
    for rankings in bundle["runs"].values():
        if set(rankings) != expected:
            raise ValueError("Requêtes incomplètes ou réservées.")
        for ids in rankings.values():
            if (
                len(ids) != len(set(ids))
                or len(ids) > 100
                or any(
                    d not in scope.documents or scope.documents[d]["split"] != "development"
                    for d in ids
                )
            ):
                raise ValueError("Classement hors corpus, dupliqué ou réservé.")


def load_bundle(root, frozen_directory, directory):
    frozen, scope, queries = load_frozen(root, frozen_directory)
    bundle = {
        key: json.loads((directory / (key + ".json")).read_text())
        for key in ("report", "runs", "sources", "traces", "measurements", "statistics")
    }
    validate_bundle(bundle, scope, queries, frozen)
    return bundle, frozen, scope, queries


class LocalDocuments:
    """Copie auditable BM25-A, lecture SQLite stricte, sans connexion PostgreSQL."""

    def __init__(self, path, scope):
        self.path, self.scope = path, scope

    def fetch(self, ids):
        ids = sorted(set(ids))
        if not ids or len(ids) > 500 or not set(ids) <= self.scope.documents.keys():
            raise ValueError("Lot de candidats hors corpus ou trop grand.")
        connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            rows = connection.execute(
                "SELECT id,payload FROM documents WHERE id IN (" + ",".join("?" for _ in ids) + ")",
                ids,
            ).fetchall()
        finally:
            connection.close()
        documents = {did: restore(payload) for did, payload in rows}
        if set(documents) != set(ids) or any(
            doc.content_hash != self.scope.documents[did]["content_hash"]
            for did, doc in documents.items()
        ):
            raise ValueError("Candidat absent ou modifié.")
        return documents


def restore_sources(rows, repository, scope):
    if set(rows) != {"lexical", "vector", "bm25-A", "bm25-B"}:
        raise ValueError("Quatre sources attendues.")
    docs = repository.fetch([r["document_id"] for values in rows.values() for r in values])
    result = {}
    for name, values in rows.items():
        if len(values) > 50 or len({r["document_id"] for r in values}) != len(values):
            raise ValueError("Source dupliquée ou trop profonde.")
        result[name] = []
        for r in values:
            did = r["document_id"]
            if (
                scope.documents[did]["split"] != "development"
                or r["content_hash"] != docs[did].content_hash
            ):
                raise ValueError("Source hors développement ou modifiée.")
            result[name].append(SearchResult(docs[did], r["score"]))
    return result


def baseline_prefixes(root, scope, queries):
    runs, metadata = load_experiment(root / "evaluation/local/rag018/development", scope, queries)
    return {
        m: {q: ids[:50] for q, ids in rankings.items()} for m, rankings in runs.items()
    }, metadata
