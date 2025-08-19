from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .routers import pages, hx

app = FastAPI(title="Grand Débat")
app.include_router(pages.router)
app.include_router(hx.router, prefix="/hx")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
