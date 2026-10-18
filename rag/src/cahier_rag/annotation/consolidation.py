"""Consolidation de snapshots en lecture seule ; désaccords conservés et non résolus."""

from collections import defaultdict

from cahier_rag.evaluation.sampling import digest

VERSION = "rag015-consolidated-v1"


def consolidate(catalogue):
    grouped, sources, campaigns = defaultdict(list), {}, []
    for campaign_id in sorted(catalogue.campaigns):
        snapshot = catalogue.snapshot(campaign_id)
        status = catalogue.status(campaign_id)
        # Le bilan et les observations doivent représenter exactement le même snapshot.
        if status["started"] != (snapshot is not None) or (
            snapshot is not None and status["session_hash"] != digest(snapshot.state)
        ):
            raise ValueError("Session modifiée pendant la lecture ; relancer le rapport.")
        campaigns.append(status)
        if snapshot is None:
            continue
        identity = snapshot.identity
        sources[campaign_id] = {
            "session_hash": digest(snapshot.state),
            "pool_hash": identity["pool_hash"],
            "queries_hash": identity["queries_hash"],
            "sample_hash": identity["sample_hash"],
            "evaluator": identity["evaluator"],
        }
        for judgment in snapshot.export():
            observation = dict(
                judgment,
                campaign_id=campaign_id,
                **{
                    key: sources[campaign_id][key]
                    for key in ("session_hash", "pool_hash", "queries_hash", "sample_hash")
                },
            )
            grouped[judgment["query_id"], judgment["document_id"]].append(observation)
    resolved, conflicts, provenance = [], [], []
    for (qid, did), observations in sorted(grouped.items()):
        observations.sort(key=lambda r: (r["campaign_id"], r["evaluator"], r["judged_at"]))
        entry = {"query_id": qid, "document_id": did, "observations": observations}
        if len({r["grade"] for r in observations}) > 1:
            conflicts.append(dict(entry, reason="grade_disagreement"))
            continue
        original = observations[0]
        resolved.append(
            {
                key: original[key]
                for key in (
                    "query_id",
                    "document_id",
                    "grade",
                    "justification",
                    "evaluator",
                    "judged_at",
                )
            }
            | {"version": VERSION}
        )
        provenance.append(entry)
    return {
        "version": VERSION,
        "sources": sources,
        "campaigns": campaigns,
        "judgments": resolved,
        "provenance": provenance,
        "conflicts": conflicts,
        "distinct_judged_pairs": len(grouped),
        "resolved_pairs": len(resolved),
        "observation_count": sum(map(len, grouped.values())),
        "sample_hash": catalogue.sample["selected_hash"],
        "queries_hash": digest(catalogue.queries),
    }
