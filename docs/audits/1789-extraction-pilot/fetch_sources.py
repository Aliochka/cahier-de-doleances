"""Récupère uniquement les six volumes figés, dans un dossier isolé, empreintes vérifiées."""

import argparse
import concurrent.futures
import hashlib
import json
import urllib.request
from pathlib import Path

REVISION = "926fd3cd986a3c3d411e93d1845fff6475cb2602"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    rows = json.loads(
        (Path(__file__).parent.parent / "1789-multicorpus/data/inventory.json").read_text()
    )["volumes"][:6]
    args.directory.mkdir(parents=True, exist_ok=True)

    def fetch(row):
        path = args.directory / (row["druid"] + ".xml")
        if not path.exists():
            url = f"https://raw.githubusercontent.com/StanfordUniversityLibraries/ap_tei/{REVISION}/{row['file']}"
            with urllib.request.urlopen(url, timeout=60) as response:
                value = response.read()
            assert hashlib.sha256(value).hexdigest() == row["sha256"]
            path.write_bytes(value)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        print(row["volume"], path.stat().st_size, "SHA-256 OK", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(fetch, rows))


if __name__ == "__main__":
    main()
