"""Benchmarks limités, artefacts f32 ordonnés et mesures explicites."""

import hashlib
import importlib.metadata
import math
import os
import platform
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from cahier_rag.contracts import canonical_json
from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingError
from cahier_rag.embeddings.data import query_inputs, synthetic_inputs
from cahier_rag.embeddings.planning import inputs_for_plan, validate_plan
from cahier_rag.evaluation.sampling import digest


class MemorySampler:
    def __enter__(self):
        import psutil

        self.process = psutil.Process()
        self.baseline = self.peak = self.process.memory_info().rss
        self.stop = threading.Event()

        def sample():
            while not self.stop.wait(0.02):
                self.peak = max(self.peak, self.process.memory_info().rss)

        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.peak = max(self.peak, self.process.memory_info().rss)
        self.stop.set()
        self.thread.join()


def synchronize(backend):
    if backend.device == "cuda":
        backend.torch.cuda.synchronize()


def run_encoding(engine, inputs, *, role, batch_size, output, prefix):
    synchronize(engine.backend)
    started = time.perf_counter()
    hasher = hashlib.sha256()
    rows = []
    tokens = 0
    norms = []
    first = []
    with (output / (prefix + ".f32")).open("xb") as stream:
        for batch in engine.encode(inputs, role=role, batch_size=batch_size):
            binary = batch.binary()
            stream.write(binary)
            hasher.update(binary)
            for index, (identifier, vector, count, source_hash) in enumerate(
                zip(batch.identifiers, batch.vectors, batch.token_lengths, batch.input_hashes)
            ):
                rows.append({"input_id": identifier, "input_hash": source_hash, "tokens": count})
                norms.append(math.sqrt(math.fsum(x * x for x in vector)))
                if len(first) < 8:
                    first.append(vector)
                tokens += count
        stream.flush()
        os.fsync(stream.fileno())
    synchronize(engine.backend)
    elapsed = time.perf_counter() - started
    metadata = {
        "role": role,
        "rows": rows,
        "dimension": engine.dimension,
        "dtype": "float32",
        "endianness": "little",
        "normalized": engine.normalize,
        "vectors_sha256": hasher.hexdigest(),
    }
    with (output / (prefix + ".json")).open("x") as stream:
        stream.write(canonical_json(metadata) + "\n")
    return {
        "rows": len(rows),
        "batch_size": batch_size,
        "seconds": elapsed,
        "items_per_second": len(rows) / elapsed,
        "role": role,
        "tokens_per_second": tokens / elapsed,
        "input_tokens_excluding_padding": tokens,
        "output_hash": hasher.hexdigest(),
        "input_order_hash": digest([r["input_id"] for r in rows]),
        "norm_min": min(norms),
        "norm_max": max(norms),
        "vector_bytes": len(rows) * engine.dimension * 4,
        "vectors_file": prefix + ".f32",
        "metadata_file": prefix + ".json",
        "metadata_hash": digest(metadata),
    }, first


def stability(reference, actual, tolerance):
    if len(reference) != len(actual) or any(len(a) != len(b) for a, b in zip(reference, actual)):
        raise EmbeddingError("Forme différente lors du contrôle de stabilité.")
    error = max(abs(a - b) for ra, rb in zip(reference, actual) for a, b in zip(ra, rb))
    cosines = [math.fsum(a * b for a, b in zip(ra, rb)) for ra, rb in zip(reference, actual)]
    result = {
        "max_absolute_difference": error,
        "minimum_cosine": min(cosines),
        "absolute_tolerance": tolerance,
        "passed": error <= tolerance and min(cosines) >= 0.999,
    }
    if not result["passed"]:
        raise EmbeddingError("Les embeddings ne respectent pas la tolérance de stabilité.")
    return result


def synthetic_check(engine):
    documents = []
    for batch in engine.encode_documents(synthetic_inputs(), batch_size=4):
        documents.extend(batch.vectors)
    queries = []
    for batch in engine.encode_queries(query_inputs()[:4], batch_size=1):
        queries.extend(batch.vectors)
    result = []
    for query, vector in zip(query_inputs(), queries):
        scores = [
            (item.input_id, math.fsum(a * b for a, b in zip(vector, doc)))
            for item, doc in zip(synthetic_inputs(), documents)
        ]
        scores.sort(key=lambda row: (-row[1], row[0]))
        result.append(
            {
                "query_id": query.input_id,
                "ranking": [{"document_id": did, "cosine": score} for did, score in scores],
            }
        )
    return {
        "version": 1,
        "scope": "synthetic-functional-only-no-corpus-relevance-score",
        "rankings": result,
    }


def benchmark(backend, plan, scope, output, *, batch_sizes=(8, 32), cpu_queries_only=False):
    validate_plan(plan)
    if backend.spec.to_dict() != plan["models"][backend.spec.key]["spec"]:
        raise EmbeddingError("Modèle différent de celui du plan.")
    if (
        not batch_sizes
        or len(set(batch_sizes)) != len(batch_sizes)
        or any(type(n) is not int or not 1 <= n <= 64 for n in batch_sizes)
    ):
        raise EmbeddingError("Tailles de lots invalides.")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    engine = EmbeddingEngine(backend)
    result = {
        "version": 1,
        "plan_hash": plan["plan_hash"],
        "model": backend.spec.to_dict(),
        "implementation_hashes": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))
        },
        "numerical_settings": {
            "seed": 42,
            "tf32": False,
            "attention": "sdpa",
            "normalization": "L2 in Python float64; storage float32",
        },
        "device": backend.device,
        "precision": backend.precision,
        "normalized": True,
        "pooling": backend.spec.pooling,
        "truncation": "refuse",
        "threads": backend.threads,
        "batch_sizes": list(batch_sizes),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "documents": {},
        "synthetic": None,
        "cpu_queries_only": cpu_queries_only,
    }
    with MemorySampler() as memory:
        try:
            started = time.perf_counter()
            engine.load()
            synchronize(backend)
            result["load_seconds"] = time.perf_counter() - started
            if backend.snapshot_hash != plan["models"][backend.spec.key]["snapshot_hash"]:
                raise EmbeddingError("Snapshot différent de celui du plan.")
            result["snapshot_hash"] = backend.snapshot_hash
            if hasattr(getattr(backend, "model", None), "parameters"):
                result["actual_model_parameters"] = sum(
                    p.numel() for p in backend.model.parameters()
                )
            result["tokenizer"] = {
                "class": type(backend.tokenizer).__name__,
                "revision": backend.spec.revision,
                "effective_limit": backend.max_tokens,
                "declared_tokenizer_limit": backend.tokenizer.model_max_length,
                "integrity_verification_seconds": backend.integrity_seconds,
                "query_prefix": backend.spec.query_prefix,
                "document_prefix": backend.spec.document_prefix,
            }
            torch = backend.torch
            hardware = {
                "machine": platform.machine(),
                "system": platform.platform(),
                "cpu": platform.processor(),
                "cpu_logical_cores": os.cpu_count(),
                "torch_cuda_runtime": torch.version.cuda,
            }
            try:
                hardware["cpu_model"] = next(
                    line.split(":", 1)[1].strip()
                    for line in Path("/proc/cpuinfo").read_text().splitlines()
                    if line.startswith("model name")
                )
            except (OSError, StopIteration):
                pass
            if backend.device == "cuda":
                hardware.update(
                    {
                        "gpu": torch.cuda.get_device_name(),
                        "compute_capability": list(torch.cuda.get_device_capability()),
                        "gpu_total_bytes": torch.cuda.get_device_properties(0).total_memory,
                    }
                )
            if backend.device == "cuda":
                import subprocess

                try:
                    hardware["nvidia_driver"] = subprocess.check_output(
                        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                        text=True,
                        timeout=5,
                    ).strip()
                except (OSError, subprocess.SubprocessError):
                    hardware["nvidia_driver"] = None
            result["hardware"] = hardware
            result["libraries"] = {
                name: importlib.metadata.version(name)
                for name in (
                    "torch",
                    "transformers",
                    "tokenizers",
                    "huggingface-hub",
                    "numpy",
                    "psutil",
                )
            }
            # Chauffage explicite : données synthétiques exclusivement.
            list(engine.encode_queries(query_inputs()[:1]))
            list(engine.encode_documents(synthetic_inputs()[:1], batch_size=1))
            if not cpu_queries_only:
                for strategy in ("A", "B", "D"):
                    inputs = inputs_for_plan(plan, strategy, scope)
                    runs = []
                    baseline = None
                    for batch_size in batch_sizes:
                        measured, first = run_encoding(
                            engine,
                            inputs,
                            role="document",
                            batch_size=batch_size,
                            output=output,
                            prefix=f"documents-{strategy}-bs{batch_size}",
                        )
                        if baseline is None:
                            baseline = first
                        measured["stability_against_first_batch_size"] = stability(
                            baseline, first, 0.005 if backend.device == "cuda" else 0.001
                        )
                        runs.append(measured)
                    result["documents"][strategy] = {
                        "runs": runs,
                        "source": plan["strategies"][strategy],
                    }
            # Latences requêtes à chaud, huit formulations synthétiques, deux passages.
            latencies = []
            query_reference = None
            for repeat in range(2):
                vectors = []
                for item in query_inputs():
                    synchronize(backend)
                    start = time.perf_counter()
                    encoded = list(engine.encode_queries([item]))[0]
                    synchronize(backend)
                    latencies.append(time.perf_counter() - start)
                    vectors.extend(encoded.vectors)
                if query_reference is None:
                    query_reference = vectors
            result["queries"] = {
                "count": 8,
                "repetitions": 2,
                "batch_size": 1,
                "seconds_per_query": latencies,
                "median_seconds": sorted(latencies)[7],
                "p95_seconds": sorted(latencies)[15],
                "query_set_hash": digest([i.fingerprint() for i in query_inputs()]),
                "stability": stability(
                    query_reference, vectors, 0.005 if backend.device == "cuda" else 0.001
                ),
            }
            result["query_vectors"], _ = run_encoding(
                engine, query_inputs(), role="query", batch_size=1, output=output, prefix="queries"
            )
            result["synthetic"] = synthetic_check(engine)
            if backend.device == "cuda":
                result["gpu_memory"] = {
                    "torch_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                    "torch_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                }
            result["estimated_vector_storage"] = {
                "formula": "rows * dimension * 4 bytes; metadata/index excluded",
                "20000_single_vectors_bytes": 20000 * engine.dimension * 4,
                "note": "The final segment count and index overhead are not known yet.",
            }
        finally:
            engine.close()
    result["ram"] = {
        "rss_baseline_bytes": memory.baseline,
        "rss_peak_sampled_bytes": memory.peak,
        "method": "process RSS sampled every 20ms, includes load, excludes other processes",
    }
    result["manifest_hash"] = digest(result)
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        stream.write(canonical_json(result) + "\n")
    return result


def inspect_benchmark(directory):
    """Vérifier aussi les matrices stockées, leurs normes et les associations d'IDs."""
    import sys
    from array import array

    from cahier_rag.embeddings.snapshots import sha256_file
    from cahier_rag.evaluation.files import load_json

    directory = Path(directory)
    manifest = load_json(directory / "manifest.json")
    payload = dict(manifest)
    expected = payload.pop("manifest_hash")
    if digest(payload) != expected:
        raise EmbeddingError("Manifeste modifié.")
    runs = []
    for strategy, record in manifest["documents"].items():
        for run in record["runs"]:
            runs.append(
                (run, record["source"]["common_input_ids"], record["source"]["common_inputs_hash"])
            )
    query = manifest["query_vectors"]
    runs.append(
        (query, [i.input_id for i in query_inputs()], manifest["queries"]["query_set_hash"])
    )
    vectors_checked = 0
    for run, expected_ids, input_hash in runs:
        paths = {key: directory / run[key] for key in ("vectors_file", "metadata_file")}
        if any(path.resolve().parent != directory.resolve() for path in paths.values()):
            raise EmbeddingError("Chemin d’artefact invalide.")
        metadata = load_json(paths["metadata_file"])
        rows = metadata["rows"]
        dimension = metadata["dimension"]
        if (
            dimension != manifest["model"]["dimension"]
            or len(rows) != run["rows"]
            or [row["input_id"] for row in rows] != expected_ids
            or digest([row["input_hash"] for row in rows]) != input_hash
            or digest(metadata) != run["metadata_hash"]
            or digest(expected_ids) != run["input_order_hash"]
            or sha256_file(paths["vectors_file"]) != run["output_hash"]
            or paths["vectors_file"].stat().st_size != len(rows) * dimension * 4
        ):
            raise EmbeddingError("Matrice ou identifiants différents du manifeste.")
        with paths["vectors_file"].open("rb") as stream:
            for _ in rows:
                values = array("f")
                values.frombytes(stream.read(dimension * 4))
                if sys.byteorder != "little":
                    values.byteswap()
                if not all(math.isfinite(v) for v in values):
                    raise EmbeddingError("Valeur stockée non finie.")
                norm = math.sqrt(math.fsum(v * v for v in values))
                if abs(norm - 1) > 1e-4:
                    raise EmbeddingError("Vecteur stocké non normalisé.")
                vectors_checked += 1
    return manifest, {
        "matrices_checked": len(runs),
        "vectors_checked": vectors_checked,
        "valid": True,
    }
