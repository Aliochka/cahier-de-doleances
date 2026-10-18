"""Exécution avec cache réutilisable, recettes versionnées et résultats jamais humains."""

import hashlib
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.contracts import PROMPT_VERSION, SYSTEM, parse_output
from cahier_rag.judges.planning import iter_inputs, load_plan


def recipe(backend, config):
    backend.load_tokenizer()
    return {
        "version": 1,
        "model": backend.spec.to_dict(),
        "snapshot_hash": backend.snapshot_hash,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": digest(SYSTEM),
        "inference": config.to_dict(),
        "libraries": {
            name: version(name) for name in ("torch", "transformers", "accelerate", "bitsandbytes")
        },
        "judgment_origin": "llm",
        "human_reference": False,
    }


def run(
    directory,
    backend,
    config,
    cache,
    *,
    limit,
    allow_full=False,
    retry_failed=False,
    stop_after=None,
):
    manifest = load_plan(directory)
    entries = manifest["entries"]
    if type(limit) is not int or not 1 <= limit <= 1500 or limit != len(entries):
        raise ValueError("Limite explicite égale au nombre de couples du plan requise.")
    if stop_after is not None and (type(stop_after) is not int or not 1 <= stop_after <= limit):
        raise ValueError("Point d'arrêt positif inférieur ou égal à la limite requis.")
    if manifest["kind"] != "human60" and not allow_full:
        raise ValueError("Campagne automatique complète : autorisation CLI --allow-full requise.")
    if manifest["kind"] == "human60" and len(entries) > 60:
        raise ValueError(
            "Calibration limitée à 60 couples ; préparer une référence figée explicite."
        )
    configuration = recipe(backend, config)
    key = cache.register(configuration)
    started = time.perf_counter()
    from cahier_rag.embeddings.benchmark import MemorySampler

    sampler = MemorySampler()
    sampler.__enter__()
    counts = {"valid": 0, "invalid": 0, "too_long": 0, "reused": 0, "processed": 0}
    pending = []
    tokens = 0
    output_tokens = 0

    def persist(batch):
        nonlocal tokens, output_tokens
        token_counts = backend.token_counts(batch)
        if len(token_counts) != len(batch) or any(
            type(n) is not int or n < 1 for n in token_counts
        ):
            raise ValueError("Comptage de tokens invalide.")
        good, records = [], []
        for item, n in zip(batch, token_counts):
            if (
                n > config.max_input_tokens
                or n + config.max_new_tokens > backend.spec.context_tokens
            ):
                records.append(
                    {
                        "query_id": item.query_id,
                        "document_id": item.document_id,
                        "input_hash": item.input_hash,
                        "status": "too_long",
                        "judgment": None,
                        "raw_output": None,
                        "tokens": n,
                    }
                )
            else:
                good.append(item)
        if good:
            backend.load()
            raw = backend.generate(good)
            output_tokens += getattr(backend, "last_output_tokens", 0)
            if len(raw) != len(good):
                raise ValueError("Nombre de sorties différent du lot.")
            for item, value in zip(good, raw):
                try:
                    result = parse_output(value)
                    status = "valid"
                except ValueError:
                    result = None
                    status = "invalid"
                records.append(
                    {
                        "query_id": item.query_id,
                        "document_id": item.document_id,
                        "input_hash": item.input_hash,
                        "status": status,
                        "judgment": result,
                        "raw_output": value,
                        "raw_hash": digest(value),
                        "tokens": token_counts[batch.index(item)],
                    }
                )
        for record in records:
            record["generated_at"] = datetime.now(timezone.utc).isoformat()
            record["judgment_origin"] = "llm"
        cache.commit(key, records)
        for record in records:
            counts[record["status"]] += 1
            tokens += record["tokens"]
        counts["processed"] += len(batch)

    try:
        for item in iter_inputs(directory, manifest):
            old = cache.get(key, item.input_hash)
            if old and (old["status"] == "valid" or not retry_failed):
                counts[old["status"]] += 1
                counts["reused"] += 1
                counts["processed"] += 1
                continue
            pending.append(item)
            if len(pending) == config.batch_size:
                persist(pending)
                pending = []
                if counts["processed"] % 10 == 0:
                    print(
                        f"{backend.spec.key} : {counts['processed']}/{len(entries)} couples",
                        flush=True,
                    )
                if stop_after and counts["processed"] >= stop_after:
                    break
        if pending:
            persist(pending)
        result = {
            "version": 1,
            "recipe_hash": key,
            "recipe": configuration,
            "plan_hash": manifest["manifest_hash"],
            "counts": counts,
            "complete": counts["processed"] == len(entries),
            "seconds": time.perf_counter() - started,
            "load_seconds": backend.load_seconds,
            "input_tokens": tokens,
            "output_tokens_excluding_eos": output_tokens,
            "peak_rss_bytes": sampler.peak,
            "judgment_origin": "llm",
        }
        torch_runtime = getattr(backend, "torch", None)
        if torch_runtime is not None:
            result["hardware"] = {
                "gpu": torch_runtime.cuda.get_device_name(),
                "cuda": torch_runtime.version.cuda,
                "peak_allocated_bytes": torch_runtime.cuda.max_memory_allocated(),
            }
        result["implementation_hashes"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(__file__).parent.glob("*.py")
        }
        atomic_json(
            Path(directory) / (backend.spec.key + "-results.json"),
            {
                "judgment_origin": "llm",
                "human_reference": False,
                "recipe_hash": key,
                "plan_hash": manifest["manifest_hash"],
                "results": [cache.get(key, entry["input_hash"]) for entry in entries],
            },
        )
        atomic_json(Path(directory) / (backend.spec.key + "-run.json"), result)
        return result
    finally:
        sampler.__exit__(None, None, None)
        backend.close()
