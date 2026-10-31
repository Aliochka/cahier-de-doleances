"""Fenêtres fondées sur pages Persée, indépendantes des bornes A ; aucune troncature cachée."""

import collections
import re

from qcommon import HERE, REG, jlines, preserve, read, rows, save, sha, source_helpers

VERSION = "qwen-boundary-windows-1.0"
SEED = "qwen-boundary-validation-2026-10-27-v1"


def main():
    preserve()
    lib = source_helpers()
    ss = lib.sources()
    registry = rows(REG / "data/registry.jsonl.gz")
    lookup = {r["persee_id"]: r for r in registry}
    annotations = rows(REG / "data/annotations.jsonl")
    allold = set(read(REG / "data/freeze.json")["known_persee_ids"]) | {
        a["persee_id"] for a in annotations
    }
    excluded = {
        int(v): set(ps)
        for v, ps in read(REG / "data/freeze.json")["novelty_excluded_source_paths"].items()
    }
    for a in annotations:
        for p in [a.get("source_xpath"), (a.get("manually_recovered_location") or {}).get("xpath")]:
            if p:
                excluded[a["volume"]].add(re.sub(r"/(?:p|head|note|list)(?:\[.*)?$", "", p))
    for z in rows(REG / "data/validation-zones.jsonl"):
        excluded[z["volume"]].update(z["xpaths"])
    frame = [
        r
        for r in registry
        if r["persee_id"] not in allold
        and r["boundaries"]["proposal"]
        and r["document_kind"] in {"cahier_autonome_probable", "document_associe", "proces_verbal"}
        and r["candidates"][0]["xpath"] not in excluded[r["metadata"]["volume"]]
    ]
    validation = []
    for v in range(1, 7):
        candidates = [r for r in frame if r["metadata"]["volume"] == v]
        groups = collections.defaultdict(list)
        for r in candidates:
            groups[
                "complex"
                if r["review_priority"] == "haute"
                or r["boundaries"]["status"] == "ambigues"
                or r["alignment_status"] != "fort"
                else "simple"
            ].append(r)
        for rs in groups.values():
            rs.sort(key=lambda r: sha(SEED + r["id"]))
        selected = []
        while len(selected) < min(6, len(candidates)):
            for g in ["complex", "simple"]:
                if groups[g] and len(selected) < 6:
                    selected.append(groups[g].pop(0))
        validation += selected
    if len(validation) < 36:
        rest = sorted(
            [r for r in frame if r not in validation], key=lambda r: sha(SEED + "extra" + r["id"])
        )
        validation += rest[: 36 - len(validation)]
    assert len(validation) == 36
    dev_ids = [
        a["persee_id"]
        for a in annotations
        if a["boundary_judgment"] == "incorrect" or a["index"] in {5, 14, 35, 66, 81, 88, 26}
    ]
    for suffix in ["2_1_1578", "6_1_2581"]:
        dev_ids.append(
            next(r["persee_id"] for r in registry if r["persee_id"].endswith("_" + suffix))
        )
    development = [lookup[i] for i in dict.fromkeys(dev_ids)]
    plans = []
    blocks_by_volume = {}
    at_by_volume = {}
    for v, s in ss.items():
        _, at = lib.base.page_index(s)
        at_by_volume[v] = at
        blocks = []
        for n in s.tree.xpath(
            "//text/body//*[self::p or self::head or self::note or self::pb][not(ancestor::p or ancestor::head or ancestor::note)]"
        ):
            a, b = s.span(n)
            text = s.text[a:b]
            if n.tag != "pb" and not text.strip():
                continue
            blocks.append(
                dict(
                    id=f"v{v}-b{len(blocks) + 1:06d}",
                    xpath=s.tree.getpath(n),
                    start=a,
                    end=b,
                    tag=n.tag,
                    text=text,
                    page=at(a).get("page"),
                    page_method=at(a).get("method"),
                    pb=dict(n.attrib) if n.tag == "pb" else None,
                )
            )
        blocks_by_volume[v] = blocks
    windows = []
    for split, records in [
        ("development", development),
        (
            "validation",
            sorted(
                validation,
                key=lambda r: (r["metadata"]["volume"], r["metadata"]["catalogue_order"]),
            ),
        ),
    ]:
        for i, r in enumerate(records, 1):
            v = r["metadata"]["volume"]
            m = r["metadata"]
            blocks = blocks_by_volume[v]
            wanted = {m["page_start"], m["page_end"]}
            indices = {i for i, b in enumerate(blocks) if b["page"] in wanted}
            expanded = set()
            for j in indices:
                expanded.update(range(max(0, j - 6), min(len(blocks), j + 7)))
            selected = [blocks[j] for j in sorted(expanded)]
            gaps = []
            for left, right in zip(sorted(expanded), sorted(expanded)[1:]):
                if right - left > 1:
                    gaps.append(
                        dict(
                            start=blocks[left]["end"],
                            end=blocks[right]["start"],
                            omitted_blocks=right - left - 1,
                            reason="middle_not_in_boundary_windows",
                        )
                    )
            b = r["boundaries"]["proposal"]
            content = [n for n in blocks if n["tag"] != "pb" and n["end"] > n["start"]]
            inside = [n for n in content if b and n["start"] >= b["start"] and n["end"] <= b["end"]]
            baseline = dict(
                raw=b,
                start_id=inside[0]["id"] if inside else None,
                end_id=inside[-1]["id"] if inside else None,
            )
            available = {n["id"] for n in selected}
            baseline["start_visible"] = baseline["start_id"] in available
            baseline["end_visible"] = baseline["end_id"] in available
            neighbours = []
            ids = [r["catalogue_neighbours"]["previous_id"], r["catalogue_neighbours"]["next_id"]]
            for other in registry:
                if other["id"] in ids:
                    neighbours.append(
                        dict(
                            title=other["metadata"]["title"],
                            pages=[other["metadata"]["page_start"], other["metadata"]["page_end"]],
                            persee_id=other["persee_id"],
                        )
                    )
            w = dict(
                id=f"{split}-{i:02d}",
                split=split,
                persee_id=r["persee_id"],
                volume=v,
                title=m["title"],
                pages=[m["page_start"], m["page_end"]],
                metadata={
                    k: m[k]
                    for k in [
                        "id",
                        "title",
                        "page_start",
                        "page_end",
                        "volume",
                        "document_url",
                        "bibliographic_reference",
                    ]
                    if k in m
                },
                source=r["source"],
                blocks=selected,
                omissions=gaps,
                first_or_last_page_missing=not all(
                    any(n["page"] == pg for n in selected) for pg in wanted
                ),
                known_neighbours=neighbours,
                baseline=baseline,
                selection="development known errors and controls"
                if split == "development"
                else "deterministic volume/complexity stratification; excludes reviewed IDs and source leaves",
                prompt_context_no_A=True,
            )
            windows.append(w)
            plans.append(
                {
                    k: w[k]
                    for k in ["id", "split", "persee_id", "volume", "title", "pages", "selection"]
                }
            )
    jlines(HERE / "data/windows.jsonl", windows)
    save(HERE / "data/selection.json", plans)
    # Block map preserves exact source positions; text stays only in the limited windows.
    used = {v: {n["id"] for w in windows if w["volume"] == v for n in w["blocks"]} for v in ss}
    jlines(
        HERE / "data/block-locators.jsonl",
        [
            dict(volume=v, **{k: b[k] for k in ["id", "xpath", "start", "end", "tag", "page"]})
            for v, bs in blocks_by_volume.items()
            for b in bs
            if b["id"] in used[v]
        ],
    )
    save(
        HERE / "data/preparation.json",
        dict(
            version=VERSION,
            seed=SEED,
            development=len(development),
            validation=len(validation),
            eligible_frame=len(frame),
            by_volume=dict(collections.Counter(r["metadata"]["volume"] for r in validation)),
            no_document_replacement=True,
            window_rule="all blocks on metadata first and last printed pages, expanded six complete blocks each side; omitted middle explicitly recorded; no text truncation",
            source_hashes={v: s.sha256 for v, s in ss.items()},
            prior_review_exclusions={v: sorted(x) for v, x in excluded.items()},
        ),
    )
    print(
        "Prepared",
        len(development),
        "development and",
        len(validation),
        "validation windows",
        flush=True,
    )


if __name__ == "__main__":
    main()
