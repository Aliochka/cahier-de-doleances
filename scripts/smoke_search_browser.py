"""Recette SEARCH-005 locale et bornée : navigateur + SSR + vrai H1/BGE-M3.

Aucune écriture SQL, aucun endpoint de contrôle dans l'application. Ce processus
pilote seulement ses propres instances temporaires. L'expiration utilise l'horloge
injectable du cache (+601 s). L'état vide injecte un Ranking vide, explicitement
rapporté : aucun seuil de pertinence n'est ajouté au moteur ANN.
"""

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    if os.environ.get("TEST_DATABASE_URL"):
        raise SystemExit("Retirer TEST_DATABASE_URL pour la recette des bases locales.")
    import uvicorn

    from app.app import app
    from app.routers import api_hybrid_search

    metrics = []
    empty_mode = False
    api_hybrid_search.observe = lambda item: metrics.append(
        {**item, "injected_empty_ranking": empty_mode}
    )
    loop = asyncio.new_event_loop()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=8015, access_log=False, log_level="warning")
    )

    def serve():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    thread = threading.Thread(target=serve)
    thread.start()
    frontend = browser = None
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if not thread.is_alive():
                raise RuntimeError("Serveur API de recette arrêté avant son démarrage.")
            backend = getattr(app.state, "hybrid_search", None)
            if server.started and backend and backend.worker.ready:
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("Recherche locale non prête.")
        model_id = id(backend.worker.service.encoder.backend.model)
        count, last_ranking, empty_mode = 0, None, False
        retrieve = backend.worker.retrieve

        async def counted(*args, **kwargs):
            nonlocal count, last_ranking
            if empty_mode:
                assert last_ranking is not None
                return replace(
                    last_ranking,
                    hits=(),
                    timings=type(last_ranking.timings)(0, 0, 0, 0, 0, 0),
                )
            count += 1
            last_ranking = await retrieve(*args, **kwargs)
            return last_ranking

        backend.worker.retrieve = counted
        original_clock = backend.cache.clock
        offset = 0
        backend.cache.clock = lambda: original_clock() + offset
        env = {
            **os.environ,
            "API_BASE_URL": "http://127.0.0.1:8015",
            "HOST": "127.0.0.1",
            "PORT": "4185",
        }
        frontend = subprocess.Popen(
            ["pnpm", "start"],
            cwd=ROOT / "frontend",
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                with urlopen("http://127.0.0.1:4185/recherche", timeout=1) as response:
                    assert response.status == 200
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("SSR local non prêt.")
        browser = subprocess.Popen(
            ["node", "tests/smoke-search-local.mjs"],
            cwd=ROOT / "frontend",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        observations = None

        async def control(action):
            nonlocal offset, empty_mode
            if action == "expire":
                offset += 601
            elif action == "empty_on":
                empty_mode = True
            elif action == "empty_off":
                empty_mode = False
            elif action != "count":
                raise ValueError("Commande de recette inconnue")
            return {"ok": True, "count": count}

        for line in browser.stdout:
            event = json.loads(line)
            if "action" in event:
                reply = asyncio.run_coroutine_threadsafe(control(event["action"]), loop).result(5)
                browser.stdin.write(json.dumps(reply) + "\n")
                browser.stdin.flush()
            else:
                observations = event["results"]
        assert browser.wait(timeout=10) == 0, "Échec du parcours navigateur"
        assert observations and count == 4
        assert id(backend.worker.service.encoder.backend.model) == model_id
        print(
            json.dumps(
                {
                    "h1_calls": count,
                    "model_reused": True,
                    "model_load_seconds": backend.worker.service.load_seconds,
                    "browser": observations,
                    "api_requests": metrics,
                },
                indent=2,
            )
        )
    finally:
        if browser and browser.poll() is None:
            browser.terminate()
            browser.wait(timeout=10)
        if frontend:
            import signal

            os.killpg(frontend.pid, signal.SIGTERM)
            frontend.wait(timeout=10)
        server.should_exit = True
        thread.join(timeout=60)
        assert not thread.is_alive(), "Serveur de recette non arrêté"


if __name__ == "__main__":
    main()
