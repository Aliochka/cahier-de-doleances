"""Recettes figées, classements RAG-020 contrôlés, artefacts locaux et essais bornés."""

import json
import resource
import time
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from cahier_rag.annotation.session import atomic_json
from cahier_rag.context.assembly import assemble
from cahier_rag.context.contracts import ContextConfig
from cahier_rag.context.repository import ContextRepository
from cahier_rag.context.tokenization import LocalTokenizer
from cahier_rag.embeddings.snapshots import sha256_file
from cahier_rag.evaluation.sampling import digest
from cahier_rag.reranking.cache import Cache
from cahier_rag.reranking.planning import load_plan, select_candidates
from cahier_rag.search.hybrid.multi.artifacts import load_bundle

METHODS = ("H1+R2", "H1+R1", "V")


def configurations():
    base = ContextConfig()
    return {
        "S1-P1-8192": replace(base, selection="S1"),
        "S2-P1-8192": base,
        "S3-P1-8192": replace(base, selection="S3"),
        "S2-P0-8192": replace(base, parent_mode="P0"),
        "S2-P2-8192": replace(base, parent_mode="P2"),
        "S2-P1-4096": replace(base, document_budget=4096),
        "S2-P1-16384": replace(base, document_budget=16384),
    }


def inputs(root):
    bundle, frozen, scope, queries = load_bundle(
        root,
        root / "evaluation/local/rag019/configuration",
        root / "evaluation/local/rag019/development",
    )
    plan_dir = root / "evaluation/local/rag020/plan"
    plan, candidates = load_plan(plan_dir)
    if (
        select_candidates(bundle)[0] != candidates
        or plan["sample_hash"] != scope.sample_hash
        or plan["queries_hash"] != digest(queries)
        or plan["rag019_frozen_hash"] != frozen["frozen_hash"]
    ):
        raise ValueError("Références RAG-020 incompatibles.")
    ranks = {}
    cache = Cache(plan_dir.parent / "scores.sqlite3", readonly=True)
    try:
        for method in METHODS:
            path = root / "evaluation/local/rag020/report" / method / "runs.json"
            ranks[method] = json.loads(path.read_text())
            if method == "V":
                expected = candidates["V"]
            else:
                model = method.split("+")[1]
                run = json.loads((plan_dir / (model + "-run.json")).read_text())
                recipe = {
                    "version": 1,
                    "plan_hash": plan["manifest_hash"],
                    "backend": plan["backends"][model],
                    "batch_documents": plan["batch_documents"],
                    "batch_segments": plan["batch_segments"],
                    "preparation": plan["configuration"],
                }
                if (
                    not run["complete"]
                    or run["recipe"] != recipe
                    or run["recipe_hash"] != digest(recipe)
                ):
                    raise ValueError("Recette de reranking incomplète.")
                scores = defaultdict(dict)
                for entry in plan["pairs"]:
                    row = cache.get(run["recipe_hash"], entry["query_id"], entry["document_id"])
                    if (
                        row is None
                        or row["unit_input_hash"] != digest(entry)
                        or row["source_hash"] != entry["source_hash"]
                    ):
                        raise ValueError("Score RAG-020 absent ou modifié.")
                    scores[entry["query_id"]][entry["document_id"]] = row["score"]
                expected = {
                    q: sorted(ids, key=lambda d: (-scores[q][d], d))
                    for q, ids in candidates["H1"].items()
                }
            if ranks[method] != expected:
                raise ValueError("Classements gelés RAG-020 modifiés.")
    finally:
        cache.close()
    development = [q for q in queries if q["split"] == "development"]
    if len(development) != 20 or any(
        set(rows) != {q["query_id"] for q in development} for rows in ranks.values()
    ):
        raise ValueError("Vingt requêtes de développement requises.")
    return ranks, scope, development


def tokenizer_location(root):
    revision = "22e683669bc0f0bd69640a1354a6d0aebcfeede5"
    folder = root / "models/rerankers/qwen3-reranker-4b" / revision
    manifest = json.loads((folder / "snapshot-manifest.json").read_text())
    path = folder / "tokenizer.json"
    # Snapshot RAG-020 local, aucun téléchargement ou chargement de poids.
    actual = sha256_file(path)
    plan, _ = load_plan(root / "evaluation/local/rag020/plan")
    if (
        digest({k: v for k, v in manifest.items() if k != "manifest_hash"})
        != manifest["manifest_hash"]
        or manifest["manifest_hash"] != plan["backends"]["R2"]["snapshot_hash"]
        or manifest["model"] != plan["backends"]["R2"]["model"]
        or actual != manifest["files"]["tokenizer.json"]
    ):
        raise ValueError("Tokenizer différent du snapshot validé RAG-020.")
    return path, {
        "repository": "Qwen/Qwen3-Reranker-4B",
        "revision": revision,
        "expected_sha256": actual,
    }


def freeze(root, directory):
    ranks, scope, queries = inputs(root)
    path, tokenizer = tokenizer_location(root)
    files = [
        root / "evaluation/queries.json",
        root / "evaluation/local/rag007/corpus.json",
        root / "evaluation/local/rag018/bm25-A.sqlite3",
        root / "evaluation/local/rag020/scores.sqlite3",
        root / "evaluation/local/rag020/plan/manifest.json",
        *[root / "evaluation/local/rag020/report" / m / "runs.json" for m in METHODS],
        path,
        *sorted(Path(__file__).parent.glob("*.py")),
    ]
    protocol = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sample_hash": scope.sample_hash,
        "queries_hash": digest(queries),
        "runs_hash": digest(ranks),
        "configurations": {k: v.to_dict() for k, v in configurations().items()},
        "tokenizer": tokenizer,
        "tokenizer_path": str(path.resolve().relative_to(root.resolve())),
        "files": {str(p.resolve().relative_to(root.resolve())): sha256_file(p) for p in files},
        "judgments_used": False,
        "parent_policy": "rag007-selected-only; development; same corpus/contribution/form",
        "selection_scope": "top50 frozen candidates; observed duplicates are not corpus prevalence",
        "segmentation": "exact prefix, no overlap, <=768 citizen-text tokens; explicit omitted ranges",
        "staged_design": "seven configurations, not a full Cartesian product",
    }
    protocol["protocol_hash"] = digest(protocol)
    directory.mkdir(parents=True, exist_ok=False)
    atomic_json(directory / "protocol.json", protocol)
    return protocol


def load_protocol(root, directory):
    protocol = json.loads((directory / "protocol.json").read_text())
    if digest({k: v for k, v in protocol.items() if k != "protocol_hash"}) != protocol[
        "protocol_hash"
    ] or protocol["configurations"] != {k: v.to_dict() for k, v in configurations().items()}:
        raise ValueError("Protocole ou configurations modifiés.")
    if any(sha256_file(root / p) != h for p, h in protocol["files"].items()):
        raise ValueError("Entrée, tokenizer ou code modifié depuis le gel.")
    ranks, scope, queries = inputs(root)
    if (
        protocol["runs_hash"] != digest(ranks)
        or protocol["queries_hash"] != digest(queries)
        or protocol["sample_hash"] != scope.sample_hash
    ):
        raise ValueError("Périmètre expérimental incompatible.")
    counter = LocalTokenizer(root / protocol["tokenizer_path"], **protocol["tokenizer"])
    return protocol, ranks, scope, queries, counter


def run(root, protocol_directory, output, *, query_limit=20):
    if type(query_limit) is not int or not 1 <= query_limit <= 20:
        raise ValueError("Limite de 1 à 20 requêtes requise.")
    protocol, ranks, scope, queries, counter = load_protocol(root, protocol_directory)
    repository = ContextRepository(root / "evaluation/local/rag018/bm25-A.sqlite3", scope)
    selected = sorted(queries, key=lambda q: q["query_id"])[:query_limit]
    output.mkdir(parents=True, exist_ok=False)
    stats = []
    started = time.perf_counter()
    with (output / "contexts.jsonl").open("x", encoding="utf-8") as stream:
        from cahier_rag.contracts import canonical_json

        for index, q in enumerate(selected):
            for method in METHODS:
                for name, config in configurations().items():
                    before = time.perf_counter()
                    context = assemble(
                        q,
                        ranks[method][q["query_id"]],
                        repository,
                        counter,
                        method=method,
                        config=config,
                    )
                    elapsed = time.perf_counter() - before
                    record = {
                        "query_id": q["query_id"],
                        "method": method,
                        "configuration_id": name,
                        "context": context,
                    }
                    stream.write(canonical_json(record) + "\n")
                    stats.append(
                        {
                            "query_id": q["query_id"],
                            "method": method,
                            "configuration_id": name,
                            "context_hash": context["context_hash"],
                            "seconds": elapsed,
                            **context["statistics"],
                            "tokens": context["budget"]["document_used"],
                            "metadata_reference_tokens": context["budget"][
                                "metadata_reference_tokens"
                            ],
                            "expansion_tokens": context["budget"]["expansion_incremental_tokens"],
                        }
                    )
            stream.flush()
            print(
                f"Contextes : {index + 1}/{len(selected)} requêtes, {len(stats)} assemblages",
                flush=True,
            )
    summary = aggregate(stats)
    manifest = {
        "version": 1,
        "protocol_hash": protocol["protocol_hash"],
        "sample_hash": scope.sample_hash,
        "queries": [q["query_id"] for q in selected],
        "contexts": len(stats),
        "seconds": time.perf_counter() - started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "contexts_sha256": sha256_file(output / "contexts.jsonl"),
        "contexts_bytes": (output / "contexts.jsonl").stat().st_size,
        "statistics_hash": digest(stats),
        "statistics": summary,
        "judgments_used": False,
    }
    manifest["manifest_hash"] = digest(manifest)
    atomic_json(output / "statistics.json", stats)
    atomic_json(output / "manifest.json", manifest)
    return manifest


def aggregate(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["method"] + " / " + row["configuration_id"]].append(row)
    result = {}
    for group, values in sorted(groups.items()):
        keys = (
            "primary_documents",
            "contributions",
            "complementary_documents",
            "short_primary",
            "long_primary",
            "excerpted_sources",
            "identical_primary_repeats",
            "suppressed_repetitions",
            "excluded_budget",
            "questionnaires",
            "questions",
            "occupancy",
            "tokens",
            "metadata_reference_tokens",
            "expansion_tokens",
            "seconds",
        )
        result[group] = {
            "contexts": len(values),
            **{k: sum(v[k] for v in values) / len(values) for k in keys},
        }
    return result
