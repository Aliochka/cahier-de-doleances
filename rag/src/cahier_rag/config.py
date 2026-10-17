"""Configuration explicite : aucune lecture de .env ni de paramètres backend à l'import."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from os import environ as process_environment
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

SOURCE_VARIABLE = "RAG_SOURCE_DATABASE_URL"
RAG_VARIABLE = "RAG_DATABASE_URL"
# Éviter les DSN libpq indirects et les paramètres qui redéfinissent la base,
# le rôle ou les transactions derrière l'URL validée.
SUPPORTED_QUERY_PARAMETERS = {
    "host",
    "port",
    "sslmode",
    "sslrootcert",
    "sslcert",
    "sslkey",
    "application_name",
    "connect_timeout",
}


class ConfigurationError(ValueError):
    """Erreur explicable sans exposer de valeur de configuration."""


def _parse_url(raw: str | None, variable: str) -> URL | None:
    if raw is None or not raw.strip():
        return None
    try:
        url = make_url(raw.strip())
        if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg2"}:
            raise ValueError()
        if not url.database or not url.database.strip():
            raise ValueError()
        if set(url.query) - SUPPORTED_QUERY_PARAMETERS:
            raise ValueError()
        if any(not isinstance(value, str) for value in url.query.values()):
            raise ValueError()
        # psycopg2 autorise un host en query pour les sockets Unix, mais celui-ci
        # prime sur le host de l'autorité : refuser cette ambiguïté.
        if url.host and "host" in url.query:
            raise ValueError()
        if url.port is not None and "port" in url.query:
            raise ValueError()
        host = url.query.get("host", url.host) or ""
        if "," in host or any(character.isspace() for character in host):
            raise ValueError()
        port = int(url.query.get("port", 5432 if url.port is None else url.port))
        if not 1 <= port <= 65535:
            raise ValueError()
        return url.set(drivername="postgresql+psycopg2")
    except (ArgumentError, ValueError, TypeError, AttributeError):
        raise ConfigurationError(
            f"{variable} : URL PostgreSQL invalide ou paramètres non pris en charge."
        ) from None


def _database_identity(url: URL) -> tuple[str, int, str]:
    """Comparer les destinations, indépendamment des rôles et mots de passe."""
    host = (url.query.get("host", url.host) or "localhost").lower().rstrip(".")
    if host in {"localhost", "127.0.0.1", "::1", "/var/run/postgresql", "/run/postgresql"}:
        host = "local"
    port = int(url.query.get("port", 5432 if url.port is None else url.port))
    return host, port, url.database


@dataclass(frozen=True)
class Settings:
    """Connexions facultatives tant qu'aucune opération ne les demande.

    Les URL restent exclues du repr, y compris leurs paramètres de requête.
    Charger cette configuration avec load_settings().
    """

    source_url: URL | None = field(default=None, repr=False)
    rag_url: URL | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if (
            self.source_url is not None
            and self.rag_url is not None
            and _database_identity(self.source_url) == _database_identity(self.rag_url)
        ):
            raise ConfigurationError(
                "RAG_SOURCE_DATABASE_URL et RAG_DATABASE_URL doivent viser des bases distinctes."
            )

    def require_source_url(self) -> URL:
        if self.source_url is None:
            raise ConfigurationError(f"{SOURCE_VARIABLE} est requise pour la connexion source.")
        return self.source_url

    def require_rag_url(self) -> URL:
        if self.rag_url is None:
            raise ConfigurationError(f"{RAG_VARIABLE} est requise pour la connexion RAG.")
        return self.rag_url


def load_settings(
    *, environ: Mapping[str, str] | None = None, env_file: str | Path | None = None
) -> Settings:
    """Lire uniquement les variables RAG ; l'environnement prime sur le fichier choisi.

    Aucun fichier n'est recherché automatiquement. L'interpolation dotenv est
    désactivée pour ne pas importer implicitement des valeurs du backend.
    Cette fonction ne modifie pas os.environ et n'ouvre aucune connexion SQL.
    """
    values: dict[str, str | None] = {}
    if env_file is not None:
        try:
            with Path(env_file).open(encoding="utf-8") as stream:
                values.update(dotenv_values(stream=stream, interpolate=False))
        except (OSError, UnicodeError):
            raise ConfigurationError(
                "Le fichier de configuration sélectionné est illisible."
            ) from None
    environment = process_environment if environ is None else environ
    for name in (SOURCE_VARIABLE, RAG_VARIABLE):
        if name in environment:
            values[name] = environment[name]
    return Settings(
        source_url=_parse_url(values.get(SOURCE_VARIABLE), SOURCE_VARIABLE),
        rag_url=_parse_url(values.get(RAG_VARIABLE), RAG_VARIABLE),
    )
