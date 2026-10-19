"""Générations indépendantes, cache par requête, reprise sans réparation implicite."""

import time
from datetime import datetime, timezone

from cahier_rag.annotation.session import atomic_json
from cahier_rag.embeddings.benchmark import MemorySampler
from cahier_rag.evaluation.sampling import digest
from cahier_rag.generation.contracts import answer_text, parse_output
from cahier_rag.generation.planning import PILOT, iter_inputs, load_plan


def run(
    directory, backend, cache, *, stage="pilot", stop_after=None, root=None, retry_errors=False
):
    plan = load_plan(directory, root)
    actual = backend.recipe()
    if actual != plan["backend"] or stage not in {"pilot", "development"}:
        raise ValueError("Recette ou étape incompatible.")
    recipe = {"version": 1, "plan_hash": plan["plan_hash"], "backend": actual}
    key = cache.register(recipe)
    if stage == "development":
        for e in plan["entries"]:
            if e["query_id"] in PILOT:
                old = cache.get(key, e["input_hash"])
                if old is None or old["status"] != "valid":
                    raise ValueError("Pilote techniquement incomplet : campagne non autorisée.")
    selected = [e for e in plan["entries"] if stage == "development" or e["query_id"] in PILOT]
    records = []
    new, reused = 0, 0
    started = time.perf_counter()
    status = "running"

    def progress():
        atomic_json(
            directory / (stage + "-progress.json"),
            {
                "stage": stage,
                "status": status,
                "completed": len(records),
                "total": len(selected),
                "new": new,
                "reused": reused,
                "plan_hash": plan["plan_hash"],
                "recipe_hash": key,
                "eta_seconds": (len(selected) - len(records))
                * (time.perf_counter() - started)
                / new
                if new
                else None,
            },
        )

    iterator = iter_inputs(directory, plan)
    with MemorySampler() as memory:
        try:
            for item, row in iterator:
                if stage == "pilot" and item.query_id not in PILOT:
                    continue
                old = cache.get(key, item.input_hash)
                if old is not None and not (retry_errors and old["status"] == "error"):
                    if (
                        old["status"] == "valid"
                        and parse_output(old["raw_output"], item) != old["output"]
                    ):
                        raise ValueError("Sortie validée différente du cache.")
                    records.append(old)
                    reused += 1
                    progress()
                    continue
                if (
                    backend.prompt(item) != row["prompt"]
                    or backend.token_counts([item])[0] != row["prompt_tokens"]
                ):
                    raise ValueError("Gabarit ou tokenization différents.")
                backend.load()
                before = time.perf_counter()
                raw = None
                parsed = None
                error = None
                status_record = "error"
                output_tokens = 0
                try:
                    raw = backend.generate([item])[0]
                    output_tokens = backend.last_output_tokens
                    try:
                        parsed = parse_output(raw, item)
                        status_record = "valid"
                    except ValueError as exc:
                        error = str(exc)
                        status_record = "invalid"
                except (RuntimeError, MemoryError, ValueError):
                    error = "local_inference_error"
                elapsed = time.perf_counter() - before
                record = {
                    "query_id": item.query_id,
                    "input_hash": item.input_hash,
                    "context_hash": item.document["context_hash"],
                    "status": status_record,
                    "raw_output": raw,
                    "output": parsed,
                    "validation_error": error,
                    "answer": answer_text(parsed) if parsed else None,
                    "seconds": elapsed,
                    "prompt_tokens": row["prompt_tokens"],
                    "output_tokens": output_tokens,
                    "finish_reason": "length"
                    if output_tokens >= backend.config.max_new_tokens
                    else "eos"
                    if raw is not None
                    else "error",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
                cache.commit(key, record, retry_invalid=retry_errors)
                records.append(record)
                new += 1
                progress()
                print(
                    f"Génération {stage}: {len(records)}/{len(selected)} — {item.query_id} — {status_record} — {elapsed:.1f}s",
                    flush=True,
                )
                if status_record == "error":
                    raise ValueError("Erreur locale conservée ; campagne arrêtée.")
                if stop_after and new >= stop_after:
                    break
            status = "complete" if len(records) == len(selected) else "stopped"
            progress()
        except BaseException:
            status = "error"
            progress()
            raise
        finally:
            iterator.close()
            backend.close()
    result = {
        "stage": stage,
        "complete": status == "complete",
        "plan_hash": plan["plan_hash"],
        "recipe_hash": key,
        "new": new,
        "reused": reused,
        "processed": len(records),
        "valid": sum(r["status"] == "valid" for r in records),
        "seconds": time.perf_counter() - started,
        "load_seconds": backend.load_seconds,
        "peak_rss_bytes": memory.peak,
        "records_hash": digest(records),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if getattr(backend, "torch", None) is not None:
        result["hardware"] = {
            "gpu": backend.torch.cuda.get_device_name(),
            "cuda": backend.torch.version.cuda,
            "peak_allocated_bytes": backend.torch.cuda.max_memory_allocated(),
            "peak_reserved_bytes": backend.torch.cuda.max_memory_reserved(),
        }
    atomic_json(directory / "history" / (stage + "-" + digest(result) + ".json"), result)
    atomic_json(directory / (stage + "-run.json"), result)
    return result
