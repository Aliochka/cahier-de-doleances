"""Smoke test local : un modèle persistant, deux requêtes, aucune écriture."""

import argparse
import json
from dataclasses import asdict

from cahier_rag.config import ConfigurationError, load_settings
from cahier_rag.embeddings.core import EmbeddingError
from cahier_rag.search.service import create_service
from cahier_rag.search.service.control import SearchError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--models", required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), required=True)
    parser.add_argument("--precision", choices=("float32", "bfloat16", "float16"), required=True)
    parser.add_argument("--query", action="append", required=True)
    args = parser.parse_args(argv)
    if len(args.query) > 3:
        parser.error("Au plus trois requêtes : cette commande n'est pas un benchmark.")
    service = None
    try:
        service = create_service(
            load_settings(env_file=args.env_file),
            args.models,
            device=args.device,
            precision=args.precision,
        )
        service.start()
        print(json.dumps({"ready": True, "load_seconds": service.load_seconds}))
        for query in args.query:
            ranking = service.retrieve(query)
            print(
                json.dumps(
                    {
                        "recipe": ranking.recipe_version,
                        "recipe_hash": ranking.recipe_hash,
                        "generation": ranking.generation,
                        "documents": len(ranking.hits),
                        "answers": len({hit.document.answer_id for hit in ranking.hits}),
                        "timings": asdict(ranking.timings),
                    }
                )
            )
        return 0
    except (ConfigurationError, EmbeddingError) as exc:
        print(json.dumps({"ready": False, "code": "configuration_error", "message": str(exc)}))
        return 1
    except SearchError as exc:
        print(json.dumps({"ready": False, "code": exc.code, "message": str(exc)}))
        return 1
    finally:
        if service is not None:
            service.close()


if __name__ == "__main__":
    raise SystemExit(main())
