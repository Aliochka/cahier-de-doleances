# app/routers/pages.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.db import SessionLocal
from app.services.forms import list_forms
from app.web import templates

router = APIRouter()


@router.get("/", name="home", response_class=HTMLResponse)
def home(request: Request):
    with SessionLocal() as db:
        # Récupérer tous les formulaires avec leur nombre de questions
        forms = list_forms(db)

        forms_list = []
        for form in forms:
            forms_list.append(
                {"id": form["id"], "name": form["name"], "questions_count": form["questions_count"]}
            )

    ctx = {"request": request, "forms": forms_list}
    return templates.TemplateResponse(request, "home/index.html", ctx)
