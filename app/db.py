from __future__ import annotations
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1) Chemin absolu (via env GDN_SQLITE_PATH)
DB_PATH = Path(os.getenv("GDN_SQLITE_PATH", "/home/romain/cahier-de-doleances/gdn.db")).expanduser().resolve()

# 2) URI SQLite read-only (uri=true indispensable quand on a des query params)
#    Note: as_posix() pour avoir 'file:/...' correct
DATABASE_URL = f"sqlite+pysqlite:///file:{DB_PATH.as_posix()}?mode=ro&cache=shared&uri=true"

# 3) Engine
engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False},  # FastAPI threads
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# 4) Test au démarrage (log friendly)
def assert_db_readable():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB introuvable: {DB_PATH}")
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as e:
        raise RuntimeError(f"Impossible d'ouvrir la DB: {DB_PATH} — {e}")
