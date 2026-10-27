"""Compare les prédictions gelées aux références gelées, sans modifier les règles."""

import datetime
import time

from common import HERE, V1, jlines, pages, read, rows, sha, source_ref, sources, write
from discover_v2 import predict
from fast_blocks import blocks, cache_nodes
from rules import segment as segment_v1
from rules_v2 import role_blocks, segment


def verify_freezes():
    for name in ["rules-freeze.json", "reference-freeze.json"]:
        for p, h in read(HERE / name)["files"].items():
            assert sha((HERE / p).read_bytes()) == h, (name, p)


def main():
    verify_freezes()
    clock = time.perf_counter()
    ss = sources()
    for s in ss.values():
        cache_nodes(s)
    candidates = rows(HERE / "data/reference-candidates.jsonl")
    zones = rows(HERE / "data/reference-zones.jsonl")
    gold = rows(HERE / "data/reference-parents.jsonl")
    articles = rows(HERE / "data/reference-articles.jsonl")
    allowed = {(c["volume"], c["xpath"]) for c in candidates}
    for z in rows(HERE / "data/validation-zones.jsonl"):
        allowed |= {(z["volume"], p) for p in z["xpaths"]}
    # Context is source-only immediate neighbours; counts remain restricted to registered zones/candidates.
    for v, p in list(allowed):
        n = ss[v].node(p)
        for sibling in list(n.itersiblings(preceding=True))[:1] + list(n.itersiblings())[:2]:
            if (
                isinstance(sibling.tag, str)
                and sibling.tag.startswith("div")
                and sibling.find("p") is not None
            ):
                allowed.add((v, ss[v].tree.getpath(sibling)))
    p2 = predict(ss, allowed)
    jlines(HERE / "data/validation-v2-predictions.jsonl", p2)
    p1 = [
        r for r in rows(V1 / "data/candidates.jsonl") if r["classification"] == "document_candidate"
    ]
    jlines(
        HERE / "data/validation-v1-predictions.jsonl",
        [r for r in p1 if any(r["volume"] == v and r["xpath"] == p for v, p in allowed)],
    )

    def admitted(p, version, scope):
        return (
            p["classification"] == "document_candidate"
            if version == "v1"
            else p["classification"]
            in ({"autonomous"} if scope == "strict" else {"autonomous", "associated"})
        )

    candidate_comparison = []
    for g in candidates:
        a = next(
            (r for r in p1 if r["volume"] == g["volume"] and r["anchor_xpath"] == g["xpath"]), None
        )
        b = next(
            (r for r in p2 if r["volume"] == g["volume"] and r["anchor_xpath"] == g["xpath"]), None
        )
        candidate_comparison.append(
            dict(
                g,
                v1_class=a["classification"] if a else "not_admitted",
                v2_class=b["classification"] if b else "not_proposed",
                v2_subtype=b["subtype"] if b else None,
                v1_id=a["id"] if a else None,
                v2_id=b["id"] if b else None,
            )
        )
    jlines(HERE / "data/candidate-comparison.jsonl", candidate_comparison)
    metrics = {"candidates": {}, "continuous_zones": {}, "articles": {}}
    parentcmp = []
    for scope in ["strict", "inclusive"]:
        kinds = {"autonomous"} if scope == "strict" else {"autonomous", "associated"}
        metrics["candidates"][scope] = {}
        for ver in ["v1", "v2"]:
            rr = [r for r in candidate_comparison if r["novel"]]
            tp = fp = fn = tn = 0
            for r in rr:
                truth = r["classification"] in kinds
                pred = r[f"{ver}_class"] in (kinds if ver == "v2" else {"document_candidate"})
                tp += truth and pred
                fp += not truth and pred
                fn += truth and not pred
                tn += not truth and not pred
            metrics["candidates"][scope][ver] = dict(
                n=len(rr),
                tp=tp,
                fp=fp,
                fn=fn,
                tn=tn,
                precision=tp / (tp + fp) if tp + fp else None,
                recall=tp / (tp + fn) if tp + fn else None,
            )
        metrics["continuous_zones"][scope] = {}
        for ver, preds in [("v1", p1), ("v2", p2)]:
            tp = fp = fn = correct_end = 0
            fused = truncated = 0
            for z in zones:
                gg = [g for g in gold if g["zone_id"] == z["id"] and g["classification"] in kinds]
                pp = [
                    p
                    for p in preds
                    if p["volume"] == z["volume"]
                    and z["start"] <= p["start"] < z["end"]
                    and admitted(p, ver, scope)
                ]
                matches = {
                    g["id"]: next((p for p in pp if p["start"] == g["start"]), None) for g in gg
                }
                matched = {p["id"] for p in matches.values() if p}
                tp += len(matched)
                fp += sum(p["id"] not in matched for p in pp)
                fn += sum(p is None for p in matches.values())
                for g in gg:
                    p = matches[g["id"]]
                    sameend = bool(p and p["end"] == g["end"])
                    correct_end += sameend
                    truncated += bool(p and p["end"] < g["end"])
                    parentcmp.append(
                        dict(
                            scope=scope,
                            version=ver,
                            zone_id=z["id"],
                            gold_id=g["id"],
                            predicted_id=p["id"] if p else None,
                            start_correct=bool(p),
                            end_correct=sameend,
                            expected_start=g["start"],
                            expected_end=g["end"],
                            predicted_start=p["start"] if p else None,
                            predicted_end=p["end"] if p else None,
                        )
                    )
                for p in pp:
                    fused += (
                        sum(
                            p["start"] <= g["start"] < p["end"]
                            for g in gold
                            if g["zone_id"] == z["id"]
                        )
                        > 1
                    )
            metrics["continuous_zones"][scope][ver] = dict(
                tp=tp,
                fp=fp,
                fn=fn,
                precision=tp / (tp + fp) if tp + fp else None,
                recall=tp / (tp + fn) if tp + fn else None,
                correct_beginnings=tp,
                correct_ends=correct_end,
                end_denominator=tp,
                both_correct=correct_end,
                fused_predictions=fused,
                truncated_matched_parents=truncated,
            )
    jlines(HERE / "data/parent-boundary-comparison.jsonl", parentcmp)
    # Article evaluation is conditional on SOURCE reference parents, to isolate segmentation from detection.
    allunits = []
    unitcmp = []
    parents = []
    for g in gold:
        s = ss[g["volume"]]
        a, b = g["start"], g["end"]
        par = dict(
            g,
            text=s.text[a:b],
            source=source_ref(s),
            pages=pages(s, a, b),
            status="A_XML_review_not_historical_certification",
            blocks=role_blocks(s, g),
        )
        parents.append(par)
        for ver, fn, blockfn in [("v1", segment_v1, blocks), ("v2", segment, role_blocks)]:
            for u in fn(s, blockfn(s, g)):
                uid = "unit-" + sha(f"{s.sha256}|{g['id']}|{u['start']}|{u['end']}|{ver}")[:20]
                exact = next(
                    (
                        r
                        for r in articles
                        if r["parent_id"] == g["id"]
                        and (r["start"], r["end"]) == (u["start"], u["end"])
                    ),
                    None,
                )
                allunits.append(
                    dict(
                        u,
                        id=uid,
                        version=ver,
                        parent_id=g["id"],
                        volume=g["volume"],
                        text=s.text[u["start"] : u["end"]],
                        parent_start=u["start"] - a,
                        parent_end=u["end"] - a,
                        source=source_ref(s),
                        pages=pages(s, u["start"], u["end"]),
                        status="A" if exact else "B",
                        verification="Codex reference comparison"
                        if exact
                        else "proposed_not_certified",
                        reference_id=exact["id"] if exact else None,
                    )
                )
    for ver in ["v1", "v2"]:
        pp = [u for u in allunits if u["version"] == ver]
        exact = starts = ends = missed = fusions = trunc = 0
        for g in articles:
            overlap = [
                u
                for u in pp
                if u["parent_id"] == g["parent_id"]
                and u["start"] < g["end"]
                and u["end"] > g["start"]
            ]
            ex = any((u["start"], u["end"]) == (g["start"], g["end"]) for u in overlap)
            st = any(u["start"] == g["start"] for u in overlap)
            en = any(u["end"] == g["end"] for u in overlap)
            exact += ex
            starts += st
            ends += en
            missed += not st
            fu = any(u["start"] < g["start"] or u["end"] > g["end"] for u in overlap)
            fusions += not ex and fu
            tr = any(u["start"] > g["start"] or u["end"] < g["end"] for u in overlap)
            trunc += not ex and tr
            unitcmp.append(
                dict(
                    version=ver,
                    reference_id=g["id"],
                    parent_id=g["parent_id"],
                    label=g["label"],
                    volume=g["volume"],
                    start=g["start"],
                    end=g["end"],
                    exact=ex,
                    start_correct=st,
                    end_correct=en,
                    overlap_ids=[u["id"] for u in overlap],
                )
            )
        totalchars = sum(g["end"] - g["start"] for g in articles)
        covered = sum(
            g["end"] - g["start"]
            for g in articles
            if any(
                u["parent_id"] == g["parent_id"]
                and (u["start"], u["end"]) == (g["start"], g["end"])
                for u in pp
            )
        )
        metrics["articles"][ver] = dict(
            reference_units=len(articles),
            exact=exact,
            exact_proportion=exact / len(articles),
            correct_starts=starts,
            correct_ends=ends,
            missing_starts=missed,
            nonexact_with_overextension=fusions,
            nonexact_with_underextension=trunc,
            reference_characters=totalchars,
            characters_in_exact_units=covered,
            coverage_on_reviewed_text=covered / totalchars,
            all_gold_implicitly_correct_after_reference_substitution=len(articles),
            scope="79 deliberately reviewed units in continuous zones; not all articles and not a blind independent human assessment",
        )
    jlines(HERE / "data/article-boundary-comparison.jsonl", unitcmp)
    jlines(HERE / "data/reference-parent-texts.jsonl", parents)
    jlines(HERE / "data/validation-article-predictions.jsonl", allunits)
    metrics.update(
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        seconds=time.perf_counter() - clock,
        annotation="Codex non-independent XML examination; no independent human timing measured",
        rules_sha256=sha((HERE / "rules_v2.py").read_bytes()),
        reference_sha256=sha((HERE / "reference-freeze.json").read_bytes()),
        frozen_rules_unchanged=True,
    )
    write(HERE / "data/evaluation-metrics.json", metrics)
    print(metrics)


if __name__ == "__main__":
    main()
