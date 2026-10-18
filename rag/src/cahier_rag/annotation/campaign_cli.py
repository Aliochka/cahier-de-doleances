"""Campagnes et évaluations locales ; les commandes de bilan lisent les sessions uniquement."""

import argparse
import json
import sys
from pathlib import Path

from cahier_rag.annotation.campaigns import Catalogue
from cahier_rag.annotation.consolidation import consolidate
from cahier_rag.annotation.reporting import METHODS, evaluate_report, load_rankings
from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.evaluation.files import load_queries
from cahier_rag.search.lexical import CorpusScope


def write_bundle(directory, files):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    for name, value in files.items():
        atomic_json(directory / name, value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    status = sub.add_parser("status")
    status.add_argument("--campaign", choices=["rag010", "rag014"])
    for name in ("create", "open", "export"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--campaign", choices=["rag010", "rag014"], required=True)
        if name in {"create", "open"}:
            cmd.add_argument("--evaluator", required=name == "create")
            cmd.add_argument("--seed", type=int)
        if name == "open":
            cmd.add_argument("--port", type=int, default=8765)
            cmd.add_argument("--env-file")
        if name == "export":
            cmd.add_argument("--output", type=Path, required=True)
    for name in ("consolidate", "conflicts", "evaluate", "report"):
        cmd = sub.add_parser(name)
        if name != "conflicts":
            cmd.add_argument("--output", type=Path, required=True)
        if name in {"evaluate", "report"}:
            cmd.add_argument("--rankings", type=Path)
    args = parser.parse_args(argv)
    try:
        queries = load_queries(args.root / "evaluation/queries.json")
        sample = load_sample(args.root / "evaluation/local/rag007/corpus.json")
        CorpusScope(sample)
        catalogue = Catalogue(args.root, queries, sample)
        if args.command in {"list", "status"}:
            names = (
                [args.campaign] if getattr(args, "campaign", None) else sorted(catalogue.campaigns)
            )
            for name in names:
                status = catalogue.status(name)
                print(
                    f"{name} · {status['label']} · {'créée' if status['started'] else 'non créée'} · {status['judged']}/{status['total']} · notes {json.dumps(status['grades'], sort_keys=True)}"
                )
            return 0
        if args.command == "create":
            session = catalogue.create(args.campaign, evaluator=args.evaluator, seed=args.seed)
            print(
                f"Campagne {args.campaign} créée explicitement : {len(session.order)} couples, aucune note. Serveur non démarré."
            )
            return 0
        if args.command == "open":
            snapshot = catalogue.snapshot(args.campaign)
            if snapshot is None:
                raise ValueError("Créer explicitement la session avant open.")
            from cahier_rag.annotation.cli import main as launch

            command = [
                "--campaign",
                args.campaign,
                "--evaluator",
                args.evaluator or snapshot.identity["evaluator"],
                "--seed",
                str(args.seed if args.seed is not None else snapshot.identity["seed"]),
                "--port",
                str(args.port),
            ]
            if args.env_file:
                command.extend(["--env-file", args.env_file])
            if args.root.resolve() != Path(__file__).resolve().parents[3]:
                raise ValueError("Ouverture serveur autorisée uniquement dans le projet installé.")
            return launch(command)
        if args.command == "export":
            snapshot = catalogue.snapshot(args.campaign)
            if snapshot is None:
                raise ValueError("Session absente.")
            write_bundle(
                args.output,
                {
                    "judgments.json": snapshot.export(),
                    "metadata.json": {"campaign_id": args.campaign, "identity": snapshot.identity},
                },
            )
            print(f"Export de {len(snapshot.export())} jugements ; source inchangée.")
            return 0
        reference = consolidate(catalogue)
        if args.command == "conflicts":
            print(
                f"{len(reference['conflicts'])} conflit(s) non résolu(s), {reference['resolved_pairs']} couples résolus."
            )
            return 3 if reference["conflicts"] else 0
        files = {
            "reference.json": reference,
            "judgments.json": reference["judgments"],
            "provenance.json": reference["provenance"],
            "conflicts.json": reference["conflicts"],
        }
        if args.command in {"evaluate", "report"}:
            runs, ranking_metadata = load_rankings(
                args.rankings or args.root / "evaluation/local/rag014/development-replay",
                queries,
                sample,
            )
            report = evaluate_report(reference, runs, queries, sample)
            report["rankings_metadata"] = ranking_metadata
            files["report.json"] = report
            files["pending.json"] = {
                s["campaign_id"]: s["pending_pairs"] for s in reference["campaigns"]
            }
            for status in reference["campaigns"]:
                print(
                    f"{status['campaign_id']} : {status['judged']}/{status['total']} ; notes {json.dumps(status['grades'], sort_keys=True)}"
                )
            for method in METHODS:
                text = " · ".join(
                    f"top {k}: {report['methods'][method]['summary'][str(k)]['judged']}/{report['methods'][method]['summary'][str(k)]['returned']} jugés"
                    for k in (5, 10, 20)
                )
                print(f"{method} · {text}")
            for k, metrics in report["matched_queries"].items():
                for name, measure in metrics.items():
                    if name == "mrr" and k != "5":
                        continue
                    label = "MRR (classement fourni)" if name == "mrr" else f"{name} (k={k})"
                    if measure["defined_queries"]:
                        print(
                            f"{label} : {measure['defined_queries']} requêtes communes calculables ; moyennes descriptives {json.dumps(measure['means'], sort_keys=True)}"
                        )
                    else:
                        print(f"{label} : comparaison commune non calculable.")
            print(
                "Jugements incomplets : aucun classement définitif. Détails, métriques calculables et absences dans report.json."
            )
        write_bundle(args.output, files)
        print(
            f"{reference['distinct_judged_pairs']} couples jugés ; {len(reference['conflicts'])} conflits. Sources préservées."
        )
        return 0
    except (ValueError, KeyError, TypeError, OSError):
        print(
            "Opération refusée : vérifier campagne, manifestes et destination. Une session existante n'est jamais remplacée. Aucun commentaire ni secret affiché.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
