"""Contrôles de provenance, des plages et du gel; aucune certification documentaire implicite."""

import collections
import json

from lib import HERE, PILOT, ROOT, read, rows, save, sha, sources


def main():
    ss = sources()
    freeze = read(HERE / "data/freeze.json")
    errors = []
    for name, expected in freeze["files"].items():
        if sha((HERE / name).read_bytes()) != expected:
            errors.append("freeze_changed:" + name)
    for v, s in ss.items():
        if s.sha256 != freeze["sources"][str(v)]:
            errors.append("source_changed:" + str(v))
    prior = read(HERE / "prior-audits-sha256.json")
    for name, expected in prior.items():
        p = ROOT / name
        if not p.exists() or sha(p.read_bytes()) != expected:
            errors.append("prior_audit_changed:" + name)
    rr = rows(HERE / "data/registry.jsonl")
    auto = rows(HERE / "data/registry-automatic.jsonl")
    metadata = rows(HERE / "data/metadata.jsonl")
    sample = rows(HERE / "data/validation-sample.jsonl")
    annotations = rows(HERE / "data/annotations.jsonl")
    assert len(rr) == len({r["persee_id"] for r in rr}) == len(metadata) == 1305
    assert dict(collections.Counter(r["metadata"]["volume"] for r in rr)) == {
        1: 24,
        2: 181,
        3: 223,
        4: 347,
        5: 298,
        6: 232,
    }
    assert len(sample) == len({r["persee_id"] for r in sample}) == len(annotations) == 100
    assert not {r["persee_id"] for r in sample} & set(freeze["known_persee_ids"])
    proposed = 0
    verified = 0
    for r in rr:
        s = ss[r["metadata"]["volume"]]
        b = r["boundaries"]["proposal"]
        assert r["metadata"]["dc_type"] == ["griev"] or r["metadata"]["dc_type"] == "griev"
        assert (
            r["technical_scores_are_probabilities"] is False
            and r["future_passages"]["produced"] is False
        )
        for c in r["candidates"]:
            assert s.node(c["anchor_xpath"]) is not None and s.node(c["xpath"]) is not None
            assert 0 <= c["start"] < c["leaf_end"] <= len(s.text)
        if b:
            proposed += 1
            assert 0 <= b["start"] < b["end"] <= len(s.text)
            assert r["boundaries"]["source_slice_sha256"] == sha(s.text[b["start"] : b["end"]])
            for p in b["divisions"]:
                assert s.node(p) is not None
        if r["boundaries"]["status"] == "verifiees":
            verified += 1
            assert r["boundaries"]["verification"] and r["boundaries"]["verified_reference"]
        assert not any("full_text" in k or k == "articles" for k in r)
    assert all(r["alignment_verification"] == "not_reviewed" for r in auto)
    assert len(rows(HERE / "data/stanford-comparison.jsonl")) == 1954
    cross = rows(HERE / "data/previous-document-crosswalk.jsonl")
    assert len(cross) == 200
    assert {r["id"] for r in rows(PILOT / "data/documents.jsonl")} <= {
        r["previous_id"] for r in cross
    }
    out = dict(
        ok=not errors,
        errors=errors,
        previous_files_checked=len(prior),
        source_files_checked=len(ss),
        registry_records=len(rr),
        metadata_records=len(metadata),
        automatic_boundaries=proposed,
        explicit_Codex_boundary_references=verified,
        validation_notices=len(sample),
        continuous_zones=len(rows(HERE / "data/zone-annotations.jsonl")),
        previous_document_ids_preserved=len(cross),
        no_application_command_or_database_access=True,
    )
    save(HERE / "data/checks.json", out)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    assert not errors


if __name__ == "__main__":
    main()
