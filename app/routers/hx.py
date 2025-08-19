from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.dal import search_contribs

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))
router = APIRouter(prefix="/hx", tags=["htmx"])

@router.get("/search", response_class=HTMLResponse, name="hx_search")
def hx_search(request: Request, q: str = "", page: int = 1, size: int = 20):
    q = (q or "").strip()
    page = max(page, 1)
    size = max(min(size, 100), 1)
    if not q:
        return templates.TemplateResponse("_results.html", {
            "request": request, "rows": [], "q": q, "page": page, "has_more": False
        })
    rows = search_contribs(q, limit=size, offset=(page-1)*size)
    return templates.TemplateResponse("_results.html", {
        "request": request, "rows": rows, "q": q, "page": page, "has_more": len(rows)==size
    })
