"""RRF non pondérée : rangs de base 1, fractions exactes et départage documentaire."""

import math
import time
from dataclasses import asdict, dataclass
from fractions import Fraction

from cahier_rag.contracts import UnitType, validate_id
from cahier_rag.search.flexible import Method
from cahier_rag.search.lexical import SearchResult, Strategy
from cahier_rag.search.preparation import Preparation


@dataclass(frozen=True)
class HybridConfig:
    k: int = 60
    depth: int = 50
    version: int = 1

    def __post_init__(self):
        if type(self.k) is not int or not 1 <= self.k <= 10000:
            raise ValueError("k entier entre 1 et 10000 requis.")
        if type(self.depth) is not int or not 1 <= self.depth <= 100:
            raise ValueError("Profondeur entre 1 et 100, plafond du moteur vectoriel.")
        if self.version != 1:
            raise ValueError("Version hybride inconnue.")

    def to_dict(self):
        return asdict(self) | {
            "formula": "sum(1/(k+rank))",
            "rank_base": 1,
            "weights": "equal",
            "tie_break": "document_id COLLATE C",
        }


def fuse(rankings, *, k=60):
    """Retourner SearchResult et traces ; un document compte une fois par moteur."""
    HybridConfig(k=k)
    scores, documents, traces = {}, {}, {}
    for method, results in sorted(rankings.items()):
        seen = set()
        for rank, result in enumerate(results, 1):
            did = result.document.document_id
            if not math.isfinite(result.score):
                raise ValueError("Score source non fini.")
            if did in documents and documents[did].content_hash != result.document.content_hash:
                raise ValueError("Contenu incompatible pour un identifiant documentaire commun.")
            if did in seen:
                continue
            seen.add(did)
            documents[did] = result.document
            scores[did] = scores.get(did, Fraction()) + Fraction(1, k + rank)
            traces.setdefault(did, {})[method] = {
                "rank": rank,
                "score": result.score,
                "rrf_contribution": float(Fraction(1, k + rank)),
            }
    ids = sorted(scores, key=lambda did: (-scores[did], did))
    for rank, did in enumerate(ids, 1):
        traces[did]["rrf"] = {"rank": rank, "score": float(scores[did])}
    return tuple(SearchResult(documents[did], float(scores[did])) for did in ids), traces


@dataclass(frozen=True)
class Retrieval:
    lexical: tuple
    vector: tuple
    hybrid: tuple
    traces: dict
    measurements: dict

    def rankings(self, limit):
        return {
            name: [r.document.document_id for r in getattr(self, name)[:limit]]
            for name in ("lexical", "vector", "hybrid")
        }


class HybridEngine:
    def __init__(self, lexical, vector, scope, config=HybridConfig()):
        self.lexical, self.vector, self.scope, self.config = lexical, vector, scope, config
        if (
            lexical.scope.sample_hash != scope.sample_hash
            or vector.store.scope.sample_hash != scope.sample_hash
        ):
            raise ValueError("Les moteurs ne partagent pas le même manifeste.")
        self.last_retrieval = None

    def retrieve(self, query, *, split="development", questionnaire_id=None, unit_type=None):
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ValueError("Requête de 1 à 1000 caractères requise.")
        if split not in {"development", "evaluation"}:
            raise ValueError("Partition explicite requise.")
        if questionnaire_id is not None:
            validate_id(questionnaire_id, "questionnaire_id")
        if unit_type is not None:
            unit_type = UnitType(unit_type)
        filters = dict(
            split=split,
            questionnaire_id=questionnaire_id,
            unit_type=unit_type,
            limit=self.config.depth,
        )
        start = time.perf_counter()
        lexical = tuple(
            self.lexical.search(
                query,
                method=Method.WEIGHTED,
                strategy=Strategy.ANSWER,
                preparation=Preparation(),
                **filters,
            )
        )
        lexical_end = time.perf_counter()
        vector = tuple(self.vector.search(query, **filters))
        vector_end = time.perf_counter()
        for results in (lexical, vector):
            if len(results) > self.config.depth:
                raise ValueError("Moteur ne respectant pas la profondeur demandée.")
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
                    raise ValueError(
                        "Résultat incompatible avec le corpus, les filtres ou la partition."
                    )
        fusion_start = time.perf_counter()
        fused, traces = fuse({"lexical": lexical, "vector": vector}, k=self.config.k)
        end = time.perf_counter()
        left = {r.document.document_id for r in lexical}
        right = {r.document.document_id for r in vector}
        measurements = {
            "lexical_ms": (lexical_end - start) * 1000,
            "vector_ms": (vector_end - lexical_end) * 1000,
            "validation_ms": (fusion_start - vector_end) * 1000,
            "fusion_ms": (end - fusion_start) * 1000,
            "total_ms": (end - start) * 1000,
            "common": len(left & right),
            "lexical_only": len(left - right),
            "vector_only": len(right - left),
            "union": len(left | right),
        }
        self.last_retrieval = Retrieval(
            lexical, vector, fused[: self.config.depth], traces, measurements
        )
        return self.last_retrieval

    def search(self, query, *, limit=10, **filters):
        if type(limit) is not int or not 1 <= limit <= self.config.depth:
            raise ValueError("Limite positive ne dépassant pas la profondeur requise.")
        return list(self.retrieve(query, **filters).hybrid[:limit])
