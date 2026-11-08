"""Restore a documentary archive into a NEW private French-locale test cluster."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from .local_application import digest
from .representations import verify_representations
from .safety import Destination


def check(archive, binary=Path("/usr/lib/postgresql/17/bin"), *, install_manifest=None):
    archive = Path(archive).resolve()
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
    with tempfile.TemporaryDirectory(prefix="documentary-restore-") as tmp:
        root = Path(tmp)
        data = root / "data"
        socket = root / "socket"
        socket.mkdir()

        def run(name, *args):
            return subprocess.run(
                [str(binary / name), *map(str, args)],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            ).stdout

        run(
            "initdb",
            "-D",
            data,
            "-A",
            "trust",
            "--no-sync",
            "--username=restore_admin",
            "--encoding=UTF8",
            "--locale=fr_FR.UTF-8",
        )
        run(
            "pg_ctl",
            "-D",
            data,
            "-l",
            root / "pg.log",
            "-o",
            f"-k {socket} -p 55493 -c listen_addresses=''",
            "-w",
            "start",
        )
        destination = None
        try:
            common = ["-h", socket, "-p", "55493", "-U", "restore_admin"]
            name = "documentary_restored_test"
            run("createdb", *common, name)
            run("psql", *common, "-d", name, "-c", "CREATE EXTENSION vector")
            run(
                "pg_restore",
                *common,
                "-d",
                name,
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                archive,
            )
            system = run(
                "psql",
                *common,
                "-d",
                name,
                "-XAt",
                "-c",
                "SELECT system_identifier FROM pg_control_system()",
            ).strip()
            destination = Destination(
                f"postgresql+psycopg2://restore_admin@/{name}?host={socket}&port=55493",
                data,
                system,
            )
            result = verify_representations(destination)
            installed = False
            if install_manifest is not None:
                from .integrate_local import TARGET, transfer, verify_gdn
                from .local_application import LocalApplicationDestination

                target = LocalApplicationDestination(TARGET, backup=install_manifest, writable=True)
                try:
                    verify_gdn(target, install_manifest)
                    transfer(destination, target)
                    verify_gdn(target, install_manifest)
                    installed = True
                finally:
                    target.close()
            return dict(
                installed_local=installed,
                archive_sha256=digest(archive),
                locale="fr_FR.UTF-8",
                restored=True,
                integrity=result,
            )
        finally:
            if destination:
                destination.close()
            run("pg_ctl", "-D", data, "-m", "fast", "-w", "stop")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    p.add_argument(
        "--install-local",
        action="store_true",
        help="Explicitly replay into the authorized local cahier_rag only",
    )
    p.add_argument("--backup-manifest", type=Path)
    args = p.parse_args()
    if args.install_local and args.backup_manifest is None:
        p.error("--backup-manifest required for local installation")
    print(
        json.dumps(
            check(
                args.archive, install_manifest=args.backup_manifest if args.install_local else None
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
