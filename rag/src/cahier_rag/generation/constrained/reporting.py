"""Comparaison descriptive v2/v3, sans nouvelle évaluation sémantique."""

import json
import math
import re
from collections import Counter

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.generation.cache import Cache as BaselineCache
from cahier_rag.generation.constrained.cache import Cache
from cahier_rag.generation.constrained.planning import iter_inputs, load_plan
from cahier_rag.generation.contracts import parse_output


def describe(record, item):
    raw = record["raw_output"]
    try:
        value = json.loads(raw)
        parseable = True
    except (ValueError, TypeError):
        value = {}
        parseable = False
    blocks = value.get("blocks", []) if isinstance(value, dict) else []
    blocks = [b for b in blocks if isinstance(b, dict)] if isinstance(blocks, list) else []
    refs = [r for b in blocks for r in b.get("references", []) if isinstance(r, str)]
    known = item.document["citation_map"]
    used = set(refs) & set(known)
    texts = [b["text"] for b in blocks if isinstance(b.get("text"), str)]
    word_count = sum(len(re.findall(r"\b\w+\b", t)) for t in texts)
    duplicates = sum(
        len(b.get("references", [])) - len(set(b.get("references", [])))
        for b in blocks
        if isinstance(b.get("references"), list)
        and all(isinstance(r, str) for r in b["references"])
    )
    fields = {"kind", "text", "references", "quotes"}
    if record["status"] == "valid" and parse_output(raw, item) != record["output"]:
        raise ValueError("Sortie validée différente du texte brut.")
    return {
        "query_id": record["query_id"],
        "status": record["status"],
        "error": record["validation_error"],
        "json_parseable": parseable,
        "blocks": len(blocks),
        "blocks_with_exact_fields": sum(set(b) == fields for b in blocks),
        "references": len(refs),
        "known_references": sum(r in known for r in refs),
        "unknown_references": sum(r not in known for r in refs),
        "duplicate_references_in_blocks": duplicates,
        "unique_sources": len(used),
        "unique_contributions": len(
            {
                (
                    known[r]["source"]["metadata"]["corpus_id"],
                    known[r]["source"]["metadata"]["contribution_id"],
                )
                for r in used
            }
        ),
        "words_in_blocks": word_count,
        "output_tokens": record["output_tokens"],
        "prompt_tokens": record["prompt_tokens"],
        "seconds": record["seconds"],
        "phases": record.get("phases", {}),
        "validation_seconds": record.get("validation_seconds"),
        "insufficient_declared": value.get("insufficient_sources")
        if isinstance(value, dict)
        else None,
        "finish_reason": record["finish_reason"],
        "used_references": sorted(used),
        "texts": texts,
    }


def distribution(values):
    values = sorted(values)
    if not values:
        return {"n": 0, "median": None, "p95": None}
    n = len(values)
    return {
        "n": n,
        "median": (values[n // 2] + values[(n - 1) // 2]) / 2,
        "p95": values[math.ceil(n * 0.95) - 1],
        "min": min(values),
        "max": max(values),
        "sum": sum(values),
    }


def aggregate(rows):
    return {
        "generations": len(rows),
        "json_parseable": sum(r["json_parseable"] for r in rows),
        "accepted": sum(r["status"] == "valid" for r in rows),
        "errors": dict(Counter(r["error"] for r in rows if r["error"])),
        **{
            k: sum(r[k] for r in rows)
            for k in (
                "references",
                "known_references",
                "unknown_references",
                "duplicate_references_in_blocks",
                "blocks",
                "blocks_with_exact_fields",
                "output_tokens",
                "words_in_blocks",
            )
        },
        "sources_per_response": distribution([r["unique_sources"] for r in rows]),
        "contributions_per_response": distribution([r["unique_contributions"] for r in rows]),
        "latency_seconds": distribution([r["seconds"] for r in rows]),
        "insufficient_declared": sum(r["insufficient_declared"] is True for r in rows),
    }


def report(root, directory):
    plan = load_plan(directory, root)
    old = json.loads((root / "evaluation/local/rag022/v2/plan/manifest.json").read_text())
    keys = {
        name: digest({"version": 1, "plan_hash": p["plan_hash"], "backend": p["backend"]})
        for name, p in [("v2", old), ("v3", plan)]
    }
    before = BaselineCache(root / "evaluation/local/rag022/v2/generation.sqlite3", readonly=True)
    after = Cache(directory.parent / "generation.sqlite3", readonly=True)
    rows = {"v2": [], "v3": []}
    exports = []
    differences = []
    try:
        for item, _ in iter_inputs(directory, plan):
            a = before.get(keys["v2"], item.input_hash)
            b = after.get(keys["v3"], item.input_hash)
            if a is None:
                raise ValueError("Référence v2 manquante.")
            if b is None:
                continue
            x, y = describe(a, item), describe(b, item)
            rows["v2"].append(x)
            rows["v3"].append(y)
            differences.append(
                {
                    "query_id": item.query_id,
                    "same_raw": a["raw_output"] == b["raw_output"],
                    "same_block_texts": x["texts"] == y["texts"]
                    if x["json_parseable"] and y["json_parseable"]
                    else None,
                    "sources_added": sorted(set(y["used_references"]) - set(x["used_references"])),
                    "sources_removed": sorted(
                        set(x["used_references"]) - set(y["used_references"])
                    ),
                    "delta_words": y["words_in_blocks"] - x["words_in_blocks"],
                    "delta_tokens": y["output_tokens"] - x["output_tokens"],
                    "delta_seconds": y["seconds"] - x["seconds"],
                    "status_before": a["status"],
                    "status_after": b["status"],
                }
            )
            exports.append(
                {
                    "query_id": item.query_id,
                    "result": b,
                    "citation_map": item.document["citation_map"],
                    "audit": {
                        "plan_hash": plan["plan_hash"],
                        "recipe_hash": keys["v3"],
                        "input_hash": item.input_hash,
                        "semantic_verification": False,
                    },
                }
            )
    finally:
        before.close()
        after.close()
    # No citizen text in the statistical summary; detailed exports remain private.
    for values in rows.values():
        for r in values:
            r.pop("texts")
    result = {
        "version": 1,
        "plan_hash": plan["plan_hash"],
        "baseline_plan": old["plan_hash"],
        "prompt_changed": False,
        "summary": {k: aggregate(v) for k, v in rows.items()},
        "per_query": rows,
        "differences": differences,
        "semantic_evaluation": False,
        "new_judge": False,
    }
    output = directory.parent / "reports" / digest(result)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in [("comparison", result), ("answers", exports)]:
        path = output / (name + ".json")
        if path.exists():
            if json.loads(path.read_text()) != value:
                raise ValueError("Rapport existant incompatible.")
        else:
            atomic_json(path, value)
    return {
        "report_directory": str(output),
        "generations": len(rows["v3"]),
        "valid": result["summary"]["v3"]["accepted"],
    }
