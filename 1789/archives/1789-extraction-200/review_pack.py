# ruff: noqa: E402
"""Dossiers source sans prédiction d'articles ; annotations conservées séparément."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import frozen_match  # noqa: E402

import datetime

from common import CACHE, HERE, compact, read, rows, sha, sources, write


def main():
    freeze = read(HERE / "freeze.json")
    assert all(frozen_match(HERE / p, h) for p, h in freeze["files"].items())
    ss = sources()
    selected = rows(HERE / "data/selection.jsonl")
    protocol = read(HERE / "protocol.json")
    CACHE.mkdir(exist_ok=True)
    for v, s in ss.items():
        lines = []
        for c in selected:
            if c["volume"] != v or c["id"] not in protocol["validation_ids"]:
                continue
            node = s.node(c["xpath"])
            ps = node.findall("p")
            lines.append(f"\nCANDIDATE {c['id']} SOURCE {c['xpath']}\n")
            lines.append("HEADS: " + " | ".join(compact(h) for h in node.findall("head")) + "\n")
            # Parent context and all short internal headings, first and final p.
            for side, neighbors in [
                ("PREVIOUS", list(node.itersiblings(preceding=True))[:1]),
                ("NEXT", list(node.itersiblings())[:1]),
            ]:
                for n in neighbors:
                    lines.append(side + ": " + compact(n)[:500] + "\n")
            ids = sorted(
                set(
                    list(range(min(16, len(ps))))
                    + list(range(max(0, len(ps) - 5), len(ps)))
                    + [i for i, p in enumerate(ps) if len(compact(p)) < 140]
                )
            )
            for i in ids:
                lines.append(f"p[{i + 1}] {compact(ps[i])}\n")
            lines.append(
                f"END SOURCE: {len(ps)} p; all omitted middle paragraphs remain in original XML\n"
            )
        (CACHE / f"validation-v{v}.txt").write_text("".join(lines))
    negatives = rows(HERE / "data/non-detection-windows.jsonl")
    for v in ss:
        lines = []
        for w in negatives:
            if w["volume"] != v:
                continue
            lines.append("\n" + w["id"] + "\n")
            for xp in w["xpaths"]:
                lines.append(xp + " " + compact(ss[v].node(xp)) + "\n")
        (CACHE / f"negative-v{v}.txt").write_text("".join(lines))
    # Read-only source bookends for the remaining selected hypotheses.
    lines = []
    for i, c in enumerate(selected):
        s = ss[c["volume"]]
        node = s.node(c["xpath"])
        ps = node.findall("p")
        context = " | ".join(compact(h) for h in node.xpath("ancestor::div2/head"))
        lines.append(
            f"[{i + 1}] {c['id']} V{c['volume']} {c['xpath']} | {c['title']} | CONTEXT {context}\n"
        )
        lines.append("FIRST " + " | ".join(compact(p) for p in ps[:2])[:460] + "\n")
        lines.append("LAST " + " | ".join(compact(p) for p in ps[-2:])[:520] + "\n")
    (CACHE / "all-bookends.txt").write_text("".join(lines))
    write(
        HERE / "data/review-pack-provenance.json",
        dict(
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_only=True,
            new_article_predictions_exist=(HERE / "data/automatic-units.jsonl").exists(),
            cache=str(CACHE),
            files={p.name: sha(p.read_bytes()) for p in CACHE.glob("*.txt")},
            human_time_seconds=None,
        ),
    )
    print("Source review packs ready; no new article predictions generated")


if __name__ == "__main__":
    main()
