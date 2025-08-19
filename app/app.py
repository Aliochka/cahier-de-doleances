# app.py — FastAPI + Jinja2Templates + htmx partials
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.dal import latest_contribs, search_contribs
from pathlib import Path
from app.routers.hx import router as hx_router
import logging
from dotenv import load_dotenv
from app.routers.question_search import router as question_search_router

load_dotenv()

log = logging.getLogger("uvicorn.error")
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent          # => /home/romain/grand_debat/app
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Monter /static (servira /app/static/*)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

from app.routers.pages import router as page_router

app.include_router(page_router)
app.include_router(hx_router)
app.include_router(question_search_router)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/partials/contribs/latest", response_class=HTMLResponse)
async def partials_latest(request: Request, limit: int = 6):
    rows = latest_contribs(limit)
    return templates.TemplateResponse("_latest_contribs.html", {"request": request, "rows": rows})

@app.get("/partials/search/answers", response_class=HTMLResponse, name="search_answers_partial")
async def search_answers_partial(request: Request, q: str = "", page: int = 1, size: int = 20):
    q = (q or "").strip()
    page = max(page, 1)
    size = max(min(size, 100), 1)
    if not q:
        return templates.TemplateResponse("_results.html", {"request": request, "rows": [], "q": q, "page": page, "has_more": False})
    rows = search_contribs(q, limit=size, offset=(page - 1) * size)
    return templates.TemplateResponse("_results.html", {"request": request, "rows": rows, "q": q, "page": page, "has_more": len(rows) == size})

# pages "pleines" si tu veux les URLs non-partials
@app.get("/search/answers", response_class=HTMLResponse, name="search_answers")
async def search_answers_page(request: Request, q: str = "", page: int = 1, size: int = 20):
    return templates.TemplateResponse("search_answers.html", {"request": request, "q": q, "page": page, "size": size})
