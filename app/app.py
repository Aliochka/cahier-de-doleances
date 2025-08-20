from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
from dotenv import load_dotenv
from app.routers import pages, search, authors, questions

load_dotenv()


app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent 
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

log = logging.getLogger("uvicorn.error")
app = FastAPI()

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(pages.router)
app.include_router(search.router)
app.include_router(authors.router)
app.include_router(questions.router)