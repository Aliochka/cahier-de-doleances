# app/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

RAW = (os.getenv("DATABASE_URL") or "").strip()

# On n'essaie plus de "reconstruire" l'URL.
# Si elle n'est pas fournie, fallback simple dans le cwd:
if not RAW:
    RAW = "sqlite+pysqlite:///./gdn.db"

# Debug: identifiant unique pour être sûr que c'est CE fichier qui parle
print("ENGINE URL (db.py v2) =", RAW)

engine = create_engine(RAW, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
