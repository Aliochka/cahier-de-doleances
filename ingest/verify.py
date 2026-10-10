"""Verify the complete GDN import against the official source profiles."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
import yaml

from ingest.sources import ROOT, SOURCES, digest
from ingest.structured_sources import JSON_SOURCES


def verify(directory, db):
    profile = json.loads((directory / "full-profile.json").read_text())
    if profile["mode"] != "full" or set(profile["sources"]) != set(SOURCES):
        raise ValueError("Les sept sources complètes doivent être profilées")
    report = {"verified_at": datetime.now(timezone.utc).isoformat(), "sources": {}}
    for key, source in profile["sources"].items():
        raw = directory / "raw-json" / f"{key}.json"
        manifest = json.loads(raw.with_suffix(".manifest.json").read_text())
        if manifest["resource_id"] != JSON_SOURCES[key] or source["sha256"] != digest(raw):
            raise ValueError(f"{key}: fichier source modifié")
        mapping_path = ROOT / "ingest/mappings" / f"{key}.yml"
        mapping = yaml.safe_load(mapping_path.read_text())
        run = db.execute(text("SELECT * FROM gdn_import_runs WHERE source_key=:key"), {"key": key}).mappings().one()
        if not run["completed"] or run["file_sha256"] != source["sha256"] or run["mapping_sha256"] != digest(mapping_path):
            raise ValueError(f"{key}: import absent, incomplet ou d'une autre version")
        form = db.execute(text("SELECT id,name FROM forms WHERE source=:source"), {"source": SOURCES[key]}).mappings().one()
        rows = db.execute(text("SELECT count(*) FROM contributions WHERE form_id=:fid"), {"fid": form["id"]}).scalar_one()
        if rows != source["rows"] or run["rows_processed"] != rows:
            raise ValueError(f"{key}: nombre de contributions incohérent")
        questions = db.execute(text("""
            SELECT q.id,q.question_code,q.type,COALESCE(st.answers_count,0) AS counter,
              (SELECT count(*) FROM answers a WHERE a.question_id=q.id) AS answers,
              (SELECT count(*) FROM answer_options ao JOIN options o ON o.id=ao.option_id WHERE o.question_id=q.id) AS links,
              (SELECT count(*) FROM options o WHERE o.question_id=q.id) AS options
            FROM questions q LEFT JOIN question_stats st ON st.question_id=q.id
            WHERE q.form_id=:fid
        """), {"fid": form["id"]}).mappings().all()
        if {q["question_code"] for q in questions} != set(source["questions"]):
            raise ValueError(f"{key}: questions manquantes ou supplémentaires")
        mapping_questions = {q["code"]: q for q in mapping["questions"]}
        for q in questions:
            code = q["question_code"]
            expected = source["questions"][code]
            if q["answers"] != expected["answers"] or q["counter"] != q["answers"]:
                raise ValueError(f"{key}/{code}: réponses ou compteur incorrects")
            if q["links"] != run["stats"]["links"].get(code, 0):
                raise ValueError(f"{key}/{code}: sélection perdue ou dupliquée")
            if q["type"] != expected["type"] or q["options"] != len(mapping_questions[code].get("options", [])):
                raise ValueError(f"{key}/{code}: type ou catalogue d'options incorrect")
            actual_labels = set(db.execute(text("SELECT label FROM options WHERE question_id=:qid"), {"qid": q["id"]}).scalars())
            if actual_labels != set(expected["labels"]):
                raise ValueError(f"{key}/{code}: labels d'options différents de la source")
        report["sources"][key] = {"name": form["name"], "rows": rows, "questions": len(questions),
                                  "answers": sum(q["answers"] for q in questions),
                                  "selection_links": sum(q["links"] for q in questions),
                                  "multi_questions": sum(q["type"] == "multi_choice" for q in questions),
                                  "csv_value_differences": sum(q["csv_value_differences"] for q in source["questions"].values()),
                                  "resource_id": JSON_SOURCES[key], "url": manifest["url"], "sha256": source["sha256"]}
        print(f"{key}: {rows} contributions vérifiées", flush=True)
    violations = db.execute(text("""
        SELECT EXISTS(SELECT 1 FROM answers a JOIN contributions c ON c.id=a.contribution_id
                      JOIN questions q ON q.id=a.question_id WHERE c.source LIKE 'gdn:%'
                      AND (a.position<>1 OR q.form_id<>c.form_id))
        OR EXISTS(SELECT 1 FROM answer_options ao JOIN answers a ON a.id=ao.answer_id
                  JOIN options o ON o.id=ao.option_id WHERE a.question_id<>o.question_id)
    """)).scalar_one()
    if violations:
        raise ValueError("Question, réponse ou option mal rattachée")
    expected_valid = db.execute(text("SELECT count(*) FROM answers WHERE text IS NOT NULL AND char_length(btrim(text))>=60")).scalar_one()
    actual_valid = db.execute(text("SELECT valid_count FROM answer_valid_stats WHERE id=1")).scalar_one()
    if expected_valid != actual_valid:
        raise ValueError("Compteur global de réponses incohérent")
    report["valid_text_answers"] = actual_valid
    report["normalized_nul_characters"] = db.execute(text("""
        SELECT COALESCE(sum((value_json::jsonb->'normalizations'->>'nul_characters')::int),0)
        FROM answers WHERE value_json IS NOT NULL
    """)).scalar_one()
    report["database_size"] = db.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar_one()
    return report


def write_report(report, path):
    lines = ["# Import complet du Grand Débat National", "", f"Vérifié le {report['verified_at']}.", "",
             "Les sept exports JSON officiels ont été comparés aux CSV : mêmes identifiants, même ordre et même nombre de contributions. Les différences de cellules CSV sont comptées ci-dessous ; les valeurs JSON originales sont conservées.", "",
             "| Formulaire | Contributions | Questions | Réponses | Liens vers les choix | Questions multiples | Différences CSV/JSON |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for source in report["sources"].values():
        lines.append("| " + " | ".join(str(source[k]) for k in ("name", "rows", "questions", "answers", "selection_links", "multi_questions", "csv_value_differences")) + " |")
    lines.extend(["", f"Taille PostgreSQL au contrôle : **{report['database_size']}**.", "",
                  f"Caractères nuls remplacés dans le texte affiché/indexé : **{report['normalized_nul_characters']}**. Les originaux restent dans `contributions.raw_json` et les fichiers téléchargés.", "",
                  "Contrôles validés : empreintes des sources, import terminé pour les sept fichiers, couverture exacte des questions, une réponse par contribution/question (position 1 et contrainte unique), liens vers les options sans perte ni doublon, catalogues limités aux labels officiels, compteurs par question et compteur global cohérents.", "",
                  "## Provenance", ""])
    for key, source in report["sources"].items():
        lines.append(f"- [{key}]({source['url']}) — ressource `{source['resource_id']}` — SHA-256 `{source['sha256']}`.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "data/gdn")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/ingestion-resultats.md")
    args = parser.parse_args()
    from app.db import engine
    with engine.connect() as db:
        report = verify(args.directory, db)
    write_report(report, args.report)
    print(f"Tous les contrôles sont passés : {args.report}")


if __name__ == "__main__":
    main()
