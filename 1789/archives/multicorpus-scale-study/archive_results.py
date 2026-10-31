"""Archive les textes de tous les top100, sans dupliquer le million d'unités."""

import gzip
import json

from common import CACHE, HERE, rows, sha, write


def main():
    needed = set()
    with gzip.open(HERE / "data/rankings.jsonl.gz", "rt") as f:
        for line in f:
            needed.update(r["g"] for r in json.loads(line)["results"])
    historical = rows(HERE / "data/history.jsonl")
    target = HERE / "data/result-documents.jsonl.gz"
    found = set()
    with target.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, filename="", mode="wb", mtime=0) as out:
            for g, d in enumerate(historical):
                if g in needed:
                    out.write((json.dumps(dict(d, g=g), ensure_ascii=False) + "\n").encode())
                    found.add(g)
            with gzip.open(CACHE / "modern.jsonl.gz", "rt") as source:
                for line in source:
                    d = json.loads(line)
                    g = 269 + d["i"]
                    if g not in needed:
                        continue
                    d.update(
                        g=g,
                        corpus="gdn-2019",
                        references={
                            "ordinal": d["ordinal"],
                            "source_hash": d["source_hash"],
                            "question_id": d["question_id"],
                            "context_path": f"/forms/{d['questionnaire_id']}/contributions/{d['parent_id']}#answer-{d['id'].split(':')[-2]}",
                        },
                    )
                    out.write((json.dumps(d, ensure_ascii=False) + "\n").encode())
                    found.add(g)
    assert found == needed
    write(
        HERE / "data/result-documents.json",
        dict(
            documents=len(found),
            historical=sum(g < 269 for g in found),
            contemporary=sum(g >= 269 for g in found),
            coverage="Every stored top100 result in all2160 rankings, exact full text and parent reference",
            source_cache_metadata_sha256=sha(CACHE / "modern.jsonl.gz"),
            result_documents_sha256=sha(target),
            source_database_access=False,
        ),
    )
    print(f"Archived {len(found)} full documents covering all stored top100 results")


if __name__ == "__main__":
    main()
