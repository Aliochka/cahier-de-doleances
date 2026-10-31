"""Textes réels à relire ; aucune note fabriquée à partir du rang ou du score."""

import gzip
import json

from common import CACHE, HERE, PRIOR, read, rows, write, write_rows


def main():
    needed = {p["g"] for p in read(HERE / "data/review-pairs.json")}
    old = rows(PRIOR / "data/corpus.jsonl")
    documents = {i: dict(d, g=i) for i, d in enumerate(d for d in old if d["status"] == "A")}
    with gzip.open(CACHE / "modern.jsonl.gz", "rt") as f:
        for line in f:
            d = json.loads(line)
            g = 269 + d["i"]
            if g in needed:
                documents[g] = dict(
                    d,
                    g=g,
                    corpus="gdn-2019",
                    title=f"Grand Débat · questionnaire {d['questionnaire_id']}",
                    references={
                        "ordinal": d["ordinal"],
                        "source_hash": d["source_hash"],
                        "question_id": d["question_id"],
                        "context_path": f"/forms/{d['questionnaire_id']}/contributions/{d['parent_id']}#answer-{d['id'].split(':')[-2]}",
                    },
                )
    assert needed <= documents.keys()
    prior = {
        (j["query_id"], j["unit_id"]): j for j in read(PRIOR / "annotations.json")["judgments"]
    }
    qs = {q["id"]: q for q in read(HERE / "queries.json")["queries"]}
    pool = []
    folder = HERE / "review"
    folder.mkdir(exist_ok=True)
    for qid in read(HERE / "protocol.json")["qualitative_queries"]:
        lines = [qs[qid]["text"] + "\nIntention : " + qs[qid]["intent"] + "\n\n"]
        for p in read(HERE / "data/review-pairs.json"):
            if p["query_id"] != qid:
                continue
            d = documents[p["g"]]
            j = prior.get((qid, d["id"]))
            pool.append(
                dict(
                    query_id=qid,
                    g=p["g"],
                    unit_id=d["id"],
                    prior_judgment=j,
                    needs_new_judgment=j is None,
                )
            )
            if j is None:
                lines.append(f"g{p['g']} · {d['title']}\n")
                if d.get("question"):
                    lines.append("Q : " + d["question"] + "\n")
                lines.append(" ".join(d["text"].split()) + "\n\n")
        (folder / f"{qid}.txt").write_text("".join(lines))
    write_rows(HERE / "data/qualitative-documents.jsonl", [documents[g] for g in sorted(needed)])
    write(HERE / "data/qualitative-pool.json", pool)
    print(
        f"Qualitative pool: {len(pool)} pairs; {sum(p['needs_new_judgment'] for p in pool)} new judgments; {len(needed)} documents"
    )


if __name__ == "__main__":
    main()
