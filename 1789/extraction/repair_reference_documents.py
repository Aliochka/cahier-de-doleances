"""Recover only two whitespace-only documents; preserve all other reference records."""

import bisect
import copy
import json
import os
import time
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from prepare_documents import (
    BASE,
    CONFIG,
    CURRENT,
    G6,
    PRIVATE,
    ROOT,
    LocalTokenizer,
    Store,
    dump,
    passage_id,
    rows,
    sha,
    verify,
    write_rows,
)
from technical_passages import split

PREVIOUS = BASE / "data/documents/reference-documents-1-b8b8b20c2f76"
REPAIRS = BASE / "extraction/two-empty-document-repairs.json"
VERSION = "reference-documents-2"


def passages_for(doc, at, counter, config, fingerprint):
    """Same splitter, representation and IDs as the existing technical preparation."""
    frames = split(
        doc["full_text"],
        [b["end"] - doc["source_start"] for b in doc["xml_blocks"] if b["tag"] in {"p", "head"}],
        counter,
        config,
    )
    ends = [b["end"] for b in doc["xml_blocks"]]
    result = []
    for i, f in enumerate(frames):
        a, z = f["start"], f["end"]
        x, y = doc["source_start"] + a, doc["source_start"] + z
        refs = []
        for b in doc["xml_blocks"][bisect.bisect_right(ends, x) :]:
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
        p = dict(
            id=passage_id(doc, a, z, fingerprint),
            document_id=doc["id"],
            document_extent_id=doc["extent_id"],
            unit_type="technical_search_passage",
            historical_article_claim=False,
            text=doc["full_text"][a:z],
            text_sha256=sha(doc["full_text"][a:z]),
            start_in_document=a,
            end_in_document=z,
            source_start=x,
            source_end=y,
            ordinal=i + 1,
            token_count=f["tokens"],
            boundary_method=f["end_reason"],
            overlap_previous=dict(
                start_in_document=a,
                end_in_document=previous_end,
                tokens=counter.count(doc["full_text"][a:previous_end]),
            )
            if previous_end > a
            else None,
            previous_id=passage_id(doc, frames[i - 1]["start"], frames[i - 1]["end"], fingerprint)
            if i
            else None,
            next_id=passage_id(doc, frames[i + 1]["start"], frames[i + 1]["end"], fingerprint)
            if i + 1 < len(frames)
            else None,
            pages=dict(start=at(x), end=at(max(x, y - 1))),
            xml_references=refs,
            version=config["version"],
            rules_fingerprint=fingerprint,
            local_context_url="/passages?passage="
            + quote(passage_id(doc, a, z, fingerprint), safe=""),
            text_recipe="source_slice_only_no_metadata_prefix",
            status="mechanical_excerpt_not_historical_article",
        )
        if doc.get("document_components"):
            p["component_ids"] = [
                c["id"] for c in doc["document_components"] if max(x, c["start"]) < min(y, c["end"])
            ]
        result.append(p)
    return result


def build():
    started = time.perf_counter()
    prior_manifest = json.loads((PREVIOUS / "manifest.json").read_text())
    config = prior_manifest["configuration"]
    assert config == json.loads(CONFIG.read_text())
    prior_inputs = json.loads((PREVIOUS / "inputs.json").read_text())["files"]
    assert (
        sha((BASE / "extraction/technical_passages.py").read_bytes())
        == prior_inputs["1789/extraction/technical_passages.py"]
    )
    for name, digest in prior_manifest["files"].items():
        assert sha((PREVIOUS / name).read_bytes()) == digest
    descriptor = json.loads(REPAIRS.read_text())
    repairs = descriptor["repairs"]
    keys = {r["document_id"] for r in repairs}
    assert keys == {
        "ap1789-registry-p1:arcpa_0000-0000_1879_num_5_1_2837",
        "ap1789-registry-p1:arcpa_0000-0000_1879_num_5_1_2877",
    }
    store = Store()
    src = store.sources[5]
    at = store.lib.base.page_index(src)[1]
    # Any human history on a target prevents an automatic replacement, including undo history.
    for log in [store.journal, PRIVATE / "article-decisions.jsonl"]:
        assert not any(e["document_id"] in keys for e in rows(log)), (
            "Human target history requires explicit reconciliation"
        )
    docs = rows(PREVIOUS / "documents.jsonl.gz")
    original = {d["id"]: copy.deepcopy(d) for d in docs}
    old_passages = rows(PREVIOUS / "passages.jsonl.gz")
    assert not any(p["document_id"] in keys for p in old_passages)
    ptoken = ROOT / config["tokenizer_path"]
    tokenizer = LocalTokenizer(
        ptoken,
        repository=config["tokenizer_repository"],
        revision=config["tokenizer_revision"],
        expected_sha256=prior_manifest["tokenizer"]["sha256"],
    )
    fingerprint = prior_manifest["rules_fingerprint"]
    # Representation regression on unchanged examples, without historical segmentation.
    for v in [1, 4, 6]:
        d = next(d for d in docs if d["volume"] == v)
        new = passages_for(
            d, store.lib.base.page_index(store.sources[v])[1], tokenizer, config, fingerprint
        )
        assert new == [p for p in old_passages if p["document_id"] == d["id"]]
    paths = [
        Path(__file__),
        REPAIRS,
        BASE / "extraction/prepare_documents.py",
        BASE / "extraction/technical_passages.py",
        CONFIG,
        src.path,
        ptoken,
        store.journal,
        PRIVATE / "article-decisions.jsonl",
        BASE / "sources/persee/alignment-cache/mets-v5.xml",
        *[
            BASE / f"sources/persee/registry-cache/arcpa_0000-0000_1879_num_5_1_{suffix}-record.xml"
            for suffix in ["2837", "2877"]
        ],
        *[p for p in PREVIOUS.iterdir() if p.is_file()],
        *[p for p in G6.iterdir() if p.is_file()],
    ]
    hashes = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths}
    out = BASE / "data/documents" / (VERSION + "-" + sha(json.dumps(hashes, sort_keys=True))[:12])
    if out.exists():
        raise ValueError("Immutable generation already exists: " + str(out))
    out.mkdir()
    (out / ".private").mkdir(mode=0o700)
    for log in [store.journal, PRIVATE / "article-decisions.jsonl"]:
        target = out / ".private" / log.name
        target.write_bytes(log.read_bytes())
        target.chmod(0o600)
    added = []
    crosswalk = []
    for r in repairs:
        d = next(d for d in docs if d["id"] == r["document_id"])
        assert [d["source_start"], d["source_end"]] == [r["old_start"], r["old_end"]] and not d[
            "full_text"
        ].strip()
        assert src.sha256 == r["source_sha256"]
        assert d["source"]["source_revision"] == descriptor["source_revision"]
        a, z = r["new_start"], r["new_end"]
        assert sha(src.text[a:z]) == r["new_text_sha256"]
        d.update(
            source_start=a,
            source_end=z,
            full_text=src.text[a:z],
            text_sha256=sha(src.text[a:z]),
            extent_id="ap1789-parent-version:" + sha(f"{d['id']}|{src.sha256}|{a}|{z}")[:24],
            version=VERSION,
            content_flags=[],
            anomalies=[],
        )
        d["original_boundary_status"] = original[d["id"]]["boundary_status"]
        d["boundary_status"] = dict(
            extracted_class="codex_reviewed",
            latest_review_status="codex_reviewed",
            human_event_id=None,
            compatible_with_latest_decision=True,
            certified=False,
            examination="Codex_XML_source_review_not_independent_human",
        )
        d["xml_blocks"] = [
            {k: b[k] for k in ["id", "xpath", "start", "end", "tag"]}
            for b in store.selected_blocks(5, a, z)
        ]
        d["annotations"] = []
        d["document_components"] = []
        for i, c in enumerate(r["components"]):
            d["document_components"].append(dict(c, id=d["id"] + ":component:" + str(i + 1)))
            for note in src.node(c["xpath"]).iter("note"):
                x, y = src.span(note)
                d["annotations"].append(
                    dict(start=x, end=y, xpath=src.tree.getpath(note), role="XML_editorial_note")
                )
        d["historical_segmentation"] = dict(
            d["historical_segmentation"],
            extent_compatible=False,
            original_extent_id=original[d["id"]]["extent_id"],
            note="Historical G6 annotations retained on the old empty extent; never transferred to recovered text.",
        )
        d["documentary_repair"] = dict(
            version=descriptor["version"],
            previous_extent_id=original[d["id"]]["extent_id"],
            reference="document-repairs.json",
            validation="Codex_examined_not_human_validated",
        )
        own = passages_for(d, at, tokenizer, config, fingerprint)
        added.extend(own)
        d["passage_ids"] = [p["id"] for p in own]
        crosswalk.append(
            dict(
                document_id=d["id"],
                old_extent_id=original[d["id"]]["extent_id"],
                new_extent_id=d["extent_id"],
                old_passage_ids=[],
                new_passage_ids=d["passage_ids"],
            )
        )
    passages = []
    grouped = {d["id"]: [] for d in docs}
    for p in old_passages + added:
        grouped[p["document_id"]].append(p)
    for d in docs:
        passages.extend(grouped[d["id"]])
    assert all(d == original[d["id"]] for d in docs if d["id"] not in keys)
    assert [p for p in passages if p["document_id"] not in keys] == old_passages
    inventory = rows(PREVIOUS / "inventory.jsonl.gz")
    for r in inventory:
        if r["id"] in keys:
            r.update(
                boundary_class="codex_reviewed",
                extraction_state="source_recovered_Codex_examined",
                anomalies=[],
            )
    write_rows(out / "documents.jsonl.gz", docs)
    write_rows(out / "passages.jsonl.gz", passages)
    write_rows(out / "inventory.jsonl.gz", inventory)
    for filename in ["metadata.jsonl.gz", "visual-sample.json"]:
        (out / filename).write_bytes((PREVIOUS / filename).read_bytes())
    longs = rows(PREVIOUS / "long-paragraphs.jsonl.gz")
    for d in docs:
        if d["id"] not in keys:
            continue
        for b in d["xml_blocks"]:
            if b["tag"] == "p":
                count = tokenizer.count(src.text[b["start"] : b["end"]])
                if count > config["maximum_tokens"]:
                    longs.append(
                        dict(
                            document_id=d["id"],
                            xpath=b["xpath"],
                            source_start=b["start"],
                            source_end=b["end"],
                            tokens=count,
                        )
                    )
    write_rows(out / "long-paragraphs.jsonl.gz", longs)
    write_rows(out / "extent-crosswalk.jsonl.gz", crosswalk)
    (out / "document-repairs.json").write_bytes(REPAIRS.read_bytes())
    dump(
        out / "inputs.json",
        dict(
            files=hashes,
            previous_directory=str(PREVIOUS.relative_to(BASE)),
            preserved_historical_generation=str(G6.relative_to(BASE)),
        ),
    )
    manifest = dict(
        version=VERSION,
        previous_directory=str(PREVIOUS.relative_to(BASE)),
        configuration=config,
        rules_fingerprint=fingerprint,
        tokenizer=prior_manifest["tokenizer"],
        files={p.name: sha(p.read_bytes()) for p in out.iterdir() if p.is_file()},
    )
    dump(out / "manifest.json", manifest)
    integrity = verify(out, tokenizer)
    # Added extents must not intersect any other document's attributed source span.
    for d in docs:
        if d["id"] in keys:
            assert not any(
                o["id"] != d["id"]
                and o["volume"] == 5
                and max(d["source_start"], o["source_start"])
                < min(d["source_end"], o["source_end"])
                for o in docs
            )
    summary = json.loads((PREVIOUS / "summary.json").read_text())
    lengths = sorted(p["token_count"] for p in passages)
    summary.update(
        version=VERSION,
        generation=out.name,
        previous_directory=str(PREVIOUS.relative_to(BASE)),
        whitespace_only_documents=[],
        cahiers_with_substantive_text=1224,
        passages=len(passages),
        passages_in_cahiers=summary["passages_in_cahiers"] + len(added),
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
        integrity=integrity,
        repaired_documents=len(keys),
        new_passages=len(added),
        unchanged_documents=len(docs) - len(keys),
        unchanged_passages=len(old_passages),
        new_documentary_overlap_pairs=0,
        secondary_human_articles_preserved=605,
        technical_rules_unchanged=True,
        elapsed_seconds=time.perf_counter() - started,
    )
    summary["by_volume"]["5"]["passages"] += len(added)
    own = [p for p in passages if p["document_id"] in {d["id"] for d in docs if d["volume"] == 5}]
    summary["by_volume"]["5"]["mean_tokens"] = sum(p["token_count"] for p in own) / len(own)
    assert all(sha((ROOT / name).read_bytes()) == digest for name, digest in hashes.items())
    dump(out / "summary.json", summary)
    manifest["files"]["summary.json"] = sha((out / "summary.json").read_bytes())
    dump(out / "manifest.json", manifest)
    assert json.loads(CURRENT.read_text())["directory"] == str(PREVIOUS.relative_to(BASE)), (
        "Active reference changed during repair"
    )
    tmp = CURRENT.with_suffix(".tmp")
    dump(
        tmp,
        dict(
            directory=str(out.relative_to(BASE)),
            version=VERSION,
            previous_directory=str(PREVIOUS.relative_to(BASE)),
        ),
    )
    os.replace(tmp, CURRENT)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return out


if __name__ == "__main__":
    build()
