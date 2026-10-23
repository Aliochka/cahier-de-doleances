# app/db.py

import os
from typing import Optional

from dotenv import load_dotenv  # type: ignore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

load_dotenv()


def _normalize_psycopg2(url: Optional[str]) -> str:
    """
    Normalise une URL PostgreSQL pour SQLAlchemy avec psycopg2-binary.
    - postgres://...         -> postgresql+psycopg2://...
    - postgresql://...       -> postgresql+psycopg2://... (si pas déjà +psycopg*)
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
    # Test configuration belongs to pytest, never to the running application.
    raw = (
        os.getenv("DATABASE_URL")
        if settings.ENV == "prod"
        else (os.getenv("DATABASE_URL") or os.getenv("SCALINGO_POSTGRESQL_URL"))
    )
    normalized = _normalize_psycopg2(raw)
    if not normalized:
        raise RuntimeError(
            "No database URL found. Please set one of:\n"
            "- DATABASE_URL for production\n"
            "- DATABASE_URL for development\n"
            "- SCALINGO_POSTGRESQL_URL for Scalingo deployment"
        )
    return normalized


DB_URL = _pick_db_url()

# PostgreSQL engine configuration
engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_timeout=5,
    pool_recycle=300,  # évite les connexions zombies en PaaS
    connect_args={"connect_timeout": 5},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


# Helper FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
