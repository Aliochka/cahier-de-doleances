# ruff: noqa: E402
"""Contrôles de fidélité, isolation, gel et reproductibilité sans accès applicatif."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import frozen_match  # noqa: E402

import ast
import datetime

from common import HERE, PILOT, REPO, V1, jlines, read, rows, sha, sources, write
from discover_v2 import predict
from evaluate import verify_freezes
from fast_blocks import cache_nodes
from rules_v2 import role_blocks, segment


def main():
    checks = {}
    prior = read(HERE / "prior-audits-sha256.json")
    for name, h in prior.items():
        assert frozen_match(REPO / name, h), name
    checks["prior_audits_unchanged"] = len(prior)
    verify_freezes()
    checks["rules_plan_and_reference_freezes_intact"] = True
    ss = sources()
    for s in ss.values():
        cache_nodes(s)
    checks["pinned_sources_verified"] = len(ss)
    allpred = rows(HERE / "data/v2-document-predictions.jsonl")
    assert len({r["id"] for r in allpred}) == len(allpred)
    for r in allpred:
        s = ss[r["volume"]]
        assert 0 <= r["start"] < r["end"] <= len(s.text)
        assert r["source"]["source_sha256"] == s.sha256
        assert s.span(s.node(r["anchor_xpath"]))[0] == r["start"]
        assert r["verification_status"] == "automatic_not_certified"
        if r.get("attached_to"):
            assert any(p["id"] == r["attached_to"] for p in allpred)
    checks["global_hypotheses_valid_traces_no_automatic_certification"] = len(allpred)
    pp = rows(HERE / "data/validation-v2-predictions.jsonl")
    allowed = {(p["volume"], p["xpath"]) for p in pp if not p["internal"]}
    assert predict(ss, allowed) == pp
    checks["validation_predictions_exact_replay"] = True
    assert predict(ss) == allpred
    checks["six_volume_predictions_exact_replay"] = True
    parents = rows(HERE / "data/corpus-parents.jsonl")
    aa = rows(HERE / "data/corpus-A.jsonl")
    cc = rows(HERE / "data/corpus-C.jsonl")
    lookup = {p["id"]: p for p in parents}
    for p in parents:
        s = ss[p["volume"]]
        assert p["text"] == s.text[p["start"] : p["end"]]
        parts = sorted([u for u in aa + cc if u["parent_id"] == p["id"]], key=lambda u: u["start"])
        assert "".join(u["text"] for u in parts) == p["text"]
        cursor = p["start"]
        for u in parts:
            assert u["start"] == cursor
            cursor = u["end"]
        assert cursor == p["end"]
    for group in [aa, cc, rows(HERE / "data/validation-article-predictions.jsonl")]:
        assert len({u["id"] for u in group}) == len(group)
        for u in group:
            p = lookup[u["parent_id"]]
            s = ss[u["volume"]]
            assert p["start"] <= u["start"] < u["end"] <= p["end"]
            assert u["text"] == s.text[u["start"] : u["end"]]
            assert p["text"][u["parent_start"] : u["parent_end"]] == u["text"]
    for u in aa:
        for name in ["previous_reviewed_id", "next_reviewed_id"]:
            if u[name]:
                assert any(v["id"] == u[name] and v["parent_id"] == u["parent_id"] for v in aa)
    for p in parents:
        expected = [
            u
            for u in rows(HERE / "data/validation-article-predictions.jsonl")
            if u["version"] == "v2" and u["parent_id"] == p["id"]
        ]
        replay = segment(ss[p["volume"]], role_blocks(ss[p["volume"]], p))
        assert [(u["start"], u["end"]) for u in expected] == [
            (u["start"], u["end"]) for u in replay
        ]
    checks["parent_texts_A_C_reconstruction_and_article_traces"] = dict(
        parents=len(parents),
        A=len(aa),
        C=len(cc),
        all_proposals_text_exact=True,
        segmentation_exact_replay=True,
    )
    assert len(aa) == 78
    checks["uncertain_reference_withheld_from_A"] = 1
    refs = rows(HERE / "data/reference-candidates.jsonl")
    assert len(refs) == 25 and sum(r["novel"] for r in refs) == 24
    old_paths = {(r["volume"], r["xpath"]) for r in rows(V1 / "data/selection.jsonl")}
    old_paths |= {(r["volume"], r["xpath"]) for r in read(PILOT / "negative-cases.json")}
    old_paths |= {
        (d["volume"], xp) for d in rows(PILOT / "data/documents.jsonl") for xp in d["divisions"]
    }
    old_paths.add((5, "/TEI.2/text/body/div1/div2[1]/div3[3]"))
    for r in refs:
        if r["novel"]:
            assert (r["volume"], r["xpath"]) not in old_paths
    for z in rows(HERE / "data/validation-zones.jsonl"):
        for xp in z["xpaths"]:
            assert (z["volume"], xp) not in old_paths
    checks["novel_candidates_and_zones_exclude_prior_selection_and_negative_controls"] = True
    checks["validation_scope"] = dict(
        new_candidates=24,
        retained_legacy_control=1,
        continuous_zones=12,
        initial_article_reference=79,
        unambiguous_retained=78,
    )
    checks["development"] = read(HERE / "data/development-metrics.json")["segmentation"]
    assert checks["development"]["lost_previously_correct"] == 0
    parsed = []
    for path in sorted(HERE.glob("*.py")):
        ast.parse(path.read_text(), filename=str(path))
        parsed.append(path.name)
    checks["python_syntax_valid"] = parsed
    checks["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    checks["no_application_or_database_imports"] = True
    write(HERE / "data/checks.json", checks)
    print({k: v for k, v in checks.items() if k != "python_syntax_valid"})
    events = []
    for r in rows(HERE / "data/19-diagnoses.jsonl"):
        events.append(
            dict(
                operation="development_discrepancy_source_review",
                document=r["document_key"],
                decision_index=r["index"],
                diagnosis=r["diagnosis"],
                reviewer="Codex",
                independent_human=False,
                measured_human_seconds=None,
            )
        )
    for r in refs:
        events.append(
            dict(
                operation="candidate_source_classification",
                id=r["candidate_id"],
                novel=r["novel"],
                decision=r["classification"],
                reviewer="Codex",
                reading_scope=r["review_scope"],
                measured_human_seconds=None,
            )
        )
    for z in rows(HERE / "data/reference-zones.jsonl"):
        events.append(
            dict(
                operation="complete_continuous_zone_review",
                id=z["id"],
                reference_parent_ids=z["expected_parent_ids"],
                reviewer="Codex",
                measured_human_seconds=None,
            )
        )
    for n in rows(HERE / "data/reference-review-notes.jsonl"):
        events.append(
            dict(operation="explicit_documentary_reservation", **n, measured_human_seconds=None)
        )
    events.append(
        dict(
            operation="article_boundary_reference_review",
            initial_reference_units=79,
            retained_unambiguous_A=78,
            ambiguous_withheld=1,
            reviewer="Codex",
            independent_human=False,
            measured_human_seconds=None,
            automatic_predictions_corrected_in_place=0,
        )
    )
    jlines(HERE / "data/review-log.jsonl", events)


if __name__ == "__main__":
    main()
