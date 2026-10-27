"""Récupération optionnelle des cinq seules images inspectées, empreintes contrôlées."""

import argparse
import urllib.request
from pathlib import Path

from common import read, sha

parser = argparse.ArgumentParser()
parser.add_argument("directory")
args = parser.parse_args()

directory = Path(args.directory)
directory.mkdir(parents=True, exist_ok=True)
for row in read("data/scan-checks.json"):
    path = directory / (row["key"] + ".jpg")
    if not path.exists():
        with urllib.request.urlopen(row["url"], timeout=60) as response:
            path.write_bytes(response.read())
    assert sha(path.read_bytes()) == row["sha256"], str(path)
    print(row["key"], "SHA-256 OK")
