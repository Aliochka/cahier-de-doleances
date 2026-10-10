import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    ENV = os.getenv("ENV", "dev").lower()

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
