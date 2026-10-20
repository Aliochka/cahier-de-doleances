"""Cycle de vie de la recherche ; un échec n'empêche pas l'application de démarrer."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from cahier_rag.config import ConfigurationError, load_settings
from cahier_rag.search.service import SearchWorker, create_service
from cahier_rag.search.service.control import Budget, SearchNotReady
from cahier_rag.search.service.reader import ReadGuard, create_search_engine
from dotenv import dotenv_values

from app.db import DB_URL
from app.services.search_hydration import Hydrator
from app.services.search_snapshots import SnapshotCache

ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)


def observe(metrics):
    logger.info("hybrid_search_metrics %s", json.dumps(metrics, sort_keys=True))


class SearchBackend:
    def __init__(self, worker, hydrator, cache):
        self.worker, self.hydrator, self.cache = worker, hydrator, cache

    def verify_source(self):
        reader = self.worker.service.reader
        budget = Budget(5)
        expected = ReadGuard(reader.source, reader.target, budget).source_identity()
        actual = ReadGuard(self.hydrator.engine, reader.target, budget).source_identity()
        if actual != expected:
            raise SearchNotReady("La base applicative ne correspond pas à la source indexée.")

    async def start(self):
        # Vérifier l'hydratation avant de réserver le GPU pour le chargement.
        verification = asyncio.wrap_future(self.hydrator.executor.submit(self.verify_source))
        try:
            await asyncio.shield(verification)
        except asyncio.CancelledError:
            # Ne pas disposer des pools avant la fin effective de cette lecture.
            with suppress(Exception):
                await verification
            raise
        await self.worker.start()

    async def close(self):
        self.cache.clear()
        try:
            await self.worker.close()
        finally:
            await self.hydrator.close()


def build_backend():
    path = Path(os.environ.get("SEARCH_CONFIG_FILE", ROOT / "search-api.env"))
    values = dict(dotenv_values(path, interpolate=False)) if path.is_file() else {}
    for key in (
        "SEARCH_CURSOR_KEY",
        "SEARCH_READER_ENV",
        "SEARCH_MODELS_DIR",
        "SEARCH_DEVICE",
        "SEARCH_PRECISION",
    ):
        if key in os.environ:
            values[key] = os.environ[key]
    key = values.get("SEARCH_CURSOR_KEY") or ""
    if len(key.encode()) < 32:
        raise ConfigurationError("SEARCH_CURSOR_KEY manquante ou trop courte.")
    cache = SnapshotCache(key)
    source = load_settings(
        env_file=values.get("SEARCH_READER_ENV") or ROOT / "rag/search-reader.env"
    )
    service = create_service(
        source,
        values.get("SEARCH_MODELS_DIR") or ROOT / "rag/models",
        device=values.get("SEARCH_DEVICE") or "cpu",
        precision=values.get("SEARCH_PRECISION") or "float32",
    )
    try:
        hydrator = Hydrator(create_search_engine(DB_URL))
        return SearchBackend(SearchWorker(service), hydrator, cache)
    except Exception:
        service.close()
        raise


@asynccontextmanager
async def lifespan(app):
    backend = None
    startup = None
    app.state.hybrid_search = None
    try:
        backend = build_backend()
        app.state.hybrid_search = backend

        async def initialize():
            try:
                await backend.start()
            except Exception:
                logger.warning(
                    "Hybrid search initialization failed; documentary endpoints remain available"
                )

        # Ne pas retarder l'ouverture des pages documentaires pendant le chargement.
        startup = asyncio.create_task(initialize())
    except Exception:
        # Ne jamais consigner les URL, exceptions DB brutes ou secrets du modèle.
        logger.warning(
            "Hybrid search unavailable at startup; documentary endpoints remain available"
        )
    try:
        yield
    finally:
        app.state.hybrid_search = None
        if startup is not None:
            if not startup.done():
                startup.cancel()
            with suppress(asyncio.CancelledError):
                await startup
        if backend is not None:
            await backend.close()
