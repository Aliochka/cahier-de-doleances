# app/db.py

from dotenv import load_dotenv  # type: ignore
load_dotenv()

import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker



def _normalize_psycopg2(url: Optional[str]) -> str:
    """
    Normalise une URL Postgres pour SQLAlchemy avec psycopg2-binary.
    - postgres://...         -> postgresql+psycopg2://...
    - postgresql://...       -> postgresql+psycopg2://... (si pas déjà +psycopg*)
    - laisse les autres schémas inchangés (sqlite://, etc.)
    """
    if not url:
        return ""
    u = url.strip()
    if u.startswith("postgres://"):
        return u.replace("postgres://", "postgresql+psycopg2://", 1)
    if u.startswith("postgresql://") and "+psycopg" not in u:
        return u.replace("postgresql://", "postgresql+psycopg2://", 1)
    return u


def _pick_db_url() -> str:
    # Priorité : DATABASE_URL > SCALINGO_POSTGRESQL_URL > fallback local sqlite
    raw = os.getenv("DATABASE_URL") or os.getenv("SCALINGO_POSTGRESQL_URL")
    normalized = _normalize_psycopg2(raw)
    return normalized or "sqlite:///./app_local.db"


DB_URL = _pick_db_url()

# Création de l'engine (adaptation pour SQLite)
if DB_URL.startswith("sqlite"):
    engine = create_engine(
        DB_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        DB_URL,
        pool_pre_ping=True,
        pool_recycle=300,  # évite les connexions zombies en PaaS
    )

SessionLocal = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
)

# Helper FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
