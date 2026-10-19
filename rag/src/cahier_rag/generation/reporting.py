"""Contrôles déterministes seulement ; grille qualitative laissée sans notes."""

import json

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.generation.cache import Cache
from cahier_rag.generation.contracts import parse_output, resolve_prompt
from cahier_rag.generation.planning import iter_inputs, load_plan

CRITERIA = [
    "Réponse à l’intention",
    "Fidélité aux sources",
    "Exactitude des attributions",
    "Qualité de synthèse",
    "Présentation des désaccords",
    "Absence de généralisation abusive",
    "Lisibilité",
]


def report(directory, root=None):
    plan = load_plan(directory, root)
    key = digest({"version": 1, "plan_hash": plan["plan_hash"], "backend": plan["backend"]})
    cache = Cache(directory.parent / "generation.sqlite3", readonly=True)
    rows = []
    exports = []
    inspection = []
    try:
        for item, entry in iter_inputs(directory, plan):
            value = cache.get(key, item.input_hash)
            if value is None:
                continue
            if (
                value["status"] == "valid"
                and parse_output(value["raw_output"], item) != value["output"]
            ):
                raise ValueError("Sortie structurée incompatible.")
            parsed = value["output"]
            cited = {r for b in parsed["blocks"] for r in b["references"]} if parsed else set()
            quotes = [q for b in parsed["blocks"] for q in b["quotes"]] if parsed else []
            allrefs = []
            if value["raw_output"]:
                try:
                    raw = json.loads(value["raw_output"])
                    allrefs = [
                        r
                        for b in raw.get("blocks", [])
                        for r in b.get("references", [])
                        if isinstance(r, str)
                    ]
                except (ValueError, AttributeError, TypeError):
                    pass
            known = set(item.document["citation_map"])
            rows.append(
                {
                    "query_id": item.query_id,
                    "status": value["status"],
                    "error": value["validation_error"],
                    "prompt_tokens": value["prompt_tokens"],
                    "compact_tokens": entry["compact_tokens"],
                    "output_tokens": value["output_tokens"],
                    "seconds": value["seconds"],
                    "finish_reason": value["finish_reason"],
                    "references": len(allrefs),
                    "resolved_references": sum(r in known for r in allrefs),
                    "unique_sources_cited": len(cited),
                    "exact_quotes": len(quotes),
                    "insufficient_sources": parsed["insufficient_sources"] if parsed else None,
                    "incomplete_sources_in_context": sum(
                        s["incomplete"] for s in item.document["sources"]
                    ),
                    "incomplete_sources_cited": sum(
                        s["incomplete"] for s in item.document["sources"] if s["reference"] in cited
                    ),
                }
            )
            exports.append(
                {
                    "query_id": item.query_id,
                    "result": value,
                    "citation_map": item.document["citation_map"],
                    "audit": {
                        "plan_hash": plan["plan_hash"],
                        "recipe_hash": key,
                        "input_hash": item.input_hash,
                        "prompt_hash": entry["prompt_hash"],
                        "model": plan["backend"]["model"],
                        "version": plan["backend"]["version"],
                        "validation_scope": "structure/references/exact quotes, not semantic support",
                    },
                }
            )
            inspection.append(
                {
                    "query_id": item.query_id,
                    "evaluator": None,
                    "criteria": {c: None for c in CRITERIA},
                    "comments": None,
                }
            )
    finally:
        cache.close()
    valid = sum(r["status"] == "valid" for r in rows)
    resolved = sum(r["resolved_references"] for r in rows)
    references = sum(r["references"] for r in rows)
    summary = {
        "version": plan["backend"]["version"],
        "plan_hash": plan["plan_hash"],
        "generations": len(rows),
        "valid": valid,
        "valid_fraction": valid / len(rows) if rows else None,
        "references": references,
        "resolved_references": resolved,
        "resolved_reference_fraction": resolved / references if references else None,
        "exact_quotes": sum(r["exact_quotes"] for r in rows),
        "insufficient_responses": sum(r["insufficient_sources"] is True for r in rows),
        "responses_using_incomplete_sources": sum(r["incomplete_sources_cited"] > 0 for r in rows),
        "prompt_tokens_total": sum(r["prompt_tokens"] for r in rows),
        "output_tokens_total": sum(r["output_tokens"] for r in rows),
        "generation_seconds_total": sum(r["seconds"] for r in rows),
        "rows": rows,
        "semantic_verification": False,
        "qualitative_scores_assigned": False,
    }
    # Nouveau rapport adressé par contenu ; aucun export historique remplacé.
    output = directory.parent / "reports" / digest(summary)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("summary", summary),
        ("answers", exports),
        ("inspection-template", inspection),
    ):
        path = output / (name + ".json")
        if path.exists():
            if json.loads(path.read_text()) != value:
                raise ValueError("Export existant incompatible.")
        else:
            atomic_json(path, value)
    prompt_file = output / (plan["backend"]["version"] + ".txt")
    if not prompt_file.exists():
        prompt_file.write_text(resolve_prompt(plan["backend"]["version"]), encoding="utf-8")
    return {
        "report_directory": str(output),
        "generations": len(rows),
        "valid": valid,
        "references_resolved": resolved,
        "references": references,
    }
