"""Fetch the official structured JSON equivalents, preserving labels and other text."""
from __future__ import annotations

import argparse
import base64
import csv
import json
import zipfile
from datetime import datetime, timezone
from itertools import islice, zip_longest
from pathlib import Path
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor

from ingest.sources import DATASET, ROOT, digest
import yaml
from slugify import slugify

JSON_SOURCES = {
    "organisation_etat_services": "7164c640-0a24-479c-a2cc-4aaad72d4b53",
    "democratie_citoyennete": "2e6a15ba-98e1-4dca-a406-47d64d64809e",
    "fiscalite_depenses": "f5b05574-a70c-45c5-92a8-d3d85a899f2f",
    "transition_ecologique": "cfe1c622-88db-483b-a36b-9423504a7020",
    "questions_rapides_organisation": "16c0eccb-b8e7-4be4-a720-742aac8dabbf",
    "questions_rapides_democratie": "02a8e332-cfe1-4bd9-b8f7-1e60d16d9de0",
    "questions_rapides_transition": "096e133e-e727-49be-a3a2-bc9e9322f8ce",
}


def question_code(response):
    decoded = base64.b64decode(response["questionId"], validate=True).decode()
    prefix, number = decoded.split(":", 1)
    if prefix != "Question" or not number.isdigit():
        raise ValueError("Identifiant de question invalide")
    return "Q" + number


def choice_value(response):
    value = response.get("value")
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict) and "labels" in parsed and "other" in parsed:
            if not isinstance(parsed["labels"], list) or any(not isinstance(label, str) for label in parsed["labels"]):
                raise ValueError("Liste de choix invalide")
            if parsed["other"] is not None and not isinstance(parsed["other"], str):
                raise ValueError("Texte autre invalide")
            return parsed
    return None


def iter_records(stream, chunk_size=131072, allow_missing_array_end=False):
    """Incrementally decode a JSON array, including records spanning read chunks."""
    decoder = json.JSONDecoder()
    buffer, position, eof = "", 0, False

    def fill():
        nonlocal buffer, position, eof
        chunk = stream.read(chunk_size)
        buffer = buffer[position:] + chunk
        position = 0
        eof = not chunk

    def token():
        nonlocal position
        while True:
            while position < len(buffer) and buffer[position].isspace():
                position += 1
            if position < len(buffer):
                return buffer[position]
            if eof:
                raise ValueError("Export JSON incomplet")
            fill()

    if token() != "[":
        raise ValueError("Un tableau JSON est attendu")
    position += 1
    first = True
    while True:
        try:
            char = token()
        except ValueError:
            # Official exports omit the array's final bracket. Only accept an
            # EOF after a fully decoded record, never a truncated object/comma.
            if allow_missing_array_end and not first:
                return
            raise
        if char == "]":
            position += 1
            break
        if not first:
            if char != ",":
                raise ValueError("Séparateur JSON absent")
            position += 1
            if token() == "]":
                raise ValueError("Virgule finale JSON interdite")
        token()
        while True:
            try:
                record, end = decoder.raw_decode(buffer, position)
                position = end
                break
            except json.JSONDecodeError as exc:
                if eof:
                    raise ValueError("Enregistrement JSON invalide ou incomplet") from exc
                fill()
        if not isinstance(record, dict):
            raise ValueError("Une contribution JSON doit être un objet")
        yield record
        first = False
    if buffer[position:].strip() or stream.read().strip():
        raise ValueError("Contenu inattendu après le tableau JSON")


def download(args):
    with urlopen(DATASET, timeout=60) as response:
        resources = {r["id"]: r for r in json.load(response)["resources"]}
    folder = args.directory / "raw-json"
    folder.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        selected = [(key, JSON_SOURCES[key]) for key in args.source or JSON_SOURCES]
        list(pool.map(lambda item: download_resource(folder, resources[item[1]], *item), selected))


def download_resource(folder, resource, key, resource_id):
    target = folder / f"{key}.json"
    manifest_path = folder / f"{key}.manifest.json"
    if target.exists() and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["resource_id"] == resource_id and manifest["sha256"] == digest(target):
            print(f"{key}: JSON déjà vérifié", flush=True)
            return
    partial = target.with_suffix(".part")
    zipped = resource["url"].endswith(".zip")
    if not zipped and resource.get("format", "").lower() != "json":
        raise ValueError(f"{key}: format source JSON inattendu")
    download_path = partial.with_suffix(".zip.part") if zipped else partial
    print(f"{key}: téléchargement JSON ({resource.get('filesize')} octets source)", flush=True)
    offset = download_path.stat().st_size if download_path.exists() else 0
    http_state_path = download_path.with_suffix(".http.json")
    state = json.loads(http_state_path.read_text()) if http_state_path.exists() else {}
    validator = state.get("etag") or state.get("last_modified")
    if (state.get("url") != resource["url"] or not validator
            or (resource.get("filesize") and offset >= resource["filesize"])):
        offset = 0
    headers = {"Range": f"bytes={offset}-", "If-Range": validator} if offset else {}
    request = Request(resource["url"], headers=headers)
    with urlopen(request, timeout=60) as response:
        resumed = response.status == 206 and offset > 0
        if resumed and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
            raise ValueError("Reprise HTTP incohérente")
        http_state_path.write_text(json.dumps({"url": resource["url"], "etag": response.headers.get("ETag"),
                                              "last_modified": response.headers.get("Last-Modified")}))
        with download_path.open("ab" if resumed else "wb") as output:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                output.write(block)
    size = download_path.stat().st_size
    if resource.get("filesize") and size != resource["filesize"]:
        raise ValueError(f"{key}: taille source incorrecte")
    if zipped:
        with zipfile.ZipFile(download_path) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith(".json") and not n.startswith("__MACOSX/")]
            if len(names) != 1:
                raise ValueError("L'archive doit contenir un seul export JSON")
            with archive.open(names[0]) as source, partial.open("wb") as output:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(block)
    partial.replace(target)
    manifest_path.write_text(json.dumps({
        "dataset": DATASET, "resource_id": resource_id, "url": resource["url"],
        "title": resource["title"], "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_size_bytes": size, "size_bytes": target.stat().st_size,
        "sha256": digest(target), "sample_rows_requested": None,
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"{key}: JSON complet vérifié ({target.stat().st_size} octets)", flush=True)

def samples(args):
    folder = args.directory / "samples-json"
    folder.mkdir(parents=True, exist_ok=True)
    for key in args.source or JSON_SOURCES:
        resource_id = JSON_SOURCES[key]
        source = args.directory / "raw-json" / f"{key}.json"
        manifest = json.loads(source.with_suffix(".manifest.json").read_text())
        if manifest["resource_id"] != resource_id or manifest["sha256"] != digest(source):
            raise ValueError(f"{key}: fichier source invalide")
        with source.open(encoding="utf-8-sig") as stream:
            records = list(islice(iter_records(stream, allow_missing_array_end=True), args.rows))
        target = folder / source.name
        target.write_text(json.dumps(records, ensure_ascii=False) + "\n")
        manifest.update(sha256=digest(target), size_bytes=target.stat().st_size,
                        sample_rows_requested=args.rows, sample_rows_written=len(records))
        target.with_suffix(".manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        print(f"{key}: {len(records)} contributions JSON échantillonnées", flush=True)


def profile(args):
    """Derive option catalogs only from explicit official labels, never free text."""
    folder = args.directory / ("samples-json" if args.samples else "raw-json")
    output = args.directory / ("sample-profile.json" if args.samples else "full-profile.json")
    report = json.loads(output.read_text()) if output.exists() else {"mode": "samples" if args.samples else "full", "sources": {}}
    for key in args.source or JSON_SOURCES:
        resource_id = JSON_SOURCES[key]
        path = folder / f"{key}.json"
        manifest = json.loads(path.with_suffix(".manifest.json").read_text())
        if manifest["resource_id"] != resource_id or manifest["sha256"] != digest(path):
            raise ValueError(f"{key}: empreinte source invalide")
        found, total = {}, 0
        csv_path = args.directory / ("samples" if args.samples else "raw") / f"{key}.csv"
        csv_manifest = json.loads(csv_path.with_suffix(".manifest.json").read_text())
        if csv_manifest["sha256"] != digest(csv_path):
            raise ValueError(f"{key}: empreinte CSV invalide")
        with path.open(encoding="utf-8-sig") as stream, csv_path.open(encoding="utf-8-sig", newline="") as csv_stream:
            csv_reader = csv.DictReader(csv_stream, strict=True)
            csv_columns = {h.split(" - ", 1)[0]: h for h in csv_reader.fieldnames}
            for record, csv_row in zip_longest(iter_records(stream, allow_missing_array_end=not args.samples), csv_reader):
                if record is None or csv_row is None or None in csv_row:
                    raise ValueError(f"{key}: longueur ou largeur CSV/JSON différente")
                if str(record["id"]) != csv_row["id"]:
                    raise ValueError(f"{key}: ordre/identifiant CSV et JSON différent à la ligne {total + 1}")
                total += 1
                seen = set()
                for response in record["responses"]:
                    code = question_code(response)
                    if code in seen:
                        raise ValueError(f"{key}: question dupliquée dans une contribution")
                    seen.add(code)
                    entry = found.setdefault(code, {"title": response["questionTitle"], "question_id": response["questionId"],
                                                   "labels": set(), "choice_records": 0, "text_records": 0,
                                                   "max_selections": 0, "other_records": 0, "answers": 0,
                                                   "csv_value_differences": 0})
                    if entry["title"] != response["questionTitle"]:
                        raise ValueError(f"{key}/{code}: intitulé variable")
                    choice = choice_value(response)
                    formatted = "|".join(choice["labels"] + ([choice["other"]] if choice["other"] else [])) if choice is not None else response.get("value")
                    column = csv_columns.get("Q" + response["questionId"])
                    if column is None:
                        raise ValueError(f"{key}/{code}: question absente du CSV")
                    # Some CSV cells are empty despite a populated JSON value.
                    # Keep the structured original; record the discrepancy.
                    entry["csv_value_differences"] += csv_row[column] != (formatted or "")
                    if choice is not None:
                        entry["choice_records"] += 1
                        entry["labels"].update(choice["labels"])
                        entry["max_selections"] = max(entry["max_selections"], len(set(choice["labels"])))
                        entry["other_records"] += bool((choice["other"] or "").strip())
                        entry["answers"] += bool(choice["labels"] or (choice["other"] or "").strip())
                        if len(entry["labels"]) > 100:
                            raise ValueError(f"{key}/{code}: plus de 100 labels officiels, vérifier la source")
                    elif response.get("value") is not None and str(response["value"]).strip():
                        entry["text_records"] += 1
                        entry["answers"] += 1
        mapping_path = ROOT / "ingest/mappings" / f"{key}.yml"
        mapping = yaml.safe_load(mapping_path.read_text())
        if {q["code"] for q in mapping["questions"]} != set(found):
            raise ValueError(f"{key}: couverture des questions incorrecte")
        for q in mapping["questions"]:
            entry = found[q["code"]]
            if entry["choice_records"] and entry["text_records"]:
                raise ValueError(f"{key}/{q['code']}: formats texte et choix mélangés")
            q["prompt"] = entry["title"]
            q["source_column"] = "Q" + entry["question_id"] + " - " + entry["title"]
            if entry["choice_records"]:
                q["type"] = "multi_choice" if entry["max_selections"] > 1 or q["type"] == "multi_choice" else "single_choice"
                previous = {o["label"]: o["code"] for o in q.get("options", [])}
                q["options"] = [{"code": previous.get(label, slugify(label)), "label": label, "position": i}
                                for i, label in enumerate(sorted(entry["labels"]), 1)]
                q["allow_other_text"] = True
                if q["type"] == "multi_choice":
                    q["delimiter"] = "|"
            else:
                q["type"] = "text"
                for obsolete in ("options", "delimiter", "allow_other_text"):
                    q.pop(obsolete, None)
            entry["type"] = q["type"]
            entry["labels"] = sorted(entry["labels"])
        mapping_path.write_text(yaml.safe_dump(mapping, allow_unicode=True, sort_keys=False, width=100))
        report["sources"][key] = {"rows": total, "resource_id": resource_id, "sha256": manifest["sha256"], "questions": found}
        print(f"{key}: {total} contributions, {len(found)} questions profilées", flush=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "samples", "profile"])
    parser.add_argument("--directory", type=Path, default=ROOT / "data/gdn")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--samples", action="store_true", help="Profiler les échantillons JSON")
    parser.add_argument("--source", choices=list(JSON_SOURCES), action="append")
    args = parser.parse_args()
    if args.workers <= 0:
        parser.error("--workers doit être positif")
    if args.rows <= 0:
        parser.error("--rows doit être positif")
    {"fetch": download, "samples": samples, "profile": profile}[args.command](args)


if __name__ == "__main__":
    main()
