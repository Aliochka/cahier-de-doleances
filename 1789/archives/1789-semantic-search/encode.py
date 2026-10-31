"""BGE-M3 réel, adaptateur existant, inférence locale CPU et fichiers autonomes."""

import importlib.metadata
import platform
import re
import sys
import time

from common import HERE, ROOT, read, rows, sha, text_sha, write, write_rows

sys.path.insert(0, str(ROOT / "rag/src"))
from cahier_rag.embeddings.benchmark import MemorySampler  # noqa: E402
from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingInput  # noqa: E402
from cahier_rag.embeddings.registry import MODELS  # noqa: E402
from cahier_rag.embeddings.transformers_backend import TransformersBackend  # noqa: E402
from cahier_rag.vector.preparation import token_count  # noqa: E402


def segments(doc, variant, tokenizer, budget=1024, overlap=128):
    """Même recherche de préfixe/frontière/chevauchement que vector.preparation.

    Seul le contexte est adapté : un cahier ne devient pas une fausse question.
    Les positions portent toujours sur le texte exact de l'article.
    """
    text = doc["text"]
    prefix = "" if variant == "A" else doc["context_prefix"]
    assert token_count(tokenizer, prefix) + overlap + 8 < budget
    start, index = 0, 0
    while start < len(text):
        low, high = start + 1, min(len(text), start + budget * 32)
        best = None
        while low <= high:
            mid = (low + high) // 2
            if token_count(tokenizer, prefix + text[start:mid]) <= budget:
                best, low = mid, mid + 1
            else:
                high = mid - 1
        assert best is not None
        end = best
        if end < len(text):
            boundaries = list(re.finditer(r"\n\s*\n|[.!?](?:\s+|$)", text[start:end]))
            if boundaries and boundaries[-1].end() >= (end - start) // 2:
                end = start + boundaries[-1].end()
        value = prefix + text[start:end]
        count = token_count(tokenizer, value)
        assert count <= budget
        yield dict(
            id=f"{variant}:{doc['id']}:{index}",
            unit_id=doc["id"],
            variant=variant,
            segment_index=index,
            start=start,
            end=end,
            tokens=count,
            text=value,
            text_sha256=text_sha(value),
        )
        if end == len(text):
            break
        offsets = tokenizer(
            text[start:end], add_special_tokens=False, truncation=False, return_offsets_mapping=True
        )["offset_mapping"]
        next_start = start + offsets[max(0, len(offsets) - overlap)][0]
        assert start < next_start <= end
        start, index = next_start, index + 1


def main():
    import numpy as np
    import psutil

    prereg = read(HERE / "preregistration.json")
    assert prereg["queries_sha256"] == sha(HERE / "queries.json")
    assert prereg["protocol_sha256"] == sha(HERE / "protocol.json")
    protocol = read(HERE / "protocol.json")
    corpus = rows(HERE / "data/corpus.jsonl")
    backend = TransformersBackend(
        MODELS["bge-m3"],
        ROOT / "rag/models",
        device="cpu",
        precision="float32",
        threads=protocol["threads"],
    )
    engine = EmbeddingEngine(backend, normalize=True)
    started = time.perf_counter()
    backend.load_tokenizer()
    historical = [d for d in corpus if d["status"] == "A"]
    prepared = [
        r
        for variant in ("A", "B")
        for d in historical
        for r in segments(d, variant, backend.tokenizer)
    ]
    assert all(r["tokens"] <= protocol["segment_tokens"] for r in prepared)
    write_rows(HERE / "data/historical-segments.jsonl", prepared)
    tokenization_seconds = time.perf_counter() - started
    with MemorySampler() as memory:
        started = time.perf_counter()
        engine.load()
        load_seconds = time.perf_counter() - started
        print(f"BGE-M3 loaded on CPU; {len(prepared)} historical segment encodings", flush=True)
        encode_times = {}
        for variant in ("A", "B"):
            subset = [r for r in prepared if r["variant"] == variant]
            order = sorted(range(len(subset)), key=lambda i: (subset[i]["tokens"], subset[i]["id"]))
            vectors = np.zeros((len(subset), 1024), dtype=np.float32)
            started = time.perf_counter()
            for offset in range(0, len(order), 8):
                indices = order[offset : offset + 8]
                inputs = [
                    EmbeddingInput(subset[i]["id"], subset[i]["text"], subset[i]["text_sha256"])
                    for i in indices
                ]
                batch = next(engine.encode_documents(inputs, batch_size=8))
                vectors[indices] = batch.vectors
                if offset % 64 == 0:
                    print(
                        f"Historical {variant}: {min(offset + 8, len(order))}/{len(order)}",
                        flush=True,
                    )
            encode_times[variant] = dict(
                seconds=time.perf_counter() - started,
                segments=len(subset),
                tokens=sum(r["tokens"] for r in subset),
            )
            np.save(HERE / f"vectors/historical_{variant}.npy", vectors, allow_pickle=False)
        query_rows, query_vectors, query_times = [], [], []
        for q in read(HERE / "queries.json")["queries"]:
            item = EmbeddingInput(q["id"], q["text"], text_sha(q["text"]))
            started = time.perf_counter()
            batch = next(engine.encode_queries([item]))
            query_times.append(time.perf_counter() - started)
            query_vectors.append(batch.vectors[0])
            query_rows.append(
                dict(id=q["id"], tokens=batch.token_lengths[0], input_hash=batch.input_hashes[0])
            )
        np.save(
            HERE / "vectors/queries.npy",
            np.asarray(query_vectors, dtype=np.float32),
            allow_pickle=False,
        )
        # Diagnostic of reusing the existing bfloat16 dense space from the same snapshot.
        modern_segments = rows(HERE / "data/contemporary-segments.jsonl")
        ordered = sorted(range(len(modern_segments)), key=lambda i: modern_segments[i]["tokens"])
        checks = sorted({ordered[round(i * (len(ordered) - 1) / 15)] for i in range(16)})
        reused = np.load(HERE / "vectors/contemporary.npy", allow_pickle=False)
        drift, check_vectors = [], []
        started = time.perf_counter()
        for i in checks:
            r = modern_segments[i]
            inp = EmbeddingInput(r["representation_id"], r["text"], text_sha(r["text"]))
            vec = np.asarray(next(engine.encode_documents([inp])).vectors[0], dtype=np.float32)
            check_vectors.append(vec)
            cosine = float(
                np.dot(vec, reused[i]) / (np.linalg.norm(vec) * np.linalg.norm(reused[i]))
            )
            query_delta = np.asarray(query_vectors) @ (vec - reused[i])
            drift.append(
                dict(
                    unit_id=r["unit_id"],
                    tokens=r["tokens"],
                    cpu_fp32_vs_reused_bf16_cosine=cosine,
                    max_query_similarity_delta=float(np.max(np.abs(query_delta))),
                )
            )
        drift_seconds = time.perf_counter() - started
        np.save(
            HERE / "vectors/precision-check-fp32.npy",
            np.asarray(check_vectors, dtype=np.float32),
            allow_pickle=False,
        )
        # The 16 verification vectors are retained separately; they do not replace archived vectors.
    report = dict(
        model=MODELS["bge-m3"].to_dict(),
        snapshot_hash=backend.snapshot_hash,
        device="cpu",
        precision="float32",
        threads=protocol["threads"],
        normalization="L2",
        pooling="cls",
        truncation=False,
        batch_size=8,
        length_sorted_batches=True,
        tokenization_seconds=tokenization_seconds,
        load_seconds=load_seconds,
        documents=encode_times,
        queries=query_rows,
        query_encoding_seconds=query_times,
        precision_check=drift,
        precision_check_seconds=drift_seconds,
        peak_rss_bytes=memory.peak,
        ram_total_bytes=psutil.virtual_memory().total,
        physical_cpus=psutil.cpu_count(logical=False),
        logical_cpus=psutil.cpu_count(),
        platform=platform.platform(),
        libraries={
            n: importlib.metadata.version(n) for n in ("torch", "transformers", "numpy", "psutil")
        },
        corpus_sha256=sha(HERE / "data/corpus.jsonl"),
        segments_sha256=sha(HERE / "data/historical-segments.jsonl"),
        query_sha256=sha(HERE / "queries.json"),
        vector_files={p.name: sha(p) for p in sorted((HERE / "vectors").glob("*.npy"))},
    )
    write(HERE / "data/encoding.json", report)
    engine.close()
    print("Encoding completed", flush=True)


if __name__ == "__main__":
    main()
