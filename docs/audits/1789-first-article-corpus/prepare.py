"""Select 24 inherited controls and six corrected references, without rediscovery."""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parents[1] / "tools/1789-document-review"
sys.path.insert(0, str(TOOL))

from reviewlib import AUDITS, Store, rows, sha  # noqa: E402

KEYS = {
    1: ["agen-clerge", "agen-noblesse", "alencon-clerge", "alencon-noblesse"],
    2: ["angoumois-noblesse", "anjou-clerge", "beaujolais-noblesse", "lawastine-tiers"],
    3: ["colmar-ville", "ribaucourt", "flines", "carces-mineurs"],
    4: ["mirecourt-noblesse", "mirecourt-clerge", "ferrieres", "ermenonville"],
    5: ["pierrelez-habitants", "perigny-brie", "plessis-secqueville", "puteaux"],
    6: ["vic-clerge", "toul-noblesse", "albertas", "beaurecueil"],
}


def main():
    s = Store()
    pilot = {r["key"]: r for r in rows(AUDITS / "1789-extraction-pilot/data/documents.jsonl")}
    cross = {
        r["previous_id"]: r
        for r in rows(AUDITS / "1789-document-registry/data/previous-document-crosswalk.jsonl")
    }
    selected = []
    for keys in KEYS.values():
        for key in keys:
            p = pilot[key]
            matches = cross[p["id"]]["matches"]
            ids = [m["registry_id"] for m in matches if m["relation"] == "exact_range"]
            if len(ids) != 1:
                ids = [m["registry_id"] for m in matches]
            if len(ids) != 1:
                raise ValueError(f"Ambiguous pilot link: {key}: {matches}")
            r = s.by_id[ids[0]]
            selected.append(
                dict(
                    document_id=r["id"],
                    persee_id=r["persee_id"],
                    title=r["metadata"]["title"],
                    volume=p["volume"],
                    reason="Contrôle hérité du pilote : "
                    + key
                    + " ; diversité de longueur/ordre, titres, sections, notes et signatures.",
                    legacy_parent_id=p["id"],
                    legacy_key=key,
                    legacy_range=[p["source_text_start"], p["source_text_end"]],
                    selection_type="inherited_development_not_new_validation",
                    source_reference="1789-extraction-pilot/data/documents.jsonl",
                )
            )
    targets = {
        "development": ["development-08", "development-13"],
        "validation": ["validation-06", "validation-19", "validation-26", "validation-32"],
    }
    for split, ids in targets.items():
        for ref in rows(AUDITS / f"1789-qwen-boundaries/data/reference-{split}.jsonl"):
            if ref["window_id"] in ids:
                key = "ap1789-registry-p1:" + ref["persee_id"]
                r = s.by_id[key]
                selected.append(
                    dict(
                        document_id=key,
                        persee_id=r["persee_id"],
                        title=r["metadata"]["title"],
                        volume=ref["volume"],
                        reason="Référence documentaire Codex corrigée/complexe, sans utilisation des prédictions Qwen : "
                        + ref["reason"],
                        legacy_parent_id=None,
                        selection_type="previously_reviewed_reference_not_new_validation",
                        source_reference=f"1789-qwen-boundaries/data/reference-{split}.jsonl#{ref['window_id']}",
                    )
                )
    assert len(selected) == 30 and len({r["document_id"] for r in selected}) == 30
    selected.sort(
        key=lambda r: (r["volume"], s.by_id[r["document_id"]]["metadata"]["catalogue_order"])
    )
    (HERE / "data/selection.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2) + "\n"
    )
    # New snapshot only; never rewrite earlier manifests after the Git size cleanup.
    files = [
        Path(p.decode()).resolve()
        for p in subprocess.check_output(["git", "ls-files", "-z", "docs/audits"]).split(b"\0")
        if p
    ]
    files += [p for p in (AUDITS / "1789-extraction-v2/.cache/sources").glob("*.xml")]
    manifest = {
        str(p.relative_to(HERE.parents[2])): sha(p.read_bytes())
        for p in files
        if p.exists() and HERE not in p.parents
    }
    (HERE / "prior-files-sha256.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Prepared 30 dossiers; no human decisions created")


if __name__ == "__main__":
    main()
