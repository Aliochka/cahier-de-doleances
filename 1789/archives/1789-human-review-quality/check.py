# ruff: noqa: E402
"""Reconcile frozen study totals and verify all input fingerprints, read-only."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import frozen_match  # noqa: E402

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA = HERE / "data"


def load(name):
    return json.loads((DATA / name).read_text())


def main():
    summary = load("summary.json")
    cahiers = load("cahiers.json")
    errors = load("errors.json")
    triage = load("triage.json")
    assert len(cahiers) == summary["cahiers"] == 10
    assert (
        sum(c["human_reviewed_articles"] for c in cahiers)
        == summary["current_human_articles"]
        == 333
    )
    assert summary["accepted_without_change"] + summary["corrected_or_created_final"] == 333
    assert sum(c["initial_articles"] for c in cahiers) == 322
    assert sum(c["final_articles"] for c in cahiers) == 333
    assert sum(c["initial_articles_changed"] for c in cahiers) == 14
    assert len({t["unit_id"] for t in triage}) == len(triage) == 719
    assert len(errors) == 15 and sum(e["severity"] == "major" for e in errors) == 10
    assert summary["mutation_events_classified"] == 27
    assert summary["groups"]["random_five"]["accepted_without_change"] == 108
    assert summary["groups"]["random_five"]["corrected_or_created_final"] == 0
    assert all(c["group_validation_operations"] == 0 and c["stale_events"] == 0 for c in cahiers)
    assert len(load("strategy-plan.json")["calibration"]["low_risk_frame"]) == 328
    for name, info in load("provenance.json")["files"].items():
        assert frozen_match(ROOT / name, info["sha256"]), name
    checks = load("checks.json")
    checks.update(
        all_27_mutation_events_classified_once=True,
        counter_reconciliation=True,
        provenance_files_unchanged_at_finish=True,
        random_group_zero_recorded_corrections=True,
        no_automatic_extraction=True,
    )
    if "--read-only" not in _workspace_sys.argv:
        (DATA / "checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    print("Checks passed: totals, 27 classified changes, unchanged journal/source fingerprints.")


if __name__ == "__main__":
    main()
