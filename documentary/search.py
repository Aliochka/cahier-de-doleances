"""Bounded historical laboratory: document branches, exact vector scan, one RRF."""

import math
import threading
import time
from fractions import Fraction

from sqlalchemy import text

from .artifacts import CORPUS, GENERATION
from .representations import ELIGIBLE, JOIN, LEXICAL_RECIPE, encoder, gate
from .storage import SCOPE


def group(rows, depth, *, vector=False):
    best = {}
    for row in rows:
        row = dict(row)
        key = row["document_id"]
        # A metadata-only lexical tie prefers the opening admissible unit.
        tie = (-row["score"], -int(row.get("text_match", False)), row["ordinal"], row["unit_id"])
        if key not in best or tie < best[key][0]:
            best[key] = tie, row
    selected = sorted(
        (pair[1] for pair in best.values()), key=lambda r: (-r["score"], r["document_id"])
    )[:depth]
    for rank, row in enumerate(selected, 1):
        row["rank"] = rank
        row["branch"] = "vector" if vector else "lexical"
    return selected


def fuse(lexical, vector, limit):
    left, right = {r["document_id"]: r for r in lexical}, {r["document_id"]: r for r in vector}
    scores = {
        key: sum(
            (Fraction(1, 60 + rows[key]["rank"]) for rows in (left, right) if key in rows),
            Fraction(),
        )
        for key in left.keys() | right.keys()
    }
    result = []
    for key in sorted(scores, key=lambda k: (-scores[k], k))[:limit]:
        lex, vec = left.get(key), right.get(key)
        # Same witness, otherwise strongest branch RRF contribution; lexical wins ties.
        winner = lex if lex and (not vec or lex["rank"] <= vec["rank"]) else vec
        result.append(
            {
                "document_id": key,
                "score": float(scores[key]),
                "lexical": lex,
                "vector": vec,
                "witness": winner,
                "witness_origin": "both"
                if lex and vec and lex["unit_id"] == vec["unit_id"]
                else winner["branch"],
            }
        )
    return result


FILTERS = """AND (:volume IS NULL OR (d.filter_metadata->>'volume')::int=:volume)
    AND (:estate IS NULL OR d.filter_metadata->'orders' ? :estate)
    AND (:place IS NULL OR strpos(lower(d.filter_metadata->>'place'),lower(:place))>0
        OR strpos(lower(d.display_title),lower(:place))>0)"""


class HistoricalSearch:
    def __init__(self, destination, *, encoder_threads=4):
        self.destination = destination
        self.threads = encoder_threads
        self.model = None
        self.lock = threading.Lock()

    def load_model(self, release):
        from cahier_rag.embeddings.registry import MODELS

        precision = release["embedding_recipe"].get("precision")
        if not release["representations_ready"] or precision not in {"float32", "bfloat16"}:
            raise ValueError("Vector representations unavailable")
        if (
            release["embedding_recipe"].get("version") != "historical-bge-1"
            or release["embedding_recipe"].get("model") != MODELS["bge-m3"].to_dict()
            or release["embedding_recipe"].get("input") != "exact technical passage only"
        ):
            raise ValueError("Historical vector recipe incompatible")
        if self.model is None:
            model = encoder(threads=self.threads, precision=precision)
            try:
                model.load()
            except Exception:
                model.close()
                raise
            self.model = model
        if self.model.backend.snapshot_hash != release["embedding_recipe"]["snapshot_hash"]:
            raise ValueError("Query model differs from stored representations")

    def close(self):
        if self.model:
            self.model.close()

    def search(self, query, *, mode="hybrid", depth=50, volume=None, estate=None, place=None):
        if mode not in {"lexical", "vector", "hybrid", "compare"} or depth not in {50, 100, 200}:
            raise ValueError("Choose lexical/vector/hybrid/compare and depth 50/100/200")
        query = query.strip()
        if not query or len(query) > 512 or not any(c.isalnum() for c in query):
            raise ValueError("Query must contain significant text, maximum 512 characters")
        if volume is not None and (type(volume) is not int or volume not in range(1, 7)):
            raise ValueError("Volume must be 1–6")
        if estate is not None and estate not in {"clergé", "noblesse", "tiers état", "tiers-état"}:
            raise ValueError("Unknown historical order")
        if estate == "tiers-état":
            estate = "tiers état"
        if place is not None and (not place.strip() or len(place) > 150):
            raise ValueError("Invalid place filter")
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("Laboratory busy; retry after the current request")
        try:
            return self._search(query, mode, depth, volume, estate, place)
        finally:
            self.lock.release()

    def _search(self, query, mode, depth, volume, estate, place):
        started = time.perf_counter()
        self.last_sql = {}
        timings = dict(
            encoding=0.0, lexical=0.0, vector=0.0, grouping=0.0, fusion=0.0, hydration=0.0
        )
        params = dict(
            SCOPE,
            volume=volume,
            estate=estate,
            place=place,
            place_pattern=f"%{place}%" if place else None,
        )
        left, right = [], []
        plans = {}
        with self.destination.transaction(readonly=True) as c:
            c.execute(text("SET LOCAL statement_timeout='15s'"))
            release = gate(c)
            if not release["statistics_ready"] or release["lexical_recipe"] != LEXICAL_RECIPE:
                raise ValueError("Lexical preparation unavailable or incompatible")
            if mode in {"vector", "hybrid", "compare"}:
                from cahier_rag.embeddings.core import EmbeddingInput

                begin = time.perf_counter()
                self.load_model(release)
                values = next(
                    self.model.encode_queries([EmbeddingInput("query", query, "laboratory")])
                ).vectors[0]
                params["vector"] = "[" + ",".join(str(v) for v in values) + "]"
                timings["encoding"] = time.perf_counter() - begin
            if mode in {"lexical", "hybrid", "compare"}:
                begin = time.perf_counter()
                terms = c.execute(
                    text("SELECT tsvector_to_array(to_tsvector('pg_catalog.french',:q))"),
                    {"q": query},
                ).scalar_one()
                if len(terms) > 32:
                    raise ValueError("Maximum 32 significant lexemes")
                if terms:
                    n = release["lexical_statistics"]["units"]
                    weights = []
                    cover, matched = [], []
                    quoted = (
                        c.execute(
                            text("SELECT quote_literal(t) FROM unnest(CAST(:terms AS text[])) t"),
                            {"terms": terms},
                        )
                        .scalars()
                        .all()
                    )
                    params["query"] = " | ".join(quoted)
                    for i, (term, literal) in enumerate(zip(terms, quoted, strict=True)):
                        df = (
                            c.execute(
                                text("""SELECT document_frequency FROM documentary.lexical_term_statistics
                            WHERE corpus_id=:corpus AND release_id=:release AND term=:term"""),
                                dict(SCOPE, term=term),
                            ).scalar_one_or_none()
                            or 0
                        )
                        weight = math.log(1 + (n - df + 0.5) / (df + 0.5))
                        params[f"t{i}"], params[f"w{i}"] = literal, weight
                        weights.append(weight)
                        match = f"(u.search_vector @@ CAST(:t{i} AS tsquery) OR d.metadata_vector @@ CAST(:t{i} AS tsquery))"
                        cover.append(f"CASE WHEN {match} THEN CAST(:w{i} AS float8) ELSE 0. END")
                        matched.append(f"CASE WHEN {match} THEN 1. ELSE 0. END")
                    params.update(total_weight=sum(weights), terms=len(terms))
                    score = f""".5*({" + ".join(cover)})/:total_weight + .3*({" + ".join(matched)})/:terms
                        + .2*(.75*ts_rank(u.search_vector,CAST(:query AS tsquery),32)
                        + .25*ts_rank(d.metadata_vector,CAST(:query AS tsquery),32))"""
                    sql = f"""SELECT u.document_id,u.unit_id,u.ordinal,u.start_offset,u.end_offset,
                        {score} AS score,u.search_vector @@ CAST(:query AS tsquery) AS text_match,
                        d.metadata_vector @@ CAST(:query AS tsquery) AS metadata_match
                        FROM {JOIN} WHERE {ELIGIBLE} {FILTERS}
                        AND (u.search_vector @@ CAST(:query AS tsquery) OR d.metadata_vector @@ CAST(:query AS tsquery))"""
                    self.last_sql["lexical"] = (sql, dict(params))
                    rows = c.execute(text(sql), params).mappings().all()
                    timings["lexical"] = time.perf_counter() - begin
                    begin = time.perf_counter()
                    left = group(rows, depth)
                    timings["grouping"] += time.perf_counter() - begin
                    plans["lexical_candidates"] = len(rows)
            if mode in {"vector", "hybrid", "compare"}:
                begin = time.perf_counter()
                # No ORDER BY vector / LIMIT: exact distances for the full admissible set.
                sql = f"""SELECT u.document_id,u.unit_id,u.ordinal,u.start_offset,u.end_offset,
                    1-(u.embedding <=> CAST(:vector AS public.vector)) AS score
                    FROM {JOIN} WHERE {ELIGIBLE} {FILTERS} AND u.embedding IS NOT NULL"""
                self.last_sql["vector"] = (sql, dict(params))
                rows = c.execute(text(sql), params).mappings().all()
                timings["vector"] = time.perf_counter() - begin
                begin = time.perf_counter()
                right = group(rows, depth, vector=True)
                timings["grouping"] += time.perf_counter() - begin
                plans["vector_candidates"] = len(rows)
            begin = time.perf_counter()
            if mode == "lexical":
                ranked = [
                    dict(
                        document_id=r["document_id"],
                        score=None,
                        lexical=r,
                        vector=None,
                        witness=r,
                        witness_origin="lexical",
                    )
                    for r in left
                ]
            elif mode == "vector":
                ranked = [
                    dict(
                        document_id=r["document_id"],
                        score=None,
                        lexical=None,
                        vector=r,
                        witness=r,
                        witness_origin="vector",
                    )
                    for r in right
                ]
            else:
                ranked = fuse(left, right, depth)
            timings["fusion"] = time.perf_counter() - begin
            begin = time.perf_counter()
            output = []
            titles = dict(
                c.execute(
                    text("""SELECT document_id,display_title FROM documentary.document
                WHERE corpus_id=:corpus AND release_id=:release AND document_id=ANY(:ids)"""),
                    dict(SCOPE, ids=list({r["document_id"] for r in left + right})),
                ).all()
            )
            for row in left + right:
                row["title"] = titles[row["document_id"]]
            # Batch hydrate witnesses; SQL joins verify that the selected unit remains admissible.
            ids = [r["witness"]["unit_id"] for r in ranked]
            hydrated = {
                row["unit_id"]: dict(row)
                for row in c.execute(
                    text(f"""SELECT u.unit_id,d.display_title,
                d.source_metadata->'metadata' AS metadata,d.provenance,d.warnings,
                substring(d.full_text FROM u.start_offset+1 FOR u.end_offset-u.start_offset) AS passage,
                CASE WHEN CAST(:headline_query AS text) IS NOT NULL THEN ts_headline('pg_catalog.french',
                    substring(d.full_text FROM u.start_offset+1 FOR u.end_offset-u.start_offset),
                    CAST(:headline_query AS tsquery),
                    'StartSel="", StopSel="", MaxFragments=1, MinWords=18, MaxWords=70') END AS snippet
                FROM {JOIN} WHERE {ELIGIBLE} AND u.unit_id=ANY(:ids)"""),
                    dict(SCOPE, ids=ids, headline_query=params.get("query")),
                ).mappings()
            }
            for rank, result in enumerate(ranked, 1):
                witness = result["witness"]
                source = hydrated.get(witness["unit_id"])
                if source is None:
                    raise ValueError("Witness is no longer admissible")
                metadata_only = result["witness_origin"] == "lexical" and not witness["text_match"]
                output.append(
                    dict(
                        result,
                        rank=rank,
                        title=source["display_title"],
                        corpus_id=CORPUS,
                        metadata=source["metadata"],
                        provenance=source["provenance"],
                        warnings=source["warnings"],
                        excerpt=" ".join(
                            (
                                source["passage"]
                                if metadata_only
                                else source["snippet"] or source["passage"]
                            ).split()
                        )[:850],
                        excerpt_format="display window; whitespace collapsed; unit offsets refer to exact full passage",
                        match_origin="metadata" if metadata_only else "text",
                        excerpt_selection="opening" if metadata_only else "branch_witness",
                        url="/document?unit=" + witness["unit_id"],
                    )
                )
            timings["hydration"] = time.perf_counter() - begin
        with self.destination.transaction(readonly=True) as c:
            current = gate(c)
            if any(
                current[k] != release[k]
                for k in ("editorial_hash", "embedding_recipe", "lexical_recipe")
            ):
                raise ValueError("Laboratory generation changed during query")
        timings["total"] = time.perf_counter() - started
        return dict(
            query=query,
            mode=mode,
            depth=depth,
            release=GENERATION,
            items=output,
            lexical=left,
            vector=right,
            timings=timings,
            candidates=plans,
            exhaustive=False,
            laboratory_only=True,
        )
