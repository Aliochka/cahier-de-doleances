"""Recherche vectorielle locale : ANN explicite ; filtres exhaustifs sans HNSW."""

import time

from sqlalchemy import text

from cahier_rag.embeddings.core import validate_vectors
from cahier_rag.fullcorpus.search import FILTERS, FullSearch
from cahier_rag.tuning.vector import AnnConfig, ann_search


def search_vector(store, vector, *, ann=False, config=AnnConfig(1000), limit=50, **filters):
    # A global HNSW followed by selective filtering may exhaust its scan budget.
    # Filtering uses exact distances, never a silently incomplete ANN result.
    filtered = any(value is not None for value in filters.values())
    if not filtered:
        if ann:
            return ann_search(store, vector, config, limit=limit)
        before = time.perf_counter()
        rows = FullSearch(store).vector(vector, limit=limit)
        return rows, dict(mode="exact", seconds=time.perf_counter() - before)
    before = time.perf_counter()
    engine = FullSearch(store)
    params = engine.parameters(
        limit, filters.get("questionnaire_id"), filters.get("unit_type"), filters.get("split")
    )
    if set(filters) - {"questionnaire_id", "unit_type", "split"}:
        raise ValueError("Filtre inconnu.")
    values = validate_vectors([vector], expected_rows=1, dimension=1024, normalize=False)[0]
    params.update(vector="[" + ",".join(str(v) for v in values) + "]", candidates=limit * 8)
    with store.guard.transaction() as (c, _):
        c.execute(text("SET LOCAL statement_timeout='30s'"))
        while True:
            rows = (
                c.execute(
                    text(f"""WITH eligible AS MATERIALIZED (
                SELECT d.space_id,d.document_id FROM rag_full.documents d WHERE {FILTERS}
            ), nearest AS MATERIALIZED (
                SELECT s.document_id,s.segment_index,
                    s.embedding <=> CAST(:vector AS public.vector) AS distance
                FROM eligible d JOIN rag_full.segments s USING(space_id,document_id)
                ORDER BY (s.embedding <=> CAST(:vector AS public.vector))+0.0,
                    s.document_id COLLATE "C",s.segment_index LIMIT :candidates)
            SELECT document_id,1-min(distance) AS score,
                (SELECT count(*) FROM nearest) AS scanned
            FROM nearest GROUP BY document_id
            ORDER BY score DESC,document_id COLLATE "C" LIMIT :limit"""),
                    params,
                )
                .mappings()
                .all()
            )
            if len(rows) >= limit or not rows or rows[0]["scanned"] < params["candidates"]:
                break
            if params["candidates"] >= 50000:
                raise ValueError("Agrégation exacte : plafond de 50 000 segments atteint.")
            params["candidates"] = min(50000, params["candidates"] * 2)
        results = engine._results(c, [(r["document_id"], r["score"], store.space) for r in rows])
    return results, dict(
        mode="exact-filtered",
        ann_requested=ann,
        seconds=time.perf_counter() - before,
        candidates=params["candidates"],
    )
