"""Inventaire exhaustif des signaux documentaires des six XML, avant sélection."""

import collections
import datetime
import re
import time

from common import HERE, VERSION, compact, jlines, pages, sha, source_ref, sources, write
from rules import CONT, INTRO, MENTION, TITLE, classify


def main():
    clock = time.perf_counter()
    ss = sources()
    candidates = []
    groups = []
    for volume, s in ss.items():
        # All levels owning text are examined; nested containers are not duplicated.
        divisions = s.tree.xpath("//text/body//*[starts-with(local-name(),'div')][p or head]")
        for node in divisions:
            xp = s.tree.getpath(node)
            heads = node.findall("head")
            ps = node.findall("p")
            title = " ".join(compact(h) for h in heads)
            opening = " ".join(compact(p) for p in ps[:2])
            a, b = s.span(node)
            structural = bool(ps) and not bool(node.xpath('./*[starts-with(local-name(),"div")]'))
            signals = (
                bool(MENTION.search(title + " " + opening))
                or TITLE.match(title)
                or CONT.match(title)
            )
            if signals:
                kind, evidence = classify(title, opening, b - a, structural)
                cid = "candidate-" + sha(f"{s.sha256}|{xp}|{a}")[:20]
                item = dict(
                    id=cid,
                    volume=volume,
                    xpath=xp,
                    anchor_xpath=xp,
                    start=a,
                    end=b,
                    divisions=[xp],
                    title=title,
                    opening=opening[:600],
                    signals=evidence,
                    classification=kind,
                    structural_leaf=structural,
                    pages=pages(s, a, b),
                    source=source_ref(s),
                    uncertainties=[],
                    internal=False,
                )
                candidates.append(item)
                if kind == "document_candidate":
                    groups.append(item)
            # Look for new documents announced inside plain paragraphs.
            for pi, p in enumerate(ps):
                text = compact(p)
                if pi >= 2 and TITLE.match(text) and len(text) < 230:
                    following = compact(ps[pi + 1]) if pi + 1 < len(ps) else ""
                    if not (INTRO.match(following) or len(text) < 40):
                        continue
                    pa, pb = s.span(p)
                    px = s.tree.getpath(p)
                    kind, evidence = classify(text, following, b - pa, True)
                    item = dict(
                        id="candidate-" + sha(f"{s.sha256}|{px}|{pa}")[:20],
                        volume=volume,
                        xpath=xp,
                        anchor_xpath=px,
                        start=pa,
                        end=b,
                        divisions=[xp],
                        title=text,
                        opening=following[:600],
                        signals=evidence + ["internal_paragraph_heading"],
                        classification=kind,
                        structural_leaf=True,
                        pages=pages(s, pa, b),
                        source=source_ref(s),
                        uncertainties=["internal_title_requires_validation"],
                        internal=True,
                    )
                    candidates.append(item)
                    if kind == "document_candidate":
                        groups.append(item)
                elif MENTION.search(text) and pi >= 2:
                    pa, pb = s.span(p)
                    px = s.tree.getpath(p)
                    candidates.append(
                        dict(
                            id="mention-" + sha(f"{s.sha256}|{px}|{pa}")[:20],
                            volume=volume,
                            xpath=xp,
                            anchor_xpath=px,
                            start=pa,
                            end=pb,
                            divisions=[xp],
                            title=None,
                            opening=text[:240],
                            signals=["body_mention_only"],
                            classification="incidental_mention",
                            pages=pages(s, pa, pb),
                            uncertainties=["not_a_document_start_by_itself"],
                            internal=True,
                        )
                    )
    byanchor = {
        (c["volume"], c["xpath"]): c
        for c in candidates
        if c["classification"] != "incidental_mention" and not c["internal"]
    }
    # Sibling continuations are grouped; internal starts split their enclosing division.
    for g in groups:
        s = ss[g["volume"]]
        node = s.node(g["xpath"])
        internal = sorted(
            [
                c
                for c in groups
                if c["volume"] == g["volume"]
                and c["xpath"] == g["xpath"]
                and c["start"] > g["start"]
            ],
            key=lambda c: c["start"],
        )
        if internal:
            g["end"] = internal[0]["start"]
            g["uncertainties"].append("split_at_internal_title")
        else:
            for sibling in node.itersiblings():
                if not isinstance(sibling.tag, str) or not sibling.tag.startswith("div"):
                    continue
                sx = s.tree.getpath(sibling)
                c = byanchor.get((g["volume"], sx))
                if not c or c["classification"] != "continuation":
                    break
                g["divisions"].append(sx)
                g["end"] = s.span(sibling)[1]
                c["attached_to_candidate"] = g["id"]
            if len(g["divisions"]) > 1:
                g["uncertainties"].append("composite_document_hypothesis")
        g["pages"] = pages(s, g["start"], g["end"])
        text = s.text[g["start"] : g["end"]]
        g["characters"] = len(text)
        g["non_whitespace_characters"] = sum(not c.isspace() for c in text)
        title_context = g["title"] + " " + g["opening"][:300]
        estate = re.search(r"\b(clerg[ée]|noblesse|tiers[ -][ée]tat)\b", title_context, re.I)
        g["estate_explicit"] = estate.group().casefold() if estate else None
        g["classification_status"] = "automatic_unverified"
    candidates.sort(key=lambda c: (c["volume"], c["start"], c["id"]))
    jlines(HERE / "data/candidates.jsonl", candidates)
    write(
        HERE / "data/inventory-summary.json",
        dict(
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            method=VERSION,
            candidates=len(candidates),
            classifications=dict(collections.Counter(c["classification"] for c in candidates)),
            per_volume={
                str(v): dict(
                    collections.Counter(c["classification"] for c in candidates if c["volume"] == v)
                )
                for v in ss
            },
            document_candidates=len(groups),
            seconds=time.perf_counter() - clock,
            inventory_sha256=sha((HERE / "data/candidates.jsonl").read_bytes()),
            selection_performed=False,
        ),
    )
    print(
        "Inventory",
        len(candidates),
        "signals;",
        len(groups),
        "document hypotheses; before selection",
    )


if __name__ == "__main__":
    main()
