# app/db.py

from dotenv import load_dotenv  # type: ignore
load_dotenv()

import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker



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
    # Priorité : TEST_DATABASE_URL > DATABASE_URL > SCALINGO_POSTGRESQL_URL
    raw = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or os.getenv("SCALINGO_POSTGRESQL_URL")
    normalized = _normalize_psycopg2(raw)
    if not normalized:
        raise RuntimeError(
            "No database URL found. Please set one of:\n"
            "- DATABASE_URL for production\n" 
            "- TEST_DATABASE_URL for testing\n"
            "- SCALINGO_POSTGRESQL_URL for Scalingo deployment"
        )
    return normalized


DB_URL = _pick_db_url()

# PostgreSQL engine configuration
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
