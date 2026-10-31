"""Régression de développement uniquement, distincte des fenêtres nouvelles."""

from common import HERE, PILOT, read, rows, sources, write
from fast_blocks import blocks, cache_nodes
from rules import segment


def main():
    ss = sources()
    for s in ss.values():
        cache_nodes(s)
    cs = rows(HERE / "data/candidates.jsonl")
    prior = rows(PILOT / "data/documents.jsonl")
    refs = read(PILOT / "data/reference.json")
    # Prior reference is a list of already reviewed development windows.
    metrics = []
    errors = []
    for d in prior:
        c = next(
            c
            for c in cs
            if c["classification"] == "document_candidate"
            and c["volume"] == d["volume"]
            and c["start"] == d["source_text_start"]
        )
        s = ss[d["volume"]]
        ps = segment(s, blocks(s, c))
        for w in refs:
            if w["document_id"] != d["id"] or w["certainty"] != "A":
                continue
            predicted = [u for u in ps if w["start"] <= u["start"] < w["end"]]
            gp = {(u["start"], u["end"]) for u in w["units"]}
            good = sum((u["start"], u["end"]) in gp for u in predicted)
            metrics.append(
                dict(document_key=d["key"], gold=len(gp), predicted=len(predicted), correct=good)
            )
            for u in predicted:
                if (u["start"], u["end"]) not in gp:
                    errors.append(
                        dict(
                            document_key=d["key"],
                            prediction=u,
                            text=s.text[u["start"] : u["end"]],
                            reference=w["units"],
                        )
                    )
    write(
        HERE / "data/development-article-regression.json",
        dict(scope="development only, not held-out generalization", windows=metrics, errors=errors),
    )
    print(
        "Development windows",
        len(metrics),
        "correct",
        sum(m["correct"] for m in metrics),
        "/",
        sum(m["gold"] for m in metrics),
    )


if __name__ == "__main__":
    main()
