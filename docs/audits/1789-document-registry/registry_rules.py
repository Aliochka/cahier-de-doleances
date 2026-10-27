"""Adaptations du rapprochement existant, développées sur les 72 contrôles seulement."""

import re
from lib import base, compact, fold

VERSION = "registry-alignment-1.0"
PARAMS = dict(
    version=VERSION,
    min_score=0.62,
    strong_score=0.78,
    strong_margin=0.10,
    ambiguous_margin=0.10,
    keep_candidates=5,
    keep_tiers_token=True,
    body_evidence_scope="first4_last3_paragraphs_only",
    body_evidence_for_fallback=True,
)
# Correct the known loss of tiers; only this loaded copy changes, never historical files.
base.STOP = base.STOP - {"tiers"}
MISSING = re.compile(
    r"(?:cahier|documents?).{0,100}(?:manque\b|nous manquent|ne se trouv.{0,20}pas)|(?:impossible|n.avons pu).{0,80}(?:trouver|retrouver)",
    re.I,
)
ASSOCIATED = re.compile(
    r"\b(?:medecins|chirurgiens|apothicaires|procureurs|notaires|marchands|corporations?|maitres|artisans|perruquiers|charcutiers|beneficiers|eveque|secondaires|officiers)\b"
)


def document_kind(title):
    t = fold(title)
    if t.startswith(("liste ", "tableau ", "table ")):
        return "liste", "metadata_title_explicit_list"
    if t.startswith(("extrait ", "extraits ")):
        return "extrait", "metadata_title_explicit_extract"
    if t.startswith(("proces verbal", "proces verbaux")):
        return "proces_verbal", "metadata_title_minutes_not_assumed_full_cahier"
    if t.startswith(
        (
            "annexe",
            "supplement",
            "pouvoirs",
            "instructions et demandes particulieres",
            "declaration",
            "deliberation",
            "arrete",
        )
    ):
        return "document_associe", "metadata_title_associated_genre"
    if t.startswith("privileges"):
        return "autre_document", "metadata_title_privilege_document"
    if ASSOCIATED.search(t):
        return "document_associe", "explicit_group_or_individual_not_territorial_cahier"
    if t.startswith(("cahier", "doleances", "voeux", "colonie")):
        return "cahier_autonome_probable", "documentary_title_hypothesis_not_certified"
    return "incertain", "document_nature_not_established"


def estate(title):
    t = fold(title)
    return [
        x
        for x, pattern in [
            ("clerge", r"\bclerge\b"),
            ("noblesse", r"\bnoblesse\b"),
            ("tiers", r"\btiers\b"),
        ]
        if re.search(pattern, t)
    ]


def enriched_leaves(source):
    leaves = base.leaf_records(source)
    for leaf in leaves:
        node = leaf["node"]
        ps = node.findall("p")
        head = " ".join(compact(h) for h in node.findall("head"))
        words = set(fold(head).split())
        if words and words <= set(
            "cahier cahiers general generale de des doleances plaintes remontrances".split()
        ):
            leaf["title"] = (
                head + " " + " ".join(compact(p) for p in ps[:2] if len(compact(p)) < 900)
            )
    return leaves


def propose(meta, source, leaves, at, v2lookup):
    kind, kind_basis = document_kind(meta["title"])
    record = dict(meta)
    if meta.get("page_start") is None:
        return dict(
            kind=kind,
            kind_basis=kind_basis,
            status="non_retrouve",
            candidates=[],
            boundary=None,
            evidence=["missing_pagination"],
            anomalies=["missing_pagination"],
        )
    candidates = base.candidates(record, source, leaves, at)
    # Add explicit role evidence and limited body evidence to existing title/page candidates.
    wanted = estate(meta["title"])
    for c in candidates:
        node = source.node(c["xpath"])
        ps = node.findall("p")
        body = " ".join(compact(p) for p in ps[:4] + ps[-3:])
        c["body_name_coverage"] = round(
            base.coverage(base.tokens(re.sub(r"\([^)]*\)", "", meta["title"])), base.tokens(body)),
            6,
        )
        observed = estate(c["title"])
        if wanted and observed and not set(wanted) & set(observed):
            c["score"] = round(c["score"] - 0.4, 6)
            c["estate_conflict"] = True
        else:
            c["estate_conflict"] = False
        p = v2lookup.get((meta["volume"], c["anchor_xpath"]))
        c["v2_support_id"] = (
            p["id"] if p and p["classification"] in {"autonomous", "associated"} else None
        )
        c["v2_class"] = p["classification"] if p else None
    candidates.sort(key=lambda c: (-c["score"], bool(c["internal"]), c["start"]))
    best = candidates[0] if candidates else None
    margin = (
        best["score"] - candidates[1]["score"]
        if len(candidates) > 1
        else (best["score"] if best else None)
    )
    evidence = []
    anomalies = []
    sufficient = bool(
        best
        and best["score"] >= PARAMS["min_score"]
        and best["own_coverage"] >= 0.5
        and not best["estate_conflict"]
    )
    if sufficient:
        if margin < PARAMS["ambiguous_margin"]:
            status = "ambigu"
            evidence.append("near_tied_candidates")
        elif best["score"] >= PARAMS["strong_score"]:
            status = "fort"
            evidence.append("title_page_context_concordant")
        else:
            status = "probable"
            evidence.append("single_candidate_with_title_or_ocr_divergence")
    else:
        supported = [
            c
            for c in candidates[:5]
            if c["v2_support_id"]
            and not c["estate_conflict"]
            and meta["page_start"] <= c["page"] <= meta["page_end"]
        ]
        if len(supported) == 1 and (
            supported[0]["own_coverage"] > 0 or supported[0]["body_name_coverage"] >= 0.5
        ):
            best = supported[0]
            status = "probable"
            evidence.append("unique_V2_support_with_partial_title_or_body_evidence")
            candidates = [best] + [c for c in candidates if c is not best]
        elif len(supported) > 1:
            status = "ambigu"
            evidence.append("multiple_V2_supported_candidates")
        else:
            status = "non_retrouve"
            evidence.append("insufficient_identity_evidence")
    boundary = (
        base.boundary(meta, best, source, leaves, at) if best and status != "non_retrouve" else None
    )
    if best:
        node = source.node(best["xpath"])
        opening = " ".join(compact(p) for p in node.findall("p")[:3])
        if MISSING.search(opening[:2200]):
            kind = "notice_absence"
            kind_basis = "source_explicit_missing_notice"
            status = "hors_perimetre"
            boundary = None
            anomalies.append("historical_cahier_announced_but_text_absent")
    if kind in {"liste", "autre_document"}:
        status = "hors_perimetre"
        evidence.append("not_retained_as_cahier_or_claim_document")
    boundary_status = "non_etablies"
    if boundary:
        boundary_status = "ambigues" if status == "ambigu" or boundary["flags"] else "proposees"
        if boundary["flags"]:
            anomalies += boundary["flags"]
    return dict(
        kind=kind,
        kind_basis=kind_basis,
        status=status,
        candidates=candidates[:5],
        margin=round(margin, 6) if margin is not None else None,
        boundary=boundary,
        boundary_status=boundary_status,
        evidence=evidence,
        anomalies=anomalies,
    )
