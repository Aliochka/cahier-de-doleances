"""Sanitized read-only production inventory, with password entered in YOUR terminal.

No file is installed on the server. No Docker service/migration/import is started.
The SSH control socket must already be authenticated by the operator.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

START = "CAHIER_READONLY_AUDIT_BEGIN"
END = "CAHIER_READONLY_AUDIT_END"


def run(*args, input=None):
    result = subprocess.run(args, input=input, capture_output=True, text=True, timeout=40)
    if result.returncode:
        return {"unavailable": args[0], "exit": result.returncode}
    return result.stdout.strip()


def redact(value):
    return "\n".join(
        "[secret-bearing line omitted]"
        if re.search(r"password|passwd|secret|token|postgres(?:ql)?(?:\+\w+)?://", line, re.I)
        else line
        for line in value.splitlines()
    )


def endpoint(value):
    parsed = urlsplit(value)
    return dict(
        host=parsed.hostname,
        port=parsed.port,
        database=parsed.path.lstrip("/"),
        role=parsed.username,
    )


def text_file(path):
    p = Path(path)
    if not p.is_file() or p.stat().st_size > 131072:
        return {"unavailable": str(p)}
    return redact(p.read_text())


def remote_inventory():
    result = {
        key: run(*command)
        for key, command in {
            "hostname": ["hostname"],
            "date": ["date", "-u", "+%FT%TZ"],
            "cpu": ["nproc"],
            "memory": ["free", "-b"],
            "filesystem": ["df", "-B1", "-T"],
            "block_devices": ["lsblk", "-o", "NAME,SIZE,FSTYPE,UUID,MOUNTPOINTS"],
            "docker_root": ["docker", "info", "--format", "{{.DockerRootDir}}"],
            "docker_version": ["docker", "version", "--format", "{{json .Server}}"],
            "compose_version": ["docker", "compose", "version"],
            "docker_usage": ["docker", "system", "df"],
            "docker_stats": ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
            "mounts": ["findmnt", "-rn", "-o", "TARGET,SOURCE,FSTYPE,OPTIONS"],
            "docker_unit": ["systemctl", "cat", "docker.service"],
            "timers": ["systemctl", "list-timers", "--all", "--no-pager"],
            "root_crontab": ["crontab", "-l"],
        }.items()
    }
    for key in ("docker_unit", "root_crontab"):
        if isinstance(result[key], str):
            result[key] = redact(result[key])
    result["fstab"] = text_file("/etc/fstab")
    ids = run("docker", "ps", "-aq")
    if not isinstance(ids, str) or not ids:
        raise RuntimeError("Cannot inspect existing Docker containers")
    containers = json.loads(run("docker", "inspect", *ids.split()))
    result["containers"] = []
    result["files"] = {}
    result["repositories"] = {}
    safe_env = {
        "ENV",
        "PGDATA",
        "PG_VERSION",
        "POSTGRES_USER",
        "POSTGRES_DB",
        "HYBRID_SEARCH_ENABLED",
        "SEARCH_DEVICE",
        "SEARCH_PRECISION",
        "SEARCH_CPU_THREADS",
        "SEARCH_MODELS_DIR",
        "SEARCH_READER_ENV",
        "SEARCH_PUBLICATION_FILE",
        "MULTICORPUS_CONFIG_FILE",
        "DOCUMENTARY_LOCAL_PREVIEW",
        "API_BASE_URL",
        "HOST",
        "PORT",
        "EXPECTED_ALEMBIC_REVISION",
        "TRUSTED_PROXY_IPS",
        "SSR_HTTP_CLIENT_IP",
        "ENFORCE_HTTPS",
        "HEALTHCHECK_HOST",
    }
    postgres = []
    for c in containers:
        env = dict(v.split("=", 1) for v in c["Config"].get("Env", []) if "=" in v)
        labels = c["Config"].get("Labels") or {}
        image = json.loads(run("docker", "image", "inspect", c["Image"]))[0]
        public = {k: v for k, v in env.items() if k in safe_env}
        for k in ("DATABASE_URL", "RAG_DATABASE_URL", "RAG_SOURCE_DATABASE_URL"):
            if env.get(k):
                public[k] = endpoint(env[k])
        for k in ("SEARCH_CURSOR_KEY", "SEARCH_PUBLICATION_KEY", "SECRET_KEY"):
            public[k + "_present"] = bool(env.get(k))
        result["containers"].append(
            dict(
                name=c["Name"],
                id=c["Id"][:12],
                image=c["Config"]["Image"],
                image_id=c["Image"],
                image_bytes=image["Size"],
                image_digests=image.get("RepoDigests"),
                revision=(image.get("Config", {}).get("Labels") or {}).get(
                    "org.opencontainers.image.revision"
                ),
                state={k: c["State"].get(k) for k in ("Status", "StartedAt", "OOMKilled")},
                health=(c["State"].get("Health") or {}).get("Status"),
                mounts=c["Mounts"],
                ports=c["NetworkSettings"]["Ports"],
                networks={
                    k: v.get("IPAddress") for k, v in c["NetworkSettings"]["Networks"].items()
                },
                restart=c["HostConfig"]["RestartPolicy"],
                environment=public,
                compose={k: v for k, v in labels.items() if k.startswith("com.docker.compose.")},
                readonly=c["HostConfig"].get("ReadonlyRootfs"),
                memory_limit=c["HostConfig"].get("Memory"),
                cpus=c["HostConfig"].get("NanoCpus"),
                entrypoint=c["Config"].get("Entrypoint") if env.get("PGDATA") else None,
                command=c["Config"].get("Cmd") if env.get("PGDATA") else None,
            )
        )
        if env.get("PGDATA"):
            postgres.append(c["Id"])
        for mount in c["Mounts"]:
            src, dst = mount["Source"], mount["Destination"]
            if dst in {"/run/search/reader.env"}:
                # Parse only the two known URLs, never publish credentials or arbitrary env.
                values = {}
                for line in Path(src).read_text().splitlines():
                    key, sep, value = line.partition("=")
                    if sep and key in {"RAG_DATABASE_URL", "RAG_SOURCE_DATABASE_URL"}:
                        values[key] = endpoint(value.strip().strip("\"'"))
                result["files"][src] = values
            elif dst == "/run/search/publication.json":
                payload = json.loads(Path(src).read_text()).get("payload", {})
                result["files"][src] = {
                    k: payload.get(k)
                    for k in (
                        "publication_id",
                        "published_at",
                        "source",
                        "target",
                        "logical_id",
                        "assurance",
                    )
                }
            elif dst.endswith(("Caddyfile", "existing-cluster.sh")):
                result["files"][src] = text_file(src)
        repo = labels.get("com.docker.compose.project.working_dir")
        if repo and repo not in result["repositories"]:
            result["repositories"][repo] = {
                "commit": run("git", "-C", repo, "rev-parse", "HEAD"),
                "branch": run("git", "-C", repo, "branch", "--show-current"),
                "status": run("git", "-C", repo, "status", "--porcelain"),
            }
        for filename in labels.get("com.docker.compose.project.config_files", "").split(","):
            if filename:
                result["files"][filename] = text_file(filename)
    result["databases"] = {}
    for container in postgres:

        def query(database, sql):
            # No maintenance SQL, counts over millions of rows or extension commands.
            transaction = (
                "BEGIN READ ONLY; SET LOCAL statement_timeout='3s'; SET LOCAL lock_timeout='500ms'; "
                + sql
                + "; ROLLBACK;"
            )
            output = run(
                "docker",
                "exec",
                "-i",
                container,
                "sh",
                "-c",
                'exec psql -XqAt -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d "$1"',
                "audit",
                database,
                input=transaction,
            )
            if isinstance(output, dict):
                return output
            return [json.loads(line) for line in output.splitlines() if line]

        databases = query(
            "postgres",
            "SELECT json_build_object('name',datname,'oid',oid,'collate',datcollate,'ctype',datctype,'provider',datlocprovider,'encoding',pg_encoding_to_char(encoding),'bytes',pg_database_size(oid)) FROM pg_database WHERE NOT datistemplate ORDER BY datname",
        )
        result["databases"][container[:12]] = {"catalogue": databases}
        if not isinstance(databases, list):
            continue
        for d in databases:
            name = d["name"]
            info = query(
                name,
                "SELECT json_build_object('cluster_id',(SELECT system_identifier::text FROM pg_control_system()),'database_name',current_database(),'database_oid',(SELECT oid FROM pg_database WHERE datname=current_database()),'server_version',current_setting('server_version'),'data_directory',current_setting('data_directory'),'role',current_user,'french_config','pg_catalog.french'::regconfig::text,'extensions',(SELECT json_agg(json_build_object('name',extname,'version',extversion)) FROM pg_extension),'schemas',(SELECT json_agg(nspname) FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema'))",
            )
            result["databases"][container[:12]][name] = info
            if isinstance(info, list) and info:
                schemas = info[0].get("schemas") or []
                extras = {}
                for schema, table in (
                    ("public", "alembic_version"),
                    ("public", "rag_alembic_version"),
                    ("documentary", "alembic_version"),
                ):
                    exists = query(
                        name,
                        "SELECT to_json(to_regclass('" + schema + "." + table + "') IS NOT NULL)",
                    )
                    if exists == [True]:
                        extras[schema + "." + table] = query(
                            name, "SELECT to_json(version_num) FROM " + schema + "." + table
                        )
                if "rag_full" in schemas:
                    extras["gdn_state"] = query(
                        name,
                        "SELECT json_build_object('space',space_id,'documents',documents,'segments',segments,'verified',verified,'vectors_complete',vectors_complete,'recipe_hash',recipe_hash,'chain_hash',chain_hash) FROM rag_full.spaces WHERE space_id='full'",
                    )
                    extras["indexes"] = query(
                        name,
                        "SELECT json_build_object('schema',n.nspname,'name',c.relname,'relfilenode',c.relfilenode,'valid',i.indisvalid,'definition',pg_get_indexdef(c.oid)) FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('rag_full','rag_tuning') ORDER BY n.nspname,c.relname",
                    )
                extras["roles"] = query(
                    name,
                    "SELECT json_build_object('name',rolname,'super',rolsuper,'createdb',rolcreatedb,'createrole',rolcreaterole,'login',rolcanlogin,'limit',rolconnlimit,'bypassrls',rolbypassrls) FROM pg_roles WHERE rolname NOT LIKE 'pg_%' ORDER BY rolname",
                )
                result["databases"][container[:12]][name + "_details"] = extras
    result["backup_listing"] = run(
        "find",
        "/backups/postgresql",
        "-maxdepth",
        "3",
        "-type",
        "f",
        "-printf",
        "%p %s %TY-%Tm-%TdT%TH:%TM\n",
    )
    for directory in ("/etc/cron.d", "/etc/systemd/system", "/usr/local/sbin"):
        for p in Path(directory).glob("*"):
            if p.is_file() and re.search(r"backup|postgres|cahier|deploy|git", p.name, re.I):
                result["files"][str(p)] = text_file(p)
    print(START)
    print(json.dumps(result, indent=2))
    print(END)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--remote-read-only", action="store_true", help=argparse.SUPPRESS)
    p.add_argument(
        "--output",
        type=Path,
        default=Path("private/search/production-preparation/privileged-audit.json"),
    )
    args = p.parse_args()
    if args.remote_read_only:
        remote_inventory()
        return
    if not sys.stdin.isatty():
        p.error("Run in your terminal so sudo can request the password privately")
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.output.exists():
        p.error("Output already exists; choose a new file rather than overwrite an audit")
    command = (
        "sudo -p '[sudo audit] Password: ' python3 -B -c "
        + shlex.quote(Path(__file__).read_text())
        + " --remote-read-only"
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
            command,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    captured = bytearray()
    while chunk := os.read(child.stdout.fileno(), 65536):
        captured.extend(chunk)
        os.write(sys.stdout.fileno(), chunk)
    if child.wait():
        raise SystemExit("Remote read-only audit failed; no inventory saved")
    raw = captured.decode().replace("\r\n", "\n")
    inventory = json.loads(raw.split(START + "\n", 1)[1].split("\n" + END, 1)[0])
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
        json.dump(inventory, f, indent=2)
    print(f"Sanitized read-only inventory saved: {args.output}")


if __name__ == "__main__":
    main()
