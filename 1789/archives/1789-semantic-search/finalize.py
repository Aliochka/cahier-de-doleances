# ruff: noqa: E402
"""Empreintes finales et liens locaux du livrable, aucune opération applicative."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import frozen_match  # noqa: E402

import datetime
import importlib.metadata
import platform
import re
import subprocess
from urllib.parse import unquote

from common import HERE, ROOT, read, sha, write

CODE = [
    "rag/src/cahier_rag/embeddings/registry.py",
    "rag/src/cahier_rag/embeddings/core.py",
    "rag/src/cahier_rag/embeddings/snapshots.py",
    "rag/src/cahier_rag/embeddings/transformers_backend.py",
    "rag/src/cahier_rag/vector/preparation.py",
    "rag/src/cahier_rag/vector/cache.py",
    "rag/src/cahier_rag/search/preparation.py",
    "rag/src/cahier_rag/search/hybrid/core.py",
    "rag/src/cahier_rag/search/service/core.py",
    "rag/src/cahier_rag/search/service/__init__.py",
    "rag/src/cahier_rag/tuning/lexical.py",
    "rag/src/cahier_rag/search/flexible.py",
]


def main():
    links = []
    for p in HERE.glob("*.md"):
        for url in re.findall(r"\]\(([^)]+)\)", p.read_text()):
            if url.startswith(("http:", "https:", "#")):
                continue
            target = (p.parent / unquote(url.split("#")[0])).resolve()
            assert target.exists() or target == HERE / "data/provenance.json", (str(p), url)
            links.append(dict(file=p.name, target=url))
    prior = read(HERE / "prior-audits-sha256.json")
    assert all(frozen_match(ROOT / p, h) for p, h in prior.items())
    diff = subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True
    ).splitlines()
    assert not diff
    write(
        HERE / "data/provenance.json",
        dict(
            completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            repository_head=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            experiment_scope="Only 1789/archives/1789-semantic-search added; no application, database or deployed configuration changes",
            database_access=False,
            production_access=False,
            model_downloads=0,
            training=False,
            embeddings_generated="540 historical representations,30 frozen queries,16 contemporary precision probes (initial diagnostic duplicated),1 outside-evaluation CLI smoke query",
            previous_audits_verified=len(prior),
            original_code_sha256={p: sha(ROOT / p) for p in CODE},
            experimental_scripts_sha256={p.name: sha(p) for p in sorted(HERE.glob("*.py"))},
            python=platform.python_version(),
            libraries={
                k: importlib.metadata.version(k)
                for k in (
                    "torch",
                    "transformers",
                    "numpy",
                    "psutil",
                    "SQLAlchemy",
                    "huggingface-hub",
                )
            },
            system_lexical_resources={
                "libstemmer": {
                    "path": "/lib/x86_64-linux-gnu/libstemmer.so.0d",
                    "version": "2.2.0-1build1",
                    "sha256": sha("/lib/x86_64-linux-gnu/libstemmer.so.0d"),
                },
                "stopwords": {
                    "origin": "/usr/share/postgresql/14/tsearch_data/french.stop",
                    "sha256": sha(HERE / "data/french.stop"),
                },
            },
            model_source="https://huggingface.co/BAAI/bge-m3/blob/5617a9f61b028005a4858fdac845db406aefb181/README.md",
            model_snapshot_manifest_sha256=sha(
                ROOT
                / "rag/models/bge-m3/5617a9f61b028005a4858fdac845db406aefb181/snapshot-manifest.json"
            ),
            checks=read(HERE / "data/checks.json"),
            reproducibility=read(HERE / "data/reproducibility.json"),
            validation={
                "ruff": "passed",
                "existing_unit_tests": 36,
                "new_query_cli_smoke": "passed locally, excluded from evaluation",
                "cached_query_cli_comparisons": 10,
            },
            local_markdown_links_verified=links,
            tracked_diff=diff,
        ),
    )
    for link in links:
        assert (HERE / link["target"].split("#")[0]).resolve().exists()
    target = HERE / "data/deliverable-sha256.json"
    write(
        target,
        {
            str(p.relative_to(HERE)): sha(p)
            for p in sorted(HERE.rglob("*"))
            if p.is_file()
            and p != target
            and "__pycache__" not in p.parts
            and ".ruff_cache" not in p.parts
        },
    )
    print(f"{len(links)} local Markdown links checked; {len(prior)} prior audit files unchanged")


if __name__ == "__main__":
    main()
