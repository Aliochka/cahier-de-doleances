"""Dossiers de lecture source; aucune prédiction V1/V2 affichée."""

from common import CACHE, HERE, compact, rows, sha, sources, write


def main():
    assert (HERE / "rules-freeze.json").exists()
    ss = sources()
    CACHE.mkdir(exist_ok=True)
    for v, s in ss.items():
        lines = []
        for z in rows(HERE / "data/validation-zones.jsonl"):
            if z["volume"] != v:
                continue
            lines.append(f"\nZONE {z['id']} [{z['start']},{z['end']})\n")
            for xp in z["xpaths"]:
                n = s.node(xp)
                lines.append("DIVISION " + xp + "\n")
                for child in n:
                    if isinstance(child.tag, str):
                        lines.append(s.tree.getpath(child) + " " + compact(child) + "\n")
            lines.append("END COMPLETE CONTINUOUS ZONE\n")
        (CACHE / f"zones-v{v}.txt").write_text("".join(lines))
        lines = []
        for c in rows(HERE / "data/validation-candidates.jsonl"):
            if c["volume"] != v:
                continue
            n = s.node(c["xpath"])
            ps = n.findall("p")
            lines.append(f"\nCANDIDATE {c['id']} {c['xpath']} {c['length']} characters\n")
            for h in n.findall("head"):
                lines.append("HEAD " + compact(h) + "\n")
            for tag, neighbors in [
                ("PREVIOUS", list(n.itersiblings(preceding=True))[:1]),
                ("NEXT", list(n.itersiblings())[:1]),
            ]:
                for x in neighbors:
                    lines.append(
                        tag
                        + " HEAD "
                        + " | ".join(compact(h) for h in x.findall("head"))
                        + " FIRST "
                        + (" ".join(compact(p) for p in x.findall("p")[:1]))[:300]
                        + "\n"
                    )
            indices = sorted(
                set(
                    list(range(min(10, len(ps))))
                    + list(range(max(0, len(ps) - 4), len(ps)))
                    + [i for i, p in enumerate(ps) if len(compact(p)) < 120]
                )
            )
            for i in indices:
                lines.append(f"p[{i + 1}] " + compact(ps[i]) + "\n")
            lines.append(f"END {len(ps)} p; omitted middle not claimed fully read\n")
        (CACHE / f"candidates-v{v}.txt").write_text("".join(lines))
    write(
        HERE / "data/validation-pack-provenance.json",
        dict(
            source_only=True,
            rules_frozen_before_reading=True,
            zone_inspection="all text and all blocks, complete continuous source intervals",
            candidate_inspection="heads, first10 and final4 p, all short p; not complete OCR collation",
            files={p.name: sha(p.read_bytes()) for p in CACHE.glob("*.txt")},
            predictions_created=False,
            cache=str(CACHE),
        ),
    )
    print("Source-only validation packs ready")


if __name__ == "__main__":
    main()
