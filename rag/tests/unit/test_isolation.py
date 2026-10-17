"""Tester le package installé hors du dépôt, en interdisant backend et réseau."""

import subprocess
import sys


def test_installed_package_imports_and_diagnostics_are_isolated(tmp_path):
    script = r"""
import importlib.abc
import importlib.util
import socket
import sys

for name in ("app", "fastapi", "torch", "transformers", "sentence_transformers", "pgvector"):
    assert importlib.util.find_spec(name) is None, name

class BlockExternal(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {
            "app", "fastapi", "torch", "cuda", "transformers", "sentence_transformers",
            "pgvector", "llama_cpp", "langchain", "llama_index",
        }:
            raise AssertionError("Import interdit : " + fullname)

sys.meta_path.insert(0, BlockExternal())
def forbidden(*args, **kwargs):
    raise AssertionError("Effet de bord interdit")

socket.socket.connect = forbidden
socket.socket.connect_ex = forbidden
socket.getaddrinfo = forbidden
import psycopg2
psycopg2.connect = forbidden
import sqlalchemy
sqlalchemy.create_engine = forbidden

import cahier_rag
import cahier_rag.config
import cahier_rag.db
from cahier_rag.__main__ import main
assert main(["check-config", "--env-file", sys.argv[1]]) == 0
assert not any(name == "app" or name.startswith("app.") for name in sys.modules)
"""
    config = tmp_path / "isolated.env"
    config.write_text(
        "RAG_SOURCE_DATABASE_URL=postgresql:///source\nRAG_DATABASE_URL=postgresql:///rag\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(config)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
