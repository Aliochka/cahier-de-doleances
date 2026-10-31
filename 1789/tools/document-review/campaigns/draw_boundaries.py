"""Frozen two-per-volume random sample, without inspecting text or article counts."""

import argparse
import json
import random
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BASE / "tools/document-review"))
from reviewlib import Store, rows, sha  # noqa: E402

SEED = 17891789
DEST = Path(__file__).with_name("twelve-boundaries.json")


def draw(directory, frozen=False):
    directory = directory.resolve()
    store = Store(directory / ".private/decisions.jsonl" if frozen else None)
    parents = rows(directory / "parents.jsonl.gz")
    manifest = json.loads((BASE / "extraction/documentary-finalization.json").read_text())
    examined = {r["document_id"] for r in manifest["repairs"]}
    examined.update(k for r in manifest["overlap_cases"] for k in [r["left_id"], r["right_id"]])
    latest = store.latest()
    rng = random.Random(SEED)
    selected = []
    populations = {}
    for volume in range(1, 7):
        ids = []
        for p in parents:
            r = store.by_id[p["id"]]
            if (
                p["volume"] != volume
                or p["boundary_class"] != "automatic_no_alert"
                or p["document_kind"] != "cahier_autonome_probable"
            ):
                continue
            if store.state(r, latest)["status"] == "human_validated":
                continue
            if (
                p["id"] in examined
                or r.get("controls")
                or p["id"] in store.references
                or store.base(r)[1] == "codex_reviewed"
            ):
                continue
            ids.append(p["id"])
        ids.sort()
        populations[str(volume)] = dict(count=len(ids), ids_sha256=sha("\n".join(ids)))
        if len(ids) < 2:
            raise ValueError("Fewer than two unexamined candidates in volume " + str(volume))
        for key in rng.sample(ids, 2):
            r = store.by_id[key]
            m = r["metadata"]
            selected.append(
                dict(
                    document_id=key,
                    persee_id=r["persee_id"],
                    title=m["title"],
                    volume=volume,
                    pages=[m["page_start"], m["page_end"]],
                    boundary_status_at_draw="automatic_no_alert",
                    human_validated_at_draw=False,
                    url="/?document=" + key,
                )
            )
    return dict(
        version="boundary-sample-1",
        seed=SEED,
        random_method="Python random.Random(seed), volumes 1..6, sample(sorted(eligible_ids),2) without replacement",
        eligibility="probable autonomous cahier, automatic_no_alert; exclude human boundaries and previously source-examined controls/references/finalization cases; no text, article-count or difficulty selection",
        generation=str(directory.relative_to(BASE)),
        parents_sha256=sha((directory / "parents.jsonl.gz").read_bytes()),
        registry_sha256=store.registry_sha,
        source_examination_performed=False,
        human_decisions_created=0,
        population_by_volume=populations,
        selected=selected,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--generation", type=Path)
    p.add_argument("--verify", action="store_true")
    args = p.parse_args()
    if args.verify:
        frozen = json.loads(DEST.read_text())
        computed = draw(BASE / frozen["generation"], frozen=True)
        if computed != frozen:
            raise ValueError("Frozen selection or eligibility changed; do not replace the sample")
        print("Frozen sample reproduced: 12, two per volume; no decisions created.")
        return
    if DEST.exists():
        raise ValueError("Frozen sample already exists; use --verify, never redraw difficult cases")
    if not args.generation or not (args.generation / "complete.json").exists():
        raise ValueError("Completed immutable generation required")
    frozen = draw(args.generation)
    DEST.write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(frozen["selected"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
