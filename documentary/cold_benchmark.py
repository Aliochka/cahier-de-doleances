"""Cold PostgreSQL shared-buffer trials in a disposable clone, never restart the working DB."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy import text

from .representations import gate
from .safety import Destination
from .search import HistoricalSearch


def benchmark_clone(source, output, binary=Path("/usr/lib/postgresql/17/bin")):
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with source.transaction(readonly=True) as c:
        gate(c)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
    with tempfile.TemporaryDirectory(prefix="doc-cold-") as tmp:
        root = Path(tmp)
        data, socket = root / "data", root / "socket"
        socket.mkdir()

        def run(name, *args):
            return subprocess.run(
                [str(binary / name), *map(str, args)],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            ).stdout

        url = source.engine.url
        run(
            "pg_dump",
            "-h",
            url.query["host"],
            "-p",
            url.query.get("port", "5432"),
            "-U",
            url.username,
            "-d",
            url.database,
            "--format=custom",
            "--no-owner",
            "--no-acl",
            "-f",
            root / "source.dump",
        )
        run(
            "initdb",
            "-D",
            data,
            "-A",
            "trust",
            "--no-sync",
            "--username=doc_cold_admin",
            "--encoding=UTF8",
            "--locale=C",
        )

        def start():
            run(
                "pg_ctl",
                "-D",
                data,
                "-l",
                root / "postgres.log",
                "-o",
                f"-k {socket} -p 55491 -c listen_addresses=''",
                "-w",
                "start",
            )

        def stop():
            run("pg_ctl", "-D", data, "-m", "fast", "-w", "stop")

        start()
        destination = None
        service = None
        try:
            run(
                "createdb",
                "-h",
                socket,
                "-p",
                55491,
                "-U",
                "doc_cold_admin",
                "documentary_cold_test",
            )
            run(
                "pg_restore",
                "-h",
                socket,
                "-p",
                55491,
                "-U",
                "doc_cold_admin",
                "-d",
                "documentary_cold_test",
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                root / "source.dump",
            )
            identity = run(
                "psql",
                "-XAt",
                "-h",
                socket,
                "-p",
                55491,
                "-U",
                "doc_cold_admin",
                "-d",
                "documentary_cold_test",
                "-c",
                "SELECT system_identifier FROM pg_control_system()",
            ).strip()
            destination = Destination(
                f"postgresql+psycopg2://doc_cold_admin@/documentary_cold_test?host={socket}&port=55491",
                data,
                identity,
            )
            service = HistoricalSearch(destination)
            baseline = service.search("Agen agriculture", mode="hybrid")
            with destination.transaction(readonly=True) as c:
                before_plans = {
                    name: c.execute(
                        text("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + sql), params
                    ).scalar_one()
                    for name, (sql, params) in service.last_sql.items()
                }
            # pg_dump does not copy planner statistics. Match source preparation
            # before interpreting restart trials as cold-cache performance.
            with destination.transaction() as c:
                for name in ("document", "search_unit", "lexical_term_statistics"):
                    c.execute(text("ANALYZE documentary." + name))
            records = []
            for depth in (50, 100, 200):
                for mode in ("lexical", "vector", "hybrid"):
                    destination.close()
                    stop()
                    start()
                    result = service.search("Agen agriculture", mode=mode, depth=depth)
                    records.append(
                        {
                            "depth": depth,
                            "mode": mode,
                            "timings": result["timings"],
                            "candidates": result["candidates"],
                        }
                    )
            result = {
                "condition": "PostgreSQL shared buffers cold after restart of disposable clone; model warm; OS cache not flushed",
                "records": records,
                "sample_size_per_mode_depth": 1,
                "restored_without_analyze": {"timings": baseline["timings"], "plans": before_plans},
            }
            Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            return result
        finally:
            if service:
                service.close()
            if destination:
                destination.close()
            stop()
