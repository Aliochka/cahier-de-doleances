"""Mesures reproductibles RAG-027, JSON locaux reprenables, aucune note de pertinence."""

import hashlib
import inspect
import json
import math
import time
from pathlib import Path

from sqlalchemy import text

from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingInput
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.embeddings.transformers_backend import TransformersBackend
from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.fullcorpus.search import FullSearch
from cahier_rag.tuning.lexical import TunedSearch
from cahier_rag.tuning.vector import PROFILES, ann_search
from cahier_rag.vector.preparation import atomic_json


def queries(root):
    data = json.loads((root / "evaluation/performance-rag027.json").read_text())
    if data["version"] != 1 or any(q["split"] != "development" for q in data["queries"]):
        raise ValueError("Jeu de développement versionné requis.")
    return data["queries"]


def encode_queries(root, directory):
    path = directory / "query-vectors.json"
    items = queries(root)
    if path.exists():
        data = json.loads(path.read_text())
        claimed = data.pop("content_hash")
        if (
            fingerprint(data) != claimed
            or data["queries"] != items
            or data["model"] != MODELS["bge-m3"].to_dict()
        ):
            raise ValueError("Cache de requêtes incompatible.")
        return data
    engine = EmbeddingEngine(
        TransformersBackend(MODELS["bge-m3"], root / "models", device="cuda", precision="bfloat16")
    )
    started = time.perf_counter()
    try:
        engine.load()
        loaded = time.perf_counter()
        vectors = []
        latencies = []
        for q in items:
            before = time.perf_counter()
            batch = next(
                engine.encode_queries([EmbeddingInput(q["query_id"], q["text"], fingerprint(q))])
            )
            vectors.append(batch.vectors[0])
            latencies.append(time.perf_counter() - before)
        data = dict(
            version=1,
            queries=items,
            model=MODELS["bge-m3"].to_dict(),
            snapshot=engine.backend.snapshot_hash,
            vectors=vectors,
            query_seconds=latencies,
            load_seconds=loaded - started,
            peak_vram_bytes=engine.backend.torch.cuda.max_memory_allocated(),
        )
        atomic_json(path, data | {"content_hash": fingerprint(data)})
        return data
    finally:
        engine.close()


def load_vectors(directory):
    data = json.loads((directory / "query-vectors.json").read_text())
    claimed = data.pop("content_hash")
    if (
        fingerprint(data) != claimed
        or data["model"] != MODELS["bge-m3"].to_dict()
        or len(data["queries"]) != len(data["vectors"])
        or any(q["split"] != "development" for q in data["queries"])
        or len({q["query_id"] for q in data["queries"]}) != len(data["queries"])
    ):
        raise ValueError("Vecteurs requêtes altérés ou incompatibles.")
    return data


def ranked(results):
    return [
        dict(
            document_id=r.document.document_id,
            score=r.score,
            text_hash=hashlib.sha256(r.document.text.encode()).hexdigest(),
            context_hash=hashlib.sha256(
                (r.document.question_text + "\0" + r.document.text).encode()
            ).hexdigest(),
            contribution_id=str(r.document.contribution_id),
            questionnaire_id=str(r.document.questionnaire_id),
            length=len(r.document.text),
            unit_type=r.document.unit_type.value,
        )
        for r in results
    ]


def compare_rankings(exact, ann, k):
    a, b = exact[:k], ann[:k]
    ids = {x["document_id"] for x in a}
    if not a:
        return dict(id_overlap=None, text_overlap=None, context_overlap=None, distance_regret=None)

    def overlap(field):
        target = {x[field] for x in a}
        return sum(x[field] in target for x in b) / len(a)

    regret = [max(0, x["score"] - y["score"]) for x, y in zip(a, b)]
    return dict(
        id_overlap=sum(x["document_id"] in ids for x in b) / len(a),
        text_overlap=overlap("text_hash"),
        context_overlap=overlap("context_hash"),
        distance_regret=sum(regret) / len(regret) if regret else None,
        max_distance_regret=max(regret) if regret else None,
        boundary_equivalent=sum(x["score"] >= a[-1]["score"] - 1e-6 for x in b) / len(a),
        missing_ids=[
            x["document_id"] for x in a if x["document_id"] not in {v["document_id"] for v in b}
        ],
    )


def freeze_phase(store, root, directory, name, driver, configuration):
    state = store.state()
    recipe = dict(
        version=1,
        corpus_hash=state["chain_hash"],
        recipe_hash=state["recipe_hash"],
        queries_hash=hashlib.sha256(
            (root / "evaluation/performance-rag027.json").read_bytes()
        ).hexdigest(),
        configuration=configuration,
        code={
            n: hashlib.sha256((Path(__file__).parent / n).read_bytes()).hexdigest()
            for n in ("lexical.py", "vector.py")
        },
        driver_hash=hashlib.sha256(inspect.getsource(driver).encode()).hexdigest(),
    )
    path = directory / (name + "-recipe.json")
    if path.exists() and json.loads(path.read_text()) != recipe:
        raise ValueError("Recette d'expérience modifiée : choisir un nouveau répertoire.")
    if not path.exists():
        atomic_json(path, recipe)


def lexical_benchmark(store, root, directory, passes=3, reference=False):
    path = directory / "lexical.json"
    output = json.loads(path.read_text()) if path.exists() else []
    keys = {(x["query_id"], x["recipe"], x["pass"]) for x in output}
    recipes = {
        "equivalent-statistics": dict(statistics=True, prefilter=None),
        "approximate-1000": dict(statistics=True, prefilter=1000),
    }
    if reference:
        recipes = {"rag026": None}
    freeze_phase(
        store, root, directory, "lexical", lexical_benchmark, dict(recipes=recipes, passes=passes)
    )
    for repeat in range(passes):
        for q in queries(root):
            for name, params in recipes.items():
                if (q["query_id"], name, repeat) in keys:
                    continue
                engine = FullSearch(store) if params is None else TunedSearch(store, **params)
                started = time.perf_counter()
                try:
                    rows = engine.lexical(q["text"])
                    item = dict(status="ok", ranking=ranked(rows), **engine.last_lexical_timings)
                except Exception as e:
                    item = dict(
                        status="error",
                        error_type=type(e).__name__,
                        total_seconds=time.perf_counter() - started,
                    )
                item.update(query_id=q["query_id"], recipe=name, **{"pass": repeat})
                output.append(item)
                atomic_json(path, output)
                print(json.dumps({k: v for k, v in item.items() if k != "ranking"}), flush=True)
    return output


def vector_benchmark(store, directory, root=Path(".")):
    data = load_vectors(directory)
    path = directory / "vector.json"
    output = json.loads(path.read_text()) if path.exists() else []
    complete = {x["query_id"] for x in output}
    freeze_phase(
        store,
        root,
        directory,
        "vector",
        vector_benchmark,
        {k: v.to_dict() for k, v in PROFILES.items()},
    )
    reference = FullSearch(store)
    for q, vector in zip(data["queries"], data["vectors"], strict=True):
        if q["query_id"] in complete:
            continue
        started = time.perf_counter()
        exact = reference.vector(vector, limit=100)
        item = dict(
            query_id=q["query_id"],
            exact=ranked(exact),
            exact_seconds=time.perf_counter() - started,
            profiles={},
        )
        # Segment winners are retrieved for the same exact units, independently of HNSW.
        with store.guard.transaction() as (c, _):
            v = "[" + ",".join(str(x) for x in vector) + "]"
            trace = (
                c.execute(
                    text("""SELECT DISTINCT ON(s.document_id) s.document_id,s.segment_index,
                s.representation_id,s.start_offset,s.end_offset,
                s.embedding <=> CAST(:vector AS public.vector) AS distance
                FROM rag_full.segments s WHERE s.space_id=:space AND s.document_id=ANY(:ids)
                ORDER BY s.document_id,distance,s.segment_index"""),
                    dict(vector=v, space=store.space, ids=[r.document.document_id for r in exact]),
                )
                .mappings()
                .all()
            )
            item["exact_segments"] = [dict(r) for r in trace]
        for name, config in PROFILES.items():
            runs = []
            for _ in range(3):
                rows, trace = ann_search(store, vector, config, limit=100)
                runs.append(trace["seconds"])
            ranking = ranked(rows)
            item["profiles"][name] = dict(
                ranking=ranking,
                seconds=runs,
                trace=trace,
                comparison={
                    str(k): compare_rankings(item["exact"], ranking, k) for k in (10, 20, 50, 100)
                },
            )
        # Literal historical API depth 50 is saved too: aggregation/candidate
        # depth may differ from taking top50 of a top100 request.
        old = reference.vector(vector, limit=50, ann=True)
        item["rag026_depth50"] = ranked(old)
        output.append(item)
        atomic_json(path, output)
        print(
            json.dumps(
                dict(
                    phase="vector",
                    completed=len(output),
                    query_id=q["query_id"],
                    exact_seconds=item["exact_seconds"],
                )
            ),
            flush=True,
        )
    return output


def latency_summary(values):
    if not values:
        return None
    v = sorted(values)
    return dict(
        n=len(v),
        minimum=v[0],
        median=(v[(len(v) - 1) // 2] + v[len(v) // 2]) / 2,
        p95=v[math.ceil(0.95 * len(v)) - 1],
        maximum=v[-1],
    )
