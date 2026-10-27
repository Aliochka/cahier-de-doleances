"""Contrôle des livrables et empreintes, sans exécuter le code applicatif."""

import datetime
import gzip
import json
import os
import re
import sys
from urllib.parse import unquote

from common import HERE, REPO, read, sha, write


def main():
    for name in ["freeze.json", "reference-freeze.json"]:
        assert all(sha((HERE / p).read_bytes()) == h for p, h in read(HERE / name)["files"].items())
    prior = read(HERE / "prior-audits-sha256.json")
    assert all(sha((REPO / p).read_bytes()) == h for p, h in prior.items())
    parsed = {}
    for p in sorted(HERE.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        if p.suffix == ".json":
            read(p)
            parsed[str(p.relative_to(HERE))] = "JSON"
        elif p.suffix == ".jsonl" or p.name.endswith(".jsonl.gz"):
            opener = gzip.open if p.suffix == ".gz" else open
            with opener(p, "rt") as f:
                parsed[str(p.relative_to(HERE))] = sum(1 for line in f if json.loads(line))
    links = []
    for p in HERE.glob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", p.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            resolved = (p.parent / unquote(target.split("#")[0])).resolve()
            assert resolved.exists(), (p, target)
            links.append(str(resolved.relative_to(REPO)))
    # Direct process execution avoids importing the service or any DB fixture.
    assert (
        os.spawnv(
            os.P_WAIT, "/usr/bin/git", ["git", "-C", str(REPO), "diff", "--exit-code", "HEAD"]
        )
        == 0
    )
    ruff = str(REPO / ".venv/bin/ruff")
    assert os.spawnv(os.P_WAIT, ruff, ["ruff", "check", str(HERE), "--ignore", "F401"]) == 0
    assert os.spawnv(os.P_WAIT, ruff, ["ruff", "format", "--check", str(HERE)]) == 0
    checks = read(HERE / "data/checks.json")
    assert checks["new_A_reference_matches"] == 48
    assert read(HERE / "data/reproducibility.json")["stable_files_identical"]
    import lxml.etree as ET

    write(
        HERE / "data/final-verification.json",
        dict(
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            python=sys.version,
            lxml=list(ET.LXML_VERSION),
            libxml=list(ET.LIBXML_VERSION),
            parsed_artifacts=parsed,
            local_links_checked=len(links),
            prior_files_unchanged=len(prior),
            tracked_application_diff=[],
            ruff_check="passed with F401 exception for frozen imports",
            ruff_format="passed",
            checks=checks,
            new_embeddings=0,
            database_access=False,
        ),
    )
    manifest = {
        str(p.relative_to(HERE)): sha(p.read_bytes())
        for p in sorted(HERE.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts and p.name != "deliverables-sha256.json"
    }
    write(HERE / "data/deliverables-sha256.json", manifest)
    print(
        "Finalized",
        len(manifest),
        "files;",
        len(links),
        "local links;",
        len(prior),
        "old audit files unchanged",
    )


if __name__ == "__main__":
    main()
