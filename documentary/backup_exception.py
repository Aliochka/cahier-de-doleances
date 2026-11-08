"""Named operator-approved exception; no database, SSH or filesystem mutation."""

import json
import re
from datetime import datetime, timedelta
from pathlib import PurePosixPath

EXCEPTION = "gavroche-cold-20261102-v1"
BASELINE_SHA256 = "e2a11f8155a1541792273eefa69e58416834383f35d4e03407ffe9fd9167c101"
SOURCE_INVENTORY_SHA256 = "eb602ade2b9284dfeefb22c945b3b0011710dbdc2ba8f8bab97742e1b9d5ac17"
SSD_UUID = "624405d4-3422-4b7d-8ca3-8579d8b513bb"
MODEL_HASH = "fe2f29e9b4699cfeb8ee4d9524c1e99df203cb4f144dbe4b463e28e65e3d1f6d"
IMAGE_IDS = {
    "cahier-de-doleances-app-app-1": "sha256:e0c26f229536597004ef299d6e8406fb087916d0511eabe8bd02e5543070c7cd",
    "cahier-de-doleances-app-frontend-1": "sha256:73e31e5b321040259aae7769d5fc4eaebcd90c493ebdc85f1168d1313176a1eb",
    "cahier-postgres": "sha256:30ee450c42fda0596abaf71066c1612c79a0aaa791e655e5e00ce2c1e33ab6cc",
    "cahier-de-doleances-app-caddy-1": "sha256:834468128c7696cec0ceea6172f7d692daf645ae51983ca76e39da54a97c570d",
}
APPROVED = {
    "path": "/backups/postgresql/wallace-original-20261102/pg17/data",
    "volume_uuid": "52ba8e78-4375-4286-8c75-5cfef6609c8a",
    "source_shutdown_at": "2026-11-02T12:04:28Z",
    "transfer_date_attested": "2026-11-02",
    "transfer_completed_at": None,  # Unknown: never invent a transfer completion time.
    "bytes": 98318745851,
    "files": 1961,
    "control_sha256": "f201724829977746e831b76ee128d0d76bcf606d538f96ede344a2d9b1ba02da",
    "manifest_path": "/backups/postgresql/restore-tests/nov02-20261108T103343Z/evidence/files.sha256.json",
    "manifest_sha256": "b32cfdb78ec132d16a256e3c94cc97655bb7d7ef9cd8c63ecb6e777721ca9b8e",
    "manifest_kind": "external-copy-sha256",  # Not a pg_basebackup manifest.
    "restore_completed_at": "2026-11-08T10:56:27.704435+00:00",
    "restore_container": "cahier-restore-nov02-20261108t103343z",
    "restore_exit_code": 0,
    "restore_network": "none",
    "restore_published_ports": [],
    "restore_verified": True,
    "hnsw_lookup_verified": True,
    "postgres_image": "sha256:30ee450c42fda0596abaf71066c1612c79a0aaa791e655e5e00ce2c1e33ab6cc",
    "evidence_log_sha256": "04fac5850a9d2074bcc8e96238c8631bf8bc7ea6ee7e8bf95eb3ea5b10b58f7d",
}


def recent(value, now):
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None or not now - timedelta(hours=24) <= timestamp <= now:
        raise ValueError("Fresh verification (under 24h) required")
    return timestamp


def check_cold_exception(proof, *, now):
    """Called after shared physical destination/role checks. Raises on any gap.

    This validates operator attestations; it cannot remotely verify the files.
    The read-only preflight supplies observations, future preservation supplies
    the asset receipts. Neither is inferred from approving the old restore point.
    """
    if (
        proof["exception"] != EXCEPTION
        or json.dumps(proof["cold_backup"], sort_keys=True) != json.dumps(APPROVED, sort_keys=True)
        or proof["restore_point_accepted"] is not True
        or not proof["acceptance_reference"].strip()
    ):
        raise ValueError("Only the specifically accepted Nov 2 backup is allowed")
    if datetime.fromisoformat(APPROVED["restore_completed_at"]) > now:
        raise ValueError("Restore is in the future")
    comparison = proof["recent_comparison"]
    recent(comparison["checked_at"], now)
    if (
        comparison["unchanged"] is not True
        or comparison["baseline_sha256"] != BASELINE_SHA256
        or comparison["observed_sha256"] != BASELINE_SHA256
        or comparison["current_snapshot"] != "1155:1155:"
        or comparison["ssd_uuid"] != SSD_UUID
        or comparison["backup_uuid"] != APPROVED["volume_uuid"]
        or comparison["source_inventory_sha256"] != SOURCE_INVENTORY_SHA256
        or comparison["source_control_sha256"] != APPROVED["control_sha256"]
        or comparison["manifest_sha256"] != APPROVED["manifest_sha256"]
    ):
        raise ValueError("Backup, storage or current production comparison mismatch")
    assets = proof["rollback_assets"]
    recent(assets["preserved_at"], now)
    root = PurePosixPath(assets["directory"])
    if (
        str(root) != assets["directory"]
        or root.parent != PurePosixPath("/backups/postgresql")
        or not re.fullmatch(r"rollback-multicorpus-\d{8}T\d{6}Z", root.name)
        or assets["volume_uuid"] != APPROVED["volume_uuid"]
        or assets["verified"] is not True
        or assets["image_ids"] != IMAGE_IDS
        or assets["model_manifest_hash"] != MODEL_HASH
        or set(assets["artifacts"]) != {"configuration", "images", "model"}
    ):
        raise ValueError("Separate, verified rollback assets required")
    for name, item in assets["artifacts"].items():
        if (
            item["path"] != str(root / (name + ".tar"))
            or type(item["bytes"]) is not int
            or item["bytes"] <= 0
            or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
            or item["sha256"] == "0" * 64
        ):
            raise ValueError("Incomplete rollback archive receipt")
