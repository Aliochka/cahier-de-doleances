"""Construit 1305 hypothèses traçables; pas d’articles ni de textes Persée."""

import collections
import time
from lib import HERE, V2, base, jlines, rows, save, sha, source_ref, sources
from registry_rules import VERSION, enriched_leaves, propose


def main():
    clock = time.perf_counter()
    ss = sources()
    v2 = rows(V2 / "data/v2-document-predictions.jsonl")
    lookup = {(p["volume"], p["anchor_xpath"]): p for p in v2}
    index = {v: (enriched_leaves(s), base.page_index(s)) for v, s in ss.items()}
    metadata = rows(HERE / "data/metadata.jsonl")
    result = []
    assert len(metadata) == 1305
    for i, m in enumerate(metadata):
        s = ss[m["volume"]]
        leaves, (_, at) = index[m["volume"]]
        pred = propose(m, s, leaves, at, lookup)
        c = pred["candidates"][0] if pred["candidates"] and pred["boundary"] else None
        v2_primary = lookup.get((m["volume"], c["anchor_xpath"])) if c else None
        result.append(
            dict(
                id="ap1789-registry-p1:" + m["id"],
                corpus_id="cahiers-1789-ap-stanford",
                persee_id=m["id"],
                metadata=m,
                document_kind=pred["kind"],
                document_kind_status="inferred_not_verified",
                kind_evidence=pred["kind_basis"],
                alignment_status=pred["status"],
                alignment_verification="not_reviewed",
                alignment_evidence=pred["evidence"],
                alignment_margin=pred.get("margin"),
                technical_scores_are_probabilities=False,
                source=source_ref(s),
                candidates=pred["candidates"],
                primary_anchor=c["anchor_xpath"] if c else None,
                source_witness_id=("stanford:" + s.sha256[:16] + ":" + sha(c["anchor_xpath"])[:16])
                if c
                else None,
                boundaries=dict(
                    status=pred.get("boundary_status", "non_etablies"),
                    proposal=pred["boundary"],
                    verification=None,
                ),
                v2_match=dict(
                    id=v2_primary["id"],
                    classification=v2_primary["classification"],
                    same_bounds=bool(
                        pred["boundary"]
                        and (v2_primary["start"], v2_primary["end"])
                        == (pred["boundary"]["start"], pred["boundary"]["end"])
                    ),
                )
                if v2_primary
                else None,
                anomalies=pred["anomalies"],
                method_version=VERSION,
                text_storage="exact_source_ranges_no_modernization_no_text_republication",
                future_passages=dict(
                    produced=False,
                    offset_basis="Unicode codepoints in decoded itertext; half-open ranges",
                    id_recipe="registry_document_id + source_revision + source_start/end + segmentation_version",
                ),
            )
        )
        if (i + 1) % 200 == 0:
            print("aligned", i + 1, flush=True)
    # Global contradictions are flagged, never silently resolved by picking another document.
    anchors = collections.defaultdict(list)
    for r in result:
        if r["primary_anchor"] and r["alignment_status"] != "hors_perimetre":
            anchors[(r["metadata"]["volume"], r["primary_anchor"])].append(r)
    for group in anchors.values():
        if len(group) > 1:
            for r in group:
                r["anomalies"].append("same_primary_anchor_multiple_notices")
                r["alignment_status"] = "ambigu"
                r["boundaries"]["status"] = "ambigues"
    for v in ss:
        seq = sorted(
            [r for r in result if r["metadata"]["volume"] == v],
            key=lambda r: r["metadata"]["catalogue_order"],
        )
        for i, r in enumerate(seq):
            r["catalogue_neighbours"] = dict(
                previous_id=seq[i - 1]["id"] if i else None,
                next_id=seq[i + 1]["id"] if i + 1 < len(seq) else None,
            )
    jlines(HERE / "data/registry-automatic.jsonl", result)
    save(
        HERE / "data/build-summary.json",
        dict(
            records=len(result),
            seconds=time.perf_counter() - clock,
            alignment_status=dict(collections.Counter(r["alignment_status"] for r in result)),
            kinds=dict(collections.Counter(r["document_kind"] for r in result)),
            boundary_status=dict(collections.Counter(r["boundaries"]["status"] for r in result)),
            per_volume={
                v: dict(
                    collections.Counter(
                        r["alignment_status"] for r in result if r["metadata"]["volume"] == v
                    )
                )
                for v in ss
            },
            unverified=True,
        ),
    )
    print("Built", len(result), "in", round(time.perf_counter() - clock, 2), "seconds", flush=True)


if __name__ == "__main__":
    main()
