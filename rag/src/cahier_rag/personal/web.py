"""Interface personnelle loopback, travail GPU séquentiel et textes échappés côté DOM."""

import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

ASSETS = Path(__file__).parent


def create_app(service, *, port=8770, corpus="rag007"):
    token = secrets.token_urlsafe(32)
    origin = f"http://127.0.0.1:{port}"
    executor = ThreadPoolExecutor(max_workers=1)
    lock = threading.Lock()
    jobs = {}

    @asynccontextmanager
    async def lifespan(app):
        yield
        executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def local(request, call_next):
        if (
            request.client is None
            or request.client.host != "127.0.0.1"
            or request.headers.get("host") != f"127.0.0.1:{port}"
            or request.headers.get("origin") not in (None, origin)
            or request.headers.get("sec-fetch-site") not in (None, "same-origin", "none")
        ):
            return Response("Origine locale requise.", status_code=403)
        if request.method != "GET":
            if (
                not secrets.compare_digest(request.headers.get("x-rag-token", ""), token)
                or request.headers.get("content-type", "").split(";")[0] != "application/json"
            ):
                return Response("Protection de session invalide.", status_code=403)
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            }
        )
        return response

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (ASSETS / "page.html").read_text()

    @app.get("/ui.js")
    def javascript():
        return Response((ASSETS / "ui.js").read_text(), media_type="text/javascript")

    @app.get("/ui.css")
    def stylesheet():
        return Response((ASSETS / "ui.css").read_text(), media_type="text/css")

    @app.get("/api/state")
    def state():
        return {
            "active_job": next(
                (key for key, value in jobs.items() if value["status"] == "running"), None
            ),
            "token": token,
            "experimental": True,
            "scope": "20 000 unités RAG-007 ; questions libres"
            if corpus == "rag007"
            else "Corpus complet RAG-026 ; questions libres",
        }

    def work(identifier, query):
        def progress(stage):
            with lock:
                jobs[identifier]["phase"] = stage

        try:
            result = service(query, progress)
            with lock:
                jobs[identifier].update(status="complete", result=result, phase="Terminé")
        except Exception:
            with lock:
                jobs[identifier].update(
                    status="error",
                    error="Calcul non terminé ou réponse non validée. Vérifier PostgreSQL, les modèles et les artefacts locaux ; aucune réponse réparée automatiquement.",
                    phase="Échec",
                )

    @app.post("/api/ask")
    async def ask(request: Request):
        body = await request.body()
        if len(body) > 8192:
            return JSONResponse({"error": "Question trop longue."}, status_code=413)
        try:
            value = await request.json()
            query = value["query"]
            if not isinstance(query, str) or not query.strip() or len(query) > 1000:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            return JSONResponse(
                {"error": "Question de 1 à 1000 caractères requise."}, status_code=400
            )
        with lock:
            if any(j["status"] == "running" for j in jobs.values()):
                return JSONResponse({"error": "Un calcul est déjà en cours."}, status_code=409)
            if len(jobs) >= 20:
                jobs.pop(next(iter(jobs)))
            identifier = secrets.token_hex(16)
            jobs[identifier] = {"status": "running", "phase": "Préparation"}
        executor.submit(work, identifier, query)
        return JSONResponse({"job_id": identifier}, status_code=202)

    @app.get("/api/jobs/{identifier}")
    def job(identifier: str):
        with lock:
            value = jobs.get(identifier)
            return (
                JSONResponse(dict(value))
                if value
                else JSONResponse({"error": "Calcul inconnu."}, status_code=404)
            )

    return app


def serve(root, *, port=8770, env_file=None, corpus="rag007", ann=False):
    if not 1024 <= port <= 65535:
        raise ValueError("Port invalide.")
    if not (root / "evaluation/local/rag025/selected.json").exists():
        raise ValueError("Recette personnelle sélectionnée requise.")
    if corpus == "rag026":
        from cahier_rag.__main__ import open_store
        from cahier_rag.config import load_settings
        from cahier_rag.fullcorpus.store import FullStore

        with open_store(load_settings(env_file=env_file)) as storage:
            if not FullStore(storage.guard, "full").state()["verified"]:
                raise ValueError("Corpus complet non vérifié ; conserver --corpus rag007.")
    import uvicorn

    from cahier_rag.personal.live import ask

    app = create_app(
        lambda query, progress: ask(
            root, query, env_file=env_file, progress=progress, corpus=corpus, ann=ann
        ),
        port=port,
        corpus=corpus,
    )
    print(
        f"RAG personnel expérimental : http://127.0.0.1:{port} — Ctrl+C pour arrêter.", flush=True
    )
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        proxy_headers=False,
        access_log=False,
        log_level="critical",
    )
    return 0
