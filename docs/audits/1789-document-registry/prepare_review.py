"""Gèle le protocole et sélectionne sans consulter de nouveaux corps de document."""

import collections
import re
from lib import HERE, ALIGN, V1, V2, PILOT, rows, read, save, jlines, sha, sources, base
from registry_rules import PARAMS

SEED = "document-registry-validation-2026-10-27-v1"


def main():
    assert not (HERE / "data/validation-sample.jsonl").exists(), "Selection already frozen"
    ss = sources()
    excluded = collections.defaultdict(set)
    old_ids = {r["persee_id"] for r in rows(ALIGN / "data/annotations.jsonl")}

    def add(v, p):
        if p:
            root = re.sub(r"/(?:p|head|note|list)(?:\[.*)?$", "", p)
            excluded[v].add(root)

    for r in rows(PILOT / "data/documents.jsonl"):
        for p in r["divisions"]:
            add(r["volume"], p)
    for name in ["reference-documents.jsonl", "non-detection-windows.jsonl"]:
        for r in rows(V1 / "data" / name):
            add(r["volume"], r.get("source_xpath"))
            for p in r.get("xpaths", []):
                add(r["volume"], p)
    for r in read(V1 / "data/additional-parent-decisions.json"):
        add(r["volume"], r["source_xpath"])
    for name in ["reference-candidates.jsonl", "validation-zones.jsonl", "reference-parents.jsonl"]:
        for r in rows(V2 / "data" / name):
            add(r["volume"], r.get("xpath"))
            for p in r.get("xpaths", []):
                add(r["volume"], p)
    for r in rows(ALIGN / "data/alignment-predictions.jsonl"):
        for c in r.get("candidates", [])[:1]:
            add(r["volume"], c["xpath"])
    for r in rows(ALIGN / "data/annotations.jsonl"):
        add(r["volume"], r.get("target_xpath"))
        for p in (r.get("boundary_reference") or {}).get("divisions", []):
            add(r["volume"], p)
    registry = rows(HERE / "data/registry-automatic.jsonl")

    def unseen(r):
        return r["persee_id"] not in old_ids and all(
            c["xpath"] not in excluded[r["metadata"]["volume"]] for c in r["candidates"][:1]
        )

    frame = [r for r in registry if unseen(r)]
    chosen = []
    quotas = {1: 8, 2: 18, 3: 20, 4: 18, 5: 18, 6: 18}
    for v, n in quotas.items():
        available = [r for r in frame if r["metadata"]["volume"] == v]
        groups = collections.defaultdict(list)
        for r in available:
            groups[r["alignment_status"]].append(r)
        for g in groups.values():
            g.sort(key=lambda r: sha(SEED + r["id"]))
        chosen_v = []
        while len(chosen_v) < min(n, len(available)):
            for status in ["non_retrouve", "ambigu", "probable", "hors_perimetre", "fort"]:
                if groups[status] and len(chosen_v) < n:
                    chosen_v.append(groups[status].pop(0))
        chosen += chosen_v
    if len(chosen) < 100:
        remaining = sorted(
            [r for r in frame if r not in chosen], key=lambda r: sha(SEED + "topup" + r["id"])
        )
        chosen += remaining[: 100 - len(chosen)]
    chosen.sort(key=lambda r: (r["metadata"]["volume"], r["metadata"]["catalogue_order"]))
    selected = []
    for i, r in enumerate(chosen, 1):
        selected.append(
            dict(
                index=i,
                persee_id=r["persee_id"],
                volume=r["metadata"]["volume"],
                stratum=r["alignment_status"],
                selection="volume quota; deterministic hash within status; difficult strata oversampled",
                prediction_sha256=sha(__import__("json").dumps(r, ensure_ascii=False)),
                novelty="not previously examined identity nor primary source leaf; automatic earlier processing does not constitute review",
            )
        )
        for c in r["candidates"][:1]:
            add(r["metadata"]["volume"], c["xpath"])
    jlines(HERE / "data/validation-sample.jsonl", selected)
    # Independent continuous source windows: one whole short leaf, and an adjacent pair where possible; catalogue not used to rank.
    zones = []
    for v, s in ss.items():
        leaves = base.leaf_records(s)
        available = []
        for i, leaf in enumerate(leaves):
            if leaf["xpath"] in excluded[v] or leaf["end"] - leaf["start"] > 18000:
                continue
            nxt = leaves[i + 1] if i + 1 < len(leaves) else None
            paths = [leaf["xpath"]]
            end = leaf["end"]
            if nxt and nxt["xpath"] not in excluded[v] and nxt["end"] - leaf["start"] <= 18000:
                paths.append(nxt["xpath"])
                end = nxt["end"]
            if end - leaf["start"] < 500:
                continue
            available.append(
                dict(
                    volume=v,
                    start=leaf["start"],
                    end=end,
                    xpaths=paths,
                    key=sha(SEED + "zone" + str(v) + leaf["xpath"]),
                )
            )
        used = []
        for z in sorted(available, key=lambda z: z["key"]):
            if any(z["start"] < b and z["end"] > a for a, b in used):
                continue
            z["id"] = f"registry-zone-v{v}-{len(used) + 1}"
            zones.append(z)
            used.append((z["start"], z["end"]))
            if len(used) == 2:
                break
    jlines(HERE / "data/validation-zones.jsonl", zones)
    files = [
        "registry_rules.py",
        "build.py",
        "lib.py",
        "prepare_review.py",
        "data/registry-automatic.jsonl",
        "data/validation-sample.jsonl",
        "data/validation-zones.jsonl",
    ]
    save(
        HERE / "data/freeze.json",
        dict(
            seed=SEED,
            params=PARAMS,
            files={p: sha((HERE / p).read_bytes()) for p in files},
            sources={v: s.sha256 for v, s in ss.items()},
            rules_must_not_change_after_review=True,
            annotator="Codex; separate evaluation, not blind nor independent human",
            identity_reference="source titles/opening/closing and neighbours; ambiguity retained",
            boundary_reference="exact source positions only when both ends actually inspected; otherwise not assessed",
            bounds_whitespace="exact half-open span or adjacent XML whitespace only; substantive end changes count errors",
            sample_size=len(selected),
            frame_size=len(frame),
            by_volume=dict(collections.Counter(r["volume"] for r in selected)),
            by_status=dict(collections.Counter(r["stratum"] for r in selected)),
            zones=len(zones),
            novelty_excluded_source_paths={v: sorted(ps) for v, ps in excluded.items()},
            known_persee_ids=sorted(old_ids),
        ),
    )
    print("Frozen", len(selected), "notices", len(zones), "zones; frame", len(frame))


if __name__ == "__main__":
    main()
