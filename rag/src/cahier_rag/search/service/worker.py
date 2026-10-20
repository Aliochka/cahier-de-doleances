"""Exécuteur persistant borné utilisable par le futur lifespan FastAPI."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from cahier_rag.search.service.control import Budget, SearchBusy, SearchNotReady


class SearchWorker:
    def __init__(self, service):
        self.service = service
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hybrid-search")
        self._lock = threading.Lock()
        self._pending = 0
        self._closed = False

    @property
    def ready(self):
        return not self._closed and self.service.ready

    async def start(self):
        # À appeler une fois au démarrage ; les requêtes ne rechargent jamais le modèle.
        with self._lock:
            if self._closed:
                raise SearchNotReady("Le moteur de recherche est arrêté.")
            future = self._executor.submit(self.service.start)
        await asyncio.wrap_future(future)

    async def retrieve(
        self, query, *, timeout=18, cancellation=None, question_id=None, budget=None
    ):
        # L'API partage cette échéance avec hydratation et sérialisation.
        budget = budget if budget is not None else Budget(timeout, cancellation=cancellation)
        # Le délai d'admission est inclus dans l'échéance absolue.
        budget.admission()
        with self._lock:
            if self._closed or not self.service.ready:
                raise SearchNotReady("Le moteur de recherche n'est pas prêt.")
            if self._pending >= 3:
                raise SearchBusy("La file de recherche est pleine.")
            self._pending += 1

        def work():
            budget.check()
            return self.service.retrieve(query, budget=budget, question_id=question_id)

        def finished(_):
            # Le permis appartient au travail, jamais à l'attente HTTP.
            with self._lock:
                self._pending -= 1

        try:
            with self._lock:
                if self._closed:
                    self._pending -= 1
                    raise SearchNotReady("Le moteur de recherche est arrêté.")
                future = self._executor.submit(work)
            future.add_done_callback(finished)
        except RuntimeError:
            with self._lock:
                self._pending -= 1
            raise SearchNotReady("Le moteur de recherche est arrêté.") from None

        # asyncio.wait ne propage pas l'annulation dans le worker. Le budget peut
        # expirer pendant une inférence ; le permis reste occupé jusqu'à sa fin.
        wrapped = asyncio.wrap_future(future)
        wrapped.add_done_callback(lambda f: None if f.cancelled() else f.exception())
        try:
            while not wrapped.done():
                budget.check()
                await asyncio.wait({wrapped}, timeout=min(0.025, max(0, budget.remaining())))
            return wrapped.result()
        except BaseException:
            budget.cancellation.set()
            future.cancel()  # Annule seulement les tâches qui ne sont pas démarrées.
            raise

    async def close(self):
        with self._lock:
            self._closed = True
        # Le shutdown bloque jusqu'à la fin effective du travail, hors event loop.
        await asyncio.to_thread(self._executor.shutdown, wait=True, cancel_futures=True)
        await asyncio.to_thread(self.service.close)
