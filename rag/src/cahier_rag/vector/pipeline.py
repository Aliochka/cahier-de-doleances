"""Encodage borné et reprise au dernier lot PostgreSQL validé."""

import time

from cahier_rag.vector.cache import cached, inputs_for, save_cache
from cahier_rag.vector.preparation import iter_units, load_prepared


def index(store, engine, directory, *, batch_size=8, unit_batch=25, stop_after=None):
    if type(unit_batch) is not int or not 1 <= unit_batch <= 25:
        raise ValueError("Lot de 1 à 25 unités requis.")
    if stop_after is not None and (type(stop_after) is not int or stop_after < 1):
        raise ValueError("Limite d’arrêt strictement positive requise.")
    manifest = load_prepared(directory, store.scope)
    if manifest != store.configuration["prepared"]:
        raise ValueError("Préparation incompatible avec l'espace.")
    backend = engine.backend
    if (
        backend.spec.to_dict() != store.configuration["model"]
        or not engine.normalize
        or engine.dimension != 1024
        or backend.precision != store.configuration["precision"]
    ):
        raise ValueError("Modèle, dimension, normalisation ou précision incompatible.")
    backend.load_tokenizer()
    if backend.snapshot_hash != manifest["snapshot_hash"]:
        raise ValueError("Snapshot tokenizer/modèle différent de la préparation.")
    status = store.initialize()
    store.verify()
    if status["state"] == "complete":
        return store.verify(require_complete=True)
    offset = status["completed_units"]
    current, processed = [], 0
    started = time.perf_counter()

    def persist(groups, position):
        inputs = inputs_for(groups)
        if len(inputs) > 2048:
            raise ValueError("Lot supérieur à 2048 segments ; réduire unit-batch.")
        vectors = cached(directory, position, inputs, store.configuration)
        if vectors is None:
            engine.load()
            vectors = []
            for batch in engine.encode_documents(inputs, batch_size=batch_size):
                if (
                    tuple(
                        i.input_id
                        for i in inputs[len(vectors) : len(vectors) + len(batch.identifiers)]
                    )
                    != batch.identifiers
                ):
                    raise ValueError("Ordre des vecteurs incompatible.")
                vectors.extend(batch.vectors)
            save_cache(directory, position, inputs, store.configuration, vectors)
        store.commit(position, groups, vectors)

    try:
        for position, group in enumerate(iter_units(directory, store.scope)):
            if position < offset:
                continue
            if current and sum(len(g) for g in current) + len(group) > 2048:
                persist(current, offset)
                offset += len(current)
                processed += len(current)
                current = []
            current.append(group)
            if len(current) >= unit_batch or (
                stop_after and processed + len(current) >= stop_after
            ):
                persist(current, offset)
                offset += len(current)
                processed += len(current)
                current = []
                if offset % 500 == 0 or stop_after:
                    print(f"Indexation : {offset}/{len(store.scope.documents)} unités", flush=True)
                if stop_after and processed >= stop_after:
                    return {
                        "interrupted": True,
                        "units": offset,
                        "seconds": time.perf_counter() - started,
                    }
        if current:
            persist(current, offset)
        report = store.finish()
        report["seconds"] = time.perf_counter() - started
        report["new_units"] = len(store.scope.documents) - status["completed_units"]
        return report
    finally:
        engine.close()
