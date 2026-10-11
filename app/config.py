import ipaddress
import logging
import os
import secrets
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv(override=False)


def _boolean(env, name, default):
    value = env.get(name, str(default)).lower()
    if value not in {"true", "false", "1", "0"}:
        raise ValueError(f"{name} must be true or false")
    return value in {"true", "1"}


class Settings:
    def __init__(self, environ=None):
        env = os.environ if environ is None else environ
        self.ENV = env.get("ENV", "dev").lower()
        if self.ENV not in {"dev", "test", "prod"}:
            raise ValueError("ENV must be dev, test or prod")
        self.BASE_URL = env.get("BASE_URL", "http://localhost:8000").rstrip("/")
        url = urlsplit(self.BASE_URL)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.path
            or url.query
            or url.fragment
        ):
            raise ValueError("BASE_URL must be an HTTP(S) origin without credentials or path")
        self.COOKIE_SECURE = _boolean(env, "COOKIE_SECURE", url.scheme == "https")
        self.CSRF_TRUSTED_ORIGINS = [
            origin.strip()
            for origin in env.get("CSRF_TRUSTED_ORIGINS", "").split(",")
            if origin.strip()
        ]
        # Keep validation local to settings to avoid importing the application.
        for origin in self.CSRF_TRUSTED_ORIGINS:
            extra = urlsplit(origin)
            if (
                extra.scheme not in {"http", "https"}
                or not extra.hostname
                or extra.username is not None
                or extra.password is not None
                or extra.path
                or extra.query
                or extra.fragment
                or any(c.isspace() for c in origin)
                or any(c in origin for c in "\\*")
            ):
                raise ValueError("CSRF_TRUSTED_ORIGINS requires exact HTTP(S) origins")
            _ = extra.port  # Reject invalid port numbers at startup.
        self.ENFORCE_HTTPS = _boolean(env, "ENFORCE_HTTPS", url.scheme == "https")
        self.ALLOWED_HOSTS = [
            h.strip() for h in env.get("ALLOWED_HOSTS", "").split(",") if h.strip()
        ]
        self.TRUSTED_PROXY_IPS = [
            h.strip() for h in env.get("TRUSTED_PROXY_IPS", "").split(",") if h.strip()
        ]
        self.SECRET_KEY = env.get("SECRET_KEY", "")
        if self.SECRET_KEY == "your-secret-key-change-in-production":
            raise ValueError("The placeholder SECRET_KEY is forbidden")
        if self.ENV == "prod":
            if "*" in self.TRUSTED_PROXY_IPS:
                raise ValueError("Production TRUSTED_PROXY_IPS must not trust every client")
            if len(self.SECRET_KEY) < 32:
                raise ValueError("Production SECRET_KEY must contain at least 32 characters")
            if not env.get("BASE_URL") or not self.ALLOWED_HOSTS or "*" in self.ALLOWED_HOSTS:
                raise ValueError("Production requires BASE_URL and explicit ALLOWED_HOSTS")
            if (
                env.get("TEST_DATABASE_URL")
                or env.get("ALEMBIC_DATABASE_URL")
                or env.get("SCALINGO_POSTGRESQL_URL")
            ):
                raise ValueError(
                    "Production accepts only DATABASE_URL; remove alternate database URLs"
                )
            if url.hostname not in self.ALLOWED_HOSTS:
                raise ValueError("BASE_URL hostname must be listed in ALLOWED_HOSTS")
            if url.scheme == "http":
                try:
                    private = ipaddress.ip_address(url.hostname).is_private
                except ValueError:
                    private = url.hostname == "localhost" or url.hostname.endswith(".local")
                if not private or env.get("COOKIE_SECURE", "").lower() not in {"false", "0"}:
                    raise ValueError(
                        "HTTP deployment requires a private LAN host and explicit COOKIE_SECURE=false"
                    )
                if self.ENFORCE_HTTPS:
                    raise ValueError("HTTP BASE_URL is incompatible with ENFORCE_HTTPS=true")
            elif not self.COOKIE_SECURE:
                raise ValueError("HTTPS deployment requires COOKIE_SECURE=true")
        elif not self.SECRET_KEY:
            self.SECRET_KEY = secrets.token_urlsafe(48)
            logging.getLogger(__name__).warning(
                "SECRET_KEY missing: temporary development key; sessions expire on restart"
            )
        self.LOGIN_EMAIL_ENABLED = _boolean(env, "LOGIN_EMAIL_ENABLED", True)
        self.ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
        self.MAILJET_API_KEY = env.get("MAILJET_API_KEY", "")
        self.MAILJET_SECRET_KEY = env.get("MAILJET_SECRET_KEY", "")
        self.FROM_EMAIL = env.get("FROM_EMAIL", "noreply@cahierdedoleances.fr")
        self.FROM_NAME = env.get("FROM_NAME", "Cahier de doléances")
        self.LOG_MAGIC_LINKS = _boolean(env, "LOG_MAGIC_LINKS", self.ENV != "prod")
        if self.ENV == "prod" and self.LOG_MAGIC_LINKS:
            raise ValueError("LOG_MAGIC_LINKS is forbidden in production")


settings = Settings()
