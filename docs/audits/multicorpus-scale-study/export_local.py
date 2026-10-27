"""Export borné de vecteurs existants ; aucune écriture PostgreSQL."""

import gzip
import hashlib
import json
import struct
import time

from common import CACHE, HERE, PRIOR, connect, read, rows, sha, text_sha, write

SQL = """SELECT d.ordinal,d.document_id,d.contribution_id,d.questionnaire_id,
 d.record->>'text',d.record->'context'->>'question_text',d.content_hash,
 d.record->>'question_id',s.segment_index,s.start_offset,s.end_offset,s.tokens,
 s.vector_hash,vector_send(s.embedding),s.representation_id
 FROM rag_full.documents d JOIN rag_full.segments s
 ON s.space_id='full' AND s.document_id=d.document_id
 WHERE d.space_id='full' AND d.ordinal=ANY(%s)
 ORDER BY d.ordinal,s.segment_index"""


def append_gzip(path, values):
    with path.open("ab") as raw:
        with gzip.GzipFile(fileobj=raw, filename="", mode="wb", mtime=0, compresslevel=1) as gz:
            for value in values:
                gz.write((json.dumps(value, ensure_ascii=False) + "\n").encode())


def main():
    import numpy as np
    import psutil

    assert sha(HERE / "protocol.json") == read(HERE / "preregistration.json")["protocol_sha256"]
    inv = read(HERE / "data/inventory.json")
    state = next(s for s in inv["spaces"] if s["space_id"] == "full")
    assert psutil.virtual_memory().available > 16 * 1024**3
    assert psutil.disk_usage(HERE).free > 40 * 1024**3
    CACHE.mkdir(parents=True, exist_ok=True)
    if (CACHE / "export.json").exists():
        report = read(CACHE / "export.json")
        assert report["complete"] and report["source_chain_hash"] == state["chain_hash"]
        print("Existing complete export retained", flush=True)
        return
    assert not (CACHE / "modern.f32").exists(), (
        "Partial cache exists; use a new isolated cache directory"
    )
    original = [d for d in rows(PRIOR / "data/corpus.jsonl") if d["status"] != "A"]
    base = {d["id"]: i for i, d in enumerate(original)}
    old_segments = rows(PRIOR / "data/contemporary-segments.jsonl")
    old_vec = np.load(PRIOR / "vectors/contemporary.npy", allow_pickle=False)
    old_by_id = {r["unit_id"]: (r, old_vec[i]) for i, r in enumerate(old_segments)}
    assert len(base) == len(original) == len(old_segments) == 240
    started = time.perf_counter()
    with connect(timeout_ms=15000) as c:
        with c.cursor() as q:
            q.execute(
                "SELECT ordinal,document_id FROM rag_full.documents WHERE space_id='full' AND document_id=ANY(%s)",
                (list(base),),
            )
            base_ord = {did: int(o) for o, did in q.fetchall()}
    assert len(base_ord) == 240
    perm = np.random.Generator(np.random.PCG64(17892019)).permutation(state["documents"]) + 1
    protected = np.asarray(list(base_ord.values()), dtype=np.int64)
    perm = perm[~np.isin(perm, protected)]
    maximum = 1000000
    ordered = np.concatenate(
        [np.array([base_ord[d["id"]] for d in original]), perm[: maximum - 240]]
    )
    assert len(np.unique(ordered)) == maximum
    np.save(CACHE / "ordinals.npy", ordered, allow_pickle=False)
    write(
        HERE / "data/selection.json",
        dict(
            seed=17892019,
            generator="NumPy PCG64 permutation",
            units=maximum,
            protected_base=240,
            source_population=state["documents"],
            query_independent=True,
            ordinal_plan_sha256=sha(CACHE / "ordinals.npy"),
            parent_deduplication=False,
        ),
    )
    offset = 0
    progress = []
    norms_min, norms_max = 2.0, 0.0
    precision = []
    # Fixed base first, then equally sized batches; selections remain nested if stopped.
    batches = [(0, 240)] + [(i, min(i + 1000, maximum)) for i in range(240, maximum, 1000)]
    metadata_path = CACHE / "modern.jsonl.gz"
    ids_path = HERE / "data/population-ids.jsonl.gz"
    assert not metadata_path.exists() and not ids_path.exists()
    with (CACHE / "modern.f32").open("xb") as vf, (CACHE / "segment-unit.u32").open("xb") as im:
        for bi, (begin, end) in enumerate(batches):
            if time.perf_counter() - started > 900:
                break
            ords = ordered[begin:end].tolist()
            mapping = {int(o): i for i, o in enumerate(ordered[begin:end], begin)}
            query_start = time.perf_counter()
            with connect(timeout_ms=15000) as c:
                with c.cursor() as q:
                    q.execute("SET LOCAL enable_hashjoin=off")
                    q.execute("SET LOCAL enable_mergejoin=off")
                    q.execute(SQL, (ords,))
                    result = q.fetchall()
            query_seconds = time.perf_counter() - query_start
            documents = {}
            vectors = []
            indices = []
            for (
                ordinal,
                did,
                parent,
                form,
                text,
                question,
                content_hash,
                qid,
                si,
                start,
                stop,
                tokens,
                vector_hash,
                binary,
                rid,
            ) in result:
                i = mapping[ordinal]
                if i not in documents:
                    documents[i] = dict(
                        i=i,
                        id=did,
                        parent_id=str(parent),
                        questionnaire_id=str(form),
                        question_id=str(qid),
                        ordinal=ordinal,
                        text=text,
                        question=question,
                        source_hash=content_hash,
                        source_text_sha256=text_sha(text),
                        segments=[],
                    )
                doc = documents[i]
                assert si == len(doc["segments"]) and 0 <= start < stop <= len(text)
                raw = bytes(binary)
                assert struct.unpack(">hh", raw[:4]) == (1024, 0)
                vector = np.frombuffer(raw, dtype=">f4", offset=4).astype("<f4")
                assert hashlib.sha256(vector.tobytes()).hexdigest() == vector_hash
                if i < 240:
                    prior = original[i]
                    assert (
                        did == prior["id"]
                        and text == prior["text"]
                        and question == prior["question"]
                    )
                    assert content_hash == prior["references"]["source_hash"]
                    assert si == 0
                    old, oldv = old_by_id[did]
                    precision.append(
                        dict(
                            id=did,
                            cosine=float(vector @ oldv),
                            max_query_similarity_delta=float(
                                np.max(
                                    np.abs(
                                        np.load(PRIOR / "vectors/queries.npy", allow_pickle=False)
                                        @ (vector - oldv)
                                    )
                                )
                            ),
                        )
                    )
                    vector = oldv
                    assert start == old["start"] and stop == old["end"]
                doc["segments"].append(
                    dict(
                        index=si,
                        start=start,
                        end=stop,
                        tokens=tokens,
                        vector_row=offset + len(vectors),
                        vector_hash=hashlib.sha256(vector.tobytes()).hexdigest(),
                        db_vector_hash=vector_hash,
                        representation_id=rid,
                        source="prior240" if i < 240 else "rag_full.full",
                    )
                )
                vectors.append(vector)
                indices.append(i)
            assert set(documents) == set(range(begin, end))
            matrix = np.asarray(vectors, dtype="<f4")
            norms = np.linalg.norm(matrix, axis=1)
            assert np.isfinite(matrix).all() and np.max(np.abs(norms - 1)) < 1e-4
            norms_min = min(norms_min, float(norms.min()))
            norms_max = max(norms_max, float(norms.max()))
            vf.write(matrix.tobytes())
            im.write(np.asarray(indices, dtype="<u4").tobytes())
            append_gzip(metadata_path, [documents[i] for i in range(begin, end)])
            append_gzip(
                ids_path,
                [
                    {
                        k: documents[i][k]
                        for k in ("i", "id", "parent_id", "questionnaire_id", "ordinal")
                    }
                    for i in range(begin, end)
                ],
            )
            offset += len(vectors)
            elapsed = time.perf_counter() - started
            if bi % 25 == 0 or end == maximum:
                record = dict(
                    documents=end,
                    segments=offset,
                    elapsed_seconds=elapsed,
                    last_query_seconds=query_seconds,
                    rss_bytes=psutil.Process().memory_info().rss,
                    available_ram=psutil.virtual_memory().available,
                )
                progress.append(record)
                write(HERE / "data/export-progress.json", progress)
                print(
                    f"Export {end:,}/{maximum:,}; {elapsed:.1f}s; last SQL {query_seconds:.2f}s",
                    flush=True,
                )
            assert psutil.virtual_memory().available > 8 * 1024**3, "Resource reserve reached"
            completed = end
    with connect() as c:
        with c.cursor() as q:
            q.execute(
                "SELECT chain_hash,recipe_hash,documents,segments,verified FROM rag_full.spaces WHERE space_id='full'"
            )
            final = q.fetchone()
    assert final == (
        state["chain_hash"],
        state["recipe_hash"],
        state["documents"],
        state["segments"],
        True,
    )
    report = dict(
        complete=completed == maximum,
        documents=completed,
        segments=offset,
        seconds=time.perf_counter() - started,
        source_chain_hash=state["chain_hash"],
        source_recipe_hash=state["recipe_hash"],
        source_unchanged=True,
        norm_min=norms_min,
        norm_max=norms_max,
        base240_vector_precision_comparison=precision,
        vector_storage_bytes=(CACHE / "modern.f32").stat().st_size,
        files={
            p.name: sha(p)
            for p in (
                metadata_path,
                CACHE / "modern.f32",
                CACHE / "segment-unit.u32",
                CACHE / "ordinals.npy",
            )
        },
        population_ids_sha256=sha(ids_path),
        cache=str(CACHE),
        progress=progress,
        read_only=True,
        new_embeddings=0,
    )
    write(CACHE / "export.json", report)
    write(HERE / "data/export.json", report)
    print(f"Export completed: {completed:,} documents, {offset:,} existing vectors", flush=True)


if __name__ == "__main__":
    main()
