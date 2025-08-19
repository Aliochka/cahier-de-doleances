from fastapi import APIRouter
from app.db import DB_PATH, engine
router = APIRouter(prefix="/debug")

@router.get("/db")
def debug_db():
    exists = DB_PATH.exists()
    size = DB_PATH.stat().st_size if exists else 0
    with engine.connect() as conn:
        row = conn.exec_driver_sql("SELECT 1").scalar_one_or_none()
    return {"path": str(DB_PATH), "exists": exists, "size": size, "probe": row}
