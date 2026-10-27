"""Ajoute les contrôles explicites sans réécrire les prédictions gelées."""

import bisect
import collections
import copy
import json
import re

from lib import (
    ALIGN,
    HERE,
    PILOT,
    V1,
    V2,
    compact,
    jlines,
    read,
    rows,
    save,
    sha,
    sources,
)


def main():
    ss = sources()
    rr = rows(HERE / "data/registry-automatic.jsonl")
    lookup = {r["persee_id"]: r for r in rr}
    sample = rows(HERE / "data/validation-sample.jsonl")
    decisions = read(HERE / "review_decisions.json")
    annotations = []
    for t in sample:
        r = lookup[t["persee_id"]]
        identity, bounds, kind, reason = decisions[str(t["index"])]
        s = ss[t["volume"]]
        c = r["candidates"][0] if r["candidates"] else None
        b = r["boundaries"]["proposal"]
        n = s.node(c["xpath"]) if c else None
        annotations.append(
            dict(
                persee_id=t["persee_id"],
                index=t["index"],
                volume=t["volume"],
                identity_judgment=identity,
                boundary_judgment=bounds,
                document_kind_reference=kind,
                reason=reason,
                source_sha256=s.sha256,
                source_xpath=c["xpath"] if c else None,
                source_anchor=c["anchor_xpath"] if c else None,
                reference_boundary=copy.deepcopy(b) if bounds == "correct" else None,
                evidence_quotes=[compact(n)[:500], compact(n)[-500:]] if n is not None else [],
                scope="source title, opening/closing, short rubrics and immediate neighbours; not full text collation or facsimile verification",
                reviewer="Codex exploratory documentary control, sees frozen predictions; not independent human",
                original_prediction_status=r["alignment_status"],
            )
        )
    targets = read(HERE / "review_targets.json")
    for a in annotations:
        target = targets.get(str(a["index"]))
        if target:
            sv, path = target
            s = ss[sv]
            n = s.node(path)
            a["manually_recovered_location"] = dict(
                xpath=path,
                start=s.span(n)[0],
                end=s.span(n)[1],
                text_quote=compact(n)[:500],
                is_exact_parent_boundary=False,
            )
    jlines(HERE / "data/annotations.jsonl", annotations)
    aa = {a["persee_id"]: a for a in annotations}
    inherited = {a["persee_id"]: a for a in rows(ALIGN / "data/annotations.jsonl")}
    v2 = rows(V2 / "data/v2-document-predictions.jsonl")
    v2byid = {v["id"]: v for v in v2}
    # Technical ranges and documentary furniture are pointers, never copied/rewritten articles.
    indexes = {}
    for v, s in ss.items():
        nodes = []
        for p in s.tree.xpath("//text/body//p | //text/body//head | //text/body//note"):
            a, b = s.span(p)
            nodes.append((a, b, s.tree.getpath(p), p.tag, compact(p)[:180]))
        nodes.sort()
        indexes[v] = (nodes, [x[0] for x in nodes])
    crosswalk = []
    pilot = rows(PILOT / "data/documents.jsonl")
    review = []
    final = []
    for r0 in rr:
        r = copy.deepcopy(r0)
        v = r["metadata"]["volume"]
        s = ss[v]
        b = r["boundaries"]["proposal"]
        nodes, starts = indexes[v]
        r["controls"] = []
        if r["persee_id"] in inherited:
            a = inherited[r["persee_id"]]
            r["controls"].append(
                dict(
                    origin="1789-persee-stanford-alignment/data/annotations.jsonl",
                    annotation=a,
                    novel_validation=False,
                )
            )
            ref = a.get("boundary_reference")
            if ref:
                r["boundaries"]["verified_reference"] = ref
                r["boundaries"]["verification"] = "inherited_Codex_control_not_independent"
                r["boundaries"]["status"] = "verifiees"
                r["boundaries"]["active_reference_range"] = [ref["start"], ref["end"]]
        a = aa.get(r["persee_id"])
        if a:
            r["controls"].append(
                dict(origin="data/annotations.jsonl", annotation=a, novel_validation=True)
            )
            r["alignment_verification"] = "Codex_review_" + a["identity_judgment"]
            r["document_kind_reference"] = a["document_kind_reference"]
            if a["boundary_judgment"] == "correct":
                r["boundaries"]["verified_reference"] = a["reference_boundary"]
                r["boundaries"]["verification"] = "new_Codex_control_not_independent"
                r["boundaries"]["status"] = "verifiees"
                r["boundaries"]["active_reference_range"] = [b["start"], b["end"]]
            elif a["boundary_judgment"] in {"incorrect", "uncertain"}:
                r["boundaries"]["status"] = "ambigues"
                r["anomalies"].append("new_control_boundary_" + a["boundary_judgment"])
            if a["identity_judgment"] in {"incorrect", "false_exclusion"}:
                r["anomalies"].append("new_control_identity_error")
                r["alignment_verification"] = "Codex_error_found_not_corrected"
        if b:
            r["boundaries"]["source_slice_sha256"] = sha(s.text[b["start"] : b["end"]])
            i = bisect.bisect_left(starts, b["start"])
            j = bisect.bisect_left(starts, b["end"])
            within = nodes[max(0, i - 1) : j + 1]
            within = [n for n in within if n[0] < b["end"] and n[1] > b["start"]]
            r["boundaries"]["locator"] = dict(
                start_xpath=within[0][2] if within else None,
                end_xpath=within[-1][2] if within else None,
                start_offset=b["start"],
                end_offset_exclusive=b["end"],
                source_sha256=s.sha256,
            )
            r["page_references"] = s.pages_for(b["start"], b["end"])
            r["structure_proposals"] = dict(
                notes=[
                    dict(xpath=n[2], start=n[0], end=n[1], role="XML_note")
                    for n in within
                    if n[3] == "note"
                ],
                sections=[
                    dict(
                        xpath=n[2],
                        start=n[0],
                        end=n[1],
                        heading=n[4],
                        status="XML_or_rubric_proposal_not_verified",
                    )
                    for n in within
                    if n[3] == "head"
                    or (
                        n[3] == "p"
                        and re.match(
                            r"^(?:CHAPITRE|SECTION|PREMIÈRE PARTIE|SECONDE PARTIE|SUPPLÉMENT|ANNEXE)",
                            n[4],
                        )
                    )
                ],
                signatures_certifications=[
                    dict(
                        xpath=n[2],
                        start=n[0],
                        end=n[1],
                        status="lexical_hint_not_separated_or_verified",
                    )
                    for n in within
                    if n[3] == "p"
                    and re.match(
                        r"^(?:Signé|Signés|Collationné|Certifi|Paraphé|Fait et arrêté)",
                        n[4],
                    )
                ],
            )
            for old in pilot:
                if old["volume"] != v:
                    continue
                oa = old["source_text_start"]
                ob = old["source_text_end"]
                if b["start"] < ob and b["end"] > oa:
                    relation = (
                        "exact_range"
                        if (oa, ob) == (b["start"], b["end"])
                        else "overlap_only_not_identity_certification"
                    )
                    crosswalk.append(
                        dict(
                            previous_id=old["id"],
                            previous_key=old["key"],
                            registry_id=r["id"],
                            relation=relation,
                            previous_range=[oa, ob],
                            new_range=[b["start"], b["end"]],
                            source_sha256=s.sha256,
                        )
                    )
        if a and a["document_kind_reference"] != r["document_kind"]:
            r["anomalies"].append("new_control_classification_disagreement")
        for zone in rows(HERE / "data/zone-annotations.jsonl"):
            if zone["zone_id"] in {"registry-zone-v2-1", "registry-zone-v2-2"} and any(
                r["primary_anchor"] == q["xpath"] and v == zone["volume"] for q in zone["reference"]
            ):
                r["anomalies"].append("new_control_source_composite_or_interleaved_columns")
                r["boundaries"]["status"] = "ambigues"
        if r["v2_match"]:
            vp = v2byid[r["v2_match"]["id"]]
            r["v2_match"]["document_kind_disagreement"] = (
                r["document_kind"] == "cahier_autonome_probable"
                and vp["classification"] != "autonomous"
            )
            crosswalk.append(
                dict(
                    previous_id=vp["id"],
                    registry_id=r["id"],
                    relation="same_anchor_not_boundary_equivalence",
                    same_bounds=r["v2_match"]["same_bounds"],
                )
            )
        reasons = []
        if r["alignment_status"] in {"ambigu", "non_retrouve"}:
            reasons.append("identity_" + r["alignment_status"])
        if any("multiple" in x or "new_control" in x for x in r["anomalies"]):
            reasons.append("contradiction_or_observed_error")
        if r["v2_match"] and not r["v2_match"]["same_bounds"]:
            reasons.append("V2_boundary_disagreement")
        if b and (len(b["divisions"]) > 1 or r["candidates"][0]["internal"]):
            reasons.append("composite_or_internal_start")
        if r["document_kind"] == "notice_absence":
            reasons.append("absence_scope_must_be_checked")
        if reasons:
            priority = "haute"
        elif r["alignment_status"] == "probable" or r["boundaries"]["status"] in {
            "ambigues",
            "non_etablies",
        }:
            priority = "intermediaire"
            reasons.append("probable_or_boundary_not_established")
        else:
            priority = "echantillonnage"
            reasons.append("strong_simple_or_excluded_document_control")
        if r["boundaries"]["status"] != "verifiees":
            reasons.append("boundary_not_certified")
        review.append(
            dict(
                id=r["id"],
                persee_id=r["persee_id"],
                volume=v,
                title=r["metadata"]["title"],
                priority=priority,
                reasons=reasons,
                alignment=r["alignment_status"],
                boundary_status=r["boundaries"]["status"],
                automatically_validated=False,
            )
        )
        r["review_priority"] = priority
        final.append(r)
    # Compare every V2 hypothesis without silently merging a contained piece into a catalogue document.
    match = collections.defaultdict(list)
    for r in rr:
        if r["primary_anchor"]:
            match[(r["metadata"]["volume"], r["primary_anchor"])].append(r["id"])
    comparison = []
    complement = []
    for p in v2:
        equivalent = match[(p["volume"], p["anchor_xpath"])]
        containing = [
            r["id"]
            for r in rr
            if r["metadata"]["volume"] == p["volume"]
            and r["boundaries"]["proposal"]
            and r["boundaries"]["proposal"]["start"]
            <= p["start"]
            < r["boundaries"]["proposal"]["end"]
        ]
        d = dict(
            stanford_id=p["id"],
            volume=p["volume"],
            title=p["title"],
            classification=p["classification"],
            anchor_xpath=p["anchor_xpath"],
            start=p["start"],
            end=p["end"],
            source=p["source"],
            matching_registry_anchors=equivalent,
            contained_by_proposals=containing,
            admitted_V2=p["classification"] in {"autonomous", "associated"},
            identity_verified=False,
        )
        comparison.append(d)
        if d["admitted_V2"] and not equivalent:
            d = dict(
                d,
                complement_status="part_of_proposed_dossier_or_unmatched"
                if containing
                else "Stanford_only_hypothesis",
                review_priority="haute",
                not_proof_of_missing_Persée_document=True,
            )
            complement.append(d)
    jlines(HERE / "data/registry.jsonl", final)
    jlines(HERE / "data/stanford-comparison.jsonl", comparison)
    jlines(HERE / "data/stanford-complement.jsonl", complement)
    jlines(HERE / "data/id-crosswalk.jsonl", crosswalk)
    jlines(HERE / "data/review-queue.jsonl", review)
    jlines(
        HERE / "data/stanford-uncertain.jsonl",
        [p for p in comparison if p["classification"] == "uncertain"],
    )
    previous_register = read(V1 / "data/register.json")
    legacy = []
    for old in previous_register:
        a = old["source_text_start"]
        b = old["source_text_end"]
        matches = []
        for r in rr:
            n = r["boundaries"]["proposal"]
            if n and r["metadata"]["volume"] == old["volume"] and n["start"] < b and n["end"] > a:
                matches.append(
                    dict(
                        registry_id=r["id"],
                        relation="exact_range"
                        if (n["start"], n["end"]) == (a, b)
                        else "overlap_not_certified_identity",
                    )
                )
        legacy.append(
            dict(
                previous_id=old["id"],
                previous_legacy_id=old.get("legacy_document_id"),
                origin="1789-extraction-200/data/register.json",
                source_sha256=old["source_sha256"],
                volume=old["volume"],
                previous_range=[a, b],
                matches=matches,
                status="references_preserved_no_automatic_id_replacement",
            )
        )
    jlines(HERE / "data/previous-document-crosswalk.jsonl", legacy)
    metrics = dict(
        sample=len(annotations),
        identity=dict(collections.Counter(a["identity_judgment"] for a in annotations)),
        boundary=dict(collections.Counter(a["boundary_judgment"] for a in annotations)),
        classification_disagreements=[
            a["index"]
            for a in annotations
            if a["document_kind_reference"] != lookup[a["persee_id"]]["document_kind"]
        ],
        by_status={
            status: dict(
                collections.Counter(
                    a["identity_judgment"]
                    for a in annotations
                    if a["original_prediction_status"] == status
                )
            )
            for status in sorted({a["original_prediction_status"] for a in annotations})
        },
        review_priority=dict(collections.Counter(x["priority"] for x in review)),
        final_boundary=dict(collections.Counter(r["boundaries"]["status"] for r in final)),
        complement=len(complement),
        v2_total=len(v2),
        v2_admitted=sum(c["admitted_V2"] for c in comparison),
        metadata_anomalies=dict(
            collections.Counter(x for r in rr for x in r["metadata"]["anomalies"])
        ),
        by_volume={
            v: dict(
                notices=sum(r["metadata"]["volume"] == v for r in rr),
                v2_admitted=sum(c["volume"] == v and c["admitted_V2"] for c in comparison),
                v2_complement=sum(c["volume"] == v for c in complement),
            )
            for v in ss
        },
        new_boundary_controls=[
            a["index"] for a in annotations if a["boundary_judgment"] in {"correct", "incorrect"}
        ],
        no_independent_human_validation=True,
    )
    save(HERE / "data/evaluation-metrics.json", metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
