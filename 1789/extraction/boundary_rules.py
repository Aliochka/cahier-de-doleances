"""Conservative documentary repairs: explicit names, XML openings and catalogue neighbours.

No OCR correction, source mutation or human annotation. Every applied change has evidence.
"""

import re
import unicodedata
from collections import Counter, defaultdict

VERSION = "documentary-boundaries-1"
GENERIC = set(
    "cahier cahiers de des du la le les d l et en au aux sur sous pour dans par avec trois ordres ordre general generale communaute communautes paroisse ville habitants noblesse clerge tiers etat bailliage baillage senechaussee senechaussees district province comte pays territoire doléances doleances plaintes remontrances liste comparants declaration deliberation instructions demandes assemblee proces verbal annexe sieur messire proprietaire fief corps quelques premier departement intra muros hors murs".split()
)
OPENING = re.compile(
    r"^(?:cahier|doleances|plaintes|remontrances|pouvoirs|instructions|demandes|voeux|liste|proces verbal|declaration|deliberation|copie|articles et limitations)\b"
)


def fold(text):
    text = "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def names(title):
    return [
        w for w in fold(re.sub(r"\([^)]*\)", "", title)).split() if len(w) >= 3 and w not in GENERIC
    ]


def estates(text):
    return set(re.findall(r"\b(?:clerge|noblesse|tiers)\b", fold(text)))


def exact_name(word, text):
    # Match typographical splitting (Saint- Victoret, Er-, mont), not fuzzy OCR substitutions.
    letters = "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
    )
    return bool(re.search(r"(?<![a-z])" + r"[^a-z]*".join(word) + r"(?![a-z])", letters))


def identity(record, anchor):
    wanted = names(record["metadata"]["title"])
    if not wanted or not all(exact_name(w, anchor["title"]) for w in wanted):
        return False
    kind = record.get("document_kind_reference") or record["document_kind"]
    observed_title = fold(anchor["title"])
    if kind == "liste" and not observed_title.startswith(("liste ", "tableau ")):
        return False
    if kind == "cahier_autonome_probable" and not (
        re.match(r"^(?:cahier|doleances|plaintes|remontrances|voeux)\b", observed_title)
        or re.search(r"\bcahier\b", observed_title)
    ):
        return False
    if (
        "trois ordres" in fold(record["metadata"]["title"])
        and "trois ordres" not in observed_title
        and estates(anchor["title"]) != {"clerge", "noblesse", "tiers"}
    ):
        return False
    expected = estates(record["metadata"]["title"])
    observed = estates(anchor["title"])
    if expected and not expected <= observed:
        return False
    return True


def anchors(store, volume):
    source = store.sources[volume]
    at = store.lib.base.page_index(source)[1]
    result = []
    for leaf in store.lib.base.leaf_records(source):
        n = leaf["node"]
        hs, ps = n.findall("head"), n.findall("p")
        heading = " ".join(store.lib.compact(h) for h in hs)
        # Limited opening context, explicit and never used to replace historical text.
        opening = heading + " " + " ".join(store.lib.compact(p) for p in ps[:2])
        title = opening[:900] if len(heading) < 120 else heading
        first = hs[0] if hs else ps[0]
        result.append(
            dict(
                start=leaf["start"],
                end=leaf["end"],
                xpath=leaf["xpath"],
                title=title,
                page=at(source.span(first)[0])["page"],
                explicit=bool(OPENING.match(fold(title))),
                internal=False,
            )
        )
        for i, p in enumerate(ps):
            t = store.lib.compact(p)
            a, z = source.span(p)
            if i < 2 or len(t) > 800 or not OPENING.match(fold(t)):
                continue
            # Only short title blocks can borrow their continuation from the next block.
            title = t
            if len(t) < 100 and i + 1 < len(ps):
                title += " " + store.lib.compact(ps[i + 1])[:500]
            result.append(
                dict(
                    start=a,
                    end=leaf["end"],
                    xpath=source.tree.getpath(p),
                    title=title,
                    page=at(a)["page"],
                    explicit=True,
                    internal=True,
                )
            )
    return result


def span_pair(state):
    p = state.get("selected") or {}
    return p.get("start"), p.get("end")


def plan(store):
    """Propose bounded repairs and retain all initial states and unresolved observations."""
    latest = store.latest()
    indices = {v: anchors(store, v) for v in store.sources}
    ats = {v: store.lib.base.page_index(src)[1] for v, src in store.sources.items()}
    states = {r["id"]: store.state(r, latest) for r in store.records}
    findings, matches = {}, {}
    for r in store.records:
        key, m = r["id"], r["metadata"]
        initial = states[key]
        row = dict(
            document_id=key,
            persee_id=r["persee_id"],
            volume=m["volume"],
            original_span=initial["selected"],
            selected=initial["selected"],
            original_alignment=r["alignment_status"],
            alignment=r["alignment_status"],
            source_sha256=store.sources[m["volume"]].sha256,
            version=VERSION,
            actions=[],
            resolved_alerts=[],
            conflicts=[],
            evidence=[],
        )
        findings[key] = row
        if (r.get("document_kind_reference") or r["document_kind"]) == "notice_absence":
            row["category"] = "absence_notice_not_an_extraction_failure"
            continue
        opts = [
            a
            for a in indices[m["volume"]]
            if a["page"] == m["page_start"] and a["explicit"] and identity(r, a)
        ]
        # A leaf opening and an internal title may both match. Abstain, never first-hit choice.
        if len(opts) == 1:
            candidate = opts[0]
            matches[key] = candidate
            current = initial["selected"] or {}
            start = current.get("start")
            near_current = (
                start is not None
                and abs(start - candidate["start"]) < 100
                and not store.sources[m["volume"]]
                .text[min(start, candidate["start"]) : max(start, candidate["start"])]
                .strip()
            )
            if (
                (near_current or start == candidate["start"])
                and initial["status"] == "proposed"
                and r["alignment_status"] in {"ambigu", "probable"}
            ):
                row["alignment"] = "fort"
                row["evidence"].append(
                    dict(reason="unique_exact_opening_identity", opening=candidate)
                )
            if not near_current and start != candidate["start"]:
                suggestion = dict(start=candidate["start"], end=candidate["end"])
                # Human events, including uncertain decisions, always take precedence.
                if initial["event"] or initial["stale"]:
                    row["conflicts"].append(
                        dict(reason="human_decision_has_priority", proposed=suggestion)
                    )
                elif initial["status"] == "codex_reviewed":
                    row["conflicts"].append(
                        dict(reason="prior_examined_reference_requires_review", proposed=suggestion)
                    )
                elif (
                    not current
                    or r["alignment_status"] in {"ambigu", "non_retrouve"}
                    or "same_primary_anchor_multiple_notices" in r["anomalies"]
                ):
                    row["selected"] = store.span_view(r, suggestion)
                    row["alignment"] = "fort"
                    row["actions"].append("unique_explicit_opening_name_estate_and_page")
                    row["evidence"].append(candidate)
        elif len(opts) > 1:
            row["conflicts"].append(dict(reason="multiple_exact_openings", alternatives=opts))
        # Retain a correctly identified current start as a neighbour even if several openings match.
        current = row["selected"] or {}
        if key not in matches and current.get("start") is not None:
            opts = [
                a
                for a in indices[m["volume"]]
                if a["explicit"] and abs(a["start"] - current["start"]) < 100 and identity(r, a)
            ]
            if len(opts) == 1:
                matches[key] = opts[0]

    # Repair a broad leaf only at an independently identified, later catalogue document.
    grouped = defaultdict(list)
    for r in store.records:
        if r["id"] in matches:
            grouped[r["metadata"]["volume"]].append(r)
    for r in store.records:
        row, state, m = findings[r["id"]], states[r["id"]], r["metadata"]
        current = row["selected"] or {}
        if current.get("start") is None:
            continue
        kind = r.get("document_kind_reference") or r["document_kind"]
        candidates = []
        for other in grouped[m["volume"]]:
            a = matches[other["id"]]
            om = other["metadata"]
            okind = other.get("document_kind_reference") or other["document_kind"]
            # No automatic parent/annex splitting, shared text or overlapping pagination.
            if kind != "cahier_autonome_probable" or okind != "cahier_autonome_probable":
                continue
            if (
                current["start"] < a["start"] < current["end"]
                and om["catalogue_order"] > m["catalogue_order"]
                and m["page_end"] <= om["page_start"]
                and (findings[other["id"]]["selected"] or {}).get("start") == a["start"]
            ):
                candidates.append((a["start"], other, a))
        if candidates:
            _, other, anchor = min(candidates, key=lambda x: x[0])
            # Do not skip an intervening catalogue opening whose identity remains unresolved.
            intervening = [
                x
                for x in store.records
                if x["metadata"]["volume"] == m["volume"]
                and m["catalogue_order"]
                < x["metadata"]["catalogue_order"]
                < other["metadata"]["catalogue_order"]
                and (findings[x["id"]]["selected"] or {}).get("start") is not None
                and current["start"]
                < (findings[x["id"]]["selected"] or {})["start"]
                < anchor["start"]
            ]
            if intervening:
                row["conflicts"].append(
                    dict(
                        reason="intervening_notice_requires_review",
                        document_ids=[x["id"] for x in intervening],
                    )
                )
                continue
            # Another explicit document title, not an article or a page-only cut.
            suggested = dict(start=current["start"], end=anchor["start"])
            if state["event"] or state["stale"] or state["status"] == "codex_reviewed":
                row["conflicts"].append(
                    dict(
                        reason="protected_boundary_not_changed",
                        proposed=suggested,
                        next_document_id=other["id"],
                    )
                )
            else:
                row["selected"] = store.span_view(r, suggested)
                row["actions"].append("stop_before_identified_next_cahier")
                row["evidence"].append(
                    dict(
                        next_document_id=other["id"],
                        opening=anchor,
                        metadata_end_page=m["page_end"],
                        next_start_page=other["metadata"]["page_start"],
                    )
                )

    # Recompute only precisely testable historical alerts, retaining their original evidence.
    for r in store.records:
        row, state, m = findings[r["id"]], states[r["id"]], r["metadata"]
        span = row["selected"]
        if span:
            a, z = span["start"], span["end"]
            source = store.sources[m["volume"]]
            tail = z
            while tail > a and source.text[tail - 1].isspace():
                tail -= 1
            content_page = ats[m["volume"]](tail - 1)["page"]
            old_flags = set(r["anomalies"]) | set(
                (r["boundaries"].get("proposal") or {}).get("flags", [])
            )
            if "new_control_boundary_incorrect" in old_flags and state["status"] in {
                "codex_reviewed",
                "human_validated",
            }:
                proposal = r["boundaries"].get("proposal") or {}
                if (a, z) != (proposal.get("start"), proposal.get("end")):
                    row["resolved_alerts"].append(
                        dict(
                            code="new_control_boundary_incorrect",
                            reason="previous_source_examined_reference_already_replaced_the_incorrect_original_proposal",
                            reference_origin=state["origin"],
                        )
                    )
            if content_page == m["page_end"] and "end_page_mismatch_requires_review" in old_flags:
                row["resolved_alerts"].append(
                    dict(
                        code="end_page_mismatch_requires_review",
                        reason="last_non_whitespace_source_character_matches_metadata_end_page",
                        end_page=content_page,
                        last_content_offset=tail - 1,
                    )
                )
            # New explicit XML/name proof resolves identity ambiguity only if matching is unique.
            if (
                r["id"] in matches
                and row["alignment"] == "fort"
                and (row["actions"] or r["alignment_status"] == "ambigu")
            ):
                for code in ["identity_ambigu"]:
                    if code == "identity_ambigu" or code in old_flags:
                        row["resolved_alerts"].append(
                            dict(
                                code=code,
                                reason="unique_explicit_opening_identity_with_source_evidence",
                            )
                        )
        row["changed"] = span_pair(dict(selected=row["selected"])) != span_pair(state)
    groups = defaultdict(list)
    for row in findings.values():
        if row["selected"]:
            groups[row["volume"], row["selected"]["start"]].append(row["document_id"])
    for r in store.records:
        row = findings[r["id"]]
        if (
            row["selected"]
            and len(groups[row["volume"], row["selected"]["start"]]) == 1
            and "same_primary_anchor_multiple_notices" in r["anomalies"]
            and r["id"] in matches
        ):
            row["resolved_alerts"].append(
                dict(
                    code="same_primary_anchor_multiple_notices",
                    reason="final_selected_openings_distinct_and_explicit_name_matches",
                )
            )
    return list(findings.values())


def effective(record, resolution):
    """Derived extraction view; registry bytes and documentary classifications are untouched."""
    if not resolution:
        return record
    resolved = {r["code"] for r in resolution["resolved_alerts"]}
    r = {
        **record,
        "alignment_status": resolution["alignment"],
        "anomalies": [a for a in record["anomalies"] if a not in resolved],
        "boundaries": {
            **record["boundaries"],
            "proposal": dict(record["boundaries"].get("proposal") or {}),
        },
    }
    r["boundaries"]["proposal"]["flags"] = [
        a for a in r["boundaries"]["proposal"].get("flags", []) if a not in resolved
    ]
    return r


def summary(rows):
    return dict(
        changed_documents=sum(r["changed"] for r in rows),
        actions=dict(Counter(a for r in rows for a in r["actions"])),
        resolved_alerts=dict(Counter(a["code"] for r in rows for a in r["resolved_alerts"])),
        documents_with_conflicts=sum(bool(r["conflicts"]) for r in rows),
    )
