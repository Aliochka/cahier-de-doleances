"""Prepared for the separately authorized deployment step. NOT run in preparation.

Default prints the non-secret inventory only. Explicit execution as root on
Gavroche saves assets into a NEW private HDD directory; never starts/stops a
service, writes to PostgreSQL, retags images or modifies source configurations.
"""

import argparse
import base64
import hashlib
import json
import os
import shlex
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def preserve(inventory, preflight):
    now = datetime.now(UTC)
    checked = datetime.fromisoformat(preflight["checked_at"])
    if (
        checked.tzinfo is None
        or not now - timedelta(hours=24) <= checked <= now
        or preflight["unchanged"] is not True
    ):
        raise ValueError("Fresh successful preflight required")
    if os.geteuid() != 0 or run("hostname") != "Gavroche":
        raise ValueError("Explicit Gavroche root session required")
    if (
        run("findmnt", "-n", "-o", "UUID", "-M", "/backups/postgresql")
        != "52ba8e78-4375-4286-8c75-5cfef6609c8a"
    ):
        raise ValueError("Wrong backup volume")
    if (
        run("findmnt", "-n", "-o", "UUID", "-M", "/data/postgresql")
        != "624405d4-3422-4b7d-8ca3-8579d8b513bb"
    ):
        raise ValueError("Wrong production SSD")
    for name, expected in inventory["images"].items():
        if json.loads(run("docker", "inspect", name))[0]["Image"] != expected:
            raise ValueError("Image changed since preparation: " + name)
    if any(not Path(p).exists() for p in inventory["configuration"]):
        raise ValueError("Missing configuration source")
    model = Path(inventory["model"])
    manifest = json.loads((model / "snapshot-manifest.json").read_text())
    manifest_hash = manifest.pop("manifest_hash")
    computed = hashlib.sha256(
        json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    if manifest_hash != inventory["model_manifest_hash"] or computed != manifest_hash:
        raise ValueError("Model manifest differs")
    for name, expected in manifest["files"].items():
        p = model / name
        if (
            not p.resolve().is_relative_to(Path("/srv/cahier-search/models").resolve())
            or sha256(p) != expected
        ):
            raise ValueError("Model content differs")
    root = Path("/backups/postgresql") / ("rollback-multicorpus-" + now.strftime("%Y%m%dT%H%M%SZ"))
    if Path("/backups/postgresql").resolve() != Path("/backups/postgresql"):
        raise ValueError("Unexpected backup path resolution")
    # 20GiB is a conservative floor for existing images + one BGE snapshot;
    # also include their actual reported logical image sizes (layers may overlap).
    image_bytes = sum(
        json.loads(run("docker", "image", "inspect", image))[0]["Size"]
        for image in inventory["images"].values()
    )
    if os.statvfs(root.parent).f_bavail * os.statvfs(root.parent).f_frsize < max(
        20 * 1024**3, image_bytes * 2 + 8 * 1024**3
    ):
        raise ValueError("Insufficient rollback archive space")
    os.umask(0o077)
    root.mkdir(mode=0o700, exist_ok=False)

    def archive(name, args):
        path = root / (name + ".tar")
        with path.open("xb") as f:
            subprocess.run(args, stdout=f, check=True)
            f.flush()
            os.fsync(f.fileno())
        # Structural read plus a full byte checksum; no load/restore is performed.
        subprocess.run(["tar", "-tf", str(path)], stdout=subprocess.DEVNULL, check=True)
        return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}

    artifacts = {
        "configuration": archive(
            "configuration",
            [
                "tar",
                "-c",
                "-p",
                "-f",
                "-",
                "-C",
                "/",
                *[p.lstrip("/") for p in inventory["configuration"]],
            ],
        ),
        "images": archive("images", ["docker", "image", "save", *inventory["images"].values()]),
        "model": archive(
            "model",
            [
                "tar",
                "--dereference",
                "-c",
                "-p",
                "-f",
                "-",
                "-C",
                "/",
                *[
                    str(model / name).lstrip("/")
                    for name in ("snapshot-manifest.json", *manifest["files"])
                ],
            ],
        ),
    }
    receipt = {
        "directory": str(root),
        "volume_uuid": "52ba8e78-4375-4286-8c75-5cfef6609c8a",
        "preserved_at": datetime.now(UTC).isoformat(),
        "verified": True,
        "artifacts": artifacts,
        "image_ids": inventory["images"],
        "model_manifest_hash": inventory["model_manifest_hash"],
    }
    with (root / "receipt.json").open("x") as f:
        json.dump(receipt, f, indent=2)
    with (root / "files.sha256").open("x") as f:
        for name, item in artifacts.items():
            f.write(item["sha256"] + "  " + name + ".tar\n")
    print("CAHIER_ROLLBACK_RECEIPT " + json.dumps(receipt), flush=True)


def via_ssh(inventory, preflight):
    if not sys.stdin.isatty():
        raise ValueError("Operator terminal required for private sudo authentication")
    # Execute from memory before any remote checkout/configuration change.
    source = Path(__file__).read_bytes()
    bootstrap = (
        "import base64,json; scope={'__name__':'rollback_preservation'}; "
        + "exec(base64.b64decode("
        + repr(base64.b64encode(source).decode())
        + "),scope); "
        + "scope['preserve']("
        + repr(inventory)
        + ","
        + repr(preflight)
        + ")"
    )
    child = subprocess.Popen(
        [
            "ssh",
            "-tt",
            "-S",
            "/tmp/cahier-gavroche-audit.sock",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "UpdateHostKeys=no",
            "gavroche@192.168.1.185",
            "sudo -p '[sudo rollback preservation] Password: ' python3 -B -c "
            + shlex.quote(bootstrap),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    captured = bytearray()
    while block := os.read(child.stdout.fileno(), 65536):
        captured.extend(block)
        os.write(sys.stdout.fileno(), block)
    if child.wait():
        raise RuntimeError(
            "Preservation failed; no complete receipt: retain partial files, do not deploy"
        )
    receipt = json.loads(captured.decode().split("CAHIER_ROLLBACK_RECEIPT ", 1)[1].splitlines()[0])
    folder = Path("private/search/multicorpus-prerequisites")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = folder / ("rollback-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ".json")
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
        json.dump(receipt, f, indent=2)
    print("Local receipt: " + str(target))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-preservation", action="store_true")
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--via-ssh", action="store_true")
    args = parser.parse_args()
    inventory = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "deploy/documentary/gavroche-rollback-inventory.json"
        ).read_text()
    )
    if not args.execute_preservation:
        print(json.dumps({"mode": "plan-only", "inventory": inventory}, indent=2))
        return
    if args.preflight is None:
        parser.error("Explicit recent preflight JSON required")
    action = via_ssh if args.via_ssh else preserve
    action(inventory, json.loads(args.preflight.read_text()))


if __name__ == "__main__":
    main()
