"""Reranking dédupliqué, lots atomiques, reprise et temps sans répétitions GPU."""

import time
from datetime import datetime, timezone

from cahier_rag.annotation.session import atomic_json
from cahier_rag.embeddings.benchmark import MemorySampler
from cahier_rag.evaluation.sampling import digest
from cahier_rag.reranking.contracts import validate_scores
from cahier_rag.reranking.planning import iter_units, load_plan


def recipe(manifest, model, backend):
    actual = backend.recipe()
    if actual != manifest["backends"][model]:
        raise ValueError("Modèle ou recette différents du plan figé.")
    return {
        "version": 1,
        "plan_hash": manifest["manifest_hash"],
        "backend": actual,
        "batch_documents": manifest["batch_documents"],
        "batch_segments": manifest["batch_segments"],
        "preparation": manifest["configuration"],
    }


def latency_prefixes(manifest, records, batches):
    by_query = {}
    batch_index = {b["batch_id"]: b for b in batches}
    for entry in manifest["pairs"]:
        pair = entry["query_id"], entry["document_id"]
        if pair in records:
            by_query.setdefault(pair[0], []).append(pair)
    result = {}
    for q, keys in sorted(by_query.items()):
        result[q] = {}
        for n in (10, 20, 50):
            if len(keys) < n:
                continue
            chosen = keys[:n]
            selected = {records[p]["batch_id"] for p in chosen}
            expected = {(q, d) for bid in selected for d in batch_index[bid]["document_ids"]}
            exact = set(chosen) == expected
            result[q][str(n)] = {
                "seconds": sum(batch_index[b]["seconds"] for b in selected) if exact else None,
                "documents": n,
                "exact_batch_boundary": exact,
                "selection": "first unique query/document IDs in frozen order; not retrieval ranks",
            }
    return result


def run(directory, model, backend, cache, *, stop_after=None):
    manifest, _ = load_plan(directory)
    if model not in manifest["backends"] or (
        stop_after is not None and (type(stop_after) is not int or stop_after <= 0)
    ):
        raise ValueError("Modèle ou point d'arrêt invalide.")
    configuration = recipe(manifest, model, backend)
    key = cache.register(configuration)
    processed, reused, new = 0, 0, 0
    gpu_seconds = 0.0
    started = time.perf_counter()
    iterator = iter_units(directory, manifest)
    pending = []
    status = "running"

    def progress():
        value = {
            "plan_hash": manifest["manifest_hash"],
            "recipe_hash": key,
            "model": model,
            "status": status,
            "processed": processed,
            "total": len(manifest["pairs"]),
            "new": new,
            "reused": reused,
            "eta_seconds": (len(manifest["pairs"]) - processed) * gpu_seconds / new
            if new
            else None,
        }
        atomic_json(directory / (model + "-progress.json"), value)

    def persist(batch):
        nonlocal processed, new, gpu_seconds
        backend.load()
        flattened = [p for _, items in batch for p in items]
        for entry, items in batch:
            if any(
                backend.token_count(p.query, p.document) != expected["tokens"][model]
                for p, expected in zip(items, entry["segments"])
            ):
                raise ValueError("Tokenisation différente du précontrôle.")
        backend.synchronize()
        before = time.perf_counter()
        scores = []
        for offset in range(0, len(flattened), manifest["batch_segments"]):
            items = flattened[offset : offset + manifest["batch_segments"]]
            scores.extend(validate_scores(backend.score(items), len(items)))
        backend.synchronize()
        elapsed = time.perf_counter() - before
        qid = batch[0][0]["query_id"]
        ids = [e["document_id"] for e, _ in batch]
        batch_id = digest([key, qid, ids])
        metadata = {
            "batch_id": batch_id,
            "query_id": qid,
            "document_ids": ids,
            "seconds": elapsed,
            "segments": len(flattened),
            "input_tokens": sum(s["tokens"][model] for e, _ in batch for s in e["segments"]),
        }
        records = []
        offset = 0
        for entry, items in batch:
            values = scores[offset : offset + len(items)]
            offset += len(items)
            records.append(
                {
                    "query_id": qid,
                    "document_id": entry["document_id"],
                    "source_hash": entry["source_hash"],
                    "unit_input_hash": digest(entry),
                    "score": max(values),
                    "batch_id": batch_id,
                    "segments": [
                        {
                            "input_hash": p.input_hash,
                            "start": p.start,
                            "end": p.end,
                            "segment_index": p.segment_index,
                            "score": score,
                        }
                        for p, score in zip(items, values)
                    ],
                }
            )
        cache.commit(key, metadata, records)
        processed += len(records)
        new += len(records)
        gpu_seconds += elapsed
        progress()
        if processed % 50 == 0:
            print(f"{model}: {processed}/{len(manifest['pairs'])} couples uniques", flush=True)

    with MemorySampler() as memory:
        try:
            for entry, items in iterator:
                if pending and pending[0][0]["query_id"] != entry["query_id"]:
                    persist(pending)
                    pending = []
                    if stop_after and processed >= stop_after:
                        break
                old = cache.get(key, entry["query_id"], entry["document_id"])
                if old is not None:
                    if (
                        old["unit_input_hash"] != digest(entry)
                        or old["source_hash"] != entry["source_hash"]
                    ):
                        raise ValueError("Contenu ou segments différents du cache.")
                    processed += 1
                    reused += 1
                    continue
                pending.append((entry, items))
                if len(pending) == manifest["batch_documents"]:
                    persist(pending)
                    pending = []
                    if stop_after and processed >= stop_after:
                        break
            if pending:
                persist(pending)
            status = "complete" if processed == len(manifest["pairs"]) else "stopped"
            progress()
        except BaseException:
            status = "error"
            progress()
            raise
        finally:
            iterator.close()
            backend.close()
    records = {}
    for e in manifest["pairs"]:
        value = cache.get(key, e["query_id"], e["document_id"])
        if value is not None:
            records[e["query_id"], e["document_id"]] = value
    batches = cache.batches(key)
    result = {
        "version": 1,
        "model": model,
        "recipe_hash": key,
        "recipe": configuration,
        "plan_hash": manifest["manifest_hash"],
        "complete": status == "complete",
        "processed": processed,
        "new": new,
        "reused": reused,
        "seconds": time.perf_counter() - started,
        "load_seconds": backend.load_seconds,
        "peak_rss_bytes": memory.peak,
        "scoring_seconds_cumulative": sum(b["seconds"] for b in batches),
        "segments_cumulative": sum(b["segments"] for b in batches),
        "input_tokens_cumulative": sum(b["input_tokens"] for b in batches),
        "latencies_prefix": latency_prefixes(manifest, records, batches),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if getattr(backend, "torch", None) is not None and backend.device == "cuda":
        result["hardware"] = {
            "gpu": backend.torch.cuda.get_device_name(),
            "cuda": backend.torch.version.cuda,
            "peak_allocated_bytes": backend.torch.cuda.max_memory_allocated(),
            "peak_reserved_bytes": backend.torch.cuda.max_memory_reserved(),
        }
    atomic_json(directory / "history" / (model + "-" + digest(result) + ".json"), result)
    atomic_json(directory / (model + "-run.json"), result)
    return result
