"""Réserve documentaire explicite; aucune réécriture de la référence gelée ou des métriques initiales."""

from common import HERE, jlines, rows, write


def main():
    gold = rows(HERE / "data/reference-articles.jsonl")
    notes = []
    for g in gold:
        if g["parent_id"] == "gold-zone-v2-2-2" and g["label"] == "4":
            notes.append(
                dict(
                    reference_id=g["id"],
                    original_status="A in frozen exploratory reference",
                    retained_status="B_documentary_boundary_uncertain",
                    reason="p5 est non numéroté entre 4° et 6°; l’autonomie de sa proposition n’est pas suffisamment assurée pour certifier la fin de 4°. Ne pas fabriquer implicitement un article5.",
                    reference_and_rules_unchanged=True,
                )
            )
    assert len(notes) == 1
    jlines(HERE / "data/reference-review-notes.jsonl", notes)
    compare = rows(HERE / "data/article-boundary-comparison.jsonl")
    excluded = {n["reference_id"] for n in notes}
    write(
        HERE / "data/reference-sensitivity.json",
        {
            v: dict(
                reviewed_unambiguous_units=sum(
                    r["version"] == v and r["reference_id"] not in excluded for r in compare
                ),
                exact=sum(
                    r["version"] == v and r["reference_id"] not in excluded and r["exact"]
                    for r in compare
                ),
                reason="documentary caveat, not rule tuning; primary frozen 79-unit results preserved",
            )
            for v in ["v1", "v2"]
        },
    )


if __name__ == "__main__":
    main()
