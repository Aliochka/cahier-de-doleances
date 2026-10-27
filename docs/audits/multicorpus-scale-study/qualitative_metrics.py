"""Pertinence sur le sous-ensemble explicitement relu ; inconnu reste inconnu."""

import collections
import gzip
import json

from common import HERE, read, write, write_rows


def main():
    grades = {
        (j["query_id"], j["g"]): j
        for j in read(HERE / "data/qualitative-judgments.json")["judgments"]
    }
    queries = set(read(HERE / "protocol.json")["qualitative_queries"])
    outputs = []
    detailed = []
    with gzip.open(HERE / "data/rankings.jsonl.gz", "rt") as f:
        for line in f:
            run = json.loads(line)
            if run["size"] not in (240, 1000000) or run["query_id"] not in queries:
                continue
            top = run["results"][:10]
            js = [grades.get((run["query_id"], r["g"])) for r in top]
            known = [j for j in js if j is not None]
            low = sum(j["grade"] for j in known) / 10
            high = (sum(j["grade"] for j in known) + 3 * (10 - len(known))) / 10
            outputs.append(
                dict(
                    size=run["size"],
                    query_id=run["query_id"],
                    method=run["method"],
                    depth=run["depth"],
                    strategy=run["strategy"],
                    judged=len(known),
                    unknown=10 - len(known),
                    mean_grade10=low if len(known) == 10 else None,
                    lower_bound=low,
                    upper_bound=high,
                    useful=sum(j["grade"] >= 2 for j in known),
                    strong=sum(j["grade"] == 3 for j in known),
                    superficial=sum(j["grade"] == 1 for j in known),
                    off_topic=sum(j["grade"] == 0 for j in known),
                    historical=sum(r["g"] < 269 for r in top),
                )
            )
            detailed.append(
                dict(
                    run,
                    results=[
                        dict(r, evaluation=grades.get((run["query_id"], r["g"]))) for r in top
                    ],
                )
            )
    groups = collections.defaultdict(list)
    for r in outputs:
        groups[r["size"], r["method"], r["depth"], r["strategy"]].append(r)
    summary = []
    for (size, method, depth, strategy), rs in groups.items():
        for category, selected in (
            ("all10", rs),
            ("counterexamples4", [r for r in rs if r["query_id"] in {"q19", "q22", "q25", "q28"}]),
        ):
            denominator = 10 * len(selected)
            unknown = sum(r["unknown"] for r in selected)
            summary.append(
                dict(
                    size=size,
                    method=method,
                    depth=depth,
                    strategy=strategy,
                    subset=category,
                    queries=len(selected),
                    judged=denominator - unknown,
                    unknown=unknown,
                    mean_grade10=sum(r["lower_bound"] for r in selected) / len(selected)
                    if not unknown
                    else None,
                    mean_bounds=[
                        sum(r["lower_bound"] for r in selected) / len(selected),
                        sum(r["upper_bound"] for r in selected) / len(selected),
                    ],
                    useful_count=sum(r["useful"] for r in selected),
                    strong_count=sum(r["strong"] for r in selected),
                    off_topic_count=sum(r["off_topic"] for r in selected),
                    superficial_count=sum(r["superficial"] for r in selected),
                    historical_count=sum(r["historical"] for r in selected),
                )
            )
    write(
        HERE / "data/qualitative-metrics.json",
        dict(
            judge="Codex exploratory non-independent",
            fixed_queries=sorted(queries),
            new_judgments=230,
            inherited_judgments=215,
            per_query=outputs,
            summary=summary,
        ),
    )
    write_rows(HERE / "data/qualitative-rankings.jsonl", detailed)
    for r in summary:
        if r["subset"] == "all10" and (r["method"] != "hybrid" or r["depth"] in (50, 1000)):
            print(
                r["size"],
                r["method"],
                r["strategy"],
                r["depth"],
                r["mean_grade10"],
                "unknown",
                r["unknown"],
                "useful",
                r["useful_count"],
            )


if __name__ == "__main__":
    main()
