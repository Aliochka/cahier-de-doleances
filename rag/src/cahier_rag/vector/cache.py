"""Lots float32 locaux vérifiables, reprise sans PostgreSQL ni réencodage réussi."""

import hashlib
import json
import platform
import struct
import time
from importlib.metadata import version
from pathlib import Path

from cahier_rag.embeddings.core import EmbeddingInput
from cahier_rag.evaluation.sampling import digest
from cahier_rag.vector.preparation import atomic_json, iter_units, load_prepared
from cahier_rag.vector.store import float32_vector


def inputs_for(groups):
    return [
        EmbeddingInput(i["representation_id"], i["text"], i["content_hash"], i["document_id"])
        for group in groups
        for i in group
    ]


def cached(directory, position, inputs, configuration):
    root = Path(directory) / "encoded"
    info = root / f"{position:05d}.json"
    if not info.exists():
        return None
    metadata = json.loads(info.read_text())
    binary_path = root / f"{position:05d}.f32"
    if binary_path.stat().st_size != len(inputs) * 1024 * 4 or len(inputs) > 2048:
        raise ValueError("Taille de cache incompatible ou excessive.")
    data = binary_path.read_bytes()
    if (
        metadata["configuration_hash"] != digest(configuration)
        or metadata["input_hashes"] != [i.fingerprint() for i in inputs]
        or metadata["sha256"] != hashlib.sha256(data).hexdigest()
        or len(data) != len(inputs) * 1024 * 4
    ):
        raise ValueError("Lot d'embeddings local incompatible ou modifié.")
    vectors = [row for row in struct.iter_unpack("<1024f", data)]
    for vector in vectors:
        float32_vector(vector)
    return vectors


def save_cache(directory, position, inputs, configuration, vectors):
    root = Path(directory) / "encoded"
    root.mkdir(exist_ok=True)
    data = b"".join(struct.pack("<1024f", *row) for row in vectors)
    if len(vectors) != len(inputs):
        raise ValueError("Nombre de vecteurs incompatible.")
    for row in vectors:
        float32_vector(row)
    target = root / f"{position:05d}.f32"
    temporary = target.with_suffix(".tmp")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        import os

        os.fsync(stream.fileno())
    temporary.replace(target)
    atomic_json(
        root / f"{position:05d}.json",
        {
            "configuration_hash": digest(configuration),
            "input_hashes": [i.fingerprint() for i in inputs],
            "sha256": hashlib.sha256(data).hexdigest(),
            "vectors": len(inputs),
        },
    )


def generate(
    directory, scope, engine, configuration, *, batch_size=8, unit_batch=25, stop_after=None
):
    if not 1 <= unit_batch <= 25 or not 1 <= batch_size <= 64:
        raise ValueError("Taille de lot invalide.")
    prepared = load_prepared(directory, scope)
    backend = engine.backend
    if (
        configuration["prepared"] != prepared
        or backend.spec.to_dict() != configuration["model"]
        or backend.precision != configuration["precision"]
        or not engine.normalize
    ):
        raise ValueError("Modèle ou recette incompatible.")
    backend.load_tokenizer()
    if backend.snapshot_hash != prepared["snapshot_hash"]:
        raise ValueError("Snapshot incompatible.")
    root = Path(directory) / "encoded"
    root.mkdir(exist_ok=True)
    parameters = {
        "configuration": configuration,
        "batch_size": batch_size,
        "unit_batch": unit_batch,
        "libraries": {name: version(name) for name in ("torch", "transformers", "numpy")},
        "platform": platform.platform(),
    }
    parameters_path = root / "parameters.json"
    if parameters_path.exists():
        if json.loads(parameters_path.read_text()) != parameters:
            raise ValueError("Reprise avec paramètres ou bibliothèques incompatibles.")
    else:
        atomic_json(parameters_path, parameters)
    started, pending, offset, count, reused = time.perf_counter(), [], 0, 0, 0
    from cahier_rag.embeddings.benchmark import MemorySampler

    sampler = MemorySampler()
    sampler.__enter__()

    def encode(groups, position):
        nonlocal count, reused
        inputs = inputs_for(groups)
        previous = cached(directory, position, inputs, configuration)
        if previous is not None:
            count += len(inputs)
            reused += len(inputs)
            return
        if len(inputs) > 2048:
            raise ValueError("Lot de plus de 2048 segments ; réduire unit-batch.")
        engine.load()
        output = []
        for batch in engine.encode_documents(inputs, batch_size=batch_size):
            if batch.identifiers != tuple(
                i.input_id for i in inputs[len(output) : len(output) + len(batch.identifiers)]
            ):
                raise ValueError("Ordre des embeddings invalide.")
            output.extend(batch.vectors)
        save_cache(directory, position, inputs, configuration, output)
        count += len(inputs)

    try:
        for group in iter_units(directory, scope):
            if pending and sum(map(len, pending)) + len(group) > 2048:
                encode(pending, offset)
                offset += len(pending)
                pending = []
            pending.append(group)
            if len(pending) >= unit_batch:
                encode(pending, offset)
                offset += len(pending)
                pending = []
                if offset % 500 == 0:
                    print(f"Embeddings : {offset}/{len(scope.documents)} unités", flush=True)
                if stop_after and offset >= stop_after:
                    break
        if pending:
            encode(pending, offset)
            offset += len(pending)
        report = {
            "units": offset,
            "segments": count,
            "reused_segments": reused,
            "seconds": time.perf_counter() - started,
            "complete": offset == len(scope.documents),
            "configuration_hash": digest(configuration),
            "parameters_hash": digest(parameters),
        }
        if backend.torch is not None and backend.device == "cuda":
            report["gpu"] = backend.torch.cuda.get_device_name()
            report["peak_gpu_bytes"] = backend.torch.cuda.max_memory_allocated()
        report["peak_rss_bytes"] = sampler.peak
        atomic_json(root / "report.json", report)
        return report
    finally:
        sampler.__exit__(None, None, None)
        engine.close()
