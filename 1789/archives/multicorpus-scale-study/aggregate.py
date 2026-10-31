"""Mesures sur les270 associations historiques déjà annotées, sans nouvelles notes."""

import collections
import statistics

from common import HERE, read, rows, write


def main():
    groups = collections.defaultdict(list)
    for r in read(HERE / "data/per-query-metrics.json"):
        groups[r["size"], r["method"], r["depth"], r["strategy"]].append(r)
    result = []
    for (size, method, depth, strategy), group in groups.items():
        denominator = sum(r["known_witnesses"] for r in group)
        assert denominator == 270
        result.append(
            dict(
                size=size,
                method=method,
                depth=depth,
                strategy=strategy,
                known_witness_pairs=denominator,
                witnesses_at={
                    str(k): sum(r["witnesses_at"][str(k)] for r in group) for k in (10, 20, 50, 100)
                },
                recall_at={
                    str(k): sum(r["witnesses_at"][str(k)] for r in group) / denominator
                    for k in (10, 20, 50, 100)
                },
                candidate_witnesses=sum(r["candidate_witnesses_at_depth"] for r in group),
                candidate_recall=sum(r["candidate_witnesses_at_depth"] for r in group)
                / denominator,
                mean_historical_at={
                    str(k): statistics.mean(r["historical_at"][str(k)] for r in group)
                    for k in (10, 20, 50, 100)
                },
                known_grade0_historical_at10=sum(r["known_historical_grade0_at10"] for r in group),
            )
        )
    costs = read(HERE / "data/ranking-costs.json")
    costgroups = collections.defaultdict(list)
    for r in costs:
        costgroups[r["size"], r["depth"], r["strategy"]].append(r)
    costsummary = []
    for (size, depth, strategy), rr in costgroups.items():
        costsummary.append(
            dict(
                size=size,
                depth=depth,
                strategy=strategy,
                mean_union_candidates=statistics.mean(r["union_candidates"] for r in rr),
                mean_historical_candidates=statistics.mean(r["historical_candidates"] for r in rr),
                mean_fusion_ms=statistics.mean(r["fusion_ms"] for r in rr),
                mean_lexical_score_ms=statistics.mean(r["lexical_score_ms"] for r in rr),
                mean_lexical_sort_ms=statistics.mean(r["lexical_sort_ms"] for r in rr),
                mean_vector_sort_ms=statistics.mean(r["vector_sort_ms"] for r in rr),
            )
        )
    witnesses = rows(HERE / "data/witnesses.jsonl")
    summary = dict(
        witness_pairs=270,
        unique_historical_units=len({r["g"] for r in witnesses}),
        queries_with_witnesses=len({r["query_id"] for r in witnesses}),
        growth=result,
        costs=costsummary,
    )
    write(HERE / "data/summary.json", summary)
    for size in read(HERE / "protocol.json")["stages"]:
        print(
            size,
            [
                (
                    r["method"],
                    r["strategy"],
                    r["depth"],
                    r["witnesses_at"],
                    r["candidate_witnesses"],
                )
                for r in result
                if r["size"] == size and (r["method"] != "hybrid" or r["depth"] in (50, 1000))
            ],
        )


if __name__ == "__main__":
    main()
