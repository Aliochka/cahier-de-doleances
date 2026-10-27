"""Mesures sur jugements explicites, sans notes déduites des scores de recherche."""

import math
import statistics

from common import HERE, read, rows, sha, write, write_rows


def dcg(grades):
    return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(grades))


def main():
    annotation = read(HERE / "annotations.json")
    assert annotation["pool_sha256"] == sha(HERE / "data/review-pool.jsonl")
    docs = {d["id"]: d for d in rows(HERE / "data/corpus.jsonl")}
    judgments = {(j["query_id"], j["unit_id"]): j for j in annotation["judgments"]}
    assert len(judgments) == len(annotation["judgments"])
    rankings = rows(HERE / "data/rankings.jsonl")
    queries = {q["id"]: q for q in read(HERE / "queries.json")["queries"]}
    metrics, detail = [], []
    for run in rankings:
        qid, population, method = (run[k] for k in ("query_id", "population", "method"))
        top = run["results"][:10]
        assert all((qid, r["id"]) in judgments for r in top)
        grades = [judgments[qid, r["id"]]["grade"] for r in top]
        relevant_pool = [
            j["grade"]
            for (q, did), j in judgments.items()
            if q == qid and (population == "mixed" or docs[did]["status"] == "A")
        ]
        ideal = sorted(relevant_pool, reverse=True)[:10]
        idcg = dcg(ideal)
        useful_ideal = [g if g >= 2 else 0 for g in ideal]
        useful_idcg = dcg(useful_ideal)
        metrics.append(
            dict(
                query_id=qid,
                category=queries[qid]["category"],
                population=population,
                method=method,
                mean_grade5=sum(grades[:5]) / 5,
                mean_grade10=sum(grades) / 10,
                ndcg10=dcg(grades) / idcg if idcg else None,
                ndcg10_useful=dcg([g if g >= 2 else 0 for g in grades]) / useful_idcg
                if useful_idcg
                else None,
                returned10=len(top),
                strong10=grades.count(3),
                useful10=sum(g >= 2 for g in grades),
                superficial10=grades.count(1),
                off_topic10=grades.count(0),
                historical10=sum(docs[r["id"]]["status"] == "A" for r in top),
                historical_useful10=sum(
                    docs[r["id"]]["status"] == "A" and judgments[qid, r["id"]]["grade"] >= 2
                    for r in top
                ),
                pool_has_useful=bool(useful_idcg),
            )
        )
        detailed = dict(run)
        detailed["full_top50_artifact"] = "rankings.jsonl"
        detailed["results"] = [
            dict(
                r,
                corpus=docs[r["id"]]["corpus"],
                parent_id=docs[r["id"]]["parent_id"],
                short_id=docs[r["id"]]["short_id"],
                text=docs[r["id"]]["text"],
                question=docs[r["id"]].get("question"),
                title=docs[r["id"]]["title"],
                references=docs[r["id"]]["references"],
                evaluation=judgments.get((qid, r["id"])),
            )
            for r in run["results"][:10]
        ]
        detail.append(detailed)
    summaries = []
    for population in ("historical", "mixed"):
        for category in ("all", "contemporaine", "historique", "ambigue", "contre_exemple"):
            for method in read(HERE / "protocol.json")["methods"]:
                subset = [
                    m
                    for m in metrics
                    if m["population"] == population
                    and m["method"] == method
                    and (category == "all" or m["category"] == category)
                ]
                returned = sum(m["returned10"] for m in subset)
                s = dict(
                    population=population,
                    category=category,
                    method=method,
                    queries=len(subset),
                    returned_at10=returned,
                )
                for key in ("mean_grade5", "mean_grade10", "historical10", "historical_useful10"):
                    s[key] = statistics.mean(m[key] for m in subset)
                for key in ("ndcg10", "ndcg10_useful"):
                    valid = [m[key] for m in subset if m[key] is not None]
                    s[key] = statistics.mean(valid) if valid else None
                    s[key + "_queries"] = len(valid)
                for key in ("strong", "useful", "superficial", "off_topic"):
                    count = sum(m[key + "10"] for m in subset)
                    s[key + "_at10"] = count
                    s[key + "_share"] = count / returned if returned else None
                summaries.append(s)
    lookup = {(r["query_id"], r["population"], r["method"]): r["results"] for r in rankings}
    novelty = []
    for population in ("historical", "mixed"):
        for qid in queries:
            lex10 = {r["id"] for r in lookup[qid, population, "lexical"][:10]}
            lex50 = {r["id"] for r in lookup[qid, population, "lexical"]}
            for method in ("vector_A", "vector_B", "hybrid_A", "hybrid_B"):
                useful = [
                    r["id"]
                    for r in lookup[qid, population, method][:10]
                    if judgments[qid, r["id"]]["grade"] >= 2
                ]
                novelty.append(
                    dict(
                        query_id=qid,
                        population=population,
                        method=method,
                        useful_new_vs_lexical10=[d for d in useful if d not in lex10],
                        useful_new_vs_lexical50=[d for d in useful if d not in lex50],
                    )
                )
    lengths = []
    for population in ("historical", "mixed"):
        for method in read(HERE / "protocol.json")["methods"]:
            hits = [
                docs[r["id"]]
                for run in rankings
                if run["population"] == population and run["method"] == method
                for r in run["results"][:10]
            ]
            lengths.append(
                dict(
                    population=population,
                    method=method,
                    median_chars_at10=statistics.median(len(d["text"]) for d in hits),
                    mean_chars_at10=statistics.mean(len(d["text"]) for d in hits),
                    longest_hist_h019_occurrences=sum(d["short_id"] == "h019" for d in hits),
                )
            )
    write(
        HERE / "data/metrics.json",
        dict(
            judge="Codex exploratory non-independent",
            pooled_pairs=len(rows(HERE / "data/review-pool.jsonl")),
            judged_pairs=len(judgments),
            graded_histories_read=269,
            queries=30,
            summary=summaries,
            per_query=metrics,
            length_diagnostics=lengths,
        ),
    )
    write_rows(HERE / "data/results.jsonl", detail)
    write(HERE / "data/novelty.json", novelty)
    comparison = [
        "# Comparaison des méthodes\n\n",
        "Notes Codex exploratoires et non indépendantes. Moyennes sur 30 requêtes. Notes moyennes sur 0–3, positions non retournées = 0. nDCG sur le pool jugé (gains 2^note−1), pas un rappel exhaustif. Part forte : note 3 parmi résultats retournés. Hors sujet : note 0 ; la note 1 reste superficielle. nDCG gradué sur 26 requêtes historiques / 30 mixtes ; variante utile sur 21 historiques / 25 mixtes. Les idéaux nuls sont exclus des moyennes et signalés, pas convertis en succès.\n",
    ]
    for population in ("historical", "mixed"):
        comparison += [
            f"\n## Population {population}\n\n",
            "| Méthode | Note@5 | Note@10 | nDCG@10 | Forte | Hors sujet | Résultats | Historiques utiles / requête |\n|---|---:|---:|---:|---:|---:|---:|---:|\n",
        ]
        for s in summaries:
            if s["population"] == population and s["category"] == "all":
                comparison.append(
                    f"| {s['method']} | {s['mean_grade5']:.3f} | {s['mean_grade10']:.3f} | {s['ndcg10']:.3f} | {100 * s['strong_share']:.1f}% | {100 * s['off_topic_share']:.1f}% | {s['returned_at10']} | {s['historical_useful10']:.2f} |\n"
                )
        comparison.append(
            "\n| Catégorie | Méthode | Note@10 | nDCG@10 utile (notes≥2) | Requêtes avec un utile connu |\n|---|---|---:|---:|---:|\n"
        )
        for s in summaries:
            if s["population"] == population and s["category"] != "all":
                val = s["ndcg10_useful"]
                comparison.append(
                    f"| {s['category']} | {s['method']} | {s['mean_grade10']:.3f} | {val:.3f}".replace(
                        "None", "—"
                    )
                    + f" | {s['ndcg10_useful_queries']} |\n"
                    if val is not None
                    else f"| {s['category']} | {s['method']} | {s['mean_grade10']:.3f} | — | 0 |\n"
                )
    (HERE / "COMPARISON.md").write_text("".join(comparison))
    for s in summaries:
        if s["category"] == "all":
            print(
                s["population"],
                s["method"],
                "grade@10",
                round(s["mean_grade10"], 3),
                "ndcg",
                round(s["ndcg10"], 3),
                "useful",
                s["useful_at10"],
                "n",
                s["returned_at10"],
            )


if __name__ == "__main__":
    main()
