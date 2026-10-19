"""Plans communs aux deux modèles ; listes sources distinctes des entrées aveugles."""

import json
from datetime import datetime, timezone
from pathlib import Path

from cahier_rag.annotation.session import atomic_json
from cahier_rag.contracts import canonical_json
from cahier_rag.embeddings.snapshots import sha256_file
from cahier_rag.evaluation.sampling import digest
from cahier_rag.reranking.contracts import Pair, PreparationConfig
from cahier_rag.reranking.preparation import segments
from cahier_rag.search.hybrid.multi.artifacts import LocalDocuments, load_bundle


def select_candidates(bundle):
    candidates = {
        name: {q: ids[:50] for q, ids in bundle["runs"][source].items()}
        for name, source in (("H1", "H1"), ("H5", "H5"), ("V", "vector"))
    }
    pairs = sorted(
        {(q, d) for rankings in candidates.values() for q, ids in rankings.items() for d in ids}
    )
    return candidates, pairs


def prepare(root, directory, backends, config=PreparationConfig()):
    bundle, frozen, scope, queries = load_bundle(
        root,
        root / "evaluation/local/rag019/configuration",
        root / "evaluation/local/rag019/development",
    )
    candidates, pairs = select_candidates(bundle)
    if set(backends) != {"R1", "R2"}:
        raise ValueError("Les deux tokenizers prévus sont requis.")
    recipes = {m: b.recipe() for m, b in backends.items()}
    repository = LocalDocuments(root / "evaluation/local/rag018/bm25-A.sqlite3", scope)
    index = {q["query_id"]: q for q in queries}
    directory.mkdir(parents=True, exist_ok=False)
    records = []
    with (directory / "inputs.jsonl").open("x", encoding="utf-8") as stream:
        for offset in range(0, len(pairs), 25):
            batch = pairs[offset : offset + 25]
            units = repository.fetch([d for q, d in batch])
            for qid, did in batch:
                if (
                    index[qid]["split"] != "development"
                    or scope.documents[did]["split"] != "development"
                ):
                    raise ValueError("Candidat réservé refusé.")
                item = {
                    "query_id": qid,
                    "document_id": did,
                    "source_hash": units[did].content_hash,
                    "segments": [],
                }
                for segment in segments(
                    qid, index[qid]["text"], units[did], list(backends.values()), config
                ):
                    counts = {
                        m: b.token_count(segment.query, segment.document)
                        for m, b in backends.items()
                    }
                    item["segments"].append(
                        {
                            "input_hash": segment.input_hash,
                            "start": segment.start,
                            "end": segment.end,
                            "segment_index": segment.segment_index,
                            "tokens": counts,
                        }
                    )
                    stream.write(canonical_json(segment.to_dict()) + "\n")
                records.append(item)
    manifest = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sample_hash": scope.sample_hash,
        "queries_hash": digest(queries),
        "rag019_frozen_hash": frozen["frozen_hash"],
        "rag019_experiment_hash": bundle["report"]["manifest_hash"],
        "configuration": config.to_dict(),
        "backends": recipes,
        "pairs": records,
        "candidates_hash": digest(candidates),
        "inputs_hash": sha256_file(directory / "inputs.jsonl"),
        "score_tie_break": "document_id binary",
        "batch_documents": 2,
        "batch_segments": 4,
        "judgments_used": False,
        "critical_sources": {
            name: sha256_file(Path(__file__).parent / name)
            for name in ("backend.py", "contracts.py", "preparation.py", "pipeline.py")
        },
    }
    manifest["manifest_hash"] = digest(manifest)
    atomic_json(directory / "candidates.json", candidates)
    atomic_json(directory / "manifest.json", manifest)
    return manifest


def load_plan(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    body = {k: v for k, v in manifest.items() if k != "manifest_hash"}
    candidates = json.loads((directory / "candidates.json").read_text())
    targets = {
        (q, d) for rankings in candidates.values() for q, ids in rankings.items() for d in ids
    }
    keys = [(p["query_id"], p["document_id"]) for p in manifest["pairs"]]
    if (
        digest(body) != manifest["manifest_hash"]
        or digest(candidates) != manifest["candidates_hash"]
        or sha256_file(directory / "inputs.jsonl") != manifest["inputs_hash"]
        or set(candidates) != {"H1", "H5", "V"}
        or set(manifest["critical_sources"])
        != {"backend.py", "contracts.py", "preparation.py", "pipeline.py"}
        or any(
            sha256_file(Path(__file__).parent / name) != value
            for name, value in manifest["critical_sources"].items()
        )
        or len(keys) != len(set(keys))
        or set(keys) != targets
        or manifest["configuration"]
        != PreparationConfig(
            **{
                k: manifest["configuration"][k]
                for k in ("contextualization", "budget", "overlap_chars", "aggregation", "version")
            }
        ).to_dict()
    ):
        raise ValueError("Plan de reranking modifié ou incompatible.")
    return manifest, candidates


def iter_units(directory, manifest):
    with (directory / "inputs.jsonl").open(encoding="utf-8") as stream:
        for entry in manifest["pairs"]:
            items = []
            for expected in entry["segments"]:
                raw = stream.readline(4000001)
                if not raw or len(raw) > 4000000:
                    raise ValueError("Fichier de couples incomplet ou trop volumineux.")
                item = Pair(**json.loads(raw))
                if (
                    item.input_hash != expected["input_hash"]
                    or item.query_id != entry["query_id"]
                    or item.document_id != entry["document_id"]
                    or item.source_hash != entry["source_hash"]
                    or (item.start, item.end, item.segment_index)
                    != (expected["start"], expected["end"], expected["segment_index"])
                ):
                    raise ValueError("Texte, positions ou identité de segment modifiés.")
                items.append(item)
            if not items:
                raise ValueError("Couple sans segment.")
            yield entry, items
        if stream.read(1):
            raise ValueError("Segments supplémentaires hors plan.")
