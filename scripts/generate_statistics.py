"""Explicit local statistics publication. No execution from public HTTP routes."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    from app.db import DB_URL
    from app.services.statistics_generation import GenerationError, generate

    url = make_url(DB_URL)
    if url.host not in (None, "localhost", "127.0.0.1", "::1") or not (
        url.database == "cahier_doleances_local" or (url.database or "").endswith("_test")
    ):
        raise SystemExit("Cette commande est limitée aux bases locales autorisées.")
    engine = create_engine(
        DB_URL,
        isolation_level="REPEATABLE READ",
        connect_args={"options": "-c statement_timeout=600000 -c lock_timeout=5000"},
    )
    try:
        with Session(engine) as db, db.begin():
            result = generate(
                db,
                checkpoint=lambda phase: print(
                    "Statistiques : " + phase, file=sys.stderr, flush=True
                ),
            )
        print(json.dumps(result))
    except Exception as exc:
        print(
            "Génération non publiée : transaction annulée. Corriger la cause puis relancer explicitement.",
            file=sys.stderr,
        )
        print("Type d’erreur : " + type(exc).__name__, file=sys.stderr)
        if isinstance(exc, GenerationError):
            print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
