"""Indicateurs de revue, correspondances anciennes et exemples, sans réseau."""

from collections import Counter

from common import read, write
from extract import trim
from verify import lines


def main():
    docs, units = lines("documents.jsonl"), lines("units.jsonl")
    parents = {d["id"]: d for d in docs}
    predictions = lines("automatic-predictions.jsonl")
    refs = read("data/reference.json")
    ledger = []
    for p in predictions:
        exact = [
            u
            for u in units
            if u["document_id"] == p["document_id"]
            and (u["start"], u["end"]) == (p["start"], p["end"])
        ]
        overlap = [
            u
            for u in units
            if u["document_id"] == p["document_id"]
            and u["start"] < p["end"]
            and u["end"] > p["start"]
        ]
        outcome = (
            ("unchanged_verified_A" if exact[0]["status"] == "A" else "unchanged_unverified_B")
            if exact
            else "boundary_changed"
            if overlap
            else "excluded_by_structure_review"
        )
        ledger.append(
            {
                "document_key": p["document_key"],
                "start": p["start"],
                "end": p["end"],
                "outcome": outcome,
                "successor_ids": [u["id"] for u in overlap],
            }
        )
    errors = []
    for r in refs:
        if r["certainty"] != "A":
            continue
        pred = [
            u
            for u in predictions
            if u["document_id"] == r["document_id"] and r["start"] <= u["start"] < r["end"]
        ]
        gold = {(u["start"], u["end"]) for u in r["units"]}
        guessed = {(u["start"], u["end"]) for u in pred}
        if gold == guessed:
            continue
        d = parents[r["document_id"]]

        def excerpt(a, b):
            return d["full_text"][a - d["source_text_start"] : b - d["source_text_start"]]

        errors.append(
            {
                "document_key": d["key"],
                "window": r["window"],
                "volume": d["volume"],
                "source_url": d["source_url"],
                "reference_comment": r["comment"],
                "incorrect_predictions": [
                    {"start": a, "end": b, "text": excerpt(a, b)} for a, b in sorted(guessed - gold)
                ],
                "missed_or_incorrectly_bounded_units": [
                    {"start": a, "end": b, "text": excerpt(a, b)} for a, b in sorted(gold - guessed)
                ],
            }
        )
    old_docs = {d["id"]: d for d in read("../1789-multicorpus/data/documents.json")}
    crosswalk = []
    for p in read("../1789-multicorpus/data/passages.json"):
        old = old_docs[p["document_id"]]
        d = next(d for d in docs if d["key"] == old["key"])
        a = p["context_reference"]["start"]
        b = p["context_reference"]["end"]
        a, b = trim(old["full_text_exact"], a, b)
        a += d["source_text_start"]
        b += d["source_text_start"]
        matches = [
            u for u in units if u["document_id"] == d["id"] and u["start"] == a and u["end"] == b
        ]
        overlapping = [
            u for u in units if u["document_id"] == d["id"] and u["start"] < b and u["end"] > a
        ]
        crosswalk.append(
            {
                "legacy_passage_id": p["id"],
                "legacy_document_id": old["id"],
                "document_id": d["id"],
                "document_key": d["key"],
                "same_source_extent": bool(matches),
                "pilot_unit_ids": [u["id"] for u in (matches or overlapping)],
                "text_serialization_identical": any(u["text"] == p["text"] for u in matches),
                "note": "Nouvelle sérialisation : espaces inter-paragraphes XML conservés et bordures hors texte éliminées, sans réécriture. Le périmètre modifié doit être revu, jamais assimilé au même identifiant.",
            }
        )
    selected = []
    for key, number in [
        ("mirecourt-noblesse", "4"),
        ("perigny-brie", "15"),
        ("montigny-ostrevent", None),
    ]:
        u = next(
            u
            for u in units
            if u["document_key"] == key and u["historical_number"] == number and u["status"] == "A"
        )
        d = parents[u["document_id"]]
        selected.append(
            {
                "result": u,
                "parent_file": "parents/" + key + ".txt",
                "context": {
                    "document_id": d["id"],
                    "anchor": u["anchor"],
                    "start": u["parent_start"],
                    "end": u["parent_end"],
                    "preceding": u["previous_unit_id"],
                    "following": u["next_unit_id"],
                },
                "interpretation": "Données de navigation seulement ; aucune route ou interface créée.",
            }
        )
    evaluation = read("data/evaluation.json")
    ed = evaluation["documents"]
    summary = {
        "documents": len(docs),
        "by_volume": dict(Counter(d["volume"] for d in docs)),
        "by_estate": dict(Counter(d["metadata"]["estate"] or "non attribué" for d in docs)),
        "parents_matching_automatic_boundaries": sum(
            d["automatic_parent_matches_reference"] for d in ed
        ),
        "parents_requiring_boundary_correction": sum(d["parent_correction_required"] for d in ed),
        "parents_with_uncertain_boundaries_after_xml_review": sum(
            d["boundaries_uncertain_after_review"] for d in ed
        ),
        "raw_candidates": len(predictions),
        "final_article_candidates": len(units),
        "A": sum(u["status"] == "A" for u in units),
        "B": sum(u["status"] == "B" for u in units),
        "C_source_ranges_not_articles": len(lines("retained-unsegmented.jsonl")),
        "non_whitespace_parent_characters": sum(d["parent_non_whitespace_characters"] for d in ed),
        "non_whitespace_A_characters": sum(d["A_non_whitespace_characters"] for d in ed),
        "A_text_coverage_of_all_parent_text": sum(d["A_non_whitespace_characters"] for d in ed)
        / sum(d["parent_non_whitespace_characters"] for d in ed),
        "A_share_of_final_candidates": sum(u["status"] == "A" for u in units) / len(units),
        "fully_reviewed_numbered_body_documents": [d["key"] for d in ed if d["A"] and not d["B"]],
        "explicit_structure_decisions": sum(d["manual_structure_decisions"] for d in ed),
        "paragraph_roles_changed": sum(d["paragraph_roles_changed"] for d in ed),
        "proposal_review_outcomes": dict(Counter(p["outcome"] for p in ledger)),
        "gold_A_windows": sum(r["certainty"] == "A" for r in refs),
        "uncertain_B_reference_windows": sum(r["certainty"] == "B" for r in refs),
        "legacy_28_crosswalk_same_extent": sum(x["same_source_extent"] for x in crosswalk),
        "human_validation_seconds": None,
        "external_historian_review": False,
        "scope": "Mesures sur un échantillon raisonné et des fenêtres de développement vérifiées par Codex, sans test aveugle ni extrapolation.",
    }
    write("data/proposal-review.json", ledger)
    write("data/boundary-errors.json", errors)
    write("data/legacy-crosswalk.json", crosswalk)
    write("data/navigation-examples.json", selected)
    write("data/summary.json", summary)
    print(summary)


if __name__ == "__main__":
    main()
