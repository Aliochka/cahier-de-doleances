"""RAG-024 : copie d'audit locale, déterministe et en lecture seule des expériences."""

import argparse
import json
from pathlib import Path

from cahier_rag.annotation.session import atomic_json
from cahier_rag.context.contracts import ContextSource
from cahier_rag.context.repository import ContextRepository
from cahier_rag.contracts import canonical_json
from cahier_rag.embeddings.snapshots import sha256_file
from cahier_rag.evaluation.sampling import digest
from cahier_rag.generation.cache import Cache as BaselineCache
from cahier_rag.generation.constrained.cache import Cache
from cahier_rag.generation.constrained.planning import load_plan as load_constrained
from cahier_rag.generation.contracts import compact, parse_output
from cahier_rag.generation.planning import iter_inputs, load_plan
from cahier_rag.search.lexical import CorpusScope

STATUSES = ("Étayé", "Partiel", "Non étayé", "Contredit", "Incertain")


def inspect_blocks(output):
    """Indices de lecture, pas des jugements sémantiques automatiques."""
    return [
        {
            "block": i,
            "characters": len(b["text"]),
            "at_600": len(b["text"]) == 600,
            "tail": b["text"][-100:],
            "references": b["references"],
        }
        for i, b in enumerate(output["blocks"], 1)
    ]


def check_source(mapping, unit):
    source = mapping["source"]
    meta, tech = source["metadata"], source["technical"]
    span = tech["excerpt"]
    expected = ContextSource(
        unit,
        tech["sample_hash"],
        span["start"],
        span["end"],
        tech["retrieval"]["method"],
        tech["retrieval"]["rank"],
        tech["role"],
        tech["parent_document_id"],
    ).to_dict()
    actual = dict(source)
    actual["technical"] = {k: v for k, v in tech.items() if k != "observed_repetitions"}
    if actual != expected or mapping["context_reference"] != source["reference"]:
        raise ValueError("Texte, positions, identifiants ou référence incohérents.")
    for name in ("answer_id", "question_id", "questionnaire_id", "contribution_id"):
        if meta[name] != str(getattr(unit, name)):
            raise ValueError("Identifiant source modifié.")


def extract(root):
    root = root.resolve()
    baseline = root / "evaluation/local/rag022/v2/plan"
    constrained = root / "evaluation/local/rag023/guarded/plan"
    plans = {"v2": load_plan(baseline, root), "v3": load_constrained(constrained, root)}
    if (baseline / "inputs.jsonl").read_bytes() != (constrained / "inputs.jsonl").read_bytes():
        raise ValueError("Les entrées des deux recettes diffèrent.")
    corpus = root / "evaluation/local/rag007/corpus.json"
    scope = CorpusScope(json.loads(corpus.read_text()))
    repository = ContextRepository(root / "evaluation/local/rag018/bm25-A.sqlite3", scope)
    queries = {q["query_id"]: q for q in json.loads((root / "evaluation/queries.json").read_text())}
    inputs = list(iter_inputs(constrained, plans["v3"]))
    wanted = {item.document["context_hash"] for item, _ in inputs}
    contexts_path = root / "evaluation/local/rag021/development/contexts.jsonl"
    contexts = {}
    with contexts_path.open() as stream:
        for line in stream:
            record = json.loads(line)
            context = record["context"]
            if context["context_hash"] in wanted:
                contexts[context["context_hash"]] = context
    caches = {
        "v2": BaselineCache(baseline.parent / "generation.sqlite3", readonly=True),
        "v3": Cache(constrained.parent / "generation.sqlite3", readonly=True),
    }
    rows = []
    try:
        for item, _ in inputs:
            q = queries[item.query_id]
            if q["split"] != "development" or q["text"] != item.query:
                raise ValueError("Requête extérieure au développement.")
            context = contexts[item.document["context_hash"]]
            if compact(context) != item.document:
                raise ValueError("Présentation compacte différente du contexte gelé.")
            mapping = item.document["citation_map"]
            docs = repository.fetch(
                [s["source"]["metadata"]["document_id"] for s in mapping.values()]
            )
            for source in mapping.values():
                check_source(source, docs[source["source"]["metadata"]["document_id"]])
            versions = {}
            for version, cache in caches.items():
                p = plans[version]
                key = digest({"version": 1, "plan_hash": p["plan_hash"], "backend": p["backend"]})
                result = cache.get(key, item.input_hash)
                if result is None:
                    raise ValueError("Génération manquante.")
                if result["status"] == "valid":
                    if parse_output(result["raw_output"], item) != result["output"]:
                        raise ValueError("Sortie différente de son texte brut.")
                versions[version] = result
            if versions["v3"]["status"] != "valid":
                raise ValueError("Campagne contrainte incomplète.")
            rows.append(
                {
                    "query_id": item.query_id,
                    "query": item.query,
                    "common_valid": versions["v2"]["status"] == "valid",
                    "input_hash": item.input_hash,
                    "document": item.document,
                    "versions": versions,
                    "v3_blocks": inspect_blocks(versions["v3"]["output"]),
                }
            )
    finally:
        for cache in caches.values():
            cache.close()
    paths = [
        baseline / "manifest.json",
        baseline / "inputs.jsonl",
        baseline.parent / "generation.sqlite3",
        constrained / "manifest.json",
        constrained / "inputs.jsonl",
        constrained / "schemas.json",
        constrained.parent / "generation.sqlite3",
        contexts_path,
        corpus,
        root / "evaluation/queries.json",
        repository.documents.path,
        Path(__file__),
    ]
    return {
        "version": "fidelity-audit-extraction-v1",
        "review_origin": "codex_assisted_targeted_reading_not_independent_human_validation",
        "statuses": list(STATUSES),
        "inputs": {str(p.relative_to(root)): sha256_file(p) for p in paths},
        "plans": {k: p["plan_hash"] for k, p in plans.items()},
        "rows": rows,
        "counts": {
            "queries": len(rows),
            "common_valid": sum(r["common_valid"] for r in rows),
            "sources": sum(len(r["document"]["sources"]) for r in rows),
            "v3_blocks_at_600": sum(b["at_600"] for r in rows for b in r["v3_blocks"]),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output", type=Path, default=Path("evaluation/local/rag024/extraction.json")
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    allowed = root / "evaluation/local/rag024"
    if not output.is_relative_to(allowed) or output.suffix != ".json":
        raise ValueError("Sortie locale rag024/*.json uniquement.")
    value = extract(root)
    if output.exists():
        if output.read_text() != canonical_json(value):
            # atomic_json termine le document par un saut de ligne.
            if json.loads(output.read_text()) != value:
                raise ValueError("Extraction existante différente, fichier préservé.")
    else:
        atomic_json(output, value)
    print(canonical_json({"counts": value["counts"], "sha256": sha256_file(output)}))


if __name__ == "__main__":
    main()
