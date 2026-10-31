"""Optional read-only proposal overlay. Does not participate in decision replay or export."""

from functools import lru_cache

from reviewlib import HERE, rows

PATH = HERE.parents[1] / "data/segmentation-proposals/comparison.jsonl.gz"


@lru_cache(maxsize=1)
def load(path, modified, size):
    return {r["document_id"]: r for r in rows(path)}


def comparison(parent):
    if not PATH.exists():
        return None
    stat = PATH.stat()
    try:
        row = load(str(PATH), stat.st_mtime_ns, stat.st_size).get(parent["id"])
    except (OSError, ValueError, KeyError):
        return dict(
            available=False, warning="Comparaison illisible ; le découpage actuel reste inchangé."
        )
    if not row:
        return None
    if (
        row["parent_extent_id"] != parent["extent_id"]
        or row["source_sha256"] != parent["source"]["source_sha256"]
    ):
        return dict(
            available=False,
            warning="Comparaison périmée : autre version du cahier ou de la source.",
        )
    old_starts = {u["start"] for u in row["old"]}
    markers = []
    for c in row["candidates"]:
        if c["confidence"] == "suspect" or (
            c["confidence"] in {"proposed", "existing"}
            and not any(abs(c["start"] - a) <= 3 for a in old_starts)
        ):
            unit = next((u for u in row["new"] if abs(u["start"] - c["start"]) <= 3), None)
            markers.append(
                dict(
                    start=c["start"],
                    end=unit["end"] if unit else None,
                    label=c["raw_label"],
                    number=c["historical_number"],
                    evidence=c["evidence"],
                    status="suspect" if c["confidence"] == "suspect" else "proposed",
                    text=unit["text"][:600]
                    if unit
                    else parent["full_text"][
                        c["start"] - parent["start"] : c["start"] - parent["start"] + 300
                    ],
                )
            )
    markers.extend(row.get("review_notes", []))
    old_ranges = {(u["start"], u["end"]) for u in row["old"]}
    changed = [
        dict(
            start=u["start"],
            end=u["end"],
            label=u["label_exact"],
            text=u["text"][:300],
            old_ranges=[
                dict(start=o["start"], end=o["end"])
                for o in row["old"]
                if o["start"] < u["end"] and u["start"] < o["end"]
            ],
        )
        for u in row["new"]
        if (u["start"], u["end"]) not in old_ranges
    ]
    return dict(
        available=True,
        method=row["version"],
        initial_article_count=row.get("initial_article_count"),
        reference_misses=row.get("reference_misses", []),
        old_count=row["old_count"],
        new_count=row["new_count"],
        markers=markers,
        changed_ranges=changed,
        role_changes=row["role_changes"],
        warning="Comparaison expérimentale en lecture seule. Les décisions humaines restent prioritaires ; aucune nouvelle segmentation n’est appliquée automatiquement.",
    )
