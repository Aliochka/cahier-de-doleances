"""Start the integrated LOCAL application. No database writes or production settings."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("part", nargs="?", choices=["all", "backend", "frontend"], default="all")
    args = p.parse_args()
    config = ROOT / "private/search/phase4/runtime.json"
    settings = json.loads(config.read_text())
    from documentary.local_application import LOCAL_IDENTITY, LocalApplicationDestination

    if (
        not settings.get("enabled")
        or not settings.get("local_preview")
        or settings["expected_target"] != LOCAL_IDENTITY
    ):
        raise SystemExit("Explicit local phase-4 preview configuration required")
    destination = LocalApplicationDestination(
        "postgresql+psycopg2:///cahier_rag?host=/var/run/postgresql"
    )
    try:
        with destination.transaction(readonly=True):
            pass
    finally:
        destination.close()
    env = dict(
        os.environ,
        ENV="dev",
        MULTICORPUS_CONFIG_FILE=str(config),
        API_BASE_URL="http://127.0.0.1:8000",
        HOST="127.0.0.1",
        PORT="3000",
        DOCUMENTARY_LOCAL_PREVIEW="1",
        DOCUMENTARY_PREVIEW_TOKEN=settings["preview_token"],
    )
    children = []
    try:
        if args.part in {"all", "backend"}:
            children.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.app:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8000",
                        "--no-access-log",
                    ],
                    cwd=ROOT,
                    env=env,
                )
            )
        if args.part in {"all", "frontend"}:
            children.append(
                subprocess.Popen(["pnpm", "--dir", "frontend", "start"], cwd=ROOT, env=env)
            )
        print(
            "Application locale : http://127.0.0.1:3000/ — API locale : http://127.0.0.1:8000/",
            flush=True,
        )
        # No token in arguments, URL, HTML or logs. Shutdown all owned children.
        while all(c.poll() is None for c in children):
            try:
                children[0].wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        for c in children:
            if c.poll() is None:
                c.terminate()
        for c in children:
            try:
                c.wait(timeout=25)
            except subprocess.TimeoutExpired:
                c.kill()
                c.wait()


if __name__ == "__main__":
    main()
