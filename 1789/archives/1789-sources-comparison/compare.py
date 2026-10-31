#!/usr/bin/env python3
"""Comparaison hors application, réseau et base ; lit les téléchargements isolés."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from lxml import etree as ET
from lxml import html

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "1789-multicorpus"
MAPPING = {
    "agen": ("agen-clerge", "1_1_1529", "2 2 6 2"),
    "angoumois": ("angoumois-noblesse", "2_1_1559", "4 2 2 3"),
    "colmar": ("colmar-ville", "3_1_1795", "5 2 2 4"),
    "mirecourt": ("mirecourt-noblesse", "4_1_1745", "6 2 2 3"),
    "pierrelez": ("pierrelez-habitants", "5_1_2339", "1 2 2 10"),
    "vic": ("vic-clerge", "6_1_2497", "3 2 2 5"),
    "guerande": ("guerande-tiers", "4_1_1780", "6 2 10 4"),
}
ARTFL = "https://artflsrv04.uchicago.edu/philologic5/archparl/"
NS = {"mods": "http://www.loc.gov/mods/v3", "mets": "http://www.loc.gov/METS/"}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(value):
    return hashlib.sha256(value).hexdigest()


def fold(value):
    return " ".join(value.split())


def distance(left, right):
    row = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        new = [i]
        for j, b in enumerate(right, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j - 1] + (a != b)))
        row = new
    return row[-1]


def parse(path):
    return html.fromstring(path.read_text(encoding="utf-8"))


def persee_paragraphs(path):
    return [p.text_content() for p in parse(path).xpath('//*[@itemprop="articleBody"]/p')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "data")
    args = parser.parse_args()
    source, out = args.downloads, args.output
    out.mkdir(parents=True, exist_ok=True)

    def write(name, value):
        (out / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    prior = {d["key"]: d for d in load(PRIOR / "data/documents.json")}
    documents, texts, pairs = [], {}, []
    page_jobs = dict((name, url) for url, name in load(source / "persee-page-jobs.json"))
    for key, (prior_key, suffix, philo_id) in MAPPING.items():
        doc = prior[prior_key]
        stanford = [b["text_exact"] for b in doc["blocks"] if b["kind"] == "p"]
        artfl = load(source / f"artfl-nav-{key}.json")
        (fragment,) = html.fromstring(artfl["text"]).xpath('//*[@class="xml-div3"]')
        current = [p.text_content() for p in fragment.xpath("./p")]
        assert len(stanford) == len(current)
        equal = sum(fold(a) == fold(b) for a, b in zip(stanford, current))
        pairs.extend(
            dict(
                key=key,
                paragraph=n,
                stanford_sha256=sha(fold(a).encode()),
                artfl_sha256=sha(fold(b).encode()),
                equal=fold(a) == fold(b),
            )
            for n, (a, b) in enumerate(zip(stanford, current), 1)
        )
        mods = ET.parse(str(source / f"persee-{key}-mods.xml"), ET.XMLParser(no_network=True))

        def text(xp):
            return mods.xpath(xp, namespaces=NS)

        page_elements = parse(source / f"persee-{key}.html").xpath("//*[@data-content-url]")
        page_rows = []
        for page in page_elements:
            name = f"persee-{key}-{page.get('id').split('_')[-2]}.html"
            ps = persee_paragraphs(source / name)
            page_rows.append(
                dict(
                    page_id=page.get("id"),
                    url=page.get("data-content-url"),
                    cache_file=name,
                    paragraphs=len(ps),
                    characters=sum(map(len, ps)),
                    image_url=parse(source / name).xpath("//img/@src")[0],
                )
            )
        persee_id = "arcpa_0000-0000_1879_num_" + suffix
        row = dict(
            key=key,
            stanford_document_id=doc["id"],
            stanford_xpath=doc["xpath"],
            stanford_source_url=doc["source_url"],
            stanford_volume=doc["volume"],
            paragraphs_stanford=len(stanford),
            paragraphs_artfl=len(current),
            identical_paragraphs=equal,
            artfl_philo_id=philo_id,
            artfl_navigation_url=ARTFL + "navigate/" + philo_id.replace(" ", "/"),
            artfl_metadata=artfl["metadata_fields"],
            artfl_response_sha256=sha((source / f"artfl-nav-{key}.json").read_bytes()),
            persee_id=persee_id,
            persee_url="https://www.persee.fr/doc/" + persee_id,
            persee_title=text("//mods:titleInfo/mods:title/text()")[0],
            persee_page_start=text("//mods:extent/mods:start/text()"),
            persee_page_end=text("//mods:extent/mods:end/text()"),
            persee_date=text("//mods:part/mods:date/text()"),
            persee_rights=text("//mods:accessCondition/text()"),
            persee_metadata_sha256=sha((source / f"persee-{key}-mods.xml").read_bytes()),
            pages=page_rows,
        )
        documents.append(row)
        texts[key] = (stanford, current)
    write("documents.json", documents)
    write("paragraph-pairs.json", pairs)

    probes = []
    for case in load(HERE / "cases.json"):
        key, n = case["key"], case["stanford_paragraph"] - 1
        values = {
            "stanford": texts[key][0][n],
            "artfl": texts[key][1][n],
            "persee": persee_paragraphs(source / case["persee_file"])[case["persee_paragraph"] - 1],
        }
        extracted, distances = {}, {}
        for provider, value in values.items():
            match = re.search(case["pattern"], fold(value), re.IGNORECASE)
            assert match, (case["id"], provider)
            extracted[provider] = match.group(1)
            distances[provider] = distance(
                fold(match.group(1)).casefold(), fold(case["reference"]).casefold()
            )
        probes.append(
            case
            | dict(
                observed=extracted,
                character_edit_distances=distances,
                contexts={k: fold(v) for k, v in values.items()},
                persee_page_url=page_jobs[case["persee_file"]],
            )
        )
    write("probes.json", probes)

    # Completeness controls are comparisons of the accessible representations,
    # never assertions about a restricted TEI export not obtained here.
    controls = []
    for key, fn, needle in [
        ("angoumois", "persee-angoumois-0003.html", "Proposeront en premier"),
        ("colmar", "persee-colmar-0012.html", "Les députés des dix villes d'Alsace"),
    ]:
        controls.append(
            dict(
                key=key,
                expected_visible_on_scan=needle,
                stanford_present=needle in fold(" ".join(texts[key][0])),
                artfl_present=needle in fold(" ".join(texts[key][1])),
                persee_page_present=needle in fold(" ".join(persee_paragraphs(source / fn))),
                persee_page_url=page_jobs[fn],
                cache_file=fn,
            )
        )
    write("completeness-controls.json", controls)

    mets = ET.parse(str(source / "persee-volume4-mets.xml"), ET.XMLParser(no_network=True))
    grievances = mets.xpath('//mets:div[@TYPE="griev"]', namespaces=NS)
    structural = dict(
        volume4_mets_griev_entries=len(grievances),
        caveat="Catalogue entries, not a count of validated unique complete cahiers.",
        relevant_entries=[
            dict(d.attrib)
            for d in grievances
            if any(s in d.get("LABEL", "") for s in ["Mirecourt", "Guérande", "Ferrières"])
        ],
        artfl_problem_metadata={
            p.stem: load(p).get("metadata_fields") for p in source.glob("artfl-problem-*.json")
        },
    )
    write("structure.json", structural)
    bibliography = load(source / "artfl-bibliography.json")
    write(
        "coverage.json",
        dict(
            entries=len(bibliography),
            files=[
                dict(
                    filename=r["filename"], philo_id=r["philo_id"], title=r["title"], year=r["year"]
                )
                for r in bibliography
            ],
            caveat="Runtime catalogue, not a count of validated cahiers or proof of a downloadable TEI archive.",
        ),
    )
    write(
        "metrics.json",
        dict(
            documents=7,
            paragraph_pairs=len(pairs),
            identical_paragraphs=sum(p["equal"] for p in pairs),
            comparison="Direct p elements, text_content vs itertext source; whitespace reduction only, no case/Unicode/hyphen/spelling normalization.",
            targeted_probes=len(probes),
            exact_reference_units={
                k: sum(p["character_edit_distances"][k] == 0 for p in probes) for k in values
            },
            probe_method="Levenshtein over whitespace-folded, casefolded selected short units. Purposive known-defect probes, not a corpus accuracy or CER/WER estimate.",
        ),
    )
    fingerprints = [
        dict(file=p.name, bytes=p.stat().st_size, sha256=sha(p.read_bytes()))
        for p in sorted(source.iterdir())
        if p.is_file() and p.name != "fetch.py"
    ]
    write("download-fingerprints.json", fingerprints)
    journal = [json.loads(line) for line in (source / "access.jsonl").read_text().splitlines()]
    write("access-log.json", journal)
    print("Pairs:", len(pairs), "identical:", sum(p["equal"] for p in pairs))
    for p in probes:
        print(p["id"], p["observed"], p["character_edit_distances"])


if __name__ == "__main__":
    main()
