# app/routers/pages.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from app.web import templates
from app.db import SessionLocal

router = APIRouter()

@router.get("/", name="home", response_class=HTMLResponse)
def home(request: Request):
    with SessionLocal() as db:
        # Récupérer tous les formulaires avec leur nombre de questions
        forms = db.execute(
            text("""
                SELECT f.id, f.name,
                       COUNT(q.id)::int AS questions_count
                FROM forms f
                LEFT JOIN questions q ON q.form_id = f.id
                GROUP BY f.id, f.name
                ORDER BY f.id
            """)
        ).mappings().all()

        forms_list = []
        for form in forms:
            forms_list.append({
                "id": form["id"],
                "name": form["name"],
                "questions_count": form["questions_count"]
            })

    ctx = {
        "request": request,
        "forms": forms_list
    }
    return templates.TemplateResponse("home/index.html", ctx)

@router.get("/mentions", name="mentions", response_class=HTMLResponse)
def mentions(request: Request):
    return templates.TemplateResponse("mentions.html", {"request": request})

@router.get("/topics", name="topics", response_class=HTMLResponse)
def topics(request: Request):
    return templates.TemplateResponse("topics.html", {"request": request})

