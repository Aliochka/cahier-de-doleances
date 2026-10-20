"""Observations descriptives sur questions libres, sans jugements ni requêtes réservées."""

import json
import time

from sqlalchemy import text

from cahier_rag.embeddings.core import EmbeddingInput
from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.fullcorpus.search import FullSearch
from cahier_rag.vector.preparation import atomic_json

QUERIES = (
    "Comment maintenir un accueil humain dans les services publics ?",
    "Comment financer des bus entre les villages et les gares ?",
    "Quels changements proposez-vous pour la fiscalité du patrimoine ?",
    "Comment permettre aux citoyens de participer aux décisions locales ?",
    '"vote blanc"',
    "isolation logements",
)


def describe(results):
    docs = [r.document for r in results]
    return dict(
        ids=[d.document_id for d in docs],
        contributions=len({d.contribution_id for d in docs}),
        short=sum(len(d.text) < 60 for d in docs),
        other=sum(d.unit_type.value == "other_text" for d in docs),
        duplicate_texts=len(docs) - len({d.text for d in docs}),
    )


def experiment(store, engine, output, *, vectors_path=None):
    if output.exists():
        raise ValueError("Rapport existant : choisir un autre chemin.")
    if vectors_path and vectors_path.exists():
        cached = json.loads(vectors_path.read_text())
        if cached["model"] != engine.backend.spec.to_dict() or cached["queries"] != list(QUERIES):
            raise ValueError("Cache requêtes incompatible.")
        expected = cached.pop("content_hash", None)
        if expected != fingerprint(cached):
            raise ValueError("Empreinte du cache de requêtes incorrecte.")
        vectors = cached["vectors"]
        query_seconds = None
    else:
        start = time.perf_counter()
        engine.load()
        inputs = [EmbeddingInput(str(i), q, fingerprint(q)) for i, q in enumerate(QUERIES)]
        vectors = [v for b in engine.encode_queries(inputs, batch_size=1) for v in b.vectors]
        query_seconds = time.perf_counter() - start
        engine.close()
        if vectors_path:
            payload = dict(
                model=engine.backend.spec.to_dict(), queries=list(QUERIES), vectors=vectors
            )
            atomic_json(vectors_path, payload | {"content_hash": fingerprint(payload)})
    search = FullSearch(store)
    report = dict(
        space=store.space,
        manifest=store.state()["recipe_hash"],
        query_encoding_including_load_seconds=query_seconds,
        queries=[],
    )
    for query, vector in zip(QUERIES, vectors, strict=True):
        item = {"query": query}
        start = time.perf_counter()
        exact = search.vector(vector, limit=50)
        item["exact_seconds"] = time.perf_counter() - start
        item["exact"] = describe(exact)
        item["ann"] = []
        for ef in (40, 100, 200, 400):
            start = time.perf_counter()
            ann = search.vector(vector, limit=50, ann=True, ef_search=ef)
            ids = {r.document.document_id for r in exact}
            item["ann"].append(
                dict(
                    ef_search=ef,
                    seconds=time.perf_counter() - start,
                    recall_vs_exact=len(ids & {r.document.document_id for r in ann}) / len(ids)
                    if ids
                    else None,
                    **describe(ann),
                )
            )
        start = time.perf_counter()
        lexical = search.lexical(query, limit=50)
        item["lexical_seconds"] = time.perf_counter() - start
        item["lexical"] = describe(lexical)
        hybrid, _, measures = search.hybrid(query, vector, ann=True)
        item["hybrid"] = describe(hybrid[:50])
        item["measurements"] = measures
        report["queries"].append(item)
        print(
            json.dumps(
                {
                    k: v
                    for k, v in item.items()
                    if k in ("query", "exact_seconds", "lexical_seconds")
                }
            ),
            flush=True,
        )
    with store.guard.transaction() as (c, _):
        report["relations"] = [
            dict(r)
            for r in c.execute(
                text("""SELECT c.relname,
            pg_total_relation_size(c.oid) AS total_bytes,pg_relation_size(c.oid) AS main_bytes
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='rag_full' AND c.relkind IN ('r','i') ORDER BY c.relname""")
            ).mappings()
        ]
    atomic_json(output, report)
    return report
