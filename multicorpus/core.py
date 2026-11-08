"""Document-level global branches and a single RRF, independent of H1."""

import math
import threading
import time
from fractions import Fraction

from cahier_rag.embeddings.core import EmbeddingInput
from cahier_rag.search.service.control import Budget, SearchBusy

VERSION = "multicorpus-lab-1"


def score_expression(terms, weights, params, text_field, metadata_field=None):
    coverage, counts = [], []
    for i, (term, weight) in enumerate(zip(terms, weights, strict=True)):
        # Terms were quoted by PostgreSQL, never interpolated into SQL.
        params[f"t{i}"], params[f"w{i}"] = term, weight
        match = f"{text_field} @@ CAST(:t{i} AS tsquery)"
        if metadata_field:
            match = f"({match} OR {metadata_field} @@ CAST(:t{i} AS tsquery))"
        coverage.append(f"CASE WHEN {match} THEN CAST(:w{i} AS float8) ELSE 0. END")
        counts.append(f"CASE WHEN {match} THEN 1. ELSE 0. END")
    params.update(total_weight=sum(weights), term_count=len(terms), query=" | ".join(terms))
    frequency = f"ts_rank({text_field},CAST(:query AS tsquery),32)::float8"
    if metadata_field:
        frequency = (
            f"(.75*{frequency}+.25*ts_rank({metadata_field},CAST(:query AS tsquery),32)::float8)"
        )
    return f".5*({' + '.join(coverage)})/:total_weight+.3*({' + '.join(counts)})/:term_count+.2*{frequency}"


def merge(batches, depth):
    rows = sorted(
        (dict(row) for batch in batches for row in batch), key=lambda r: (-r["score"], r["key"])
    )[:depth]
    if len({r["key"] for r in rows}) != len(rows):
        raise ValueError("Adapter returned duplicate documentary identities")
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def rrf(left, right, limit=50):
    lex, vec = ({r["key"]: r for r in rows} for rows in (left, right))
    scores = {
        key: sum(
            (Fraction(1, 60 + rows[key]["rank"]) for rows in (lex, vec) if key in rows), Fraction()
        )
        for key in lex.keys() | vec.keys()
    }
    out = []
    for key in sorted(scores, key=lambda k: (-scores[k], k))[:limit]:
        a, b = lex.get(key), vec.get(key)
        winner = a if a and (not b or a["rank"] <= b["rank"]) else b
        out.append(
            dict(
                key=key,
                corpus=winner["corpus"],
                document_id=winner["document_id"],
                lexical=a,
                vector=b,
                witness=winner,
                score=float(scores[key]),
                witness_origin="both"
                if a
                and b
                and a["unit_id"] == b["unit_id"]
                and a.get("segment_index") == b.get("segment_index")
                else winner["branch"],
            )
        )
    return out


class MultiSearch:
    def __init__(self, adapters, encoder, *, h1=None):
        self.adapters = {a.corpus: a for a in adapters}
        self.encoder, self.h1 = encoder, h1
        self.lock = threading.Lock()
        self.last_sql = {}

    def search(
        self,
        query,
        *,
        corpus="tous",
        mode="hybrid",
        depth=50,
        question=None,
        volume=None,
        estate=None,
        place=None,
        budget=None,
    ):
        if corpus not in {"2019", "1789", "tous"} or mode not in {
            "lexical",
            "vector",
            "hybrid",
            "compare",
        }:
            raise ValueError("Unknown corpus or search mode")
        if type(depth) is not int or depth not in {50, 100, 200}:
            raise ValueError("Depth must be 50, 100 or 200")
        query = query.strip()
        if not query or len(query) > 512 or not any(c.isalnum() for c in query):
            raise ValueError("Significant query required, maximum 512 characters")
        selected = sorted(self.adapters) if corpus == "tous" else [corpus]
        if any(k not in self.adapters for k in selected):
            raise ValueError("Selected corpus unavailable; no silent fallback")
        if question is not None and (
            corpus != "2019" or type(question) is not int or not 0 < question < 2**63
        ):
            raise ValueError("Question filter requires 2019 alone and a positive ID")
        if any(v is not None for v in (volume, estate, place)) and corpus != "1789":
            raise ValueError("Historical filters require 1789 alone")
        if volume is not None and (type(volume) is not int or volume not in range(1, 7)):
            raise ValueError("Volume must be 1–6")
        if estate not in {None, "clergé", "noblesse", "tiers état"}:
            raise ValueError("Unknown historical order")
        if place is not None and (not place.strip() or len(place) > 150):
            raise ValueError("Invalid place")
        if not self.lock.acquire(blocking=False):
            raise SearchBusy("Laboratory busy; retry when current query finishes")
        try:
            budget = budget if budget is not None else Budget(18)
            with budget.monitor():
                return self._search(
                    query,
                    selected,
                    mode,
                    depth,
                    dict(question=question, volume=volume, estate=estate, place=place),
                    budget,
                )
        finally:
            self.lock.release()

    def _search(self, query, selected, mode, depth, filters, budget):
        started = time.perf_counter()
        timings, diagnostics, identities = {}, {}, {}
        self.last_timings = timings
        adapters = [self.adapters[k] for k in selected]
        begin = time.perf_counter()
        with budget.phase("validation"):
            for a in adapters:
                identities[a.corpus] = a.identity(budget)
        timings["validation"] = time.perf_counter() - begin
        vector, left, right = None, [], []
        if mode != "lexical":
            begin = time.perf_counter()
            with budget.phase("encoding", 3):
                vector = next(
                    self.encoder.encode_queries([EmbeddingInput("query", query, VERSION)])
                ).vectors[0]
            timings["encoding"] = time.perf_counter() - begin
        else:
            timings["encoding"] = 0.0
        self.last_sql = {}
        with budget.phase("sql", 10):
            # One parser and one statistical population across the selected stores.
            terms, quoted = adapters[0].parse(query, budget)
            if len(terms) > 32:
                raise ValueError("Maximum 32 significant lexemes")
            begin = time.perf_counter()
            weights, population, frequencies = [], 0, dict.fromkeys(terms, 0)
            for a in adapters:
                n, df = a.statistics(terms, budget)
                population += n
                for t in terms:
                    frequencies[t] += df.get(t, 0)
            for t in terms:
                df = frequencies[t]
                if not 0 <= df <= population:
                    raise ValueError("Incompatible lexical statistics")
                weights.append(math.log(1 + (population - df + 0.5) / (df + 0.5)))
            timings["statistics"] = time.perf_counter() - begin
            for a in adapters:
                a.last_sql = {}
                if mode != "vector" and terms:
                    begin = time.perf_counter()
                    rows, trace = a.lexical(quoted, weights, depth, filters, budget)
                    timings[f"lexical_{a.corpus}"] = time.perf_counter() - begin
                    diagnostics[f"lexical_{a.corpus}"] = trace
                    left.append(rows)
                if vector is not None:
                    begin = time.perf_counter()
                    rows, trace = a.vector(vector, depth, filters, budget)
                    timings[f"vector_{a.corpus}"] = time.perf_counter() - begin
                    diagnostics[f"vector_{a.corpus}"] = trace
                    right.append(rows)
                self.last_sql.update({f"{a.corpus}_{k}": v for k, v in a.last_sql.items()})
        begin = time.perf_counter()
        left, right = merge(left, depth), merge(right, depth)
        timings["global_sort"] = time.perf_counter() - begin
        begin = time.perf_counter()
        ranked = rrf(left, right, 50)
        if mode in {"lexical", "vector"}:
            branch = left if mode == "lexical" else right
            ranked = [
                dict(
                    key=r["key"],
                    corpus=r["corpus"],
                    document_id=r["document_id"],
                    lexical=r if mode == "lexical" else None,
                    vector=r if mode == "vector" else None,
                    witness=r,
                    witness_origin=mode,
                    score=None,
                )
                for r in branch[:50]
            ]
        timings["fusion"] = time.perf_counter() - begin
        begin = time.perf_counter()
        with budget.phase("hydration", 2):
            items = {}
            for a in adapters:
                if hasattr(a, "label_candidates"):
                    a.label_candidates([r for r in left + right if r["corpus"] == a.corpus], budget)
                requested = [r for r in ranked if r["corpus"] == a.corpus]
                items.update(a.hydrate(requested, budget, " | ".join(quoted) if quoted else None))
            output = [dict(r, **items[r["key"]], rank=i) for i, r in enumerate(ranked, 1)]
            for a in adapters:
                if a.identity(budget) != identities[a.corpus]:
                    raise ValueError("Corpus identity changed during query")
        timings["hydration"] = time.perf_counter() - begin
        timings["total"] = time.perf_counter() - started
        budget.check()
        return dict(
            query=query,
            corpus=selected,
            mode=mode,
            depth=depth,
            limit=50,
            items=output,
            lexical=left,
            vector=right,
            timings=timings,
            diagnostics=diagnostics,
            statistics=dict(population=population, frequencies=frequencies),
            publication=identities,
            recipe=VERSION,
            laboratory_only=True,
            exhaustive=False,
        )
