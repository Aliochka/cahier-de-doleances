"""Freeze bounded fusion controls before reading held-out source windows."""

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "tools/document-review"))
import fusion  # noqa: E402
from articles import Articles  # noqa: E402
from collection import discover  # noqa: E402
from production import dump, jsonl  # noqa: E402
from reviewlib import Store, rows, sha  # noqa: E402

DEVELOPMENT_SUFFIXES = {
    "1_1_1547",
    "1_1_1554",
    "2_1_1649",
    "2_1_1631",
    "3_1_1932",
    "3_1_2023",
    "4_1_2231",
    "4_1_1781",
    "5_1_2911",
    "6_1_2781",
    "6_1_2612",
}


def inputs(store, engine, events):
    protected = defaultdict(list)
    shared = defaultdict(list)
    for e in events:
        for r in e["before"] + e["after"]:
            protected[e["document_id"]].extend(r["spans"])
    for pair in rows(engine.directory / "document-overlaps.jsonl.gz"):
        for key in [pair["left_id"], pair["right_id"]]:
            shared[key].append([pair["start"], pair["end"]])
    return protected, shared


def scan(store, engine, events):
    protected, shared = inputs(store, engine, events)
    hypotheses = []
    for p in engine.parents.values():
        own = list(engine.state(p["id"], events)[1].values())
        hypotheses += fusion.detect(store, p, own, protected[p["id"]], shared[p["id"]])
    return hypotheses


def freeze(store, engine, events, hypotheses, previous_controls=()):
    excluded = {e["document_id"] for e in events}
    excluded.update(p["id"] for p in rows(BASE / "data/article-corpus/parents.jsonl.gz"))
    excluded.update(
        k
        for k, p in engine.parents.items()
        if p.get("legacy_parent_ids")
        or any(p["persee_id"].endswith(s) for s in DEVELOPMENT_SUFFIXES)
    )
    prior = json.loads((BASE / "docs/thematic-extraction-checks.json").read_text())
    excluded.update(r["parent_id"] for r in prior["source_checks"])
    excluded.update(previous_controls)
    rng = random.Random(178906)
    validation = []
    refusals = []
    populations = {}
    for v in range(1, 7):
        own = [h for h in hypotheses if h["volume"] == v and h["parent_id"] not in excluded]
        by_unit = defaultdict(list)
        for h in own:
            if h["confidence"] == "proposed":
                by_unit[h["source_unit_id"]].append(h)
        eligible = sorted(by_unit)
        populations[str(v)] = dict(units=len(eligible), ids_sha256=sha("\n".join(eligible)))
        for uid in rng.sample(eligible, min(2, len(eligible))):
            h = min(by_unit[uid], key=lambda h: sha(h["id"]))
            validation.append(h)
        # Deliberate negative mechanisms, source text not read before selection.
        negative = [h for h in own if h["confidence"] == "uncertain" and not h["protected"]]
        priorities = [
            "dependent_subheading",
            "numbered_subdivision_inside_development_kept_together",
            "same_vocabulary_as_preceding_development_requires_review",
            "singleton_title_without_sufficient_neighbour_support",
            "no_explicit_request_formula",
        ]
        for reason in priorities:
            matches = [h for h in negative if reason in h["reasons"]]
            if matches:
                refusals.append(min(matches, key=lambda h: sha(h["id"])))
                break

    def item(h):
        return {
            k: h[k]
            for k in [
                "id",
                "parent_id",
                "volume",
                "source_unit_id",
                "title_start",
                "title_end",
                "end",
                "xpath",
                "confidence",
                "reasons",
            ]
        }

    return dict(
        version="fusion-validation-1",
        generation=engine.directory.name,
        seed=178906,
        rule_files_sha256={
            n: sha((BASE / "extraction" / n).read_bytes()) for n in ["fusion.py", "thematic.py"]
        },
        article_journal_sha256=sha(engine.log.journal.read_bytes()),
        selection="Two eligible source units per volume if available: random.sample(sorted IDs), one SHA256-selected proposed boundary per unit. Development, human-reviewed and previous control parents excluded. Refusals selected separately by fixed mechanism priorities and hash; not a random performance sample.",
        excluded_parent_ids=sorted(excluded),
        populations=populations,
        validation=[item(h) for h in validation],
        refusals=[item(h) for h in refusals],
        source_review_performed_before_freeze=False,
        independent_human_validation=False,
    )


if __name__ == "__main__":
    store = Store()
    engine = Articles(store, directory=discover())
    ev = engine.log.history()
    hs = scan(store, engine, ev)
    root = BASE / "extraction/.local/fusion"
    root.mkdir(parents=True, exist_ok=True)
    jsonl(root / "hypotheses.jsonl.gz", hs)
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, default=1)
    args = parser.parse_args()
    prior = (
        json.loads((BASE / "extraction/fusion-validation-plan.json").read_text())
        if args.round > 1
        else None
    )
    excluded = (
        {r["parent_id"] for group in ["validation", "refusals"] for r in prior[group]}
        if prior
        else set()
    )
    plan = freeze(store, engine, ev, hs, previous_controls=excluded)
    plan["version"] = "fusion-validation-" + str(args.round)
    plan["excluded_prior_control_parents"] = sorted(excluded)
    destination = BASE / (
        "extraction/fusion-validation-v2.json"
        if args.round > 1
        else "extraction/fusion-validation-plan.json"
    )
    if destination.exists():
        raise ValueError("Frozen selection already exists; do not overwrite")
    dump(destination, plan)
    print(
        json.dumps(
            dict(
                counts=dict(Counter(h["confidence"] for h in hs)),
                suspected_units=len({h["source_unit_id"] for h in hs}),
                validation=len(plan["validation"]),
                refusals=len(plan["refusals"]),
                populations=plan["populations"],
            ),
            indent=2,
        )
    )
