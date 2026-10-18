"""Serveur local unique, fichiers d'annotation ignorés par Git."""

import argparse
import fcntl
import sys
from pathlib import Path

from cahier_rag.annotation.documents import Documents
from cahier_rag.annotation.session import Session
from cahier_rag.config import load_settings
from cahier_rag.db import create_rag_engine
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.evaluation.files import load_json, load_queries
from cahier_rag.evaluation.sampling import digest
from cahier_rag.search.lexical import CorpusScope


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluator", required=True)
    parser.add_argument("--seed", type=int, default=20261020)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--env-file")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    local = root / "evaluation/local"
    engine = None
    try:
        if not 1024 <= args.port <= 65535:
            raise ValueError("Port entre 1024 et 65535 requis.")
        pool = load_json(local / "rag009/annotations/pool.json")
        manifest = load_json(local / "rag009/annotations/manifest.json")
        queries = load_queries(root / "evaluation/queries.json")
        sample = load_sample(local / "rag007/corpus.json")
        scope = CorpusScope(sample)
        if (
            digest(pool) != manifest["pool_hash"]
            or manifest["candidate_count"] != 400
            or manifest["split"] != "development"
            or manifest["sample_hash"] != scope.sample_hash
            or manifest["queries_hash"] != digest(queries)
        ):
            raise ValueError("Manifestes RAG-007/009 incompatibles.")
        folder = local / "rag010"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (folder / "session.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            session = Session(
                pool,
                queries,
                sample,
                folder / "session.json",
                evaluator=args.evaluator,
                seed=args.seed,
            )
            engine = create_rag_engine(load_settings(env_file=args.env_file))
            import uvicorn

            from cahier_rag.annotation.web import create_app

            app = create_app(session, Documents(engine, session.candidates), port=args.port)
            print(f"Annotation locale : http://127.0.0.1:{args.port} (Ctrl+C pour arrêter)")
            uvicorn.run(
                app,
                host="127.0.0.1",
                port=args.port,
                proxy_headers=False,
                access_log=False,
                log_level="critical",
            )
        return 0
    except ModuleNotFoundError:
        print("Installer l’option web : uv sync --locked --extra annotation", file=sys.stderr)
        return 2
    except (ValueError, OSError, KeyError, TypeError):
        print(
            "Démarrage refusé : vérifier les fichiers locaux, l’évaluateur, le port et la configuration ; une seule session autorisée.",
            file=sys.stderr,
        )
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
