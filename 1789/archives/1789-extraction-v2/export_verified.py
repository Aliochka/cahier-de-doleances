"""Export dérivé des références examinées; jamais une correction des prédictions gelées."""

from common import HERE, compact, jlines, pages, rows, sha, source_ref, sources, write


def main():
    notes = rows(HERE / "data/reference-review-notes.jsonl")
    reserved = {n["reference_id"] for n in notes}
    ss = sources()
    parents = rows(HERE / "data/reference-parent-texts.jsonl")
    gold = rows(HERE / "data/reference-articles.jsonl")
    units = []
    remaining = []
    for p in parents:
        s = ss[p["volume"]]
        node = s.node(p["xpath"])
        p["title_xml"] = " | ".join(compact(h) for h in node.findall("head"))
        p["corpus_id"] = "cahiers-1789-ap-stanford"
        p["method_version"] = "v2-source-reference-1"
        p["text_sha256"] = sha(p["text"])
        aa = sorted(
            [u for u in gold if u["parent_id"] == p["id"] and u["id"] not in reserved],
            key=lambda u: u["start"],
        )
        for i, u in enumerate(aa):
            # Raw range is authoritative. Actual XML notes remain in the parent and as separate annotations.
            annotations = []
            for n in node.iter("note"):
                a, b = s.span(n)
                if u["start"] < b and a < u["end"]:
                    annotations.append(
                        dict(
                            xpath=s.tree.getpath(n),
                            start=a,
                            end=b,
                            text=s.text[a:b],
                            role="editorial_note_xml",
                        )
                    )
            spans = []
            cursor = u["start"]
            for n in sorted(annotations, key=lambda n: n["start"]):
                if cursor < n["start"]:
                    spans.append([cursor, n["start"]])
                cursor = max(cursor, n["end"])
            if cursor < u["end"]:
                spans.append([cursor, u["end"]])
            units.append(
                dict(
                    u,
                    corpus_id=p["corpus_id"],
                    order_in_reviewed_subset=i + 1,
                    order_is_exhaustive=False,
                    parent_start=u["start"] - p["start"],
                    parent_end=u["end"] - p["start"],
                    text_sha256=sha(u["text"]),
                    source=source_ref(s),
                    pages=pages(s, u["start"], u["end"]),
                    previous_reviewed_id=aa[i - 1]["id"] if i else None,
                    next_reviewed_id=aa[i + 1]["id"] if i + 1 < len(aa) else None,
                    extraction_version="v2-source-reference-1",
                    text_spans_without_xml_notes=spans,
                    separated_annotations=annotations,
                    warning="A verifies XML boundaries only. OCR/editorial text inside ordinary p can remain. Adjacent reviewed IDs do not certify absence of unreviewed articles in between.",
                )
            )
        cursor = p["start"]
        for a, b in [(u["start"], u["end"]) for u in aa] + [(p["end"], p["end"])]:
            if cursor < a:
                remaining.append(
                    dict(
                        id="C-" + sha(f"{s.sha256}|{cursor}|{a}")[:20],
                        parent_id=p["id"],
                        volume=p["volume"],
                        start=cursor,
                        end=a,
                        parent_start=cursor - p["start"],
                        parent_end=a - p["start"],
                        text=s.text[cursor:a],
                        status="C",
                        meaning="not covered by reviewed article windows; may be unreviewed articles, rubrics, signatures or notes",
                    )
                )
            assert cursor <= a
            cursor = b
    jlines(HERE / "data/corpus-parents.jsonl", parents)
    jlines(HERE / "data/corpus-A.jsonl", units)
    jlines(HERE / "data/corpus-C.jsonl", remaining)
    jlines(
        HERE / "data/corpus-B-proposals.jsonl",
        [
            u
            for u in rows(HERE / "data/validation-article-predictions.jsonl")
            if u["version"] == "v2" and u["status"] == "B"
        ],
    )
    write(
        HERE / "data/corpus-summary.json",
        dict(
            parents=len(parents),
            reviewed_A=len(units),
            uncovered_C=len(remaining),
            B_proposals=sum(
                u["version"] == "v2" and u["status"] == "B"
                for u in rows(HERE / "data/validation-article-predictions.jsonl")
            ),
            reference_export_not_automatic_correction=True,
            ambiguous_reference_units_withheld=len(reserved),
            no_full_article_order_claim=True,
        ),
    )


if __name__ == "__main__":
    main()
