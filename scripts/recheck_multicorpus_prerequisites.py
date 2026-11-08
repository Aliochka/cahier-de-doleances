"""Focused read-only Gavroche preflight. Never restore, copy or deploy remotely.

Run in an operator terminal; sudo password remains there. Reuses only the
previous verifier's read-only helpers, NOT its restoration entry point.
"""

import argparse
import base64
import contextlib
import hashlib
import io
import json
import os
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

MARKER = "CAHIER_PREFLIGHT "


def remote(helper_source, inventory):
    ns = {"__name__": "readonly_helpers"}
    exec(helper_source, ns)
    run, query = ns["command"], ns["query"]
    if os.geteuid() != 0 or run("hostname") != "Gavroche":
        raise RuntimeError("Explicit Gavroche root inspection required")
    containers = {}
    for name, expected in inventory["images"].items():
        c = json.loads(run("docker", "inspect", name))[0]
        if c["Image"] != expected or not c["State"]["Running"]:
            raise RuntimeError("Deployed image/state changed: " + name)
        containers[name] = {
            "image": c["Image"],
            "started": c["State"]["StartedAt"],
            "health": c["State"].get("Health", {}).get("Status"),
            "mounts": c["Mounts"],
        }
    pg_mounts = {m["Destination"]: m["Source"] for m in containers["cahier-postgres"]["mounts"]}
    if pg_mounts.get("/var/lib/postgresql/data") != "/data/postgresql/pg17/data":
        raise RuntimeError("Wrong production PGDATA mount")
    ssd = run("findmnt", "-n", "-o", "UUID", "-M", "/data/postgresql")
    hdd = run("findmnt", "-n", "-o", "UUID", "-M", "/backups/postgresql")
    if ssd != "624405d4-3422-4b7d-8ca3-8579d8b513bb" or hdd != ns["BACKUP_UUID"]:
        raise RuntimeError("Wrong mounted SSD/HDD")
    # RO diagnostics only: no server, destination mount, copy agent or restore.
    common = [
        "docker",
        "run",
        "--rm",
        "--pull=never",
        "--network",
        "none",
        "--read-only",
        "--user",
        "999:999",
        "--cap-drop=ALL",
        "--cpus",
        "1",
        "--memory",
        "4g",
    ]
    raw = run(
        *common,
        "--mount",
        f"type=bind,src={ns['SOURCE']},dst=/source,readonly",
        "--entrypoint",
        "python",
        ns["PY_IMAGE"],
        "-I",
        "-c",
        helper_source,
        "--inspect-agent",
    )
    source = json.loads(raw.split(ns["PREFIX"], 1)[1])
    manifest = Path(
        "/backups/postgresql/restore-tests/nov02-20261108T103343Z/evidence/files.sha256.json"
    )
    if manifest.is_symlink() or not manifest.is_file():
        raise RuntimeError("Missing external verified-copy manifest")
    with contextlib.redirect_stdout(io.StringIO()):
        observed = ns["snapshot"]("cahier-postgres")
    observed_hash = hashlib.sha256(
        json.dumps(observed, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    current_snapshot = query(
        "cahier-postgres", "cahier_search", "SELECT to_json(pg_current_snapshot()::text)"
    )[0]
    # Hash the exact installed model files, never load the model or encode text.
    model_code = "from cahier_rag.embeddings.registry import MODELS; from cahier_rag.embeddings.snapshots import verify_snapshot; import json; p,h=verify_snapshot(MODELS['bge-m3'],'/models'); print(json.dumps({'path':str(p),'manifest_hash':h}))"
    model = json.loads(
        run(
            *common,
            "--mount",
            "type=bind,src=/srv/cahier-search/models,dst=/models,readonly",
            "--entrypoint",
            "python",
            ns["PY_IMAGE"],
            "-c",
            model_code,
            timeout=120,
        )
    )
    if model["manifest_hash"] != inventory["model_manifest_hash"]:
        raise RuntimeError("Model snapshot differs")
    missing = [p for p in inventory["configuration"] if not Path(p).exists()]
    if missing:
        raise RuntimeError("Rollback sources missing: " + repr(missing))
    result = {
        "checked_at": datetime.now(UTC).isoformat(),
        "baseline_sha256": "e2a11f8155a1541792273eefa69e58416834383f35d4e03407ffe9fd9167c101",
        "observed_sha256": observed_hash,
        "unchanged": observed_hash
        == "e2a11f8155a1541792273eefa69e58416834383f35d4e03407ffe9fd9167c101",
        "current_snapshot": current_snapshot,
        "ssd_uuid": ssd,
        "backup_uuid": hdd,
        "source_inventory_sha256": source["inventory_sha256"],
        "source_control_sha256": source["control_sha256"],
        "manifest_sha256": ns["digest"](manifest),
        "resources": {
            "disk": run("df", "-B1", "/data/postgresql", "/backups/postgresql", "/"),
            "memory": run("free", "-b"),
            "cpus": run("nproc"),
        },
        "containers": containers,
        "model": model,
        "server_checkout": run(
            "git",
            "-c",
            "safe.directory=/srv/cahier-de-doleances-app",
            "-C",
            "/srv/cahier-de-doleances-app",
            "rev-parse",
            "HEAD",
        ),
        "configuration_sources_present": True,
        "notes": "Presence/metadata plus pinned manifest/control; not a fresh full 98GB content scan or another restore test",
    }
    print(MARKER + json.dumps(result), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--remote-helper", help=argparse.SUPPRESS)
    p.add_argument("--inventory", help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.remote_helper:
        remote(
            base64.b64decode(args.remote_helper).decode(),
            json.loads(base64.b64decode(args.inventory)),
        )
        return
    if not sys.stdin.isatty():
        p.error("Run in your terminal to authenticate sudo privately")
    root = Path(__file__).resolve().parents[1]
    helper = (root / "scripts/verify_nov02_postgres_backup.py").read_bytes()
    inventory = (root / "deploy/documentary/gavroche-rollback-inventory.json").read_bytes()
    code = Path(__file__).read_text()
    command = (
        "sudo -p '[sudo read-only preflight] Password: ' python3 -B -u -c "
        + shlex.quote(code)
        + " --remote-helper "
        + shlex.quote(base64.b64encode(helper).decode())
        + " --inventory "
        + shlex.quote(base64.b64encode(inventory).decode())
    )
    directory = root / "private/search/multicorpus-prerequisites"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = directory / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ".log")
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
            command,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    captured = bytearray()
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        while block := os.read(child.stdout.fileno(), 65536):
            f.write(block)
            f.flush()
            captured.extend(block)
            os.write(sys.stdout.fileno(), block)
    if child.wait():
        raise SystemExit("Read-only preflight failed; see " + str(target))
    data = json.loads(captured.decode().split(MARKER, 1)[1].splitlines()[0])
    data["local_base_commit"] = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    with os.fdopen(
        os.open(target.with_suffix(".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
    ) as f:
        json.dump(data, f, indent=2)
    print("Private evidence: " + str(target.with_suffix(".json")))


if __name__ == "__main__":
    main()
