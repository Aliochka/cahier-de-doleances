# ruff: noqa: E402
"""Outils du nouvel audit ; sources antérieures strictement en lecture."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import resolve_reference  # noqa: E402

import hashlib
import json
import os
from pathlib import Path

os.environ["OPENBLAS_NUM_THREADS"] = "4"
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIOR = HERE.parent / "1789-semantic-search"
CACHE = HERE.parents[1] / ".cache/multicorpus-scale-study"


def sha(path):
    h = hashlib.sha256()
    with resolve_reference(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def read(path):
    return json.loads(resolve_reference(path).read_text())


def rows(path):
    with resolve_reference(path).open() as f:
        return [json.loads(line) for line in f if line.strip()]


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_rows(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in values))


def connect(database="cahier_rag", timeout_ms=10000):
    import psycopg2

    assert database in {"cahier_rag", "cahier_doleances_local"}
    # No environment DSN, password, remote host or production URL accepted.
    c = psycopg2.connect(
        host="/var/run/postgresql",
        port=5432,
        user="ro",
        dbname=database,
        connect_timeout=3,
        application_name="multicorpus_scale_readonly",
        options=f"-c default_transaction_read_only=on -c statement_timeout={timeout_ms} -c lock_timeout=1000 -c work_mem=32MB -c max_parallel_workers_per_gather=0",
    )
    c.set_session(readonly=True, autocommit=False)
    with c.cursor() as q:
        q.execute(
            "SELECT current_database(),inet_server_addr(),current_setting('transaction_read_only')"
        )
        db, addr, ro = q.fetchone()
        assert db == database and addr is None and ro == "on"
    c.rollback()
    return c
