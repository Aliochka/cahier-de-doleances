"""Interface aveugle same-origin, sans journalisation documentaire."""

import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError

ASSETS = Path(__file__).parent


def create_app(
    session, documents, *, port=8765, campaign_id="rag010", campaign_label="Campagne initiale"
):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    origin = f"http://127.0.0.1:{port}"
    token = secrets.token_urlsafe(32)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if (
            request.client is None
            or request.client.host != "127.0.0.1"
            or request.headers.get("host") != f"127.0.0.1:{port}"
            or request.headers.get("sec-fetch-site") not in (None, "same-origin", "none")
            or request.headers.get("origin") not in (None, origin)
        ):
            return Response("Origine locale requise.", status_code=403)
        if request.method not in {"GET", "HEAD"}:
            if (
                not secrets.compare_digest(request.headers.get("x-annotation-token", ""), token)
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

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        return JSONResponse(
            {"error": "Base RAG indisponible ; aucune annotation perdue. Réessayer."},
            status_code=503,
        )

    @app.exception_handler(OSError)
    async def storage_error(request, error):
        return JSONResponse(
            {"error": "Échec de sauvegarde locale. Rester sur cette page et réessayer."},
            status_code=503,
        )

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse(
            {"error": "État ou paramètres invalides ; recharger si un autre onglet est ouvert."},
            status_code=409,
        )

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (ASSETS / "page.html").read_text()

    @app.get("/ui.js")
    def script():
        return Response((ASSETS / "ui.js").read_text(), media_type="text/javascript")

    @app.get("/ui.css")
    def style():
        return Response((ASSETS / "ui.css").read_text(), media_type="text/css")

    @app.get("/api/state")
    def state():
        return {
            **session.view(),
            "token": token,
            "campaign_id": campaign_id,
            "campaign_label": campaign_label,
        }

    @app.get("/api/document")
    def document(position: int, parent: bool = False):
        if not 0 <= position < len(session.order):
            raise ValueError("Position invalide.")
        return {"documents": documents.get(session.order[position], parent=parent)}

    @app.post("/api/change")
    async def change(request: Request):
        if len(await request.body()) > 65000:
            return Response(status_code=413)
        try:
            payload = await request.json()
            if not isinstance(payload, dict) or set(payload) - {
                "revision",
                "position",
                "comment",
                "grade",
                "destination",
            }:
                raise ValueError()
            return {
                **session.change(**payload),
                "campaign_id": campaign_id,
                "campaign_label": campaign_label,
            }
        except (TypeError, KeyError):
            raise ValueError("Paramètres invalides.") from None

    @app.get("/api/export")
    def export():
        return JSONResponse(
            session.export(),
            headers={
                "Content-Disposition": 'attachment; filename="'
                + ("judgments.json" if campaign_id == "rag010" else f"{campaign_id}-judgments.json")
                + '"'
            },
        )

    return app
