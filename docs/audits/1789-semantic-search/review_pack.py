"""Supports de relecture sans nom de méthode, rang ou score."""

from common import HERE, rows


def compact(text):
    return " ".join(text.split())


def main():
    directory = HERE / "review"
    directory.mkdir(exist_ok=True)
    pool = rows(HERE / "data/review-pool.jsonl")
    corpus = rows(HERE / "data/corpus.jsonl")
    for qid in sorted({r["query"]["id"] for r in pool}):
        subset = [r for r in pool if r["query"]["id"] == qid]
        q = subset[0]["query"]
        lines = [q["text"] + "\nINTENTION : " + q["intent"] + "\n"]
        for r in sorted(subset, key=lambda r: r["document"]["short_id"]):
            d = r["document"]
            lines.append(f"{d['short_id']} {d['title']} : {compact(d['text'])}\n")
        (directory / f"{qid}.txt").write_text("".join(lines))
    seen = {r["document"]["id"] for r in pool}
    for name, docs in (
        ("historical", [d for d in corpus if d["status"] == "A"]),
        ("contemporary", [d for d in corpus if d["status"] != "A" and d["id"] in seen]),
    ):
        lines = []
        for d in sorted(docs, key=lambda d: d["short_id"]):
            lines.append(f"{d['short_id']} {d['title']} [{d.get('label', '')}]\n")
            if d.get("question"):
                lines.append("Q : " + d["question"] + "\n")
            lines.append(compact(d["text"]) + "\n\n")
        (directory / f"{name}-catalogue.txt").write_text("".join(lines))


if __name__ == "__main__":
    main()
