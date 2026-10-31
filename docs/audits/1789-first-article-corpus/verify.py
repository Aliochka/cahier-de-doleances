"""Independent material integrity checks, not a historical certification."""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools/1789-document-review"))
from reviewlib import Store, load, rows, sha  # noqa: E402


def validate(store, parents, units):
    by_id = {p["id"]: p for p in parents}
    assert len(by_id) == len(parents), "Duplicate parents"
    assert len({u["id"] for u in units}) == len(units), "Duplicate unit IDs"
    groups = defaultdict(list)
    for p in parents:
        source = store.sources[p["volume"]]
        assert p["source"]["source_sha256"] == source.sha256, "Source mismatch"
        assert p["full_text"] == source.text[p["start"] : p["end"]], "Parent fidelity"
        assert sha(p["full_text"]) == p["text_sha256"], "Parent hash"
        assert p["boundary_status"] in {"codex_reviewed", "human_validated"}, "Unestablished parent"
    for u in units:
        assert u["parent_id"] in by_id, "Wrong parent"
        p = by_id[u["parent_id"]]
        source = store.sources[p["volume"]]
        assert u["source"]["source_sha256"] == source.sha256, "Wrong source"
        assert p["start"] <= u["start"] < u["end"] <= p["end"], "Unit out of parent"
        assert u["parent_extent_id"] == p["extent_id"], "Parent extent mismatch"
        assert (
            u["parent_start"] == u["start"] - p["start"]
            and u["parent_end"] == u["end"] - p["start"]
        ), "Relative offsets"
        assert u["text_spans"] and all(
            u["start"] <= x < y <= u["end"] for x, y in u["text_spans"]
        ), "Span out of unit"
        assert u["text"] == "".join(source.text[x:y] for x, y in u["text_spans"]), "Unit fidelity"
        assert u["text"] == "".join(p["full_text"][x:y] for x, y in u["parent_text_spans"]), (
            "Parent span fidelity"
        )
        assert sha(u["text"]) == u["text_sha256"], "Unit hash"
        for loc in u["xml_blocks"]:
            assert store.block_maps[p["volume"]][loc["id"]]["xpath"] == loc["xpath"], "XML link"
            assert u["start"] <= loc["start"] < loc["end"] <= u["end"], "XML locator span"
        assert u["human_validated"] is False, "No invented human article validation"
        assert u["type"] in {"article", "section", "technical_passage"}, "Unknown type"
        assert u["status"] in {"A", "B", "C"}, "Unknown status"
        groups[p["id"]].append(u)
    for key, p in by_id.items():
        own = sorted(groups[key], key=lambda u: u["order"])
        assert [u["id"] for u in own] == p["unit_ids"], "Parent navigation"
        cursor = p["start"]
        spans = sorted((x, y, u["id"]) for u in own for x, y in u["text_spans"])
        for a, z, _ in spans:
            assert cursor == a, ("Gap or duplicate source character", key, cursor, a)
            cursor = z
        assert cursor == p["end"], "Uncovered parent text"
        for i, u in enumerate(own):
            assert u["order"] == i + 1, "Order"
            assert u["previous_unit_id"] == (own[i - 1]["id"] if i else None), "Previous unit"
            assert u["next_unit_id"] == (own[i + 1]["id"] if i + 1 < len(own) else None), (
                "Next unit"
            )
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=HERE / "data")
    args = parser.parse_args()
    data = args.directory
    store = Store()
    parents = rows(data / "parents.jsonl.gz")
    units = sum([rows(data / f"units-{k}.jsonl.gz") for k in "ABC"], [])
    validate(store, parents, units)
    if data.resolve() == (HERE / "data").resolve():
        expected_journal = (
            load(data / "source-manifest.json").get("human_decisions", {}).get("journal_sha256")
        )
        if expected_journal:
            actual_journal = sha(store.journal.read_bytes() if store.journal.exists() else b"")
            assert actual_journal == expected_journal, (
                "Decision journal changed since extraction; regenerate before verifying"
            )
    prior = load(HERE / "prior-files-sha256.json")
    for name, fingerprint in prior.items():
        assert sha((HERE.parents[2] / name).read_bytes()) == fingerprint, (
            "Prior source changed",
            name,
        )
    for name, record in load(data / "extraction-manifest.json")["files"].items():
        assert sha((data / name).read_bytes()) == record["sha256"], (
            "Export fingerprint mismatch",
            name,
        )
    legacy = {u["id"]: u for u in rows(HERE.parent / "1789-extraction-pilot/data/units.jsonl")}
    other = {u["id"]: u for u in rows(HERE.parent / "1789-extraction-v2/data/corpus-A.jsonl")}
    legacy.update(other)
    for u in units:
        for old in u["legacy_unit_ids"]:
            assert old in legacy and legacy[old]["text"] == u["text"], "Legacy crosswalk"
    types = Counter(u["type"] for u in units)
    statuses = Counter(u["status"] for u in units)
    articles = [u for u in units if u["type"] == "article"]
    n_a = sum(u["status"] == "A" for u in articles)
    quality = dict(
        ok=True,
        prepared=len(load(data / "selection.json")) if (data / "selection.json").exists() else 30,
        exploitable_parents=len(parents),
        withheld=len(load(data / "withheld.json")),
        by_volume=dict(Counter(p["volume"] for p in parents)),
        units_by_type=dict(types),
        units_by_status=dict(statuses),
        articles_total=len(articles),
        articles_codex_examined=n_a,
        articles_proposed=len(articles) - n_a,
        articles_uncertain_fraction=(len(articles) - n_a) / len(articles) if articles else None,
        human_validated_parents=sum(p["boundary_status"] == "human_validated" for p in parents),
        human_validated_articles=0,
        all_source_characters_preserved_exactly_once_in_unit_spans=True,
        parent_texts_complete_for_selected_extents=True,
        prior_files_unchanged=len(prior),
        extraction_is_not_historical_certification=True,
        human_activity=store.stats(),
        local_outputs={p.name: p.stat().st_size for p in data.glob("*.gz")},
    )
    (data / "quality.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(quality, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
