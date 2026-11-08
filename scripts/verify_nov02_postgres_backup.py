"""Verify the Nov 2 cold backup on an independent, network-isolated copy.

Run locally in an operator terminal (sudo password stays in that terminal):
    python3 scripts/verify_nov02_postgres_backup.py --restore-test

Only the new restore-tests directory and disposable test containers are writable.
The original is mounted read-only, including while copying. Production SQL is
read-only, bounded and contains no full scans of the large application tables.
No deployment, backup gate change, original cleanup or production restart.
"""

import argparse
import base64
import hashlib
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

SOURCE = "/backups/postgresql/wallace-original-20261102/pg17/data"
BACKUP_UUID = "52ba8e78-4375-4286-8c75-5cfef6609c8a"
CLUSTER = "7695026423032606758"
PG_IMAGE = "sha256:30ee450c42fda0596abaf71066c1612c79a0aaa791e655e5e00ce2c1e33ab6cc"
PY_IMAGE = "sha256:e0c26f229536597004ef299d6e8406fb087916d0511eabe8bd02e5543070c7cd"
PREFIX = "CAHIER_BACKUP_EVENT "


def emit(event, **values):
    print(
        PREFIX + json.dumps({"event": event, "utc": datetime.now(UTC).isoformat(), **values}),
        flush=True,
    )


def command(*args, input=None, timeout=90):
    p = subprocess.run(args, input=input, text=True, capture_output=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f"{args[:3]!r}: {p.stderr[-2500:]}")
    return p.stdout.strip()


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def inventory(root):
    entries = []
    for p in sorted(root.rglob("*")):
        s = p.lstat()
        if stat.S_ISLNK(s.st_mode):
            # External WAL/tablespaces must not silently refer to production.
            raise RuntimeError(f"Symlink requires a separate reviewed plan: {p.relative_to(root)}")
        if not (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)):
            raise RuntimeError(f"Unexpected file type: {p.relative_to(root)}")
        entries.append(
            {
                "path": str(p.relative_to(root)),
                "size": s.st_size,
                "mode": s.st_mode,
                "uid": s.st_uid,
                "gid": s.st_gid,
                "mtime_ns": s.st_mtime_ns,
                "ctime_ns": s.st_ctime_ns,
                "dev": s.st_dev,
                "ino": s.st_ino,
            }
        )
    return entries


def copy_agent(copy=False):
    """Runs without network, with /source strictly read-only, as postgres UID."""
    root = Path("/source")
    entries = inventory(root)
    required = ("PG_VERSION", "global/pg_control", "base", "pg_wal", "pg_xact", "pg_multixact")
    if not all((root / name).exists() for name in required):
        raise RuntimeError("Incomplete cluster layout")
    if (root / "PG_VERSION").read_text().strip() != "17":
        raise RuntimeError("Wrong PostgreSQL major")
    for name in ("postmaster.pid", "backup_label", "standby.signal", "recovery.signal"):
        if (root / name).exists():
            raise RuntimeError(f"Unexpected {name}: requires review before restoring")
    if list((root / "pg_tblspc").iterdir()):
        raise RuntimeError("External tablespaces require a separately reviewed copy")
    regular = [e for e in entries if stat.S_ISREG(e["mode"])]
    summary = {
        "files": len(regular),
        "bytes": sum(e["size"] for e in regular),
        "layout": [p.name for p in sorted(root.iterdir())],
        "owners": sorted({(e["uid"], e["gid"]) for e in entries}),
        "control_sha256": digest(root / "global/pg_control"),
        "inventory_sha256": hashlib.sha256(
            json.dumps(entries, sort_keys=True).encode()
        ).hexdigest(),
        "wal_files": [e for e in regular if e["path"].startswith("pg_wal/")],
        "key_metadata": [
            e
            for e in regular
            if e["path"]
            in {"PG_VERSION", "global/pg_control", "postmaster.opts", "backup_label.old"}
        ],
    }
    emit("source_inventory", **summary)
    if not copy:
        return
    if any((e["uid"], e["gid"]) != (os.getuid(), os.getgid()) for e in entries):
        raise RuntimeError("Mixed owners: refusing a recursive ownership change")
    dest = Path("/copy")
    if list(dest.iterdir()):
        raise RuntimeError("Copy destination must be empty")
    rows = []
    copied = 0
    last = time.monotonic()
    for e in entries:
        src, dst = root / e["path"], dest / e["path"]
        if stat.S_ISDIR(e["mode"]):
            dst.mkdir()
            continue
        h = hashlib.sha256()
        with src.open("rb") as inp, dst.open("xb") as out:
            while block := inp.read(4 * 1024 * 1024):
                h.update(block)
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
        if (src.stat().st_dev, src.stat().st_ino) == (dst.stat().st_dev, dst.stat().st_ino):
            raise RuntimeError("Source and destination share an inode")
        if h.hexdigest() != digest(dst):
            raise RuntimeError(f"Copy checksum mismatch: {e['path']}")
        shutil.copystat(src, dst)
        rows.append({"path": e["path"], "bytes": e["size"], "sha256": h.hexdigest()})
        copied += e["size"]
        if time.monotonic() - last > 10:
            emit("copy_progress", bytes=copied, total=summary["bytes"], files=len(rows))
            last = time.monotonic()
    for e in reversed(entries):
        if stat.S_ISDIR(e["mode"]):
            shutil.copystat(root / e["path"], dest / e["path"])
    if inventory(root) != entries:
        raise RuntimeError("Original metadata changed during verification")
    manifest = Path("/evidence/files.sha256.json")
    manifest.write_text(json.dumps(rows, sort_keys=True))
    emit(
        "copy_verified",
        bytes=copied,
        files=len(rows),
        manifest_sha256=digest(manifest),
        original_metadata_unchanged=True,
        control_sha256=digest(dest / "global/pg_control"),
    )


def query(container, database, sql, timeout=8):
    text = (
        f"BEGIN READ ONLY; SET LOCAL statement_timeout='{timeout}s'; "
        "SET LOCAL lock_timeout='500ms'; " + sql + "; ROLLBACK;"
    )
    raw = command(
        "docker",
        "exec",
        "-i",
        container,
        "psql",
        "-XqAt",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "cahier",
        "-d",
        database,
        input=text,
        timeout=timeout + 15,
    )
    return [json.loads(line) for line in raw.splitlines() if line]


def snapshot(container):
    result = {}
    queries = {
        "identity": """SELECT json_build_object('sid',(SELECT system_identifier::text FROM pg_control_system()),
            'version',current_setting('server_version'),'db',current_database(),
            'databases',(SELECT json_agg(json_build_object('name',datname,'oid',oid,'collate',datcollate,
                'ctype',datctype)) FROM pg_database WHERE NOT datistemplate),
            'extensions',(SELECT json_agg(json_build_object('name',extname,'version',extversion)) FROM pg_extension),
            'french_probe',to_tsvector('french','ÉTATS généraux privilèges curés agriculture Agen')::text)""",
        "indexes": """SELECT json_build_object('schema',n.nspname,'name',c.relname,'node',c.relfilenode,
            'valid',i.indisvalid,'ready',i.indisready,'definition',pg_get_indexdef(c.oid))
            FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('public','rag_full','rag_tuning') ORDER BY n.nspname,c.relname""",
        "relations": """SELECT json_build_object('schema',n.nspname,'name',c.relname,
            'estimated_rows',c.reltuples,'pages',c.relpages,'node',c.relfilenode)
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind IN ('r','p')
            AND n.nspname IN ('public','rag_full','rag_tuning') ORDER BY n.nspname,c.relname""",
        "columns": """SELECT json_build_object('schema',table_schema,'table',table_name,'column',column_name,
            'type',data_type) FROM information_schema.columns WHERE table_schema IN ('public','rag_full','rag_tuning')
            ORDER BY table_schema,table_name,ordinal_position""",
    }
    for db in ("cahier_doleances", "cahier_search"):
        values = {}
        result[db] = values
        for name, sql in queries.items():
            try:
                values[name] = query(container, db, sql)
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                values[name] = {"error": str(exc)[:1500]}
        for relation in (
            "public.alembic_version",
            "public.rag_alembic_version",
            "rag_full.spaces",
            "rag_tuning.statistics",
        ):
            if query(container, db, f"SELECT to_json(to_regclass('{relation}') IS NOT NULL)") == [
                True
            ]:
                values[relation] = query(
                    container, db, f"SELECT to_jsonb(t) FROM {relation} t LIMIT 10"
                )
        if db == "cahier_search" and "rag_full.spaces" in values:
            values["lexical_sample"] = query(
                container,
                db,
                "SELECT row_to_json(t) FROM (SELECT space_id,term,documents FROM rag_tuning.term_statistics WHERE space_id='full' AND term IN ('agricultur','fiscal','justic','éduc')) t",
            )
            sample_sql = """SELECT json_build_object('ordinal',ordinal,'document_id',document_id,
                'content_hash',content_hash,'record_md5',md5(record::text)) FROM rag_full.documents_full
                WHERE space_id='full' AND ordinal IN (1,2586178,5172356) ORDER BY ordinal"""
            try:
                values["document_samples"] = query(container, db, sample_sql)
                ids = [r["document_id"] for r in values["document_samples"]]
                quoted = ",".join("'" + str(v).replace("'", "''") + "'" for v in ids)
                if quoted:
                    values["segment_samples"] = query(
                        container,
                        db,
                        f"""SELECT json_build_object(
                        'document_id',document_id,'segment_index',segment_index,
                        'representation_id',representation_id,'content_hash',content_hash,
                        'vector_hash',vector_hash,'dimensions',vector_dims(embedding),
                        'stored_vector_md5',md5(vector_send(embedding))) FROM rag_full.segments_full
                        WHERE space_id='full' AND document_id IN ({quoted}) ORDER BY document_id,segment_index LIMIT 30""",
                    )
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                values["sample_error"] = str(exc)[:1500]
        if db == "cahier_doleances":
            tables = {r["name"] for r in values.get("relations", []) if isinstance(r, dict)}
            cols = {
                (r["table"], r["column"]) for r in values.get("columns", []) if isinstance(r, dict)
            }
            for table in ("forms", "questions", "options", "question_stats", "alembic_version"):
                if table in tables:
                    try:
                        values[table + "_digest"] = query(
                            container,
                            db,
                            f"SELECT json_build_object('count',count(*),'md5',md5(string_agg(row_to_json(t)::text,'' ORDER BY row_to_json(t)::text))) FROM public.{table} t",
                        )
                    except (RuntimeError, subprocess.TimeoutExpired) as exc:
                        values[table + "_digest"] = {"error": str(exc)[:1000]}
            # PK lookups only, not MAX(created_at) scans of millions of records.
            for table in ("answers", "contributions", "authors", "users", "bookmarks"):
                if (table, "id") in cols:
                    selected = [
                        c
                        for c in ("id", "created_at", "last_login", "submitted_at")
                        if (table, c) in cols
                    ]
                    try:
                        values[table + "_last_id"] = query(
                            container,
                            db,
                            f"SELECT row_to_json(t) FROM (SELECT {','.join(selected)} FROM public.{table} ORDER BY id DESC LIMIT 1) t",
                        )
                    except (RuntimeError, subprocess.TimeoutExpired) as exc:
                        values[table + "_last_id"] = {"error": str(exc)[:1000]}
            for table in ("users", "bookmarks"):
                if table in tables:
                    fields = [
                        c
                        for c in (
                            "id",
                            "created_at",
                            "last_login",
                            "is_active",
                            "profile_completed",
                            "page_type",
                            "page_id",
                            "user_id",
                        )
                        if (table, c) in cols
                    ]
                    try:
                        values[table + "_summary"] = query(
                            container,
                            db,
                            f"SELECT json_build_object('count',count(*),'safe_fields_md5',md5(string_agg(row_to_json(t)::text,'' ORDER BY id))) FROM (SELECT {','.join(fields)} FROM public.{table}) t",
                        )
                    except (RuntimeError, subprocess.TimeoutExpired) as exc:
                        values[table + "_summary"] = {"error": str(exc)[:1000]}
        emit("database_snapshot", container=container, database=db, result=values)
    return result


def remote(source_code):
    if os.geteuid() != 0 or command("hostname") != "Gavroche":
        raise RuntimeError("Explicit Gavroche root session required")
    if command("findmnt", "-n", "-o", "UUID", "--target", "/backups/postgresql") != BACKUP_UUID:
        raise RuntimeError("Backup filesystem identity mismatch")
    prod = json.loads(command("docker", "inspect", "cahier-postgres"))[0]
    if prod["Image"] != PG_IMAGE or not prod["State"]["Running"]:
        raise RuntimeError("Unexpected production image/state")
    mounts = {m["Destination"]: m["Source"] for m in prod["Mounts"]}
    if mounts.get("/var/lib/postgresql/data") != "/data/postgresql/pg17/data":
        raise RuntimeError("Unexpected production data mount")
    if (
        Path(SOURCE).resolve() != Path(SOURCE)
        or Path(SOURCE).stat().st_dev == Path(mounts["/var/lib/postgresql/data"]).stat().st_dev
    ):
        raise RuntimeError("Backup is a symlink or shares production storage")
    before = {"id": prod["Id"], "image": prod["Image"], "started": prod["State"]["StartedAt"]}
    emit("production_before", **before)
    common = [
        "docker",
        "run",
        "--rm",
        "--pull=never",
        "--network",
        "none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt",
        "no-new-privileges",
        "--cpus",
        "1",
        "--memory",
        "4g",
    ]
    mount_source = ["--mount", f"type=bind,src={SOURCE},dst=/source,readonly"]
    uid = Path(SOURCE).stat().st_uid
    gid = Path(SOURCE).stat().st_gid
    if (uid, gid) != (999, 999):
        raise RuntimeError("Unexpected backup owner")
    common.extend(["--user", f"{uid}:{gid}"])
    client = [
        *common,
        "--user",
        f"{uid}:{gid}",
        *mount_source,
        "--entrypoint",
        "python",
        PY_IMAGE,
        "-I",
        "-u",
        "-c",
        source_code,
    ]
    control = command(
        *common,
        *mount_source,
        "--env",
        "LC_ALL=C",
        "--entrypoint",
        "pg_controldata",
        PG_IMAGE,
        "/source",
    )
    emit("backup_control", path=SOURCE, output=control)
    if CLUSTER not in control or not any(
        line.partition(":")[2].strip() == "shut down" and "cluster state" in line
        for line in control.splitlines()
    ):
        raise RuntimeError("Backup is not the expected cleanly stopped production cluster")
    history = []
    for filename in ("/root/.bash_history", "/home/gavroche/.bash_history"):
        p = Path(filename)
        if p.is_file() and p.stat().st_size < 4 * 1024**2:
            for line in p.read_text(errors="replace").splitlines():
                if (
                    "rsync" in line
                    and ("postgres" in line or "wallace" in line)
                    and not any(
                        word in line.lower() for word in ("password", "secret", "token", "://")
                    )
                ):
                    history.append({"file": filename, "command": line[:1200]})
    emit(
        "transfer_history",
        matches=history,
        directory_metadata={
            "ctime": Path(SOURCE).stat().st_ctime,
            "mtime": Path(SOURCE).stat().st_mtime,
        },
    )
    # Inspect the older sibling separately; never copy or start it.
    sibling = str(Path(SOURCE).parent.parent / "pg17-validation")
    if Path(sibling, "PG_VERSION").is_file():
        try:
            output = command(
                *common,
                "--mount",
                f"type=bind,src={sibling},dst=/source,readonly",
                "--env",
                "LC_ALL=C",
                "--entrypoint",
                "pg_controldata",
                PG_IMAGE,
                "/source",
            )
            emit("sibling_control", path=sibling, output=output)
        except RuntimeError as exc:
            emit("sibling_control_error", detail=str(exc))
    command_output = command(*client, "--inspect-agent")
    print(command_output, flush=True)
    inv = next(
        json.loads(s[len(PREFIX) :]) for s in command_output.splitlines() if s.startswith(PREFIX)
    )
    if shutil.disk_usage("/backups/postgresql").free < inv["bytes"] * 1.15 + 2 * 1024**3:
        raise RuntimeError("Insufficient independent test copy disk budget")
    current = snapshot("cahier-postgres")
    if current["cahier_search"]["identity"][0]["sid"] != CLUSTER:
        raise RuntimeError("Production SQL identity mismatch")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    parent = Path("/backups/postgresql/restore-tests")
    if parent.exists() and (parent.is_symlink() or parent.resolve() != parent):
        raise RuntimeError("Unexpected restore-tests parent")
    parent.mkdir(exist_ok=True, mode=0o700)
    target = parent / ("nov02-" + stamp)
    target.mkdir(mode=0o700)
    for name in ("pgdata", "evidence"):
        p = target / name
        p.mkdir(mode=0o700)
        os.chown(p, uid, gid)  # New, empty directories only. Never recursive.
    emit("restore_destination", directory=str(target), free_bytes=shutil.disk_usage(parent).free)
    copier = [
        *common,
        "--user",
        f"{uid}:{gid}",
        *mount_source,
        "--mount",
        f"type=bind,src={target}/pgdata,dst=/copy",
        "--mount",
        f"type=bind,src={target}/evidence,dst=/evidence",
        "--entrypoint",
        "python",
        PY_IMAGE,
        "-I",
        "-u",
        "-c",
        source_code,
        "--copy-agent",
    ]
    # Inherit stdout for continuous copy progress; no password or secret output.
    subprocess.run(copier, check=True)
    name = "cahier-restore-nov02-" + stamp.lower()
    started = False
    try:
        command(
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--pull=never",
            "--network",
            "none",
            "--read-only",
            "--user",
            f"{uid}:{gid}",
            "--cap-drop=ALL",
            "--security-opt",
            "no-new-privileges",
            "--cpus",
            "2",
            "--memory",
            "2g",
            "--shm-size",
            "256m",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,mode=1777",
            "--mount",
            f"type=bind,src={target}/pgdata,dst=/var/lib/postgresql/data",
            "--env",
            "PGHOST=/tmp",
            "--entrypoint",
            "postgres",
            PG_IMAGE,
            "-D",
            "/var/lib/postgresql/data",
            "-c",
            "listen_addresses=",
            "-c",
            "unix_socket_directories=/tmp",
            "-c",
            "archive_mode=off",
            "-c",
            "archive_command=",
            "-c",
            "restore_command=",
            "-c",
            "primary_conninfo=",
        )
        started = True
        inspected = json.loads(command("docker", "inspect", name))[0]
        if inspected["HostConfig"]["NetworkMode"] != "none" or inspected["HostConfig"].get(
            "PortBindings"
        ):
            raise RuntimeError("Test network isolation failure")
        emit(
            "test_isolation",
            name=name,
            network="none",
            published_ports=[],
            mounts=inspected["Mounts"],
        )
        ready = False
        for _ in range(45):
            try:
                query(name, "postgres", "SELECT to_json(current_database())", timeout=2)
                ready = True
                break
            except RuntimeError:
                time.sleep(2)
        if not ready:
            raise RuntimeError("Test server did not become ready")
        restored = snapshot(name)
        # Actual HNSW lookup on the COPY only, with a plan check before execution.
        try:
            row = restored["cahier_search"]["segment_samples"][0]
            doc = str(row["document_id"]).replace("'", "''")
            vector = f"(SELECT embedding FROM rag_full.segments_full WHERE space_id='full' AND document_id='{doc}' AND segment_index={int(row['segment_index'])})"
            sql = f"SELECT document_id,segment_index FROM rag_full.segments_full ORDER BY embedding <=> {vector} LIMIT 3"
            plan_raw = command(
                "docker",
                "exec",
                "-i",
                name,
                "psql",
                "-XqAt",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "cahier",
                "-d",
                "cahier_search",
                input="BEGIN READ ONLY; SET LOCAL statement_timeout='30s'; EXPLAIN (FORMAT JSON) "
                + sql
                + "; ROLLBACK;",
                timeout=45,
            )
            plan = json.loads(plan_raw)
            emit("hnsw_plan", plan=plan)
            if "segments_full_hnsw" not in plan_raw:
                raise RuntimeError("Plan does not use expected HNSW: refusing expensive scan")
            emit(
                "hnsw_lookup",
                rows=query(
                    name, "cahier_search", "SELECT row_to_json(t) FROM (" + sql + ") t", timeout=30
                ),
            )
        except (RuntimeError, KeyError, IndexError, subprocess.TimeoutExpired) as exc:
            emit("hnsw_check_error", detail=str(exc)[:1800])
        after_sql = snapshot("cahier-postgres")
        differences = {}
        for db in restored:
            differences[db] = [
                key for key in restored[db] if restored[db][key] != after_sql[db].get(key)
            ]
        emit(
            "comparison",
            differences=differences,
            production_changed_during_test={
                db: [k for k in current[db] if current[db][k] != after_sql[db].get(k)]
                for db in current
            },
        )
    finally:
        if started:
            command("docker", "stop", "--time", "60", name, timeout=80)
            logs = subprocess.run(
                ["docker", "logs", "--tail", "100", name],
                text=True,
                capture_output=True,
                check=True,
            )
            emit("test_logs", output=logs.stdout + logs.stderr)
            state = json.loads(command("docker", "inspect", name))[0]["State"]
            emit("test_stopped", name=name, state=state)
        final = json.loads(command("docker", "inspect", "cahier-postgres"))[0]
        after = {"id": final["Id"], "image": final["Image"], "started": final["State"]["StartedAt"]}
        emit("production_after", unchanged=(before == after), **after)
        final_control = command(
            *common,
            *mount_source,
            "--env",
            "LC_ALL=C",
            "--entrypoint",
            "pg_controldata",
            PG_IMAGE,
            "/source",
        )
        emit("original_control_after", unchanged=(control == final_control), output=final_control)
    emit("complete", directory=str(target))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore-test", action="store_true")
    parser.add_argument("--remote-source", help=argparse.SUPPRESS)
    parser.add_argument("--copy-agent", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--inspect-agent", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.copy_agent or args.inspect_agent:
        copy_agent(copy=args.copy_agent)
        return
    if args.remote_source:
        remote(base64.b64decode(args.remote_source).decode())
        return
    if not args.restore_test or not sys.stdin.isatty():
        parser.error("Run --restore-test in your terminal to enter sudo privately")
    source = Path(__file__).read_text()
    output = Path("private/search/backup-20261102-validation")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    logfile = output / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ".jsonl")
    remote_cmd = (
        "sudo -p '[sudo backup verification] Password: ' python3 -B -u -c "
        + shlex.quote(source)
        + " --remote-source "
        + shlex.quote(base64.b64encode(source.encode()).decode())
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
            remote_cmd,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    with os.fdopen(os.open(logfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as log:
        while block := os.read(child.stdout.fileno(), 65536):
            log.write(block)
            log.flush()
            os.write(sys.stdout.fileno(), block)
    code = child.wait()
    print(f"Local evidence: {logfile}; remote exit={code}")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
