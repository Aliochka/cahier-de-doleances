"""Comparaison descriptive : chaque moteur exécuté une seule fois par requête."""

import math
import statistics
from datetime import datetime, timezone

from cahier_rag.evaluation.sampling import digest

METHODS = ("lexical", "vector", "hybrid")


def summarize(values):
    ordered = sorted(values)
    return {
        "median": statistics.median(ordered) if ordered else None,
        "p95": ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)] if ordered else None,
    }


def compare(engine, queries, *, limit=10, questionnaire_id=None, unit_type=None):
    if type(limit) is not int or not 1 <= limit <= engine.config.depth:
        raise ValueError("Limite positive inférieure à la profondeur requise.")
    chosen = [q for q in queries if q["split"] == "development"]
    if not chosen or len({q["query_id"] for q in chosen}) != len(chosen):
        raise ValueError("Requêtes de développement uniques requises.")
    rankings = {method: {} for method in METHODS}
    runs = {method: {} for method in METHODS}
    diagnostics, measurements, documents = {}, [], {}
    parents = {method: set() for method in METHODS}
    for query in chosen:
        qid = query["query_id"]
        retrieved = engine.retrieve(
            query["text"],
            split="development",
            questionnaire_id=questionnaire_id,
            unit_type=unit_type,
        )
        top = retrieved.rankings(limit)
        full = retrieved.rankings(engine.config.depth)
        measure = dict(retrieved.measurements, query_id=qid)
        measure["methods"] = {}
        for method in METHODS:
            rankings[method][qid] = top[method]
            runs[method][qid] = full[method]
            results = getattr(retrieved, method)
            selected = results[:limit]
            contributions = {(r.document.corpus_id, r.document.contribution_id) for r in selected}
            parents[method].update(contributions)
            for result in results:
                unit = result.document
                documents[unit.document_id] = {
                    key: unit.to_dict()[key]
                    for key in (
                        "document_id",
                        "corpus_id",
                        "content_hash",
                        "answer_id",
                        "contribution_id",
                        "question_id",
                        "questionnaire_id",
                        "unit_type",
                    )
                }
                documents[unit.document_id]["length"] = len(unit.text)
            measure["methods"][method] = {
                "results": len(selected),
                "candidates": len(results),
                "contributions": len(contributions),
                "short_lt60": sum(len(r.document.text) < 60 for r in selected),
                "other_text": sum(r.document.unit_type.value == "other_text" for r in selected),
            }
        hybrid_top = top["hybrid"]
        measure["hybrid_origins"] = {
            kind: sum(
                ("lexical" in retrieved.traces[did], "vector" in retrieved.traces[did]) == flags
                for did in hybrid_top
            )
            for kind, flags in (
                ("common", (True, True)),
                ("lexical_only", (True, False)),
                ("vector_only", (False, True)),
            )
        }
        diagnostics[qid] = retrieved.traces
        measurements.append(measure)
    report = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "configuration": engine.config.to_dict(),
        "sample_hash": engine.scope.sample_hash,
        "split": "development",
        "queries_hash": digest(chosen),
        "limit": limit,
        "filters": {
            "questionnaire_id": str(questionnaire_id) if questionnaire_id else None,
            "unit_type": unit_type,
        },
        "measurements": measurements,
        "latency_ms": {
            name: summarize([m[name] for m in measurements])
            for name in ("lexical_ms", "vector_ms", "fusion_ms", "total_ms")
        },
        "methods": {
            method: {
                "queries_with_results": sum(
                    bool(m["methods"][method]["results"]) for m in measurements
                ),
                "unique_contributions": len(parents[method]),
                "results": sum(m["methods"][method]["results"] for m in measurements),
            }
            for method in METHODS
        },
        "rankings_hash": digest(rankings),
        "runs_hash": digest(runs),
        "diagnostics_hash": digest(diagnostics),
        "documents_hash": digest(documents),
        "quality_metrics": None,
    }
    return {
        "rankings": rankings,
        "runs": runs,
        "diagnostics": diagnostics,
        "documents": documents,
        "report": report,
    }
