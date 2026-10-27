"""Gel après développement, avant consultation du lot de validation inédit."""

import datetime

from common import HERE, V1, read, sha, write


def main():
    assert not (HERE / "rules-freeze.json").exists()
    plan = read(HERE / "validation-plan.json")
    assert all(sha((HERE / p).read_bytes()) == h for p, h in plan["files"].items())
    dev = read(HERE / "data/development-metrics.json")["segmentation"]
    assert dev["v2_exact"] == 260 and dev["lost_previously_correct"] == 0
    configuration = dict(
        version="documentary-v2.0",
        source_revision="926fd3cd986a3c3d411e93d1845fff6475cb2602",
        classes=["autonomous", "part", "associated", "mention", "out_of_scope", "uncertain"],
        strict_cahier_class="autonomous",
        inclusive_document_classes=["autonomous", "associated"],
        numbering_is_not_verification=True,
        automatic_units_status="B",
        offsets="decoded XML Unicode, half-open",
        matching="only boundary whitespace trimmed; original text untouched",
        new_validation_not_examined=True,
        rule_changes=[
            "contextual exclusion of introduction/pre1789 headings",
            "explicit absence variants",
            "rubric vs internal restart",
            "professional associated documents and minutes",
            "p1 titles and non-cahier openings",
            "continuations and attached pieces",
            "short nominal headings before marker with bare-marker safeguard",
            "prefix punctuation retained with its paragraph",
            "ArtIer and Ari OCR variants without normalization",
        ],
    )
    write(HERE / "configuration.json", configuration)
    files = [
        "common.py",
        "rules_v2.py",
        "discover_v2.py",
        "configuration.json",
        "prepare_validation.py",
        "validation-plan.json",
    ]
    write(
        HERE / "rules-freeze.json",
        dict(
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            reference_exists=False,
            new_validation_source_packs_examined=False,
            files={p: sha((HERE / p).read_bytes()) for p in files},
            v1_dependencies={
                str(V1.name + "/" + p): sha((V1 / p).read_bytes())
                for p in ["rules.py", "pilot_segment.py", "fast_blocks.py"]
            },
            development_result=dev,
        ),
    )
    print("V2 frozen;260/269 development units, zero lost among250 V1-correct units")


if __name__ == "__main__":
    main()
