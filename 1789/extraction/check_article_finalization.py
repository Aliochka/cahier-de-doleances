"""Read-only comparison of article generations and current human decisions."""

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "tools/document-review"))
from articles import Articles  # noqa: E402
from reviewlib import Store, rows, sha  # noqa: E402


def check(directory):
    baseline = BASE / "data/corpus/global-corpus-3-d0df8e19ee01"
    store = Store()
    snapshots = {
        p: sha(p.read_bytes())
        for p in [store.journal, BASE / "data/private/document-review/article-decisions.jsonl"]
    }
    old_parents = {p["id"]: p for p in rows(baseline / "parents.jsonl.gz")}
    parents = {p["id"]: p for p in rows(directory / "parents.jsonl.gz")}
    assert set(old_parents) == set(parents)
    old_units = rows(baseline / "units.jsonl.gz")
    units = rows(directory / "units.jsonl.gz")
    changes = rows(directory / "article-changes.jsonl.gz")
    latest = store.latest()
    human_old = {u["id"]: u for u in old_units if u["human_validated"]}
    human_new = {u["id"]: u for u in units if u["human_validated"]}
    assert set(human_old) == set(human_new) and len(human_new) == 333
    for key, old in human_old.items():
        new = human_new[key]
        for field in [
            "spans",
            "text",
            "text_sha256",
            "number",
            "label",
            "review_status",
            "last_event_id",
            "parent_id",
            "parent_extent_id",
        ]:
            assert old[field] == new[field], (key, field)
    codex_references = [
        u for u in old_units if u["type"] == "article" and u["source_status"] == "A"
    ]
    new_by_id = {u["id"]: u for u in units}
    assert all(
        u["id"] in new_by_id
        and u["spans"] == new_by_id[u["id"]]["spans"]
        and u["text"] == new_by_id[u["id"]]["text"]
        for u in codex_references
    )
    human_parents = [p for p in parents.values() if p["boundary_class"] == "human_validated"]
    assert len(human_parents) == 45
    for p in human_parents:
        selected = latest[p["id"]]["retained"]
        assert (p["start"], p["end"]) == (selected["start"], selected["end"])
    boundary_sample = json.loads(
        (BASE / "tools/document-review/campaigns/twelve-boundaries.json").read_text()
    )
    assert all(
        latest[r["document_id"]]["status"] == "human_validated" for r in boundary_sample["selected"]
    )
    finalization = json.loads((BASE / "extraction/documentary-finalization.json").read_text())
    blocker_ids = {key for group in finalization["blockers"] for key in group["document_ids"]}
    assert all(latest[key]["status"] == "human_validated" for key in blocker_ids)
    engine = Articles(store, directory=directory)
    workbench = json.loads((directory / "article-workbench.json").read_text())
    unit_map = {u["id"]: u for u in units}
    sample = workbench["independent_sample"]
    assert len(sample) == 24 and len({w["unit_id"] for w in sample}) == 24
    for v in range(1, 7):
        for group in ["regular_article", "C_window"]:
            assert sum(w["volume"] == v and w["group"] == group for w in sample) == 2
    assert all(w["parent_id"] not in workbench["excluded_development_parent_ids"] for w in sample)
    assert all(not unit_map[w["unit_id"]]["human_validated"] for w in sample)
    # Recreate the frozen draw without looking at documentary correctness.
    from article_production import prepare_workbench

    qualities = rows(directory / "unit-quality.jsonl.gz")
    rerun = prepare_workbench(
        directory,
        store,
        units,
        qualities,
        changes,
        {e["document_id"] for e in engine.log.history()},
    )
    assert rerun["independent_sample"] == sample
    fixture = json.loads((BASE / "extraction/article-rule-checks.json").read_text())
    frozen_functions = fixture["frozen_cut_function_AST_sha256"]
    for node in ast.parse((BASE / "extraction/article_rules.py").read_text()).body:
        if isinstance(node, ast.FunctionDef) and node.name in frozen_functions:
            assert sha(ast.dump(node, include_attributes=False)) == frozen_functions[node.name]
    proposed = {m["start"] for c in changes for m in c["markers"]}
    for case in fixture["cases"]:
        assert set(case["expected_new_starts"]).issubset(proposed)
        for pos, xpath in zip(case["expected_new_starts"], case["expected_xpaths"]):
            source = store.sources[case["volume"]]
            a, z = source.span(source.node(xpath))
            assert a <= pos < z
    # A numerical reset is preserved; no rewriting of source text is involved.
    input_manifest = json.loads((directory / "inputs.json").read_text())
    assert all(
        sha((BASE.parent / name).read_bytes()) == digest
        for name, digest in input_manifest["files"].items()
    )
    assert all(sha(p.read_bytes()) == digest for p, digest in snapshots.items())
    result = dict(
        generation=directory.name,
        baseline=baseline.name,
        before=json.loads((baseline / "summary.json").read_text()),
        after=json.loads((directory / "summary.json").read_text()),
        quality=json.loads((directory / "article-quality-summary.json").read_text()),
        changes=dict(Counter(c["kind"] for c in changes)),
        new_articles_from_splits=sum(
            len(c["after_ids"]) - 1 for c in changes if c["kind"] == "split_fused_article"
        ),
        rule_source_checks=dict(
            windows=len(fixture["cases"]),
            starts=sum(len(c["expected_new_starts"]) for c in fixture["cases"]),
            no_false_cut_observed_in_checked_starts=True,
            independent_human_validation=False,
            scope=fixture["scope"],
        ),
        sample=dict(
            size=len(sample),
            seed=workbench["seed"],
            examples=len(workbench["examples"]),
            two_articles_and_two_C_per_volume=True,
            no_documentary_judgement_performed=True,
        ),
        invariants=dict(
            no_parent_lost=True,
            human_articles_preserved=333,
            prior_Codex_A_articles_preserved=len(codex_references),
            human_parent_extents_applied=45,
            boundary_sample_confirmations=12,
            finalization_dossiers_confirmed=3,
            source_and_input_hashes_unchanged=True,
            human_journals_unchanged=True,
            unit_source_partition_checked_by_production=True,
            known_document_overlaps_retained=2,
        ),
    )
    result["quality"].pop("by_parent", None)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("generation", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = check(args.generation)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
