"""Chaîne complète reprenable, phases et résultats conservés indépendamment."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from cahier_rag.embeddings.core import EmbeddingEngine
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.embeddings.transformers_backend import TransformersBackend
from cahier_rag.fullcorpus.experiment import experiment
from cahier_rag.fullcorpus.pipeline import embed, extract, require_disk
from cahier_rag.migrate import upgrade_schema
from cahier_rag.vector.preparation import atomic_json


def complete(store, settings, directory, *, batch_size=32):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    log = directory / "progress.jsonl"
    prior = directory / "phase.json"
    timings = json.loads(prior.read_text()).get("timings", {}) if prior.exists() else {}
    current_phase = "starting"

    def phase(name, action):
        nonlocal current_phase
        current_phase = name
        atomic_json(directory / "phase.json", dict(phase=name, status="running", timings=timings))
        started = time.perf_counter()
        result = action()
        timings[name] = timings.get(name, 0) + time.perf_counter() - started
        return result

    try:
        phase("extraction", lambda: extract(store, log_path=log))
        backend = TransformersBackend(
            MODELS["bge-m3"], Path("models"), device="cuda", precision="bfloat16"
        )
        engine = EmbeddingEngine(backend)
        phase("embedding", lambda: embed(store, engine, batch_size=batch_size, log_path=log))
        if not store.state()["verified"]:
            value = phase("verification", store.verify)
            atomic_json(directory / "integrity.json", value)
        # Pas de réexécution d'un CREATE INDEX terminé. La transaction Alembic
        # assure la cohérence si une construction est interrompue (repart de zéro).
        with store.guard.transaction() as (c, _):
            ann = c.execute(text("SELECT to_regclass('rag_full.segments_full_hnsw')")).scalar_one()
        if not ann:
            available = None
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemAvailable:"):
                    available = int(line.split()[1]) * 1024
            if available is None or available < 80 * 1024**3:
                raise ValueError(
                    "RAM disponible insuffisante pour le budget ANN de 40 Gio et sa marge."
                )
            require_disk(directory, 150 * 1024**3)
            phase("ann_migration", lambda: upgrade_schema(settings))
        report = directory / "full-search.json"
        if not report.exists():
            phase(
                "search",
                lambda: experiment(
                    store, engine, report, vectors_path=directory / "query-vectors-v1.json"
                ),
            )
        with store.guard.transaction() as (c, _):
            rows = [
                dict(r)
                for r in c.execute(
                    text("""SELECT c.relname,
                pg_total_relation_size(c.oid) AS total_bytes FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='rag_full'
                AND c.relkind IN ('r','i') ORDER BY c.relname""")
                ).mappings()
            ]
        atomic_json(
            directory / "completion.json",
            dict(
                status="complete",
                timings=timings,
                state=store.state() | {"updated_at": str(store.state()["updated_at"])},
                relations=rows,
            ),
        )
        atomic_json(
            directory / "phase.json", dict(phase="complete", status="complete", timings=timings)
        )
    except BaseException as error:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        failure = dict(type=type(error).__name__, phase=current_phase, timings=timings)
        atomic_json(directory / f"failure-{stamp}.json", failure)
        atomic_json(directory / "failure.json", failure)
        atomic_json(
            directory / "phase.json",
            dict(
                phase=current_phase,
                status="failed",
                error_type=type(error).__name__,
                timings=timings,
            ),
        )
        raise
