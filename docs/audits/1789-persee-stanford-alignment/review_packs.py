"""Packs locaux de contrôle, sans accès réseau et sans transcription Persée."""

from auditlib import HERE, compact, jlines, load_sources, rows, save, sha


def main():
    ss = load_sources()
    packs = []
    for r in rows(HERE / "data/alignment-predictions.jsonl"):
        s = ss[r["volume"]]
        c = r["candidates"][0] if r["candidates"] else None
        lines = [
            f"ID {r['persee_id']} | {r['selection']} | {r['title']} | pages {r['metadata_pages']} | type {r['metadata_type']}\n",
            f"Prediction {r['status']}, margin {r['margin']}\n",
        ]
        if c:
            n = s.node(c["xpath"])
            ps = n.findall("p")
            lines += [f"TOP {c['anchor_xpath']} score {c['score']} title {c['title'][:550]}\n"]
            for index in sorted(
                set([0, 1, 2, max(0, len(ps) - 3), max(0, len(ps) - 2), max(0, len(ps) - 1)])
            ):
                if index < len(ps):
                    lines.append(f"p[{index + 1}] {compact(ps[index])[:650]}\n")
            for path in (r.get("boundary") or {}).get("divisions", [])[1:]:
                q = s.node(path)
                qp = q.findall("p")
                lines.append(
                    "ATTACHED "
                    + path
                    + " "
                    + " | ".join(compact(h) for h in q.findall("head"))
                    + "\n"
                )
                if qp:
                    lines.append(
                        "opening "
                        + compact(qp[0])[:260]
                        + "\nclosing "
                        + compact(qp[-1])[:350]
                        + "\n"
                    )
            for sib in list(n.itersiblings(preceding=True))[:1] + list(n.itersiblings())[:1]:
                if isinstance(sib.tag, str) and sib.tag.startswith("div"):
                    lines.append(
                        "NEIGHBOUR "
                        + s.tree.getpath(sib)
                        + " "
                        + " | ".join(compact(h) for h in sib.findall("head"))
                        + " "
                        + (" ".join(compact(p) for p in sib.findall("p")[:1]))[:160]
                        + "\n"
                    )
            lines.append(
                "ALTERNATIVES "
                + str(
                    [
                        (x["anchor_xpath"], x["score"], x["title"][:130])
                        for x in r["candidates"][1:3]
                    ]
                )
                + "\n"
            )
        packs.append(dict(id=r["persee_id"], volume=r["volume"], text="".join(lines)))
    jlines(HERE / ".cache/review-packs.jsonl", packs)
    for v in range(1, 7):
        (HERE / ".cache" / f"review-v{v}.txt").write_text(
            "\n".join(p["text"] for p in packs if p["volume"] == v)
        )
    save(
        HERE / "data/review-pack-provenance.json",
        dict(
            file_sha256=sha((HERE / ".cache/review-packs.jsonl").read_bytes()),
            reviewer="Codex, sees predictions; not independent human or blind reference",
            scope="title, first3/last3 source paragraphs, attached sections, adjacent headings and alternatives; full-body collation only when explicitly logged",
        ),
    )


if __name__ == "__main__":
    main()
