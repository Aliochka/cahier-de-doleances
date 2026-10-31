"""Restauration autorisée des seuls six fichiers figés ; aucune collecte nouvelle."""

import urllib.request

from common import HERE, REVISION, SOURCES, read, sha, write


def main():
    SOURCES.mkdir(parents=True, exist_ok=True)
    manifest = read(HERE.parent / "1789-multicorpus/data/inventory.json")["volumes"][:6]
    restored = []
    for row in manifest:
        path = SOURCES / (row["druid"] + ".xml")
        if path.exists():
            assert sha(path.read_bytes()) == row["sha256"]
            status = "existing_verified"
        else:
            url = f"https://raw.githubusercontent.com/StanfordUniversityLibraries/ap_tei/{REVISION}/{row['file']}"
            with urllib.request.urlopen(url, timeout=30) as r:
                data = r.read()
            assert sha(data) == row["sha256"]
            path.write_bytes(data)
            status = "restored_verified"
        restored.append(
            dict(volume=row["volume"], file=str(path), sha256=row["sha256"], status=status)
        )
        print(row["volume"], status, flush=True)
    write(
        HERE / "data/source-restoration.json",
        dict(
            reason="Previous temporary cache gone; user explicitly authorized restoring these six pinned files",
            revision=REVISION,
            files=restored,
        ),
    )


if __name__ == "__main__":
    main()
