"""Profils ANN RAG-027 sans reconstruire l'index ; traces des segments conservées."""

import time
from dataclasses import asdict, dataclass

from sqlalchemy import text

from cahier_rag.embeddings.core import validate_vectors
from cahier_rag.fullcorpus.search import FILTERS, FullSearch

EXACT_QUESTION_LIMIT = 5000


@dataclass(frozen=True)
class AnnConfig:
    ef_search: int = 400
    candidates: int = 400
    iterative: str = "strict_order"
    max_scan_tuples: int = 20000
    scan_mem_multiplier: int = 1

    def __post_init__(self):
        if type(self.ef_search) is not int or not 40 <= self.ef_search <= 1000:
            raise ValueError("ef_search entre 40 et 1000.")
        if type(self.candidates) is not int or not 100 <= self.candidates <= 50000:
            raise ValueError("Candidats entre 100 et 50000.")
        if self.iterative not in {"off", "strict_order"}:
            raise ValueError("Mode itératif non supporté.")
        if type(self.max_scan_tuples) is not int or not 1000 <= self.max_scan_tuples <= 200000:
            raise ValueError("Plafond de parcours invalide.")
        if type(self.scan_mem_multiplier) is not int or not 1 <= self.scan_mem_multiplier <= 4:
            raise ValueError("Multiplicateur mémoire entre 1 et 4.")

    def to_dict(self):
        return asdict(self) | {
            "version": 1,
            "index": "RAG026 unchanged m16/ef_construction64",
            "aggregation": "max cosine; unit id then segment index ties",
        }


PROFILES = {
    "reference": AnnConfig(),
    "ef800": AnnConfig(800),
    "ef1000": AnnConfig(1000),
    "wide400": AnnConfig(400, 800),
    "wide800": AnnConfig(800, 800),
    "deep1600": AnnConfig(1000, 1600, "strict_order", 100000, 2),
    "deep3200": AnnConfig(1000, 3200, "strict_order", 100000, 4),
    "off1000": AnnConfig(1000, 400, "off"),
}


def ann_search(
    store,
    vector,
    config=AnnConfig(),
    *,
    limit=50,
    questionnaire_id=None,
    unit_type=None,
    split=None,
    question_id=None,
):
    start = time.perf_counter()
    engine = FullSearch(store)
    values = validate_vectors([vector], expected_rows=1, dimension=1024, normalize=False)[0]
    params = engine.parameters(limit, questionnaire_id, unit_type, split, question_id)
    params["vector"] = "[" + ",".join(str(v) for v in values) + "]"
    params["candidates"] = config.candidates
    with store.guard.transaction() as (c, _):
        c.execute(text("SET LOCAL statement_timeout='30s'"))
        index = "rag_full.segments_" + store.space + "_hnsw"
        if not c.execute(text("SELECT to_regclass(:name)"), {"name": index}).scalar_one():
            raise ValueError("Index HNSW absent.")
        for key, value in (
            ("ef_search", config.ef_search),
            ("iterative_scan", config.iterative),
            ("max_scan_tuples", config.max_scan_tuples),
            ("scan_mem_multiplier", config.scan_mem_multiplier),
        ):
            c.execute(
                text("SELECT set_config(:key,:value,true)"),
                {"key": "hnsw." + key, "value": str(value)},
            )
        c.execute(text("SET LOCAL enable_seqscan=off"))
        exact_question = False
        if question_id is not None:
            # Small scopes need exact distances: an ANN scan can miss them entirely.
            params["scope_probe_limit"] = EXACT_QUESTION_LIMIT + 1
            eligible_count = c.execute(
                text(f"""SELECT count(*) FROM (
                SELECT 1 FROM rag_full.documents d WHERE {FILTERS} LIMIT :scope_probe_limit
            ) eligible"""),
                params,
            ).scalar_one()
            exact_question = eligible_count <= EXACT_QUESTION_LIMIT
        while True:
            sql = f"""WITH nearest AS MATERIALIZED (
                SELECT s.document_id,s.segment_index,s.representation_id,s.start_offset,s.end_offset,
                    s.embedding <=> CAST(:vector AS public.vector) AS distance
                FROM rag_full.segments s JOIN rag_full.documents d USING(space_id,document_id)
                WHERE {FILTERS} ORDER BY s.embedding <=> CAST(:vector AS public.vector)
                LIMIT :candidates), units AS (
                SELECT DISTINCT ON(document_id) * FROM nearest
                ORDER BY document_id,distance,segment_index,representation_id COLLATE "C")
                SELECT *,1-distance AS score,(SELECT count(*) FROM nearest) AS scanned
                FROM units ORDER BY distance,document_id COLLATE "C" LIMIT :limit"""
            if exact_question:
                sql = f"""WITH eligible AS MATERIALIZED (
                    SELECT d.space_id,d.document_id FROM rag_full.documents d WHERE {FILTERS}
                ), nearest AS MATERIALIZED (
                    SELECT s.document_id,s.segment_index,s.representation_id,s.start_offset,s.end_offset,
                        s.embedding <=> CAST(:vector AS public.vector) AS distance
                    FROM eligible d JOIN rag_full.segments s USING(space_id,document_id)
                    ORDER BY (s.embedding <=> CAST(:vector AS public.vector))+0.0,
                        s.document_id COLLATE "C",s.segment_index,s.representation_id COLLATE "C"
                    LIMIT :candidates), units AS (
                    SELECT DISTINCT ON(document_id) * FROM nearest
                    ORDER BY document_id,distance,segment_index,representation_id COLLATE "C")
                    SELECT *,1-distance AS score,(SELECT count(*) FROM nearest) AS scanned
                    FROM units ORDER BY distance,document_id COLLATE "C" LIMIT :limit"""
            rows = c.execute(text(sql), params).mappings().all()
            # A bounded ANN selection may contain fewer units than requested.
            # Never turn a sparse large scope into an unbounded exact distance scan.
            if (
                not rows
                or len(rows) >= limit
                or rows[0]["scanned"] < params["candidates"]
                or params["candidates"] >= 50000
            ):
                break
            params["candidates"] = min(50000, params["candidates"] * 2)
        results = engine._results(c, [(r["document_id"], r["score"], store.space) for r in rows])
    return results, dict(
        configuration=config.to_dict(),
        mode="exact-question" if exact_question else "ann",
        candidates_requested=params["candidates"],
        retrieved_segments=rows[0]["scanned"] if rows else 0,
        seconds=time.perf_counter() - start,
        winners=[dict(r) for r in rows],
    )
