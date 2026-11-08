"""Offline adversarial checks; no production connection or archive creation."""

import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from documentary.backup_exception import (
    APPROVED,
    BASELINE_SHA256,
    EXCEPTION,
    IMAGE_IDS,
    MODEL_HASH,
    SOURCE_INVENTORY_SHA256,
    SSD_UUID,
)
from documentary.production import APPLICATION_IDENTITY, IDENTITY, check_backup_proof
from documentary.safety import UnsafeDestination

NOW = datetime(2026, 11, 8, 20, tzinfo=UTC)


def complete_proof():
    stamp = NOW.isoformat()
    root = "/backups/postgresql/rollback-multicorpus-20261108T190000Z"
    return {
        "exception": EXCEPTION,
        "target": dict(IDENTITY),
        "application": dict(APPLICATION_IDENTITY),
        "operator": "Offline test operator",
        "cold_backup": copy.deepcopy(APPROVED),
        "restore_point_accepted": True,
        "acceptance_reference": "Explicit operator acceptance",
        "recent_comparison": {
            "checked_at": stamp,
            "unchanged": True,
            "baseline_sha256": BASELINE_SHA256,
            "observed_sha256": BASELINE_SHA256,
            "current_snapshot": "1155:1155:",
            "ssd_uuid": SSD_UUID,
            "backup_uuid": APPROVED["volume_uuid"],
            "source_inventory_sha256": SOURCE_INVENTORY_SHA256,
            "source_control_sha256": APPROVED["control_sha256"],
            "manifest_sha256": APPROVED["manifest_sha256"],
        },
        "rollback_assets": {
            "image_ids": dict(IMAGE_IDS),
            "model_manifest_hash": MODEL_HASH,
            "preserved_at": stamp,
            "directory": root,
            "volume_uuid": APPROVED["volume_uuid"],
            "verified": True,
            "artifacts": {
                n: {"path": root + "/" + n + ".tar", "bytes": 100, "sha256": "a" * 64}
                for n in ("configuration", "images", "model")
            },
        },
    }


def test_approved_old_backup_with_fresh_comparison_and_preserved_assets():
    check_backup_proof(complete_proof(), now=NOW)
    p = complete_proof()
    p.pop("exception")  # No implicit fallback based on age/path.
    with pytest.raises(UnsafeDestination):
        check_backup_proof(p, now=NOW)


@pytest.mark.parametrize("field", list(APPROVED))
def test_every_historical_evidence_field_is_pinned(field):
    p = complete_proof()
    p["cold_backup"][field] = "different"
    with pytest.raises(UnsafeDestination):
        check_backup_proof(p, now=NOW)


@pytest.mark.parametrize(
    "section,field,value",
    [
        (None, "exception", "generic-old-backup"),
        (None, "restore_point_accepted", False),
        (None, "operator", ""),
        (None, "acceptance_reference", ""),
        ("target", "database_oid", 16384),
        ("target", "cluster_id", "wrong"),
        ("application", "database_name", "other"),
        ("recent_comparison", "unchanged", False),
        ("recent_comparison", "observed_sha256", "a" * 64),
        ("recent_comparison", "baseline_sha256", "a" * 64),
        ("recent_comparison", "checked_at", (NOW - timedelta(hours=25)).isoformat()),
        ("recent_comparison", "checked_at", (NOW + timedelta(seconds=1)).isoformat()),
        ("recent_comparison", "checked_at", "2026-11-08T19:00:00"),
        ("recent_comparison", "ssd_uuid", "wrong"),
        ("recent_comparison", "backup_uuid", "wrong"),
        ("recent_comparison", "current_snapshot", "1156:1156:"),
        ("recent_comparison", "source_inventory_sha256", "a" * 64),
        ("recent_comparison", "source_control_sha256", "a" * 64),
        ("recent_comparison", "manifest_sha256", "a" * 64),
        ("rollback_assets", "verified", False),
        ("rollback_assets", "artifacts", {}),
        ("rollback_assets", "preserved_at", (NOW - timedelta(days=2)).isoformat()),
        ("rollback_assets", "directory", APPROVED["path"]),
        (
            "rollback_assets",
            "directory",
            "/backups/postgresql/../rollback-multicorpus-20261108T190000Z",
        ),
        ("rollback_assets", "volume_uuid", "wrong"),
    ],
)
def test_refuses_other_destinations_stale_checks_and_missing_conservation(section, field, value):
    p = complete_proof()
    (p if section is None else p[section])[field] = value
    with pytest.raises(UnsafeDestination):
        check_backup_proof(p, now=NOW)


@pytest.mark.parametrize(
    "field,value", [("bytes", 0), ("sha256", "0" * 64), ("path", APPROVED["path"]), ("bytes", True)]
)
def test_refuses_incomplete_or_original_directory_asset_receipt(field, value):
    p = complete_proof()
    p["rollback_assets"]["artifacts"]["images"][field] = value
    with pytest.raises(UnsafeDestination):
        check_backup_proof(p, now=NOW)


def test_versioned_baseline_matches_reviewed_fingerprint():
    data = json.loads(
        (Path(__file__).parents[1] / "deploy/documentary/gavroche-nov02-baseline.json").read_text()
    )
    assert (
        hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        == BASELINE_SHA256
    )


def test_draft_attestation_does_not_claim_preservation_is_complete():
    p = complete_proof()
    p["rollback_assets"] = None
    with pytest.raises(UnsafeDestination):
        check_backup_proof(p, now=NOW)


def test_real_prepared_attestation_matches_accepted_evidence_but_cannot_import():
    p = json.loads(
        (
            Path(__file__).parents[1] / "deploy/documentary/nov02-backup-proof.prepared.json"
        ).read_text()
    )
    assert p["cold_backup"] == APPROVED
    assert p["restore_point_accepted"] is True
    assert p["rollback_assets"] is None
    with pytest.raises(UnsafeDestination):
        check_backup_proof(p, now=NOW)


@pytest.mark.parametrize("key,value", [("image_ids", {}), ("model_manifest_hash", "a" * 64)])
def test_rollback_assets_must_preserve_the_expected_images_and_model(key, value):
    p = complete_proof()
    p["rollback_assets"][key] = value
    with pytest.raises(UnsafeDestination):
        check_backup_proof(p, now=NOW)


def test_preservation_default_is_plan_only(tmp_path):
    import subprocess
    import sys

    script = Path(__file__).parents[1] / "scripts/preserve_gavroche_rollback.py"
    p = subprocess.run(
        [sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert json.loads(p.stdout)["mode"] == "plan-only"
    assert not list(tmp_path.iterdir())
