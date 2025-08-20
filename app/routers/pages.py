from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.dal import latest_contribs
from app.web import templates

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates" 

router = APIRouter()

@router.get("/", name="home", response_class=HTMLResponse)
def home(request: Request, q: str | None = None):
    return templates.TemplateResponse("index.html", {"request": request, "q": q or ""})

@router.get("/mentions", name="mentions", response_class=HTMLResponse)
def mentions(request: Request):
    return templates.TemplateResponse("mentions.html", {"request": request})

@router.get("/topics", name="topics", response_class=HTMLResponse)
def topics(request: Request):
    # TODO: remplace "topics.html" par ton vrai template d’exploration
    return templates.TemplateResponse("topics.html", {"request": request})

@router.get("/search/answers", name="search_answers", response_class=HTMLResponse)
def search_answers_page(request: Request, q: str = ""):
    return templates.TemplateResponse("search_answers.html", {"request": request, "q": q})

@router.get("/search/questions", name="search_questions", response_class=HTMLResponse)
def search_questions_page(request: Request):
    # TODO: remplace "search_questions.html" par ton vrai template
    return templates.TemplateResponse("search_questions.html", {"request": request})

@router.get("/partials/contribs/latest", name="partials_latest_contribs", response_class=HTMLResponse)
def partials_latest_contribs(request: Request, limit: int = 6):
    rows = latest_contribs(limit=limit)
    return templates.TemplateResponse("_latest_contribs.html", {"request": request, "rows": rows})
