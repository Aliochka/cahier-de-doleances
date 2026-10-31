"""Sélection déterministe après inventaire ; gel avant annotation de validation."""

import collections
import datetime

from common import HERE, PILOT, compact, jlines, read, rows, sha, sources, write


def key(value):
    return sha("selection-1789-200-v1|" + value)


def main():
    assert not (HERE / "freeze.json").exists(), "Protocol already frozen; no reselection"
    old = rows(PILOT / "data/documents.jsonl")
    cs = rows(HERE / "data/candidates.jsonl")
    ss = sources()
    pec = read(HERE / "data/development-regression.json")["pecqueuse"]["candidate_id"]
    frame = []
    excluded = []
    for c in cs:
        if c["classification"] != "document_candidate":
            continue
        overlap = [
            d["key"]
            for d in old
            if d["volume"] == c["volume"]
            and d["source_text_start"] < c["end"]
            and d["source_text_end"] > c["start"]
        ]
        if overlap or c["id"] == pec:
            excluded.append(
                dict(
                    candidate_id=c["id"],
                    reason="development_overlap",
                    development_keys=overlap or ["pecqueuse"],
                )
            )
        else:
            frame.append(c)
    grouped = {
        v: sorted([c for c in frame if c["volume"] == v], key=lambda c: (c["characters"], c["id"]))
        for v in ss
    }
    quotas = {v: min(28, len(g)) for v, g in grouped.items()}
    while sum(quotas.values()) < 170:
        for v in ss:
            if quotas[v] < len(grouped[v]) and sum(quotas.values()) < 170:
                quotas[v] += 1
    selected = []
    for v, group in grouped.items():
        cells = collections.defaultdict(list)
        for rank, c in enumerate(group):
            c["length_stratum"] = min(2, 3 * rank // len(group))
            c["structure_stratum"] = (
                "internal"
                if c["internal"]
                else "composite"
                if len(c["divisions"]) > 1
                else "standard"
            )
            cell = (
                c["length_stratum"],
                c["estate_explicit"] or "unspecified",
                c["structure_stratum"],
            )
            c["selection_cell"] = list(cell)
            cells[cell].append(c)
        for cell in cells:
            cells[cell].sort(key=lambda c: key(c["id"]))
        chosen = []
        while len(chosen) < quotas[v]:
            for cell in sorted(cells):
                if cells[cell] and len(chosen) < quotas[v]:
                    chosen.append(cells[cell].pop(0))
        selected.extend(chosen)
    # One ordinary shorter and one longer/structurally difficult document per volume.
    validation = []
    for v in ss:
        group = [c for c in selected if c["volume"] == v]
        short = [c for c in group if c["length_stratum"] == 0] or group
        first = min(short, key=lambda c: key("validation-short|" + c["id"]))
        difficult = [
            c
            for c in group
            if c["id"] != first["id"]
            and (c["structure_stratum"] != "standard" or c["length_stratum"] == 2)
        ]
        second = min(
            difficult or [c for c in group if c["id"] != first["id"]],
            key=lambda c: key("validation-difficult|" + c["id"]),
        )
        validation.extend([first["id"], second["id"]])
    for c in selected:
        c["validation_split"] = "held_out" if c["id"] in validation else "unreviewed_new"
    jlines(HERE / "data/selection.jsonl", selected)
    write(HERE / "data/selection-exclusions.json", excluded)
    # Negative coverage: raw windows outside all accepted document hypotheses.
    windows = []
    for v, s in ss.items():
        accepted = [
            c for c in cs if c["volume"] == v and c["classification"] == "document_candidate"
        ]
        eligible = []
        for node in s.tree.xpath("//text/body//p"):
            a, b = s.span(node)
            if 100 < b - a < 5000 and not any(c["start"] <= a < c["end"] for c in accepted):
                eligible.append(node)
        eligible.sort(key=lambda n: key("negative|" + str(v) + "|" + s.tree.getpath(n)))
        for n in eligible:
            siblings = n.getparent().findall("p")
            i = siblings.index(n)
            chosen = siblings[max(0, i - 2) : i + 4]
            a, b = s.span(chosen[0])[0], s.span(chosen[-1])[1]
            if any(w["volume"] == v and w["start"] < b and w["end"] > a for w in windows):
                continue
            windows.append(
                dict(
                    id=f"negative-v{v}-{sum(w['volume'] == v for w in windows) + 1}",
                    volume=v,
                    start=a,
                    end=b,
                    xpaths=[s.tree.getpath(x) for x in chosen],
                    selection="hashed raw paragraph outside accepted hypotheses; context two preceding and three following p",
                    text=s.text[a:b],
                )
            )
            if sum(w["volume"] == v for w in windows) == 2:
                break
    jlines(HERE / "data/non-detection-windows.jsonl", windows)
    protocol = dict(
        version="discovery-200-v1",
        inventory_before_selection=True,
        selected_new=170,
        inherited=30,
        quotas=quotas,
        selection="round-robin over volume x length tercile x explicit estate word x structural type; within cell SHA256 order; no query or manual title choice",
        seed_string="selection-1789-200-v1",
        selection_is_statistically_representative=False,
        development="30 prior parents plus Pecqueuse; excluded from held-out inference",
        validation_ids=validation,
        validation_method="2 selected new candidates per volume: hashed short and hashed difficult/long",
        article_reference="source-only windows annotated before new segmentation predictions; limited windows, not assumed complete parent article counts",
        negative_windows=[w["id"] for w in windows],
        negative_sampling="conditional on non-detection, not global recall sampling",
        no_tuning_after_validation=True,
        judge="Codex; separate from development, not independent human or a blind historical validation",
        status_A="only reviewed exact boundaries or inherited previous A; never regular numbering alone",
        human_validation_seconds=None,
    )
    write(HERE / "protocol.json", protocol)
    frozen = [
        "common.py",
        "rules.py",
        "pilot_segment.py",
        "discover.py",
        "select.py",
        "protocol.json",
        "data/candidates.jsonl",
        "data/selection.jsonl",
        "data/non-detection-windows.jsonl",
    ]
    write(
        HERE / "freeze.json",
        dict(
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            new_article_predictions_examined=False,
            validation_reference_created=False,
            files={p: sha((HERE / p).read_bytes()) for p in frozen},
        ),
    )
    print(
        "Selected",
        len(selected),
        "new candidates; quotas",
        quotas,
        "held out",
        len(validation),
        "negative windows",
        len(windows),
    )


if __name__ == "__main__":
    main()
