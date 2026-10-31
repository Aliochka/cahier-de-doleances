"""One reproducible draw, independent of article counts and segmentation alerts."""

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
sys.path.insert(0, str(TOOL))
from articles import Articles, canonical  # noqa: E402
from reviewlib import Store, sha  # noqa: E402

SEED = 17892019
OUTPUT = HERE / "five-cahiers.json"


def draw(population):
    return random.Random(SEED).sample(sorted(population), 5)


def main():
    if OUTPUT.exists():
        raise SystemExit("Le tirage est déjà figé ; aucun nouveau tirage ni remplacement.")
    store = Store()
    articles = Articles(store)
    events = articles.log.history()
    # Exclude any dossier with a real review event, including uncertainty or undo.
    examined = {e["document_id"] for e in events}
    ready = sorted(
        p["id"] for p in articles.parents.values() if articles.parent_version(p)["ready"]
    )
    excluded = sorted(set(ready) & examined)
    eligible = sorted(set(ready) - examined)
    selected = draw(eligible)  # Counts, titles and alerts are never passed to the draw.
    entry = []
    for key in selected:
        p = articles.parents[key]
        base = [u for u in articles.base[key].values() if u["type"] == "article"]
        entry.append(
            dict(
                id=key,
                title=p["metadata"]["title"],
                persee_id=p["persee_id"],
                volume=p["volume"],
                proposed_articles=len(base),
                initial_human_article_decisions=0,
                parent_extent_id=p["extent_id"],
                initial_units_sha256=sha(canonical(articles.base[key])),
                selection_status="articles_not_human_reviewed",
            )
        )
    inputs = {
        str(path.relative_to(TOOL.parents[2])): dict(
            bytes=path.stat().st_size, sha256=sha(path.read_bytes())
        )
        for path in [
            articles.log.journal,
            store.journal,
            *(
                articles.directory / name
                for name in [
                    "parents.jsonl.gz",
                    "units-A.jsonl.gz",
                    "units-B.jsonl.gz",
                    "units-C.jsonl.gz",
                ]
            ),
            TOOL / "segmentation.py",
            TOOL / "segmentation_comparison.py",
        ]
    }
    result = dict(
        id="five-cahiers-01",
        title="Cinq cahiers tirés au sort — campagne 1",
        created_at=datetime.now(timezone.utc).isoformat(),
        seed=SEED,
        algorithm="Python random.Random(seed).sample(sorted(eligible_document_ids), 5), without replacement",
        python_version=sys.version.split()[0],
        population_human_validated_parents=ready,
        excluded_any_prior_article_event=excluded,
        eligible_document_ids=eligible,
        selected=entry,
        inputs=inputs,
        journal_baseline_events=len(events),
        scope="Préparation uniquement : aucun bilan de la nouvelle campagne, aucune nouvelle segmentation.",
        reported_previous_effort="Environ 30 minutes pour Terre-Franche, Vic et Mirecourt, communiqué par l’utilisateur ; hors de cette campagne.",
    )
    # Preserve a private reference snapshot for later comparison without exposing reader names.
    baseline = TOOL.parents[1] / "data/private/document-review/campaigns/five-cahiers-01"
    baseline.mkdir(parents=True, exist_ok=False)
    (baseline / "article-decisions.jsonl").write_bytes(articles.log.journal.read_bytes())
    (baseline / "initial-units.json").write_text(
        canonical({key: articles.base[key] for key in selected}) + "\n"
    )
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    for i, p in enumerate(entry, 1):
        print(i, p["title"], p["proposed_articles"], p["persee_id"])
    print("Eligible:", len(eligible), "Excluded:", len(excluded), "Journal events:", len(events))


if __name__ == "__main__":
    main()
