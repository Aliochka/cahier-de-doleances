"""Exécution progressive et reprenable ; aucune transaction source pendant les écritures."""

import shutil
import time
from pathlib import Path

from cahier_rag.contracts import CONTRACT_VERSION, canonical_json
from cahier_rag.embeddings.core import EmbeddingInput
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.fullcorpus.reader import FullReader
from cahier_rag.fullcorpus.store import vector_hash
from cahier_rag.vector.preparation import (
    TokenConfig,
    contextualize,
    representation_identity,
    segments,
    token_count,
)


def recipe(audit, space):
    return dict(
        version=1,
        corpus="gdn-2019",
        space=space,
        audit_source=audit["source"],
        selection_hash=audit["selection_hash"],
        contract_version=CONTRACT_VERSION,
        reader="gdn-v1",
        adapter="full-keyset-v1",
        selection="hashtextextended(parent,26) mod 50 = 0; first 100000 usable units"
        if space == "pilot100k"
        else "all usable units through audited max_answer_id",
        max_answer_id=audit["source_meta"][0]["max_answer_id"],
        model=MODELS["bge-m3"].to_dict(),
        tokens=TokenConfig().to_dict(),
        precision="bfloat16",
        storage="float32",
        normalize=True,
        historical_partitions="RAG007 membership retained; other documents unassigned",
    )


def require_disk(path, minimum=100 * 1024**3):
    if shutil.disk_usage(path).free < minimum:
        raise ValueError("Espace disque insuffisant : arrêt avant le prochain lot.")


def extract(store, *, stop_after=None, log_path=None):
    state = store.state()
    if state["extraction_complete"]:
        return state
    reader = FullReader(store.guard.source, pilot=store.space == "pilot100k")
    start, initial = time.perf_counter(), state["documents"]
    while state["documents"] < state["expected_units"]:
        require_disk(Path.cwd())
        before = state["documents"]
        batch = reader.read_batch(
            after=store.cursor(state), max_documents=min(1000, state["expected_units"] - before)
        )
        # Reject corpus growth or changed provenance rather than silently including it.
        if batch.next_cursor and batch.next_cursor.answer_id > int(
            state["manifest"]["max_answer_id"]
        ):
            raise ValueError("Source modifiée depuis l'audit.")
        store.commit_documents(batch, state)
        state = store.state()
        if state["documents"] // 10000 != before // 10000:
            progress("extract", state, start, initial, log_path)
        if batch.exhausted and state["documents"] != state["expected_units"]:
            raise ValueError("Source épuisée avant le compte attendu.")
        if stop_after and state["documents"] - initial >= stop_after:
            return state
    # Full corpus must actually be exhausted, including rows producing no unit.
    if store.space == "full":
        trailing = reader.read_batch(after=store.cursor(state), max_documents=1)
        if trailing.documents:
            raise ValueError("Documents supplémentaires absents de l'inventaire.")
    store.finish_extraction()
    progress("extract", store.state(), start, initial, log_path)
    return store.state()


def prepare_metadata(unit, scope_hash, start, end, index, count, config=TokenConfig()):
    item = dict(
        version=1,
        configuration=config.to_dict(),
        sample_hash=scope_hash,
        document_id=unit.document_id,
        source_hash=unit.content_hash,
        split="full",
        contribution_id=str(unit.contribution_id),
        questionnaire_id=str(unit.questionnaire_id),
        unit_type=unit.unit_type.value,
        segment_index=index,
        start=start,
        end=end,
        tokens=count,
        text=contextualize(unit.question_text, unit.text[start:end]),
    )
    item["representation_id"] = representation_identity(item)
    item["content_hash"] = fingerprint(item)
    return item


def prepare_unit(unit, tokenizer, config, scope_hash):
    # Fast path EXACTLY equal to segments() for an unsplit answer; avoids ~12
    # repeated tokenizations per short answer at 5 million units. Long answers
    # use the historical segmentation, including its boundary/overlap rules.
    value = contextualize(unit.question_text, unit.text)
    if len(unit.text) <= 4000:
        count = token_count(tokenizer, value)
        if count <= config.budget:
            if (
                token_count(tokenizer, contextualize(unit.question_text, "")) + config.overlap + 8
                >= config.budget
            ):
                raise ValueError("Question trop longue pour le budget.")
            return [prepare_metadata(unit, scope_hash, 0, len(unit.text), 0, count, config)]
    return list(segments(unit, tokenizer, config, scope_hash, "full"))


def progress(phase, state, start, initial, path):
    done = state["documents"] if phase == "extract" else state["vector_cursor"]
    seconds = time.perf_counter() - start
    rate = (done - initial) / seconds if seconds else 0
    value = dict(
        phase=phase,
        space=state["space_id"],
        units=done,
        total=state["expected_units"],
        segments=state["segments"],
        seconds=seconds,
        units_per_second=rate,
        remaining_seconds=(state["expected_units"] - done) / rate if rate else None,
    )
    line = canonical_json(value)
    print(line, flush=True)
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def embed(store, engine, *, batch_size=16, stop_after=None, log_path=None):
    state = store.state()
    if not state["extraction_complete"]:
        raise ValueError("Extraire et vérifier le compte documentaire avant l'encodage.")
    if state["vectors_complete"]:
        return state
    if engine.backend.spec.to_dict() != state["manifest"]["model"]:
        raise ValueError("Modèle/révision incompatible avec le manifeste.")
    if not engine.normalize or engine.backend.precision != state["manifest"]["precision"]:
        raise ValueError("Recette d'encodage incompatible.")
    start, initial = time.perf_counter(), state["vector_cursor"]
    engine.backend.load_tokenizer()
    loaded = time.perf_counter()
    engine.load()
    load_seconds = time.perf_counter() - loaded
    try:
        while state["vector_cursor"] < state["documents"]:
            require_disk(Path.cwd())
            # One exceptionally long answer can have hundreds of segments; keep
            # at most 256 source units per checkpoint to bound peak memory.
            pending = store.documents(state["vector_cursor"], 256)
            docs, prepared = [], []
            for ordinal, doc in pending:
                parts = prepare_unit(
                    doc, engine.backend.tokenizer, TokenConfig(), state["recipe_hash"]
                )
                if prepared and len(prepared) + len(parts) > 2048:
                    break
                if len(parts) > 2048:
                    raise ValueError("Unité supérieure à 2048 segments.")
                prepared.extend(parts)
                docs.append((ordinal, doc))
            ordered = sorted(prepared, key=lambda p: (p["tokens"], p["representation_id"]))
            inputs = [
                EmbeddingInput(p["representation_id"], p["text"], p["content_hash"])
                for p in ordered
            ]
            vectors = {}
            for batch in engine.encode_documents(inputs, batch_size=batch_size):
                vectors.update(zip(batch.identifiers, batch.vectors, strict=True))
            rows = []
            for p in prepared:
                vector = vectors[p["representation_id"]]
                rows.append(
                    {
                        k: p[k]
                        for k in (
                            "document_id",
                            "segment_index",
                            "representation_id",
                            "start",
                            "end",
                            "tokens",
                            "content_hash",
                        )
                    }
                    | dict(embedding=vector, vector_hash=vector_hash(vector))
                )
            previous = state["vector_cursor"]
            store.commit_vectors(state, docs[-1][0], rows)
            state = store.state()
            if state["vector_cursor"] // 500 != previous // 500:
                progress("embed", state, start, initial, log_path)
            if stop_after and state["vector_cursor"] - initial >= stop_after:
                break
    finally:
        engine.close()
    progress("embed", store.state(), start, initial, log_path)
    import resource

    metrics = dict(
        batch_size=batch_size,
        unit_batch=256,
        padding="length-sorted per checkpoint",
        load_seconds=load_seconds,
        total_seconds=time.perf_counter() - start,
        encoded_units=store.state()["vector_cursor"] - initial,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        model_snapshot=engine.backend.snapshot_hash,
    )
    if engine.backend.torch is not None:
        metrics["peak_vram_bytes"] = engine.backend.torch.cuda.max_memory_allocated()
        metrics["gpu"] = engine.backend.torch.cuda.get_device_name()
        metrics["torch"] = engine.backend.torch.__version__
    print(canonical_json({"embedding_run": metrics}), flush=True)
    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(canonical_json({"embedding_run": metrics}) + "\n")
    return store.state()
