"""Serveur local unique, fichiers d'annotation ignorés par Git."""

import argparse
import sys
from pathlib import Path

from cahier_rag.annotation.campaigns import Catalogue
from cahier_rag.annotation.documents import Documents
from cahier_rag.config import load_settings
from cahier_rag.db import create_rag_engine
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.evaluation.files import load_queries
from cahier_rag.search.lexical import CorpusScope


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluator", required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--campaign", choices=["rag010", "rag014"], default="rag010")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--env-file")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    local = root / "evaluation/local"
    engine = None
    try:
        if not 1024 <= args.port <= 65535:
            raise ValueError("Port entre 1024 et 65535 requis.")
        queries = load_queries(root / "evaluation/queries.json")
        sample = load_sample(local / "rag007/corpus.json")
        CorpusScope(sample)
        catalogue = Catalogue(root, queries, sample)
        spec = catalogue.get(args.campaign)
        catalogue.load_pool(args.campaign)
        if args.campaign != "rag010" and not spec.session_path.exists():
            raise ValueError("Créer explicitement la campagne avant son lancement.")
        with spec.writer_lock():
            session = catalogue.session(
                args.campaign,
                evaluator=args.evaluator,
                seed=args.seed,
                allow_create=args.campaign == "rag010",
            )
            engine = create_rag_engine(load_settings(env_file=args.env_file))
            import uvicorn

            from cahier_rag.annotation.web import create_app

            app = create_app(
                session,
                Documents(engine, session.candidates),
                port=args.port,
                campaign_id=spec.campaign_id,
                campaign_label=spec.label,
            )
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
