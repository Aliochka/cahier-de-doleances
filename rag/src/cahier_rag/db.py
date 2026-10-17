"""Fabriques paresseuses et transactions sources explicitement en lecture seule."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, Engine, create_engine

from cahier_rag.config import Settings


def create_source_engine(settings: Settings) -> Engine:
    """Créer un moteur sans connexion ; l'appelant doit ensuite appeler dispose().

    Les transactions sont READ ONLY via SQLAlchemy/psycopg2. Un rôle PostgreSQL
    réellement limité à SELECT reste obligatoire, à provisionner séparément.
    """
    return create_engine(
        settings.require_source_url(),
        connect_args={"connect_timeout": 5},
        pool_timeout=5,
        pool_pre_ping=True,
        hide_parameters=True,
        execution_options={"postgresql_readonly": True},
    )


def create_rag_engine(settings: Settings) -> Engine:
    """Créer le moteur expérimental sans ouvrir de connexion ni créer de table."""
    return create_engine(
        settings.require_rag_url(),
        connect_args={"connect_timeout": 5},
        pool_timeout=5,
        pool_pre_ping=True,
        hide_parameters=True,
    )


@contextmanager
def source_connection(engine: Engine) -> Iterator[Connection]:
    """Ouvrir et fermer explicitement une transaction source READ ONLY.

    L'option est appliquée avant begin(), même si l'appelant fournit un moteur
    qui n'a pas été créé par create_source_engine().
    """
    with engine.connect() as connection:
        connection = connection.execution_options(postgresql_readonly=True)
        with connection.begin():
            yield connection
