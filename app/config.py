import os
class Settings:
    DB_PATH = os.getenv("GDN_SQLITE_PATH", "./gdn.db")  # set dans .env
settings = Settings()
