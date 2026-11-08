"""Offline checks: never contact Gavroche or start Docker."""

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def verifier(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "backup_verifier", Path(__file__).parents[1] / "scripts/verify_nov02_postgres_backup.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for folder in ("source", "copy", "evidence"):
        (tmp_path / folder).mkdir()
    root = tmp_path / "source"
    for folder in ("global", "base", "pg_wal", "pg_xact", "pg_multixact", "pg_tblspc"):
        (root / folder).mkdir()
    (root / "PG_VERSION").write_text("17\n")
    (root / "global/pg_control").write_bytes(b"test control\0")
    (root / "base/data").write_text("Doléances : éducation 🕊\n" * 1000)

    def mapped_path(value):
        return (
            tmp_path / value[1:]
            if value.startswith(("/source", "/copy", "/evidence"))
            else Path(value)
        )

    monkeypatch.setattr(module, "Path", mapped_path)
    return module, tmp_path


def test_copy_checks_all_bytes_without_sharing_inodes(verifier):
    module, root = verifier
    before = module.inventory(root / "source")
    module.copy_agent(copy=True)
    assert module.inventory(root / "source") == before
    rows = json.loads((root / "evidence/files.sha256.json").read_text())
    assert len(rows) == 3
    for row in rows:
        src, dst = root / "source" / row["path"], root / "copy" / row["path"]
        assert src.read_bytes() == dst.read_bytes()
        assert src.stat().st_ino != dst.stat().st_ino
        assert module.digest(dst) == row["sha256"]


@pytest.mark.parametrize(
    "signal", ["postmaster.pid", "backup_label", "standby.signal", "recovery.signal"]
)
def test_refuses_unreviewed_cluster_state(verifier, signal):
    module, root = verifier
    (root / "source" / signal).touch()
    with pytest.raises(RuntimeError, match=signal):
        module.copy_agent(copy=True)
    assert not list((root / "copy").iterdir())


def test_refuses_external_tablespace_or_wal(verifier):
    module, root = verifier
    (root / "source/pg_tblspc/1234").symlink_to(root / "copy", target_is_directory=True)
    with pytest.raises(RuntimeError, match="Symlink"):
        module.copy_agent(copy=True)
    assert not list((root / "copy").iterdir())


def test_refuses_existing_destination(verifier):
    module, root = verifier
    existing = root / "copy/keep"
    existing.write_text("preserve")
    with pytest.raises(RuntimeError, match="empty"):
        module.copy_agent(copy=True)
    assert existing.read_text() == "preserve"
