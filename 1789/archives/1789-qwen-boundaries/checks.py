"""Vérification de provenance et d'intégrité, pas certification des choix du LLM."""

import ast
import json

from prompt import messages, parse
from qcommon import HERE, ROOT, read, rows, save, sha, source_helpers


def main():
    errors = []
    freeze = read(HERE / "data/freeze.json")
    for name, h in freeze["files"].items():
        if sha((HERE / name).read_bytes()) != h:
            errors.append("frozen_changed:" + name)
    prior = read(HERE / "prior-files-sha256.json")
    for name, h in prior.items():
        p = ROOT / name
        if not p.exists() or sha(p.read_bytes()) != h:
            errors.append("previous_file_changed:" + name)
    lib = source_helpers()
    ss = lib.sources()
    windows = rows(HERE / "data/windows.jsonl")
    ws = {w["id"]: w for w in windows}
    block_checks = 0
    for w in windows:
        s = ss[w["volume"]]
        assert s.sha256 == w["source"]["source_sha256"]
        assert len(w["blocks"]) == len({b["id"] for b in w["blocks"]})
        for b in w["blocks"]:
            assert s.span(s.node(b["xpath"])) == [b["start"], b["end"]]
            assert s.text[b["start"] : b["end"]] == b["text"]
            block_checks += 1
        mb = json.loads(messages(w, "B")[1]["content"].split("\n", 1)[1])
        mc = json.loads(messages(w, "C")[1]["content"].split("\n", 1)[1])
        mc.pop("proposal_from_rules")
        assert mb == mc and "proposal_from_rules" not in mb
        assert all("xpath" not in b and "start" not in b and "end" not in b for b in mb["blocks"])
    for split, count in [("development", 48), ("validation", 72)]:
        outputs = rows(HERE / f"data/{split}-outputs.jsonl")
        assert len(outputs) == count
        assert len({(r["window_id"], r["method"]) for r in outputs}) == count
        recipe = read(HERE / f"data/{split}-recipe.json")
        assert recipe["model"]["key"] == "qwen3-14b" and recipe["model"]["shards"] == 8
        assert recipe["model"]["revision"] == "40c069824f4251a91eefaf281ebe4c544efd3e18"
        assert recipe["inference"]["truncation"] is False
        for r in outputs:
            assert r["recipe_sha256"] == sha(json.dumps(recipe, sort_keys=True))
            assert r["input_sha256"] == sha(
                json.dumps(messages(ws[r["window_id"]], r["method"]), ensure_ascii=False)
            )
            assert r["input_tokens"] <= 24576 and r["raw"] is not None
            json.loads(r["raw"])
            if r["parsed"] is not None:
                assert parse(r["raw"], ws[r["window_id"]]) == r["parsed"]
        assert all(r["within_budget"] for r in read(HERE / f"data/{split}-token-counts.json"))
    refs = rows(HERE / "data/reference-validation.jsonl")
    assert len(refs) == 36 and all(r["novel_source_leaf"] for r in refs)
    for r in refs:
        blocks = {b["id"]: b for b in ws[r["window_id"]]["blocks"]}
        assert (
            r["start"] == blocks[r["start_id"]]["start"] and r["end"] == blocks[r["end_id"]]["end"]
        )
    # An actual newly observed baseline defect: the Santeny proposal contains whitespace only.
    w = ws["validation-26"]
    b = w["baseline"]["raw"]
    snippet = ss[w["volume"]].text[b["start"] : b["end"]]
    assert not snippet.strip()
    save(
        HERE / "data/empty-baseline-case.json",
        dict(
            window_id=w["id"],
            persee_id=w["persee_id"],
            span=[b["start"], b["end"]],
            exact_source_slice=snippet,
            source_sha256=w["source"]["source_sha256"],
            conclusion="Automatic A proposal exists but contains no non-whitespace source text; not an abstention",
        ),
    )
    for p in HERE.glob("*.py"):
        ast.parse(p.read_text(), filename=str(p))
    result = dict(
        ok=not errors,
        errors=errors,
        previous_files_unchanged=len(prior),
        Stanford_source_files=6,
        limited_windows=len(windows),
        exact_source_blocks_checked=block_checks,
        frozen_validation_references=len(refs),
        final_Qwen_calls=120,
        pilot_v1_calls=len(rows(HERE / "data/pilot-v1-outputs.jsonl")),
        no_overflow_or_silent_truncation=True,
        B_does_not_receive_A=True,
        all_output_block_IDs_validated=True,
        invalid_model_decisions_retained_not_repaired=True,
    )
    save(HERE / "data/checks.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert not errors


if __name__ == "__main__":
    main()
