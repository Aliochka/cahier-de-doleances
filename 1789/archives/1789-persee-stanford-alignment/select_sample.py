"""Sélection limitée, déterministe, faite avant les rapprochements nouveaux."""

import collections
import datetime
import hashlib
import json

from fetch_metadata import CACHE, HERE, NS
from lxml import etree


def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    assert not (HERE / "sample-plan.json").exists()
    catalogue = []
    for v in range(1, 7):
        root = etree.parse(str(CACHE / f"mets-v{v}.xml"))
        divs = root.findall(".//mets:structMap//mets:div", NS)
        for order, n in enumerate(divs):
            pid = (n.get("ID") or "").removeprefix("TdM_")
            if not pid.startswith(f"arcpa_0000-0000_1879_num_{v}_1_"):
                continue
            catalogue.append(
                dict(
                    id=pid,
                    volume=v,
                    title=n.get("LABEL"),
                    type=n.get("TYPE"),
                    catalogue_order=order,
                    local_order=n.get("ORDER"),
                    ancestors=[
                        a.get("LABEL")
                        for a in n.iterancestors()
                        if a.tag == "{http://www.loc.gov/METS/}div"
                    ],
                    mets_file=f"mets-v{v}.xml",
                    mets_xpath=root.getpath(n),
                )
            )
    (CACHE / "catalogue.json").write_text(
        json.dumps(catalogue, ensure_ascii=False, indent=2) + "\n"
    )
    old = json.loads((HERE.parent / "1789-sources-comparison/data/documents.json").read_text())
    controls = {r["persee_id"]: "previous_seven_source_comparison" for r in old}
    controls.update(
        {
            "arcpa_0000-0000_1879_num_2_1_1563": "known_V2_Anjou_clerge",
            "arcpa_0000-0000_1879_num_3_1_1861": "known_V2_Courtiches",
            "arcpa_0000-0000_1879_num_3_1_1924": "known_V2_Grasse",
            "arcpa_0000-0000_1879_num_5_1_2333": "known_Pecqueuse",
            "arcpa_0000-0000_1879_num_4_1_2175": "known_Ferrieres",
            "arcpa_0000-0000_1879_num_5_1_2915": "known_Soissons_clergy_context_not_absent_notice",
        }
    )
    chosen = []
    for v in range(1, 7):
        frame = [r for r in catalogue if r["volume"] == v and r["type"] != "theme"]
        selected = [
            dict(r, selection="development_control", control=controls[r["id"]])
            for r in frame
            if r["id"] in controls
        ]
        negatives = [
            r for r in frame if r["type"] != "griev" and r["id"] not in {r["id"] for r in selected}
        ]
        if negatives:
            selected.append(
                dict(
                    min(negatives, key=lambda r: digest("negative|" + r["id"])),
                    selection="negative_document_type_control",
                    control=None,
                )
            )
        fresh = sorted(
            [r for r in frame if r["id"] not in {r["id"] for r in selected}],
            key=lambda r: digest("alignment-1789-v1|" + r["id"]),
        )
        for r in fresh[: 12 - len(selected)]:
            selected.append(dict(r, selection="new_hash_sample", control=None))
        assert len(selected) == 12
        chosen.extend(selected)
    assert len(chosen) == 72
    save(
        "sample-plan.json",
        dict(
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            metadata_only=True,
            stanford_alignment_examined=False,
            seed="alignment-1789-v1",
            total=72,
            per_volume=12,
            development=sum(r["selection"] == "development_control" for r in chosen),
            new_hash=sum(r["selection"] == "new_hash_sample" for r in chosen),
            negative_type=sum(r["selection"] == "negative_document_type_control" for r in chosen),
            representative=False,
            design="Known controls, one non-griev record/volume where available, remainder SHA-256 order in non-theme METS documentary catalogue. No source alignment or replacement of difficult records.",
        ),
    )
    save("data/sample.json", chosen)
    save(
        "data/catalogue-summary.json",
        dict(
            per_volume={
                v: dict(collections.Counter(r["type"] for r in catalogue if r["volume"] == v))
                for v in range(1, 7)
            },
            all_entries_are_catalogue_not_verified_cahiers=True,
            scope="Six issue METS metadata records, not documentary text harvesting",
            griev_total=sum(r["type"] == "griev" for r in catalogue),
        ),
    )
    print("sample", len(chosen), collections.Counter(r["selection"] for r in chosen))


if __name__ == "__main__":
    main()
