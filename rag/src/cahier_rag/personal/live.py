"""Questions libres sur tout RAG-007 ; aucune lecture du jeu de requêtes réservé."""

import json
import time
from pathlib import Path

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.generation.contracts import GenerationInput, compact
from cahier_rag.personal.campaign import Cache, answer
from cahier_rag.search.hybrid.core import fuse


def merge_vector_partitions(rankings, limit=50):
    by_id = {}
    for rows in rankings:
        for result in rows:
            did = result.document.document_id
            if did in by_id:
                raise ValueError("Partitions vectorielles non disjointes.")
            by_id[did] = result
    return sorted(by_id.values(), key=lambda r: (-r.score, r.document.document_id))[:limit]


def live_context(query, ranked, scope, counter):
    from cahier_rag.context.assembly import fit_source, render
    from cahier_rag.context.contracts import ContextConfig

    config = ContextConfig()
    sources = []
    parents = set()
    for rank, result in enumerate(ranked, 1):
        unit = result.document
        expected = scope.documents.get(unit.document_id)
        if not expected or expected["content_hash"] != unit.content_hash:
            raise ValueError("Document extérieur ou modifié.")
        parent = unit.corpus_id, unit.contribution_id
        if parent in parents:
            continue
        if len(sources) >= config.max_primary:
            break
        source = fit_source(
            unit,
            sources,
            counter,
            config,
            config.document_budget,
            sample_hash=scope.sample_hash,
            method="H1+R2-personal-all-rag007",
            rank=rank,
            role="primary",
        )
        if source is None:
            break
        sources.append(source)
        parents.add(parent)
    payload = render(sources, "P1")
    if counter.count(payload) > 8192:
        raise ValueError("Budget documentaire dépassé.")
    context = {
        "version": 1,
        "purpose": "personal-free-query",
        "query_partition": None,
        "query_hash": digest(query),
        "sample_hash": scope.sample_hash,
        "configuration": config.to_dict(),
        "model_document_payload": payload,
        "citation_map": {s.reference: s.to_dict() for s in sources},
        "tokenizer": counter.description,
        "document_tokens": counter.count(payload),
    }
    context["context_hash"] = digest(context)
    return compact(context), context


def ask(root, query, *, env_file=None, progress=lambda stage: None):
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise ValueError("Question de 1 à 1000 caractères requise.")
    from cahier_rag.__main__ import open_store
    from cahier_rag.config import load_settings
    from cahier_rag.context.experiments import tokenizer_location
    from cahier_rag.context.tokenization import LocalTokenizer
    from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingInput
    from cahier_rag.embeddings.registry import MODELS
    from cahier_rag.embeddings.transformers_backend import TransformersBackend
    from cahier_rag.personal.backend import Generator
    from cahier_rag.reranking.backend import TransformersReranker
    from cahier_rag.reranking.contracts import PreparationConfig
    from cahier_rag.reranking.preparation import segments
    from cahier_rag.reranking.registry import MODELS as RERANKERS
    from cahier_rag.search.flexible import FlexibleEngine
    from cahier_rag.search.lexical import CorpusScope, SearchResult
    from cahier_rag.vector.engine import VectorEngine
    from cahier_rag.vector.preparation import load_prepared
    from cahier_rag.vector.store import VectorStore, recipe

    root = Path(root)
    local = root / "evaluation/local/rag025"
    selected = json.loads((local / "selected.json").read_text())
    scope = CorpusScope(json.loads((root / "evaluation/local/rag007/corpus.json").read_text()))
    qid = "personal:" + digest(query)
    timings = {}
    started = time.perf_counter()
    progress("Recherche H1 sur les 20 000 unités")
    with open_store(load_settings(env_file=env_file)) as storage:
        lexical = FlexibleEngine(storage.guard, scope)
        lexical.validate()
        prepared = load_prepared(root / "evaluation/local/rag013/bge-B", scope)
        store = VectorStore(storage.guard, scope, recipe(prepared))
        embedding = EmbeddingEngine(
            TransformersBackend(
                MODELS["bge-m3"], root / "models", device="cuda", precision="bfloat16"
            )
        )
        vector = VectorEngine(store, embedding)
        try:
            vector.load()
            batch = next(embedding.encode_queries([EmbeddingInput(qid, query, digest(query))]))
            parts = [
                store.search(batch.vectors[0], limit=50, split=s)
                for s in ("development", "evaluation")
            ]
            right = merge_vector_partitions(parts)
            left = lexical.search(query, limit=50, split=None)
            ranked, traces = fuse({"lexical": left, "vector": right}, k=60)
            ranked = list(ranked[:50])
            vector_recipe = store.configuration
        finally:
            vector.close()
    timings["retrieval_seconds"] = time.perf_counter() - started
    if sum(len(r.document.text) for r in ranked) > 20000000:
        raise ValueError("Lot de reclassement supérieur à 20 millions de caractères.")
    progress("Reclassement Qwen3-Reranker-4B")
    reranker = TransformersReranker(RERANKERS["R2"], root / "models/rerankers", budget=1024)
    before = time.perf_counter()
    scores = {}
    positions = {}
    try:
        reranker.load()
        for result in ranked:
            pairs = []
            best = None
            spans = []
            for pair in segments(qid, query, result.document, [reranker], PreparationConfig()):
                pairs.append(pair)
                if len(pairs) == 4:
                    values = reranker.score(pairs)
                    spans.extend(
                        {"start": p.start, "end": p.end, "score": s}
                        for p, s in zip(pairs, values, strict=True)
                    )
                    pairs = []
            if pairs:
                values = reranker.score(pairs)
                spans.extend(
                    {"start": p.start, "end": p.end, "score": s}
                    for p, s in zip(pairs, values, strict=True)
                )
            if not spans:
                raise ValueError("Document sans segment.")
            best = max(s["score"] for s in spans)
            scores[result.document.document_id] = best
            positions[result.document.document_id] = spans
        reranker_recipe = reranker.recipe()
    finally:
        reranker.close()
    timings["reranking_seconds"] = time.perf_counter() - before
    ranked = sorted(
        (SearchResult(r.document, scores[r.document.document_id]) for r in ranked),
        key=lambda r: (-r.score, r.document.document_id),
    )
    progress("Construction S2/P1, budget 8 192 tokens")
    path, settings = tokenizer_location(root)
    document, context = live_context(query, ranked, scope, LocalTokenizer(path, **settings))
    progress("Génération Qwen3-14B")
    backend = Generator(root / "models/judges", token_filter=selected["token_filter"])
    cache = Cache(local / "personal-generation.sqlite3")
    try:
        if backend.recipe() != selected["backend"]:
            raise ValueError("Recette personnelle différente du gel sélectionné.")
        result = answer(
            GenerationInput(qid, query, document), backend, cache, method=selected["method"]
        )
    finally:
        backend.close()
        cache.close()
    timings["total_seconds"] = time.perf_counter() - started
    record = {
        "version": 1,
        "purpose": "personal-free-query",
        "query": query,
        "query_id": qid,
        "corpus_hash": scope.sample_hash,
        "corpus_size": len(scope.documents),
        "partition_filter": None,
        "vector_recipe": vector_recipe,
        "reranker_recipe": reranker_recipe,
        "rrf_traces": traces,
        "reranking_spans": positions,
        "context": context,
        "document": document,
        "result": result,
        "timings": timings,
    }
    record_id = digest(record)
    atomic_json(local / "requests" / (record_id + ".json"), record)
    if result["status"] != "valid":
        raise ValueError("Réponse non validée, conservée pour audit local.")
    return {
        "answer": result["output"],
        "sources": document["sources"],
        "citation_map": document["citation_map"],
        "experimental": True,
        "record_id": record_id,
        "timings": timings,
        "corpus_size": len(scope.documents),
    }
