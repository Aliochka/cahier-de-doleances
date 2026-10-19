"""RRF multi-source à fractions exactes, filtres vérifiés et récupération partagée."""

import math
import time
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType

from cahier_rag.contracts import UnitType, validate_id
from cahier_rag.search.lexical import SearchResult

CONFIGURATIONS = MappingProxyType(
    {
        "H1": (("lexical", "1"), ("vector", "1")),
        "H2": (("bm25-A", "1"), ("vector", "1")),
        "H3": (("bm25-B", "1"), ("vector", "1")),
        "H4": (("lexical", "1"), ("bm25-A", "1"), ("vector", "1")),
        "H5": (("lexical", "1/4"), ("bm25-A", "1/4"), ("vector", "1/2")),
    }
)


def configuration():
    return {
        "version": 1,
        "k": 60,
        "depth": 50,
        "rank_base": 1,
        "formula": "sum(weight_m/(k+rank_m))",
        "tie_break": "document_id binary",
        "configurations": {name: dict(weights) for name, weights in CONFIGURATIONS.items()},
    }


def validated_weights(weights):
    if not weights or any(not isinstance(k, str) or not k for k in weights):
        raise ValueError("Sources nommées et poids positifs requis.")
    try:
        result = {k: Fraction(str(v)) for k, v in weights.items()}
    except (ValueError, ZeroDivisionError):
        raise ValueError("Poids rationnels strictement positifs requis.") from None
    if any(v <= 0 for v in result.values()):
        raise ValueError("Poids rationnels strictement positifs requis.")
    return result


def fuse(rankings, weights, *, k=60):
    if type(k) is not int or not 1 <= k <= 10000:
        raise ValueError("k entier positif requis.")
    weights = validated_weights(weights)
    if set(rankings) != set(weights):
        raise ValueError("Sources et poids différents.")
    scores, documents, traces = {}, {}, {}
    for source, results in sorted(rankings.items()):
        seen = set()
        for rank, result in enumerate(results, 1):
            did = result.document.document_id
            if not math.isfinite(result.score):
                raise ValueError("Score source non fini.")
            if did in documents and documents[did].content_hash != result.document.content_hash:
                raise ValueError("Contenu incompatible pour un même document.")
            if did in seen:
                continue
            seen.add(did)
            documents[did] = result.document
            contribution = weights[source] / (k + rank)
            scores[did] = scores.get(did, Fraction()) + contribution
            traces.setdefault(did, {})[source] = {
                "rank": rank,
                "score": result.score,
                "weight": str(weights[source]),
                "rrf_contribution": float(contribution),
                "rrf_fraction": str(contribution),
            }
    ids = sorted(scores, key=lambda d: (-scores[d], d))
    for rank, did in enumerate(ids, 1):
        traces[did]["rrf"] = {
            "rank": rank,
            "score": float(scores[did]),
            "fraction": str(scores[did]),
        }
    return tuple(SearchResult(documents[d], float(scores[d])) for d in ids), traces


@dataclass(frozen=True)
class Retrieval:
    sources: dict
    hybrids: dict
    traces: dict
    measurements: dict


class MultiHybridEngine:
    """Sources = fonctions search(query, limit, split, questionnaire_id, unit_type)."""

    def __init__(self, sources, scope, *, profiles=CONFIGURATIONS, k=60, depth=50):
        if (
            type(k) is not int
            or not 1 <= k <= 10000
            or type(depth) is not int
            or not 1 <= depth <= 100
        ):
            raise ValueError("k positif et profondeur 1–100 requis.")
        if not profiles:
            raise ValueError("Au moins une configuration requise.")
        self.profiles = {
            name: validated_weights(dict(weights)) for name, weights in profiles.items()
        }
        needed = {m for weights in self.profiles.values() for m in weights}
        if not needed <= set(sources):
            raise ValueError("Source de classement absente.")
        self.sources = {m: sources[m] for m in sorted(needed)}
        self.scope, self.k, self.depth = scope, k, depth

    def retrieve(
        self, query, *, split="development", questionnaire_id=None, unit_type=None, limit=50
    ):
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ValueError("Requête de 1 à 1000 caractères requise.")
        if (
            split not in {"development", "evaluation"}
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise ValueError("Partition et limite 1–100 requises.")
        if questionnaire_id is not None:
            validate_id(questionnaire_id, "questionnaire_id")
        if unit_type is not None:
            unit_type = UnitType(unit_type)
        filters = dict(
            split=split, questionnaire_id=questionnaire_id, unit_type=unit_type, limit=self.depth
        )
        selected, times, validations = {}, {}, {}
        started = time.perf_counter()
        for name, search in self.sources.items():
            before = time.perf_counter()
            results = tuple(search(query, **filters))
            after = time.perf_counter()
            if len(results) > self.depth:
                raise ValueError("Source ne respectant pas la profondeur.")
            for result in results:
                doc = result.document
                expected = self.scope.documents.get(doc.document_id)
                if (
                    not expected
                    or expected["content_hash"] != doc.content_hash
                    or expected["split"] != split
                    or (questionnaire_id is not None and doc.questionnaire_id != questionnaire_id)
                    or (unit_type is not None and doc.unit_type != unit_type)
                ):
                    raise ValueError("Résultat hors corpus, filtre ou partition.")
            validations[name] = 1000 * (time.perf_counter() - after)
            times[name] = 1000 * (after - before)
            selected[name] = results
        hybrids, traces, fusions, attributable = {}, {}, {}, {}
        for name, weights in self.profiles.items():
            before = time.perf_counter()
            results, trace = fuse({m: selected[m] for m in weights}, weights, k=self.k)
            fusions[name] = 1000 * (time.perf_counter() - before)
            hybrids[name], traces[name] = results[:limit], trace
            attributable[name] = sum(times[m] + validations[m] for m in weights) + fusions[name]
        return Retrieval(
            selected,
            hybrids,
            traces,
            {
                "sources_ms": times,
                "validation_ms": validations,
                "fusion_ms": fusions,
                "attributable_sequential_ms": attributable,
                "shared_session_ms": 1000 * (time.perf_counter() - started),
            },
        )

    def search(self, query, *, profile="H1", limit=10, **filters):
        if profile not in self.profiles:
            raise ValueError("Configuration hybride inconnue.")
        return list(self.retrieve(query, limit=limit, **filters).hybrids[profile])
