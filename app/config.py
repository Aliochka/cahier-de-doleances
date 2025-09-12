import os
from pathlib import Path

class Settings:
    DB_PATH = os.getenv("DATABASE_URL", "./sandox.db")  # set dans .env
    
    # Authentication
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
    
    # Email configuration (Mailjet)
    MAILJET_API_KEY = os.getenv("MAILJET_API_KEY", "")
    MAILJET_SECRET_KEY = os.getenv("MAILJET_SECRET_KEY", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@cahierdedoleances.fr")
    FROM_NAME = os.getenv("FROM_NAME", "Cahier de doléances")
    
    # Application
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

settings = Settings()


def _default_db_path() -> str:
    return "./sandbox.db"

def get_db_path() -> str:
    # 1) explicit env
    path = os.environ.get("DATABASE_URL")
    if path and path.strip():
        return path.strip()
    # 2) default
    return _default_db_path()

def get_sqlite_url(path: str | None = None) -> str:
    p = Path(path or get_db_path())
    # sqlite URL: three leading slashes for relative paths
    # ensure platform-neutral
    return f"sqlite:///{p.as_posix()}"