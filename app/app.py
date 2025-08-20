from fastapi import FastAPI
from app.routers.pages import router as page_router
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
from dotenv import load_dotenv
from app.routers.question_search import router as question_search_router
from app.routers import answers_search

load_dotenv()

log = logging.getLogger("uvicorn.error")
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Monter /static (servira /app/static/*)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


app.include_router(page_router)
app.include_router(question_search_router)
app.include_router(answers_search.router)


