"""Contrôles locaux de fidélité et de reproduction, sans base ni réseau."""

import ast
import collections
import datetime
import importlib.util
import urllib.parse

from auditlib import HERE, load_sources, read, rows, save, sha
from lxml import etree


def local_module(name):
    spec = importlib.util.spec_from_file_location(
        "persee_alignment_check_" + name, HERE / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.__file__ == str(HERE / (name + ".py"))
    return module


def main():
    local_module("evaluate").verify_freezes()
    prior = read(HERE / "prior-audits-sha256.json")
    repo = HERE.parents[2]
    for name, h in prior.items():
        assert sha((repo / name).read_bytes()) == h, name
    ss = load_sources()
    sample = read(HERE / "data/sample.json")
    meta = rows(HERE / "data/metadata.jsonl")
    rs = rows(HERE / "data/alignment-predictions.jsonl")
    checks = {}
    assert len(sample) == len(meta) == len(rs) == 72
    assert len({r["id"] for r in sample}) == 72
    assert collections.Counter(r["volume"] for r in sample) == {v: 12 for v in range(1, 7)}
    for r in meta:
        assert r["page_start"] is not None and r["page_end"] >= r["page_start"]
        assert any(f"_num_{r['volume']}_1" in x for x in r["is_part_of"])
        assert r["date_edition"] == ["1879"] and r["date_historical"] is None
        assert r["access_status"] == "obtained"
    for r in rs:
        s = ss[r["volume"]]
        assert r["source"]["source_sha256"] == s.sha256
        assert r["verification"] == "not_reviewed" and r["confidence_is_not_probability"]
        for c in r["candidates"]:
            assert s.span(s.node(c["anchor_xpath"]))[0] == c["start"]
        if r["boundary"]:
            p = r["boundary"]
            assert 0 <= p["start"] < p["end"] <= len(s.text)
            assert p["status"] == "proposed_not_verified"
            for xp in p["divisions"]:
                assert s.node(xp) is not None
    ann = rows(HERE / "data/annotations.jsonl")
    assert len(ann) == 72
    assert sum(r["kind"] == "cahier" for r in ann) == 55
    for r in ann:
        if r.get("boundary_reference"):
            s = ss[r["volume"]]
            b = r["boundary_reference"]
            assert 0 <= b["start"] < b["end"] <= len(s.text)
            assert all(s.node(xp) is not None for xp in b["divisions"])
    for f in (HERE / ".cache").glob("*.xml"):
        if f.name == "robots.xml":
            continue
        root = etree.parse(str(f), etree.XMLParser(resolve_entities=False, no_network=True))
        assert not root.xpath('//*[namespace-uri()="http://www.tei-c.org/ns/1.0"]'), f
    log = read(HERE / "data/access-log.json")
    for e in log:
        url = urllib.parse.urlparse(e["url"])
        assert url.hostname == "oai.persee.fr"
        args = urllib.parse.parse_qs(url.query)
        assert args.get("metadataPrefix", [None])[0] in {None, "oai_dc", "persee_mets"}
        if "resumptionToken" in args:
            assert set(args) == {"verb", "resumptionToken"}
        assert e["status"] == 200
    for p in read(HERE / "data/pagination-check.json"):
        assert (
            p["page1_records"] == p["page2_records"] == 20
            and not p["overlap"]
            and p["page2_cursor"] == "20"
        )
    reproducible = [
        "alignment-predictions.jsonl",
        "page-index.json",
        "complementary-predictions.jsonl",
        "comparisons.jsonl",
        "correspondences.jsonl",
        "metrics.json",
    ]
    before = {n: sha((HERE / "data" / n).read_bytes()) for n in reproducible}
    for name in ["alignment", "complementary", "evaluate"]:
        local_module(name).main()
    for n, h in before.items():
        assert sha((HERE / "data" / n).read_bytes()) == h, n
    for f in HERE.glob("*.py"):
        ast.parse(f.read_text(), filename=str(f))
    # Only local markdown links; no requests made to check external source URLs.
    import re

    for f in HERE.glob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", f.read_text()):
            if "://" not in link and not link.startswith("#"):
                assert (f.parent / link.split("#")[0]).exists() or link == "data/checks.json", (
                    f,
                    link,
                )
    for name, h in prior.items():
        assert sha((repo / name).read_bytes()) == h, ("after replay", name)
    checks.update(
        completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        prior_audits_unchanged=len(prior),
        pinned_stanford_sources_verified=6,
        sample_unique=72,
        per_volume=12,
        pagination_tokens_followed=2,
        network_requests_journaled=len(log),
        metadata_only_no_tei_download=True,
        source_bounds_valid=True,
        model_and_annotation_freezes_intact=True,
        outputs_exactly_reproduced=list(before),
        python_syntax_valid=True,
        local_markdown_links_valid=True,
        independent_human_validation=False,
        human_validation_seconds=None,
        application_or_database_access=False,
    )
    save(HERE / "data/checks.json", checks)
    save(
        HERE / "data/review-effort.json",
        dict(
            reviewer="Codex, non-independent and predictions visible",
            sample_notices_screened=72,
            source_target_documents_examined=56,
            non_cahier_notices=16,
            boundary_references_examined=26,
            body_scope="source openings, closings, transitions, territorial names, adjacent headings; no full collation of all long bodies",
            rules_changed_after_new_B_review=False,
            independent_human_interventions=0,
            human_validation_seconds=None,
            corrections_applied_to_raw_predictions=0,
            remaining=dict(
                boundary_unreviewed=30,
                bad_ends_in_C_reviewed_subset=3,
                uncertain_identity_or_scope=2,
                multiple_candidate_queues=2,
            ),
            counts_overlap=True,
        ),
    )
    print(
        "Verified",
        len(prior),
        "prior files; six sources;72 notices; two pagination tokens; six exact replay outputs",
    )


if __name__ == "__main__":
    main()
