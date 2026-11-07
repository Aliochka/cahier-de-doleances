"""Exploratory comparisons, never automatic relevance judgments."""

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from cahier_rag.search.service.control import Budget
from sqlalchemy import text

QUERIES = [
    ("transversal", "Suppression des privilèges"),
    ("transversal", "Justice"),
    ("transversal", "Fiscalité"),
    ("transversal", "Représentation des citoyens"),
    ("transversal", "Éducation"),
    ("transversal", "Agriculture"),
    ("transversal", "Liberté d'expression"),
    ("transversal", "Inégalités sociales"),
    ("historical", "Gabelle"),
    ("historical", "Justice seigneuriale"),
    ("historical", "Corvées"),
    ("historical", "États généraux"),
    ("historical", "Abolition des corporations"),
    ("contemporary", "Transition écologique"),
    ("contemporary", "Pouvoir d'achat"),
    ("contemporary", "Services publics"),
    ("contemporary", "Fiscalité écologique"),
    ("place", "Agen"),
    ("combined", "Agen agriculture"),
    ("frequent", "impôt"),
    ("no-lexical", "zxqv1789inexistant"),
    ("ocr", "jurandes"),
]


def distribution(values):
    rows = sorted(values)
    if not rows:
        return None
    return dict(
        n=len(rows),
        p50=statistics.median(rows),
        p95=rows[min(len(rows) - 1, int(0.95 * len(rows)))],
        min=rows[0],
        max=rows[-1],
    )


def benchmark(service, output, *, resume=False):
    output.parent.mkdir(parents=True, exist_ok=True)
    result = dict(
        recipe="multicorpus-lab-1",
        exploratory=True,
        judgments=None,
        cases=[],
        matrix=[],
        plans={},
        concurrency=[],
    )

    if resume and output.exists():
        result = json.loads(output.read_text())
        if result["recipe"] != "multicorpus-lab-1":
            raise ValueError("Incompatible benchmark resume")

    def save():
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")

    def run(query, corpus="tous", mode="compare", depth=50, reference=False, **filters):
        started = time.perf_counter()
        try:
            if reference:
                r = service.h1.retrieve(query)
                return dict(
                    ok=True,
                    elapsed=time.perf_counter() - started,
                    generation=r.generation,
                    timings=r.timings.__dict__,
                    recipe=r.recipe_version,
                    hits=[
                        dict(
                            key="2019:" + str(h.document.answer_id),
                            unit_id=h.document.document_id,
                            question=h.document.question_text,
                            text=h.document.text[:850],
                            score=h.rrf_score,
                        )
                        for h in r.hits
                    ],
                )
            r = service.search(query, corpus=corpus, mode=mode, depth=depth, **filters)
            return dict(ok=True, elapsed=time.perf_counter() - started, **r)
        except Exception as ex:
            return dict(
                ok=False,
                elapsed=time.perf_counter() - started,
                error=getattr(ex, "code", type(ex).__name__),
                stage=getattr(ex, "stage", None),
                timings=dict(getattr(service, "last_timings", {})),
            )

    for category, query in QUERIES:
        if any(r["query"] == query for r in result["cases"]):
            continue
        row = dict(query=query, category=category, human_judgment=None)
        for label, corpus in [("A_H1", "2019"), ("B_new_2019", "2019"), ("C_multi", "tous")]:
            row[label] = run(query, corpus, reference=label == "A_H1")
            print(
                json.dumps(
                    dict(
                        case=query,
                        configuration=label,
                        ok=row[label]["ok"],
                        seconds=round(row[label]["elapsed"], 3),
                    )
                ),
                flush=True,
            )
        result["cases"].append(row)
        save()
    for corpus in ["2019", "1789", "tous"]:
        for depth in [50, 100, 200]:
            for mode in ["lexical", "vector", "hybrid"]:
                for query in ["Gabelle", "impôt"]:
                    for repeat in range(2):
                        if any(
                            r["query"] == query
                            and r["corpus"] == corpus
                            and r["mode"] == mode
                            and r["depth"] == depth
                            and r["repeat"] == repeat
                            for r in result["matrix"]
                        ):
                            continue
                        value = run(query, corpus, mode, depth)
                        # Raw private results retained for future response-level judging.
                        result["matrix"].append(
                            dict(
                                value,
                                query=query,
                                corpus=corpus,
                                mode=mode,
                                depth=depth,
                                repeat=repeat,
                            )
                        )
                        save()
    result["filters"] = [
        run("agriculture", "1789", volume=1, estate="noblesse"),
        run("Agen agriculture", "1789", place="Agen"),
    ]
    # Representative actual question, taken only from successful results.
    question = next(
        (
            int(i["metadata"]["question_id"])
            for c in result["cases"]
            for i in c["B_new_2019"].get("items", [])
            if i["corpus"] == "2019"
        ),
        None,
    )
    if question:
        result["filters"].append(run("impôt", "2019", question=question))
    # Plans use guarded read-only transactions and the same deadline, no new indexes/settings.
    for corpus in ["2019", "1789"]:
        run("Gabelle", corpus)
        adapter = service.adapters[corpus]
        for branch, (sql, params) in adapter.last_sql.items():
            budget = Budget(10)
            try:
                with budget.monitor(), adapter.connection(budget) as c:
                    if corpus == "2019" and branch == "vector":
                        adapter.configure_vector(c)
                    result["plans"][f"{corpus}_{branch}"] = c.execute(
                        text("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + sql), params
                    ).scalar_one()
            except Exception as ex:
                result["plans"][f"{corpus}_{branch}"] = dict(
                    error=getattr(ex, "code", type(ex).__name__)
                )
        run("impôt", corpus, mode="lexical")
        if "lexical" in adapter.last_sql:
            sql, params = adapter.last_sql["lexical"]
            budget = Budget(10)
            try:
                with budget.monitor(), adapter.connection(budget) as c:
                    result["plans"][f"{corpus}_frequent_actual"] = c.execute(
                        text("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + sql), params
                    ).scalar_one()
            except Exception as ex:
                result["plans"][f"{corpus}_frequent_actual"] = dict(
                    error=getattr(ex, "code", type(ex).__name__)
                )
    result["very_frequent"] = [
        dict(run(q, corpus, mode="lexical"), query=q, selection=corpus)
        for q in ["France", "faire"]
        for corpus in ["2019", "tous"]
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        result["concurrency"] = list(pool.map(lambda _: run("Gabelle"), range(4)))
    result["distributions"] = {
        f"{corpus}/{mode}/{depth}": distribution(
            [
                v["elapsed"]
                for v in result["matrix"]
                if v["ok"] and v["corpus"] == corpus and v["mode"] == mode and v["depth"] == depth
            ]
        )
        for corpus in ["2019", "1789", "tous"]
        for mode in ["lexical", "vector", "hybrid"]
        for depth in [50, 100, 200]
    }
    save()
    return dict(
        output=str(output),
        comparisons=len(result["cases"]),
        matrix=len(result["matrix"]),
        successful=sum(c["ok"] for c in result["matrix"]),
    )
