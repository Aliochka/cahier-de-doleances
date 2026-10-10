"""Download and inspect the seven final GDN CSV exports without touching the DB."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path
from urllib.request import urlopen

import yaml

DATASET = "https://www.data.gouv.fr/api/1/datasets/5c5c3236634f4155110aa4ea/"
# Final snapshots only: older exports overlap and must not be stacked.
SOURCES = {
    "organisation_etat_services": "18ce2874-16f4-4b1a-a48e-5438b263b9d5",
    "democratie_citoyennete": "3e6be4ff-74a9-4255-a248-c72559c330fd",
    "fiscalite_depenses": "bc085888-e6bd-445d-b3f4-632190c29e3f",
    "transition_ecologique": "a6275209-9fd8-424f-a606-5beaead143bb",
    "questions_rapides_organisation": "e2a2d423-3011-49cc-8de8-7806eb8ff032",
    "questions_rapides_democratie": "00f08a5d-b400-4cf8-9737-fddb7e7a8147",
    "questions_rapides_transition": "9506723c-1810-4b2a-bd91-7ef1f222090f",
}
ROOT = Path(__file__).resolve().parents[1]
csv.field_size_limit(2**31 - 1)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fetch(args):
    with urlopen(DATASET, timeout=60) as response:
        dataset = json.load(response)
    resources = {r["id"]: r for r in dataset["resources"]}
    folder = args.directory / ("raw" if args.full else "samples")
    folder.mkdir(parents=True, exist_ok=True)
    for key, resource_id in SOURCES.items():
        resource = resources[resource_id]
        if resource["format"].lower() != "csv":
            raise ValueError(f"{key}: la ressource n'est plus un CSV")
        target = folder / f"{key}.csv"
        manifest_path = folder / f"{key}.manifest.json"
        if target.exists() and manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if (
                manifest["resource_id"] == resource_id
                and manifest["sample_rows_requested"] == (None if args.full else args.rows)
                and manifest["sha256"] == digest(target)
            ):
                print(f"{key}: fichier déjà vérifié", flush=True)
                continue
        partial = target.with_suffix(".part")
        with urlopen(resource["url"], timeout=60) as response:
            if args.full:
                with partial.open("wb") as output:
                    for block in iter(lambda: response.read(1024 * 1024), b""):
                        output.write(block)
                row_count = None
                expected_size = resource.get("filesize")
                if expected_size and partial.stat().st_size != expected_size:
                    raise ValueError(f"{key}: taille différente du catalogue")
            else:
                reader = csv.reader(
                    io.TextIOWrapper(response, encoding="utf-8-sig", newline=""), strict=True
                )
                header = next(reader)
                row_count = 0
                with partial.open("w", encoding="utf-8", newline="") as output:
                    writer = csv.writer(output)
                    writer.writerow(header)
                    for row in islice(reader, args.rows):
                        if len(row) != len(header):
                            raise ValueError(f"{key}: ligne CSV de largeur incorrecte")
                        writer.writerow(row)
                        row_count += 1
        partial.replace(target)
        manifest = {
            "dataset": DATASET,
            "resource_id": resource_id,
            "url": resource["url"],
            "title": resource["title"],
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "sample_rows_requested": None if args.full else args.rows,
            "sample_rows_written": row_count,
            "size_bytes": target.stat().st_size,
            "sha256": digest(target),
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        print(
            f"{key}: {row_count if row_count is not None else 'export complet'} lignes, {manifest['size_bytes']} octets",
            flush=True,
        )


def identity(column):
    return column.split(" - ", 1)[0]


def escape(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def audit(args):
    folder = args.directory / ("raw" if args.full else "samples")
    report = [
        "# Audit des exports Grand Débat National",
        "",
        "Source : https://www.data.gouv.fr/datasets/donnees-ouvertes-du-grand-debat-national",
        "",
        "Cet audit ne modifie aucune base. Les valeurs libres et les identifiants personnels ne sont pas reproduits.",
        "",
        "Les échantillons sont les premières lignes, pas un tirage représentatif. Une absence de séparateur dans un échantillon ne prouve pas qu'une question est à choix unique.",
        "",
    ]
    for key, resource_id in SOURCES.items():
        path = folder / f"{key}.csv"
        manifest = json.loads(path.with_suffix(".manifest.json").read_text())
        if manifest["resource_id"] != resource_id or manifest["sha256"] != digest(path):
            raise ValueError(f"{key}: provenance ou empreinte invalide ; relancer fetch")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            header = reader.fieldnames
            if not header or len(set(header)) != len(header):
                raise ValueError(f"{key}: en-tête vide ou dupliqué")
            columns = [h for h in header if " - " in h]
            counts = {h: Counter() for h in columns}
            pipe_counts = Counter()
            n = 0
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError(f"{key}: largeur CSV incorrecte")
                n += 1
                for column in columns:
                    value = row[column].strip()
                    if value:
                        counts[column][value] += 1
                        if "|" in value:
                            pipe_counts[column] += 1
        mapping = yaml.safe_load((ROOT / "ingest/mappings" / f"{key}.yml").read_text())
        by_identity = {identity(h): h for h in columns}
        mapped = Counter(identity(q.get("source_column", "")) for q in mapping["questions"])
        report.extend(
            [
                f"## {key}",
                "",
                f"Ressource `{resource_id}` — {n} lignes analysées — SHA-256 `{manifest['sha256']}`.",
                "",
                f"Export {'complet' if manifest['sample_rows_requested'] is None else 'partiel'} : [{escape(manifest['title'])}]({manifest['url']}).",
                "",
                "| Code mapping | Type actuel | Réponses non vides | Valeurs distinctes | Réponses avec `\\|` | Question source |",
                "| --- | --- | ---: | ---: | ---: | --- |",
            ]
        )
        notes = []
        for q in mapping["questions"]:
            configured = q.get("source_column", "")
            actual = configured if configured in header else by_identity.get(identity(configured))
            if actual in counts:
                values = counts[actual]
                report.append(
                    f"| {q['code']} | {q['type']} | {sum(values.values())} | {len(values)} | {pipe_counts[actual]} | {escape(actual.split(' - ', 1)[1])} |"
                )
                if pipe_counts[actual] and q["type"] != "multi_choice":
                    notes.append(
                        f"À examiner : **{q['code']}** contient des séparateurs de choix mais est classée `{q['type']}`."
                    )
                if configured != actual:
                    notes.append(
                        f"L'en-tête exact du mapping **{q['code']}** diffère du CSV (identifiant source reconnu)."
                    )
            elif configured not in header:
                notes.append(f"**Colonne absente : {q['code']}**.")
        report.append("")
        report.extend("- " + note for note in notes)
        missing = [h for h in columns if not mapped[identity(h)]]
        duplicate = [h for h, number in mapped.items() if h and number > 1]
        if missing:
            report.append(
                "\n**Questions source non couvertes :** "
                + "; ".join(escape(h) for h in missing)
                + ".\n"
            )
        if duplicate:
            report.append(
                "\n**Colonnes affectées à plusieurs questions :** " + "; ".join(duplicate) + ".\n"
            )
        report.append("")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(report) + "\n")
    print(f"Rapport : {args.report}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "audit"])
    parser.add_argument("--directory", type=Path, default=ROOT / "data/gdn")
    parser.add_argument("--rows", type=int, default=1000, help="Nombre de lignes par échantillon")
    parser.add_argument("--full", action="store_true", help="Exports complets, environ 1,6 Go")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/ingestion-audit.md")
    args = parser.parse_args()
    if args.rows <= 0:
        parser.error("--rows doit être positif")
    (fetch if args.command == "fetch" else audit)(args)


if __name__ == "__main__":
    main()
