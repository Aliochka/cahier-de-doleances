# app/routers/pages.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.web import templates

router = APIRouter()

@router.get("/", name="home", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home/index.html", {"request": request })

@router.get("/mentions", name="mentions", response_class=HTMLResponse)
def mentions(request: Request):
    return templates.TemplateResponse("mentions.html", {"request": request})

@router.get("/topics", name="topics", response_class=HTMLResponse)
def topics(request: Request):
    return templates.TemplateResponse("topics.html", {"request": request})

