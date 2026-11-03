"""Stable complete documents and technical passages, without historical segmentation."""

import argparse
import bisect
import gzip
import importlib.metadata
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent
sys.path.insert(0, str(BASE / "tools/document-review"))
from reviewlib import PRIVATE, Store, module, rows, sha  # noqa: E402
from technical_passages import split  # noqa: E402

LocalTokenizer = module(
    "technical_local_tokenizer", ROOT / "rag/src/cahier_rag/context/tokenization.py"
).LocalTokenizer

VERSION = "reference-documents-1"
G6 = BASE / "data/corpus/global-corpus-6-29e180f0c67f"
CONFIG = BASE / "extraction/technical-passages-config.json"
CURRENT = BASE / "data/documents/current.json"


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_rows(path, values):
    with path.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as f:
        for row in values:
            f.write((json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode())


def metadata(row):
    m = row["metadata"]
    title = m["title"]
    estate_patterns = [
        ("clergé", r"\bclerg[ée]\b"),
        ("noblesse", r"\bnoblesse\b"),
        ("tiers état", r"\btiers[ -]?[ée]tat\b"),
    ]
    orders = [label for label, pattern in estate_patterns if re.search(pattern, title, re.I)]
    if re.search(r"\btrois ordres\b", title, re.I):
        orders = [x[0] for x in estate_patterns]
    pattern = r"(?:bailliage|sénéchaussée|ville|paroisse|communauté|village|bourg|diocèse|province|juridiction|duché|comté)(?:\s+(?:particulier|royal|secondaire|principal))*\s+(?:d['’]|de\s+|du\s+|des\s+)([^()]+)"
    places = list(re.finditer(pattern, title, re.I))
    if not places:
        places = list(re.finditer(r"^Cahier\s+(?:de\s+|d['’])([A-ZÀ-Ý][^()]+)", title))
    place = places[-1].group(1).strip(" .,;") if places else None
    return dict(
        id=row["id"],
        persee_id=row["persee_id"],
        title=title,
        volume=row["volume"],
        document_kind=row["document_kind"],
        historical_orders=orders,
        historical_orders_status="explicit_in_metadata_title" if orders else "not_established",
        origin=dict(label=place, status="literal_metadata_label_not_geocoded", source_field="title")
        if place
        else None,
        territorial_context=m.get("ancestors", []),
        lexical_fields=dict(
            title=title,
            place_labels=[place] if place else [],
            territorial_labels=m.get("ancestors", []),
            historical_orders=orders,
        ),
        original_metadata=m,
    )


def verify(directory, counter=None):
    """Verify persisted files afresh, independent of the chunking decisions."""
    manifest = json.loads((directory / "manifest.json").read_text())
    for filename, digest in manifest["files"].items():
        assert sha((directory / filename).read_bytes()) == digest, filename
    docs = {d["id"]: d for d in rows(directory / "documents.jsonl.gz")}
    inventory = rows(directory / "inventory.jsonl.gz")
    assert len(docs) == 1267 and len(inventory) == 1305
    assert len({r["id"] for r in inventory}) == len(inventory)
    assert set(docs) <= {r["id"] for r in inventory}
    metadatas = {m["id"]: m for m in rows(directory / "metadata.jsonl.gz")}
    assert set(metadatas) == {r["id"] for r in inventory}
    baseline = {p["id"]: p for p in rows(G6 / "parents.jsonl.gz")}
    repair_file = directory / "document-repairs.json"
    repairs = json.loads(repair_file.read_text())["repairs"] if repair_file.exists() else []
    if repairs:
        source_store = Store()
        for repair in repairs:
            old = baseline[repair["document_id"]]
            assert [old["start"], old["end"]] == [repair["old_start"], repair["old_end"]]
            src = source_store.sources[repair["volume"]]
            assert src.sha256 == repair["source_sha256"]
            nodes = [src.node(c["xpath"]) for c in repair["components"]]
            for component, node in zip(repair["components"], nodes):
                a, z = src.span(node)
                assert [a, z] == [component["start"], component["end"]]
                assert sha(src.text[a:z]) == component["text_sha256"]
            assert all(a.getnext() is b for a, b in zip(nodes, nodes[1:]))
            assert [src.span(nodes[0])[0], src.span(nodes[-1])[1]] == [
                repair["new_start"],
                repair["new_end"],
            ]
            text = src.text[repair["new_start"] : repair["new_end"]]
            assert sha(text) == repair["new_text_sha256"]
            baseline[repair["document_id"]] = dict(
                old,
                start=repair["new_start"],
                end=repair["new_end"],
                full_text=text,
                text_sha256=sha(text),
            )
    byparent = defaultdict(list)
    ids = set()
    for p in rows(directory / "passages.jsonl.gz"):
        assert p["id"] not in ids
        ids.add(p["id"])
        d = docs[p["document_id"]]
        assert d["extent_id"] == p["document_extent_id"]
        a, z = p["start_in_document"], p["end_in_document"]
        assert 0 <= a < z <= len(d["full_text"])
        assert p["text"] == d["full_text"][a:z] and p["text"].strip()
        assert p["source_start"] == d["source_start"] + a
        assert p["source_end"] == d["source_start"] + z
        assert p["text_sha256"] == sha(p["text"])
        assert p["id"] == passage_id(d, a, z, manifest["rules_fingerprint"])
        assert (
            p["unit_type"] == "technical_search_passage" and p["historical_article_claim"] is False
        )
        assert 0 < p["token_count"] <= manifest["configuration"]["maximum_tokens"]
        assert p["token_count"] + 2 <= manifest["configuration"]["model_context_tokens"]
        if counter:
            assert counter.count(p["text"]) == p["token_count"]
        for ref in p["xml_references"]:
            assert (
                p["source_start"]
                <= ref["intersection_start"]
                < ref["intersection_end"]
                <= p["source_end"]
            )
        byparent[d["id"]].append(p)
    covered, repeated, chars, whitespace_only_chars = 0, 0, 0, 0
    for key, d in docs.items():
        old = baseline[key]
        assert d["full_text"] == old["full_text"]
        assert d["source_start"] == old["start"] and d["source_end"] == old["end"]
        assert d["text_sha256"] == old["text_sha256"] == sha(d["full_text"])
        assert d["document_kind"] == old["document_kind"]
        assert d["source"] == old["source"]
        own = byparent[key]
        assert d["passage_ids"] == [p["id"] for p in own]
        if not d["full_text"].strip():
            assert not own and d["content_flags"] == ["source_slice_whitespace_only"]
            whitespace_only_chars += len(d["full_text"])
            chars += len(d["full_text"])
            continue
        assert (
            own
            and own[0]["start_in_document"] == 0
            and own[-1]["end_in_document"] == len(d["full_text"])
        )
        end = 0
        for rank, p in enumerate(own):
            a, z = p["start_in_document"], p["end_in_document"]
            assert p["ordinal"] == rank + 1 and a <= end < z
            assert p["previous_id"] == (own[rank - 1]["id"] if rank else None)
            assert p["next_id"] == (own[rank + 1]["id"] if rank + 1 < len(own) else None)
            overlap = p["overlap_previous"]
            if rank and a < end:
                assert overlap["start_in_document"] == a and overlap["end_in_document"] == end
                assert overlap["tokens"] <= manifest["configuration"]["overlap_maximum_tokens"]
                repeated += end - a
            else:
                assert overlap is None
            covered += z - end
            end = z
        chars += len(d["full_text"])
    assert covered + whitespace_only_chars == chars
    return dict(
        errors=0,
        documents=len(docs),
        passages=len(ids),
        source_characters=chars,
        covered_characters=covered,
        explicitly_excluded_whitespace_only_document_characters=whitespace_only_chars,
        substantive_coverage_fraction=1.0,
        full_parent_preservation_fraction=1.0,
        overlapping_characters=repeated,
        exact_text_verified=True,
        stable_ids_verified=True,
        no_parent_boundary_changes=not repairs,
        documented_parent_repairs=len(repairs),
    )


def passage_id(document, start, end, fingerprint):
    value = [document["id"], document["extent_id"], start, end, fingerprint]
    return "ap1789-technical-passage-1:" + sha(json.dumps(value, ensure_ascii=False))[:28]


def build():
    started = time.perf_counter()
    config = json.loads(CONFIG.read_text())
    store = Store()
    store.automatic_corrections = {
        r["document_id"]: r for r in rows(G6 / "boundary-resolutions.jsonl.gz")
    }
    events = store.latest()
    tokenizer_path = ROOT / config["tokenizer_path"]
    tokenizer = LocalTokenizer(
        tokenizer_path,
        repository=config["tokenizer_repository"],
        revision=config["tokenizer_revision"],
        expected_sha256=sha(tokenizer_path.read_bytes()),
    )
    tokenizer.description["counting"] = (
        "exact source passage text; no metadata prefix, no template, no inference"
    )
    assert (
        json.loads(tokenizer_path.with_name("tokenizer_config.json").read_text())[
            "model_max_length"
        ]
        == config["model_context_tokens"]
    )
    paths = [
        Path(__file__),
        BASE / "extraction/technical_passages.py",
        CONFIG,
        ROOT / "rag/src/cahier_rag/context/tokenization.py",
        tokenizer_path,
        tokenizer_path.with_name("tokenizer_config.json"),
        store.journal,
        PRIVATE / "article-decisions.jsonl",
        *[s.path for s in store.sources.values()],
        *[p for p in G6.iterdir() if p.is_file()],
    ]
    input_hashes = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths}
    for name, digest in json.loads((G6 / "complete.json").read_text())["files"].items():
        assert sha((G6 / name).read_bytes()) == digest
    overrides = PRIVATE / "corpus-overrides/rebuilds.jsonl"
    if overrides.exists() and rows(overrides):
        raise ValueError(
            "Reconcile explicit parent rebuilds before freezing a reference collection; no boundaries will be changed here."
        )
    rules = {
        "config": config,
        "algorithm_sha256": sha((BASE / "extraction/technical_passages.py").read_bytes()),
        "tokenizer_sha256": sha(tokenizer_path.read_bytes()),
        "tokenizers_version": importlib.metadata.version("tokenizers"),
    }
    fingerprint = sha(json.dumps(rules, sort_keys=True))
    out = (
        BASE
        / "data/documents"
        / (
            VERSION
            + "-"
            + sha(json.dumps([input_hashes, rules["tokenizers_version"]], sort_keys=True))[:12]
        )
    )
    if out.exists():
        raise ValueError("Immutable output already exists: " + str(out))
    out.mkdir(parents=True)
    snapshots = out / ".private"
    snapshots.mkdir(mode=0o700)
    for path in [store.journal, PRIVATE / "article-decisions.jsonl"]:
        target = snapshots / path.name
        target.write_bytes(path.read_bytes())
        target.chmod(0o600)
    parents = rows(G6 / "parents.jsonl.gz")
    inv = rows(G6 / "inventory.jsonl.gz")
    docs, passages, windows = [], [], []
    longs = []
    boundary_conflicts = []
    page_functions = {v: store.lib.base.page_index(s)[1] for v, s in store.sources.items()}
    for parent in parents:
        src = store.sources[parent["volume"]]
        assert src.sha256 == parent["source"]["source_sha256"]
        assert parent["source"]["source_revision"] == config["source_revision"]
        assert src.text[parent["start"] : parent["end"]] == parent["full_text"]
        state = store.state(store.by_id[parent["id"]], events)
        selected = state["selected"] or {}
        compatible = (
            not state["stale"]
            and selected.get("start") == parent["start"]
            and selected.get("end") == parent["end"]
        )
        if not compatible:
            boundary_conflicts.append(parent["id"])
        d = dict(
            id=parent["id"],
            corpus_id=parent["corpus_id"],
            extent_id=parent["extent_id"],
            metadata_id=parent["id"],
            persee_id=parent["persee_id"],
            volume=parent["volume"],
            document_kind=parent["document_kind"],
            full_text=parent["full_text"],
            text_sha256=parent["text_sha256"],
            source_start=parent["start"],
            source_end=parent["end"],
            source=parent["source"],
            source_version=parent["source_version"],
            xml_blocks=parent["blocks"],
            annotations=parent["annotations"],
            boundary_status=dict(
                extracted_class=parent["boundary_class"],
                latest_review_status=state["status"],
                human_event_id=(state["event"] or {}).get("id"),
                compatible_with_latest_decision=compatible,
                certified=compatible and state["status"] == "human_validated",
            ),
            anomalies=parent["anomalies"],
            legacy_parent_ids=parent["legacy_parent_ids"],
            historical_segmentation=dict(
                role="secondary_archived_annotations",
                generation=str(G6.relative_to(BASE)),
                parent_id=parent["id"],
            ),
            passage_ids=[],
            content_flags=["source_slice_whitespace_only"]
            if not parent["full_text"].strip()
            else [],
            version=VERSION,
        )
        local_ends = [
            b["end"] - parent["start"] for b in parent["blocks"] if b["tag"] in {"p", "head"}
        ]
        frames = split(d["full_text"], local_ends, tokenizer, config)
        block_ends = [b["end"] for b in parent["blocks"]]
        page_at = page_functions[parent["volume"]]
        for block in parent["blocks"]:
            if block["tag"] == "p" and block["end"] - block["start"] > 1000:
                count = tokenizer.count(src.text[block["start"] : block["end"]])
                if count > config["maximum_tokens"]:
                    longs.append(
                        dict(
                            document_id=d["id"],
                            xpath=block["xpath"],
                            source_start=block["start"],
                            source_end=block["end"],
                            tokens=count,
                        )
                    )
        for i, frame in enumerate(frames):
            a, z = frame["start"], frame["end"]
            x, y = parent["start"] + a, parent["start"] + z
            refs = []
            for b in parent["blocks"][bisect.bisect_right(block_ends, x) :]:
                if b["start"] >= y:
                    break
                if max(x, b["start"]) < min(y, b["end"]):
                    refs.append(
                        dict(
                            block_id=b["id"],
                            xpath=b["xpath"],
                            intersection_start=max(x, b["start"]),
                            intersection_end=min(y, b["end"]),
                        )
                    )
            previous_end = frames[i - 1]["end"] if i else a
            overlap = (
                dict(
                    start_in_document=a,
                    end_in_document=previous_end,
                    tokens=tokenizer.count(d["full_text"][a:previous_end]),
                )
                if previous_end > a
                else None
            )
            uid = passage_id(d, a, z, fingerprint)
            passage = dict(
                id=uid,
                document_id=d["id"],
                document_extent_id=d["extent_id"],
                unit_type="technical_search_passage",
                historical_article_claim=False,
                text=d["full_text"][a:z],
                text_sha256=sha(d["full_text"][a:z]),
                start_in_document=a,
                end_in_document=z,
                source_start=x,
                source_end=y,
                ordinal=i + 1,
                token_count=frame["tokens"],
                boundary_method=frame["end_reason"],
                overlap_previous=overlap,
                previous_id=passage_id(d, frames[i - 1]["start"], frames[i - 1]["end"], fingerprint)
                if i
                else None,
                next_id=passage_id(d, frames[i + 1]["start"], frames[i + 1]["end"], fingerprint)
                if i + 1 < len(frames)
                else None,
                pages=dict(start=page_at(x), end=page_at(max(x, y - 1))),
                xml_references=refs,
                version=config["version"],
                rules_fingerprint=fingerprint,
                local_context_url="/passages?passage=" + quote(uid, safe=""),
                text_recipe="source_slice_only_no_metadata_prefix",
                status="mechanical_excerpt_not_historical_article",
            )
            passages.append(passage)
            d["passage_ids"].append(uid)
        docs.append(d)
        if len(docs) % 250 == 0:
            print("Prepared", len(docs), "documents", flush=True)
    # Separate metadata and unresolved notices remain in the same complete inventory.
    inventory = [
        {
            k: r[k]
            for k in [
                "id",
                "persee_id",
                "volume",
                "title",
                "document_kind",
                "extraction_state",
                "boundary_class",
                "anomalies",
                "parent_id",
            ]
        }
        for r in inv
    ]
    write_rows(out / "documents.jsonl.gz", docs)
    write_rows(out / "metadata.jsonl.gz", [metadata(r) for r in inv])
    write_rows(out / "inventory.jsonl.gz", inventory)
    write_rows(out / "passages.jsonl.gz", passages)
    write_rows(out / "long-paragraphs.jsonl.gz", longs)
    rng = random.Random(config["sample_seed"])
    for v in range(1, 7):
        candidates = sorted(
            [
                d
                for d in docs
                if d["volume"] == v
                and d["document_kind"] == "cahier_autonome_probable"
                and d["passage_ids"]
            ],
            key=lambda d: d["id"],
        )
        for d in rng.sample(candidates, config["sample_per_volume"]):
            rank = rng.randrange(len(d["passage_ids"]))
            windows.append(dict(document_id=d["id"], passage_id=d["passage_ids"][rank], volume=v))
    dump(
        out / "visual-sample.json",
        dict(
            seed=config["sample_seed"],
            selection="Two random probable cahiers with substantive text per volume, then one random passage each; sorted document IDs; whitespace-only slices excluded, no difficulty selection",
            windows=windows,
            validation_created=False,
        ),
    )
    dump(
        out / "inputs.json",
        dict(files=input_hashes, preserved_historical_generation=str(G6.relative_to(BASE))),
    )
    manifest = dict(
        version=VERSION,
        configuration=config,
        rules_fingerprint=fingerprint,
        tokenizer=tokenizer.description,
        files={p.name: sha(p.read_bytes()) for p in out.iterdir() if p.is_file()},
    )
    dump(out / "manifest.json", manifest)
    integrity = verify(out, tokenizer)
    assert not boundary_conflicts, (
        "New parent decisions are incompatible; output preserved without activation: "
        + str(boundary_conflicts)
    )
    lengths = sorted(p["token_count"] for p in passages)
    byvolume = {}
    for v in range(1, 7):
        ds = [d for d in docs if d["volume"] == v]
        own_ids = {d["id"] for d in ds}
        ps = [p for p in passages if p["document_id"] in own_ids]
        byvolume[str(v)] = dict(
            documents=len(ds),
            probable_cahiers=sum(d["document_kind"] == "cahier_autonome_probable" for d in ds),
            passages=len(ps),
            mean_tokens=sum(p["token_count"] for p in ps) / len(ps),
        )
    summary = dict(
        version=VERSION,
        generation=out.name,
        notices=len(inv),
        documents=len(docs),
        probable_cahiers=sum(d["document_kind"] == "cahier_autonome_probable" for d in docs),
        document_categories=dict(Counter(r["document_kind"] for r in inv)),
        extracted_categories=dict(Counter(d["document_kind"] for d in docs)),
        notices_without_text=len(inv) - len(docs),
        whitespace_only_documents=[d["id"] for d in docs if d["content_flags"]],
        cahiers_with_substantive_text=sum(
            d["document_kind"] == "cahier_autonome_probable" and bool(d["full_text"].strip())
            for d in docs
        ),
        passages=len(passages),
        passages_in_cahiers=sum(
            len(d["passage_ids"]) for d in docs if d["document_kind"] == "cahier_autonome_probable"
        ),
        token_statistics=dict(
            minimum=lengths[0],
            median=lengths[len(lengths) // 2],
            mean=sum(lengths) / len(lengths),
            p95=lengths[int(0.95 * (len(lengths) - 1))],
            maximum=lengths[-1],
            below_400=sum(n < 400 for n in lengths),
            between_400_800=sum(400 <= n <= 800 for n in lengths),
            above_800=sum(n > 800 for n in lengths),
        ),
        boundary_methods=dict(Counter(p["boundary_method"] for p in passages)),
        long_XML_paragraphs=len(longs),
        extracted_boundary_classes=dict(
            Counter(d["boundary_status"]["extracted_class"] for d in docs)
        ),
        unresolved_or_suspect_documents=sum(
            d["boundary_status"]["extracted_class"] in {"uncertain", "automatic_suspect"}
            for d in docs
        ),
        existing_documentary_overlap_pairs=len(rows(G6 / "document-overlaps.jsonl.gz")),
        by_volume=byvolume,
        integrity=integrity,
        human_journals_preserved=True,
        historical_generation_preserved=True,
        no_historical_segmenter_executed=True,
        no_embeddings=True,
        elapsed_seconds=time.perf_counter() - started,
    )
    assert all(
        sha((ROOT / name).read_bytes()) == digest for name, digest in input_hashes.items()
    ), "Input changed during preparation"
    dump(out / "summary.json", summary)
    manifest["files"]["summary.json"] = sha((out / "summary.json").read_bytes())
    dump(out / "manifest.json", manifest)
    tmp = CURRENT.with_suffix(".tmp")
    dump(tmp, dict(directory=str(out.relative_to(BASE)), version=VERSION))
    os.replace(tmp, CURRENT)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", type=Path)
    args = parser.parse_args()
    if args.verify_only:
        c = json.loads((args.verify_only / "manifest.json").read_text())["configuration"]
        p = ROOT / c["tokenizer_path"]
        t = LocalTokenizer(
            p,
            repository=c["tokenizer_repository"],
            revision=c["tokenizer_revision"],
            expected_sha256=sha(p.read_bytes()),
        )
        print(json.dumps(verify(args.verify_only, t), indent=2))
    else:
        build()
