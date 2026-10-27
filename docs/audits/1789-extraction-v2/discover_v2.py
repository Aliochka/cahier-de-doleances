"""Prédictions V2: six classes, liens de dossier et bornes sans correction manuelle."""

import collections
import time

from common import HERE, compact, jlines, pages, sha, source_ref, sources, write
from fast_blocks import cache_nodes
from rules_v2 import BEGIN, PROFESSIONAL, classify, fold, title_of


def predict(ss, allowed=None):
    result = []
    roots = {}
    for volume, s in ss.items():
        leaves = s.tree.xpath(
            '//text/body//*[starts-with(local-name(),"div")][p and not(*[starts-with(local-name(),"div")])]'
        )
        for node in leaves:
            xp = s.tree.getpath(node)
            if allowed is not None and (volume, xp) not in allowed:
                continue
            a, b = s.span(node)
            title, opening = title_of(node)
            kind, subtype, evidence = classify(node, title, opening)
            cid = "candidate-" + sha(f"{s.sha256}|{xp}|{a}")[:20]
            item = dict(
                id=cid,
                volume=volume,
                xpath=xp,
                anchor_xpath=xp,
                start=a,
                end=b,
                source_span=[a, b],
                divisions=[xp],
                title=title,
                classification=kind,
                subtype=subtype,
                evidence=evidence,
                internal=False,
                uncertainties=[] if kind != "uncertain" else ["document_identity_not_established"],
            )
            result.append(item)
            roots[volume, xp] = item
            ps = node.findall("p")
            for i, p in enumerate(ps[2:], 2):
                text = compact(p)
                f = fold(text)
                if not (BEGIN.match(f) or (f.startswith("MEMOIRE") and PROFESSIONAL.search(f))):
                    continue
                if len(text) > 600 and not f.startswith("CAHIER"):
                    continue
                following = " ".join(compact(q) for q in ps[i + 1 : i + 3])
                ck, st, ev = classify(node, text, following, True, kind)
                pa, pb = s.span(p)
                px = s.tree.getpath(p)
                child = dict(
                    id="candidate-" + sha(f"{s.sha256}|{px}|{pa}")[:20],
                    volume=volume,
                    xpath=xp,
                    anchor_xpath=px,
                    start=pa,
                    end=b,
                    source_span=[pa, b],
                    divisions=[xp],
                    title=text,
                    classification=ck,
                    subtype=st,
                    evidence=ev,
                    internal=True,
                    enclosing_candidate_id=cid,
                    uncertainties=["internal_document_boundary_hypothesis"]
                    if ck in {"autonomous", "associated"}
                    else [],
                )
                result.append(child)
    # All strong internal starts delimit one another; rubrics do not split parents.
    for (v, xp), root in roots.items():
        children = sorted(
            [
                r
                for r in result
                if r["volume"] == v
                and r["xpath"] == xp
                and r["internal"]
                and r["classification"] in {"autonomous", "associated"}
            ],
            key=lambda r: r["start"],
        )
        if children:
            root["end"] = children[0]["start"]
            root["uncertainties"].append("internal_documents_separated")
        for i, c in enumerate(children):
            c["end"] = children[i + 1]["start"] if i + 1 < len(children) else c["source_span"][1]
    for (v, xp), root in roots.items():
        if root["classification"] not in {"autonomous", "associated"} or root.get("attached_to"):
            continue
        s = ss[v]
        node = s.node(xp)
        for sibling in node.itersiblings():
            if not isinstance(sibling.tag, str) or not sibling.tag.startswith("div"):
                continue
            sx = s.tree.getpath(sibling)
            r = roots.get((v, sx))
            if not r:
                break
            attach = r["classification"] == "part" or (
                r["classification"] == "associated"
                and fold(r["title"]).startswith(
                    ("DEMANDES PARTICULIERES", "TRAVAIL", "SUPPLEMENT AU")
                )
            )
            if not attach:
                break
            root["divisions"].append(sx)
            root["end"] = r["end"]
            r["attached_to"] = root["id"]
            root["uncertainties"].append("continuation_or_associated_piece_attached")
    for r in result:
        s = ss[r["volume"]]
        r["pages"] = pages(s, r["start"], r["end"])
        r["source"] = source_ref(s)
        r["verification_status"] = "automatic_not_certified"
    return sorted(result, key=lambda r: (r["volume"], r["start"], r["id"]))


def main():
    clock = time.perf_counter()
    ss = sources()
    for s in ss.values():
        cache_nodes(s)
    result = predict(ss)
    jlines(HERE / "data/v2-document-predictions.jsonl", result)
    counts = collections.Counter(r["classification"] for r in result)
    write(
        HERE / "data/v2-discovery-summary.json",
        dict(
            records=len(result),
            classifications=dict(counts),
            per_volume={
                str(v): dict(
                    collections.Counter(r["classification"] for r in result if r["volume"] == v)
                )
                for v in ss
            },
            seconds=time.perf_counter() - clock,
            all_automatic_unverified=True,
        ),
    )
    print(dict(counts))


if __name__ == "__main__":
    main()
