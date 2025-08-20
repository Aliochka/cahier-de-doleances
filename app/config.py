import os
from pathlib import Path

class Settings:
    DB_PATH = os.getenv("DATABASE_URL", "./sandox.db")  # set dans .env
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