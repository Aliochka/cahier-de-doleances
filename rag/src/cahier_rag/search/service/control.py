"""Échéances et annulation coopérative, sans dépendance HTTP."""

import math
import threading
import time
from contextlib import contextmanager


class SearchError(Exception):
    code = "search_error"


class SearchNotReady(SearchError):
    code = "search_not_ready"


class SearchUnavailable(SearchError):
    code = "search_unavailable"


class SearchBusy(SearchError):
    code = "search_busy"


class InvalidQuery(SearchError):
    code = "invalid_query"


class SearchCancelled(SearchError):
    code = "search_cancelled"


class SearchTimeout(SearchError):
    code = "search_timeout"

    def __init__(self, stage):
        self.stage = stage
        super().__init__(f"Délai de recherche dépassé ({stage}).")


class Budget:
    """Un budget par travail. L'annulation ne tue jamais un thread d'inférence.

    Le moniteur n'annule que la connexion actuellement empruntée. Le verrou
    empêche un cancel tardif d'atteindre un autre utilisateur du pool.
    """

    def __init__(self, seconds=18, *, cancellation=None, clock=time.monotonic):
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("Budget strictement positif et fini requis.")
        self.clock = clock
        self.deadline = clock() + seconds
        self.cancellation = cancellation if cancellation is not None else threading.Event()
        self.stage = "startup"
        self._stage_deadline = self.deadline
        self._lock = threading.Lock()
        self._connection = None

    def remaining(self):
        return min(self.deadline, self._stage_deadline) - self.clock()

    def check(self):
        if self.cancellation.is_set():
            raise SearchCancelled("Recherche annulée.")
        if self.remaining() <= 0:
            raise SearchTimeout(self.stage)

    def admission(self, seconds=1):
        self.stage = "admission"
        self._stage_deadline = min(self.deadline, self.clock() + seconds)

    @contextmanager
    def phase(self, stage, seconds=None):
        self.stage = stage
        self._stage_deadline = min(
            self.deadline, self.clock() + seconds if seconds is not None else self.deadline
        )
        self.check()
        try:
            yield
            self.check()
        finally:
            self._stage_deadline = self.deadline

    @contextmanager
    def connection(self, connection):
        with self._lock:
            self.check()
            self._connection = connection
        try:
            yield
        finally:
            with self._lock:
                self._connection = None

    @contextmanager
    def monitor(self):
        finished = threading.Event()

        def watch():
            while not finished.wait(0.025):
                with self._lock:
                    if self._connection is not None and (
                        self.cancellation.is_set() or self.remaining() <= 0
                    ):
                        try:
                            self._connection.cancel()
                        except Exception:
                            # La requête peut déjà avoir fini ; le worker fera rollback.
                            pass
                        return

        watcher = threading.Thread(target=watch, name="search-cancel", daemon=True)
        watcher.start()
        try:
            yield
        finally:
            finished.set()
            watcher.join()
