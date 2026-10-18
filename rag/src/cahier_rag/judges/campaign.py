"""RAG-017 : pool traçable, contrôles hors ligne et campagnes v2 séparées."""

import argparse
import json
from pathlib import Path

from cahier_rag.annotation.campaigns import Catalogue
from cahier_rag.annotation.reporting import load_rankings
from cahier_rag.annotation.session import atomic_json
from cahier_rag.config import load_settings
from cahier_rag.db import create_rag_engine
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.evaluation.files import load_json, load_queries
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.backend import TransformersJudge
from cahier_rag.judges.cache import Cache
from cahier_rag.judges.contracts import InferenceConfig
from cahier_rag.judges.models import MODELS
from cahier_rag.judges.pipeline import recipe, run
from cahier_rag.judges.planning import iter_inputs, load_plan, prepare
from cahier_rag.judges.protocols import V2
from cahier_rag.representations.repository import RepresentationRepository
from cahier_rag.search.lexical import CorpusScope


def pool(runs, pools, complement, deep, *, target=2500):
    if type(target) is not int or not 2000 <= target <= 3000:
        raise ValueError("Cible entre 2000 et 3000 requise.")
    origins = {}

    def add(qid, did, origin):
        origins.setdefault((qid, did), []).append(origin)

    for method, rankings in runs.items():
        for qid, ids in rankings.items():
            for rank, did in enumerate(ids[:50], 1):
                add(qid, did, {"source": "rag014-top50", "method": method, "rank": rank})
    for name, rows in pools.items():
        for row in rows:
            add(row["query_id"], row["document_id"], {"source": name, "metadata": row})
    for row in complement:
        add(row["query_id"], row["document_id"], {"source": "rag016-top10"})
    initial = len(origins)
    if initial > target:
        raise ValueError("Le pool obligatoire dépasse la cible ; ne pas supprimer ses couples.")
    # Enrichissement équilibré par rang, requête, moteur, sans tirage arbitraire.
    for rank in range(51, 101):
        for qid in sorted(runs["lexical"]):
            for method in ("lexical", "vector"):
                if deep[method][qid][:50] != runs[method][qid][:50]:
                    raise ValueError("Préfixe gelé modifié dans la récupération profonde.")
                ids = deep[method][qid]
                if len(origins) < target and len(ids) >= rank:
                    add(
                        qid,
                        ids[rank - 1],
                        {"source": "rag017-depth100", "method": method, "rank": rank},
                    )
    if len(origins) != target:
        raise ValueError("Profondeur disponible insuffisante pour la cible explicite.")
    # Conserver toutes les occurrences de récupération, même après atteinte de la cible.
    for method in ("lexical", "vector"):
        for qid, ids in deep[method].items():
            for rank, did in enumerate(ids[50:], 51):
                if (qid, did) in origins:
                    origin = {"source": "rag017-depth100", "method": method, "rank": rank}
                    if origin not in origins[qid, did]:
                        add(qid, did, origin)
    return [
        {"query_id": q, "document_id": d, "origins": origins[q, d]} for q, d in sorted(origins)
    ], {
        "initial_union": initial,
        "deficit_to_2000": max(0, 2000 - initial),
        "added": len(origins) - initial,
        "target": target,
        "enrichment": "rank 51..100, sorted query_id, lexical then vector",
    }


def build(root, directory, *, target=2500, env_file=None):
    queries = load_queries(root / "evaluation/queries.json")
    sample = load_sample(root / "evaluation/local/rag007/corpus.json")
    scope = CorpusScope(sample)
    runs, frozen = load_rankings(
        root / "evaluation/local/rag014/development-replay", queries, sample
    )
    deep, deeper = load_rankings(root / "evaluation/local/rag017/deepening", queries, sample)
    if frozen["baselines"] != deeper["baselines"]:
        raise ValueError("Recettes de moteurs différentes.")
    catalogue = Catalogue(root, queries, sample)
    pools = {name: catalogue.load_pool(name) for name in catalogue.campaigns}
    old = load_plan(root / "evaluation/local/rag016/top10")
    if (
        old["sample_hash"] != scope.sample_hash
        or old["query_hash"] != digest(queries)
        or len(old["entries"]) != 101
    ):
        raise ValueError("Complément RAG-016 incompatible.")
    rows, selection = pool(runs, pools, old["entries"], deep, target=target)
    for row in rows:
        row["document_hash"] = scope.documents[row["document_id"]]["content_hash"]
        row["query_hash"] = digest(
            next(q["text"] for q in queries if q["query_id"] == row["query_id"])
        )
    engine = create_rag_engine(load_settings(env_file=env_file))
    try:
        manifest = prepare(
            directory,
            [(r["query_id"], r["document_id"]) for r in rows],
            RepresentationRepository(engine, scope),
            queries,
            kind="rag017",
            prompt_version=V2,
            source_hashes={
                "frozen_rankings": frozen,
                "deepening": deeper,
                "pool_hashes": {k: digest(v) for k, v in pools.items()},
                "complement_hash": old["manifest_hash"],
                "selection": selection,
                "pool_hash": digest(rows),
            },
        )
    finally:
        engine.dispose()
    atomic_json(directory / "pool.json", rows)
    return manifest


def preflight(directory, backend, config):
    manifest = load_plan(directory)
    if manifest["prompt_version"] != V2 or backend.prompt_version != V2:
        raise ValueError("Précontrôle v2 uniquement.")
    configuration = recipe(backend, config)
    counts = []
    for item in iter_inputs(directory, manifest):
        n = backend.token_counts([item])[0]
        counts.append({"input_hash": item.input_hash, "tokens": n})
    failed = sum(
        r["tokens"] > config.max_input_tokens
        or r["tokens"] + config.max_new_tokens > backend.spec.context_tokens
        for r in counts
    )
    result = {
        "plan_hash": manifest["manifest_hash"],
        "recipe_hash": digest(configuration),
        "counts": counts,
        "exceeded": failed,
        "success": not failed,
        "max_tokens": max(r["tokens"] for r in counts),
    }
    result["preflight_hash"] = digest(result)
    atomic_json(directory / (backend.spec.key + "-preflight.json"), result)
    return result


def execute(directory, backend, config, cache, *, limit, retry_failed=False, stop_after=None):
    manifest = load_plan(directory)
    if manifest["prompt_version"] != V2:
        raise ValueError("Campagne v2 uniquement.")
    # Les DEUX précontrôles doivent réussir avant la première génération.
    for key in MODELS:
        check = load_json(directory / (key + "-preflight.json"))
        body = dict(check)
        claimed = body.pop("preflight_hash")
        if (
            digest(body) != claimed
            or not check["success"]
            or check["plan_hash"] != manifest["manifest_hash"]
        ):
            raise ValueError("Précontrôle invalide, incomplet ou trop long.")
        if [r["input_hash"] for r in check["counts"]] != [
            e["input_hash"] for e in manifest["entries"]
        ]:
            raise ValueError("Précontrôle des entrées incomplet.")
    own = load_json(directory / (backend.spec.key + "-preflight.json"))
    if own["recipe_hash"] != digest(recipe(backend, config)):
        raise ValueError("Recette différente du précontrôle.")
    return run(
        directory,
        backend,
        config,
        cache,
        limit=limit,
        allow_full=True,
        retry_failed=retry_failed,
        stop_after=stop_after,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--plan", type=Path, default=Path("evaluation/local/rag017/pool"))
    parser.add_argument("--models", type=Path, default=Path("models/judges"))
    parser.add_argument("--env-file")
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("prepare")
    build_parser.add_argument("--target", type=int, default=2500)
    sub.add_parser("preflight")
    running = sub.add_parser("run")
    running.add_argument("--judge", choices=MODELS, required=True)
    running.add_argument("--limit", type=int, required=True)
    running.add_argument("--retry-failed", action="store_true")
    running.add_argument("--stop-after", type=int)
    reporting = sub.add_parser("report")
    reporting.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    config = InferenceConfig()
    if args.command == "prepare":
        manifest = build(args.root, args.plan, target=args.target, env_file=args.env_file)
        print(json.dumps({"pairs": len(manifest["entries"]), "hash": manifest["manifest_hash"]}))
    elif args.command == "preflight":
        for key, spec in MODELS.items():
            backend = TransformersJudge(spec, args.models, config, prompt_version=V2)
            try:
                result = preflight(args.plan, backend, config)
                print(
                    key,
                    {"success": result["success"], "max_tokens": result["max_tokens"]},
                    flush=True,
                )
                if not result["success"]:
                    return 2
            finally:
                backend.close()
    elif args.command == "run":
        backend = TransformersJudge(MODELS[args.judge], args.models, config, prompt_version=V2)
        cache = Cache(args.plan.parent / "cache.sqlite3")
        try:
            result = execute(
                args.plan,
                backend,
                config,
                cache,
                limit=args.limit,
                retry_failed=args.retry_failed,
                stop_after=args.stop_after,
            )
            print(json.dumps({k: result[k] for k in ("counts", "seconds", "complete")}, indent=2))
        finally:
            cache.close()
    else:
        from cahier_rag.judges.evaluation import report_campaign

        report_campaign(args.root, args.plan, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
