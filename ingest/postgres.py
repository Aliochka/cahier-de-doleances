"""Verified, resumable structured GDN JSON ingestion directly into PostgreSQL.

Run from the repository root: python -m ingest.postgres --samples
or python -m ingest.postgres for the complete exports.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import unicodedata
from datetime import datetime, timezone
from itertools import chain, islice
from pathlib import Path

import yaml
from psycopg2.extras import Json

from ingest.sources import ROOT, SOURCES, digest, identity
from ingest.structured_sources import JSON_SOURCES, choice_value, iter_records, question_code

csv.field_size_limit(2**31 - 1)


def label_key(value):
    return unicodedata.normalize("NFC", value).strip().replace("’", "'").casefold()


def compile_mapping(mapping, header):
    if not header or len(set(header)) != len(header):
        raise ValueError("Liste de colonnes vide ou dupliquée")
    for required in ("id", "authorId", "publishedAt"):
        if required not in header:
            raise ValueError(f"Colonne obligatoire absente : {required}")
    columns = {}
    for column in header:
        prefix = identity(column)
        if prefix in columns:
            raise ValueError(f"Identifiant de colonne ambigu : {prefix}")
        columns[prefix] = column
    compiled, seen_codes, seen_columns = [], set(), set()
    for question in mapping["questions"]:
        q = dict(question)
        if q["code"] in seen_codes:
            raise ValueError(f"Code de question dupliqué : {q['code']}")
        seen_codes.add(q["code"])
        column = columns.get(identity(q["source_column"]))
        if not column or column in seen_columns:
            raise ValueError(f"Colonne absente ou réutilisée : {q['code']}")
        seen_columns.add(column)
        q["column"] = column
        # The official prompt is authoritative; mappings keep sections and types.
        q["prompt"] = column.split(" - ", 1)[1]
        if q["type"] not in {"text", "single_choice", "multi_choice"}:
            raise ValueError(f"Type non géré : {q['type']}")
        q["by_label"] = {}
        option_codes = set()
        for option in q.get("options", []):
            key = label_key(option["label"])
            if key in q["by_label"] or option["code"] in option_codes:
                raise ValueError(f"Option ambiguë : {q['code']}")
            q["by_label"][key] = option
            option_codes.add(option["code"])
        if q["type"] in {"single_choice", "multi_choice"} and not q["by_label"]:
            raise ValueError(f"Choix sans options prédéfinies : {q['code']}")
        if q["type"] == "multi_choice" and q.get("delimiter") != "|":
            raise ValueError(f"Séparateur multi_choice invalide : {q['code']}")
        compiled.append(q)
    uncovered = {h for h in header if " - " in h} - seen_columns
    if uncovered:
        raise ValueError(f"Questions non couvertes : {sorted(uncovered)}")
    return compiled


def parse_text_answer(raw):
    """Keep one nonempty text response; never split it on choice separators."""
    if not raw.strip():
        return None
    return {"body": raw, "value_json": None, "selected_codes": []}


def timestamp(value):
    if not value.strip():
        return ""
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.isoformat(sep=" ")


def stage_record(key, row, questions):
    source_id = row["id"].strip()
    if not source_id:
        raise ValueError("Identifiant de contribution vide")
    raw_json = json.dumps(row, ensure_ascii=False, sort_keys=True)
    answers = []
    responses = {}
    for response in row["responses"]:
        code = question_code(response)
        if code in responses:
            raise ValueError("Question répétée dans une contribution")
        responses[code] = response
    if set(responses) != {q["code"] for q in questions}:
        raise ValueError("Couverture des questions incorrecte dans une contribution")
    for question in questions:
        response = responses[question["code"]]
        choice = choice_value(response) if question["type"] != "text" else None
        if choice is not None:
            selected = []
            for label in choice["labels"]:
                option = question["by_label"].get(label_key(label))
                if option is None:
                    raise ValueError(f"Label officiel absent du mapping : {question['code']}")
                if option["code"] not in selected:
                    selected.append(option["code"])
            if question["type"] == "single_choice" and len(selected) > 1:
                raise ValueError(
                    f"Plusieurs choix sur une question classée unique : {question['code']}"
                )
            other = choice["other"]
            parts = choice["labels"] + ([other] if other and other.strip() else [])
            answer = (
                {
                    "body": "\n".join(parts),
                    "selected_codes": selected,
                    "value_json": {
                        "source_value": response["value"],
                        "labels": choice["labels"],
                        "selected_codes": selected,
                        "other_text": [other] if other and other.strip() else [],
                    },
                }
                if parts
                else None
            )
        elif question["type"] != "text" and response.get("value"):
            raise ValueError(f"Valeur de choix non structurée : {question['code']}")
        else:
            original = response.get("value") or ""
            formatted = response.get("formattedValue")
            presentation = (
                formatted if isinstance(formatted, str) and formatted.strip() else original
            )
            answer = parse_text_answer(presentation)
        if answer:
            nul_count = answer["body"].count("\x00")
            if nul_count:
                answer["body"] = answer["body"].replace("\x00", "\ufffd")
                # PostgreSQL cannot store U+0000 in text or JSONB. The exact
                # source remains escaped in contributions.raw_json (TEXT).
                answer["value_json"] = answer["value_json"] or {}
                answer["value_json"]["normalizations"] = {"nul_characters": nul_count}
                other = answer["value_json"].get("other_text")
                if other:
                    answer["value_json"]["other_text"] = [
                        v.replace("\x00", "\ufffd") for v in other
                    ]
            answer["question_id"] = question["id"]
            answers.append(answer)
    return (
        f"{key}:{source_id}",
        (row.get("authorId") or "").strip(),
        row.get("authorZipCode") or "",
        timestamp(row.get("publishedAt") or ""),
        (row.get("title") or "").replace("\x00", "\ufffd"),
        hashlib.sha256((key + "\0" + raw_json).encode()).hexdigest(),
        raw_json,
        json.dumps(answers, ensure_ascii=False),
    )


def prepare_schema(cursor):
    cursor.execute("""
        CREATE TEMP TABLE gdn_stage (
            source_id text PRIMARY KEY, author_source_id text, zipcode text,
            submitted_at text, title text, raw_hash text, raw_json text, answers jsonb
        ) ON COMMIT PRESERVE ROWS;
        CREATE TEMP TABLE gdn_answers (
            source_id text, question_id bigint, body text, value_json jsonb, selected_codes jsonb,
            PRIMARY KEY (source_id, question_id)
        ) ON COMMIT PRESERVE ROWS;
    """)


def provision(cursor, key, mapping, questions):
    cursor.execute("SELECT id FROM forms WHERE source=%s", (SOURCES[key],))
    forms = cursor.fetchall()
    if len(forms) > 1:
        raise ValueError(f"Formulaire source dupliqué : {key}")
    form = mapping["form"]
    if forms:
        form_id = forms[0][0]
        cursor.execute(
            "UPDATE forms SET name=%s,version=%s WHERE id=%s",
            (form["name"], form["version"], form_id),
        )
    else:
        cursor.execute(
            "INSERT INTO forms(name,version,source) VALUES (%s,%s,%s) RETURNING id",
            (form["name"], form["version"], SOURCES[key]),
        )
        form_id = cursor.fetchone()[0]
    for q in questions:
        cursor.execute(
            """
            INSERT INTO questions(form_id,question_code,prompt,section,position,type,options_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(form_id,question_code) DO UPDATE SET prompt=EXCLUDED.prompt,
              section=EXCLUDED.section, position=EXCLUDED.position, type=EXCLUDED.type,
              options_json=EXCLUDED.options_json
            RETURNING id
        """,
            (
                form_id,
                q["code"],
                q["prompt"],
                q.get("section"),
                q["position"],
                q["type"],
                json.dumps(
                    {
                        "source_column": q["column"],
                        "delimiter": q.get("delimiter"),
                        "allow_other_text": q.get("allow_other_text", False),
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        q["id"] = cursor.fetchone()[0]
        for option in q.get("options", []):
            cursor.execute(
                """
                INSERT INTO options(question_id,code,label,position) VALUES (%s,%s,%s,%s)
                ON CONFLICT(question_id,code) DO UPDATE SET label=EXCLUDED.label,position=EXCLUDED.position
            """,
                (q["id"], option["code"], option["label"], option["position"]),
            )
    return form_id


def process_batch(cursor, key, form_id, records):
    cursor.execute("TRUNCATE gdn_stage, gdn_answers")
    buffer = io.StringIO()
    csv.writer(buffer).writerows(records)
    buffer.seek(0)
    cursor.copy_expert("COPY gdn_stage FROM STDIN WITH (FORMAT CSV)", buffer)
    cursor.execute("ANALYZE gdn_stage")
    cursor.execute("""
        INSERT INTO gdn_answers
        SELECT s.source_id, a.question_id, a.body, a.value_json, a.selected_codes
        FROM gdn_stage s CROSS JOIN LATERAL jsonb_to_recordset(s.answers)
          AS a(question_id bigint, body text, value_json jsonb, selected_codes jsonb);

        INSERT INTO authors(source_author_id,zipcode,is_anonymous)
        SELECT DISTINCT ON (author_source_id) author_source_id, NULLIF(zipcode,''), true
        FROM gdn_stage WHERE author_source_id IS NOT NULL AND author_source_id<>''
        ORDER BY author_source_id, source_id
        ON CONFLICT(source_author_id) DO NOTHING;
    """)
    cursor.execute("ANALYZE gdn_answers")
    cursor.execute(
        """
        INSERT INTO contributions(source_contribution_id,author_id,form_id,source,submitted_at,
                                  title,import_batch_id,raw_hash,raw_json)
        SELECT s.source_id, au.id, %s, %s, NULLIF(s.submitted_at,'')::timestamp,
               NULLIF(s.title,''), %s, s.raw_hash, s.raw_json
        FROM gdn_stage s LEFT JOIN authors au ON au.source_author_id=s.author_source_id
        ON CONFLICT(source_contribution_id) DO UPDATE SET
          author_id=EXCLUDED.author_id, submitted_at=EXCLUDED.submitted_at, title=EXCLUDED.title,
          raw_hash=EXCLUDED.raw_hash, raw_json=EXCLUDED.raw_json
        WHERE contributions.raw_hash IS DISTINCT FROM EXCLUDED.raw_hash;

        INSERT INTO answers(contribution_id,question_id,position,text,value_json)
        SELECT c.id, s.question_id, 1, s.body, s.value_json::text
        FROM gdn_answers s JOIN contributions c ON c.source_contribution_id=s.source_id
        ON CONFLICT(contribution_id,question_id,position) DO UPDATE SET
          text=EXCLUDED.text, value_json=EXCLUDED.value_json
        WHERE answers.text IS DISTINCT FROM EXCLUDED.text
           OR answers.value_json IS DISTINCT FROM EXCLUDED.value_json;

        DELETE FROM answer_options ao USING answers a, contributions c, gdn_answers s
        WHERE ao.answer_id=a.id AND a.contribution_id=c.id
          AND c.source_contribution_id=s.source_id AND a.question_id=s.question_id;

        INSERT INTO answer_options(answer_id,option_id)
        SELECT a.id,o.id FROM gdn_answers s
        JOIN contributions c ON c.source_contribution_id=s.source_id
        JOIN answers a ON a.contribution_id=c.id AND a.question_id=s.question_id AND a.position=1
        CROSS JOIN LATERAL jsonb_array_elements_text(s.selected_codes) code
        JOIN options o ON o.question_id=s.question_id AND o.code=code.value
        ON CONFLICT DO NOTHING;
    """,
        (form_id, "gdn:" + key, "gdn:" + key),
    )
    # Validate each batch while its source values are still available.
    cursor.execute("""
        SELECT count(*) FROM gdn_answers s
        JOIN contributions c ON c.source_contribution_id=s.source_id
        JOIN answers a ON a.contribution_id=c.id AND a.question_id=s.question_id
        WHERE a.position<>1 OR a.text IS DISTINCT FROM s.body
          OR a.value_json::jsonb IS DISTINCT FROM s.value_json
          OR (SELECT count(*) FROM answer_options ao WHERE ao.answer_id=a.id)
             <>jsonb_array_length(s.selected_codes)
    """)
    if cursor.fetchone()[0]:
        raise ValueError("Le lot importé ne correspond pas aux réponses source")


def verify_source(cursor, key, form_id, questions, stats):
    cursor.execute("SELECT count(*) FROM contributions WHERE form_id=%s", (form_id,))
    if cursor.fetchone()[0] != stats["rows"]:
        raise ValueError(f"{key}: nombre de contributions différent de la source")
    cursor.execute(
        """
        SELECT q.id, count(a.id), COALESCE(st.answers_count,0)
        FROM questions q LEFT JOIN answers a ON a.question_id=q.id
        LEFT JOIN question_stats st ON st.question_id=q.id
        WHERE q.form_id=%s GROUP BY q.id,st.answers_count
    """,
        (form_id,),
    )
    actual = {qid: (number, count) for qid, number, count in cursor.fetchall()}
    for q in questions:
        expected = stats["answers"].get(q["code"], 0)
        if actual.get(q["id"]) != (expected, expected):
            raise ValueError(f"{key}/{q['code']}: réponses ou compteur incohérents")
    cursor.execute(
        """
        SELECT count(*) FROM answers a JOIN contributions c ON c.id=a.contribution_id
        JOIN answer_options ao ON ao.answer_id=a.id JOIN options o ON o.id=ao.option_id
        WHERE c.form_id=%s AND o.question_id<>a.question_id
    """,
        (form_id,),
    )
    if cursor.fetchone()[0]:
        raise ValueError("Une option est rattachée à une autre question")


def import_source(connection, key, args):
    folder = args.directory / ("samples-json" if args.samples else "raw-json")
    path = folder / f"{key}.json"
    manifest = json.loads(path.with_suffix(".manifest.json").read_text())
    file_hash = digest(path)
    if manifest["resource_id"] != JSON_SOURCES[key] or manifest["sha256"] != file_hash:
        raise ValueError(f"{key}: fichier ou provenance invalides")
    if (manifest["sample_rows_requested"] is not None) != args.samples:
        raise ValueError(f"{key}: échantillon/export complet incorrect")
    mapping_path = ROOT / "ingest/mappings" / f"{key}.yml"
    mapping_hash = digest(mapping_path)
    mapping = yaml.safe_load(mapping_path.read_text())
    expected_profile = None
    if not args.samples:
        profile_path = args.directory / "full-profile.json"
        profile = json.loads(profile_path.read_text())
        expected_profile = profile["sources"].get(key)
        if not expected_profile or expected_profile["sha256"] != file_hash:
            raise ValueError(f"{key}: profiler et vérifier les exports complets avant import")
    with path.open(encoding="utf-8-sig") as stream, connection.cursor() as cursor:
        reader = iter_records(stream, allow_missing_array_end=not args.samples)
        first = next(reader)
        header = ["id", "authorId", "publishedAt"] + [
            "Q" + r["questionId"] + " - " + r["questionTitle"] for r in first["responses"]
        ]
        questions = compile_mapping(mapping, header)
        reader = chain([first], reader)
        if expected_profile:
            for q in questions:
                expected = expected_profile["questions"][q["code"]]
                if q["type"] != expected["type"] or {
                    o["label"] for o in q.get("options", [])
                } != set(expected["labels"]):
                    raise ValueError(f"{key}/{q['code']}: mapping différent du profil complet")
        cursor.execute(
            "SELECT file_sha256,mapping_sha256,rows_processed,completed,stats FROM gdn_import_runs WHERE source_key=%s",
            (key,),
        )
        previous = cursor.fetchone()
        if args.samples and previous and previous[2] > manifest["sample_rows_written"]:
            raise ValueError(
                f"{key}: refus d'un pilote réduit après l'import complet ; utiliser une base séparée"
            )
        same = previous and previous[:2] == (file_hash, mapping_hash)
        if same and previous[3] and not args.restart:
            print(f"{key}: déjà importé et vérifié ({previous[2]} lignes)", flush=True)
            return
        if previous and not same and not previous[3] and not args.restart:
            raise ValueError(
                f"{key}: import incomplet d'un autre fichier/mapping ; vérifier puis utiliser --restart"
            )
        stats = (
            previous[4]
            if same and not args.restart
            else {"rows": 0, "answers": {}, "links": {}, "other": {}}
        )
        stats.setdefault("nul_replacements", 0)
        resume = stats["rows"]
        form_id = provision(cursor, key, mapping, questions)
        codes_by_id = {q["id"]: q["code"] for q in questions}
        cursor.execute(
            """
            INSERT INTO gdn_import_runs(source_key,file_sha256,mapping_sha256,rows_processed,completed,stats)
            VALUES (%s,%s,%s,%s,false,%s)
            ON CONFLICT(source_key) DO UPDATE SET file_sha256=EXCLUDED.file_sha256,
              mapping_sha256=EXCLUDED.mapping_sha256,rows_processed=EXCLUDED.rows_processed,
              completed=false,stats=EXCLUDED.stats,updated_at=now()
        """,
            (key, file_hash, mapping_hash, resume, Json(stats)),
        )
        connection.commit()
        print(f"{key}: import à partir de la ligne {resume + 1}", flush=True)
        # Keep planner estimates current as the database grows from a pilot
        # to millions of rows; stale estimates can turn batch joins into scans.
        for table in ("authors", "contributions", "answers", "answer_options"):
            cursor.execute(f"ANALYZE {table}")
        connection.commit()
        for _ in islice(reader, resume):
            pass
        while True:
            rows = list(islice(reader, args.batch_size))
            if not rows:
                break
            records = []
            for offset, row in enumerate(rows, resume + 1):
                try:
                    record = stage_record(key, row, questions)
                except (ValueError, KeyError) as exc:
                    raise ValueError(f"{key}, enregistrement {offset}: {exc}") from exc
                records.append(record)
                for answer in json.loads(record[-1]):
                    code = codes_by_id[answer["question_id"]]
                    stats["answers"][code] = stats["answers"].get(code, 0) + 1
                    stats["links"][code] = stats["links"].get(code, 0) + len(
                        answer["selected_codes"]
                    )
                    other = (answer["value_json"] or {}).get("other_text", [])
                    stats["other"][code] = stats["other"].get(code, 0) + bool(other)
                    stats["nul_replacements"] += (
                        (answer["value_json"] or {})
                        .get("normalizations", {})
                        .get("nul_characters", 0)
                    )
            process_batch(cursor, key, form_id, records)
            stats["rows"] += len(rows)
            resume = stats["rows"]
            cursor.execute(
                "UPDATE gdn_import_runs SET rows_processed=%s,stats=%s,updated_at=now() WHERE source_key=%s",
                (resume, Json(stats), key),
            )
            connection.commit()
            print(
                f"  {key}: {resume} contributions, {sum(stats['answers'].values())} réponses",
                flush=True,
            )
            if resume // 50000 != (resume - len(rows)) // 50000:
                for table in ("authors", "contributions", "answers", "answer_options"):
                    cursor.execute(f"ANALYZE {table}")
                connection.commit()
        if expected_profile:
            if stats["rows"] != expected_profile["rows"]:
                raise ValueError(f"{key}: nombre de contributions différent du profil complet")
            for q in questions:
                expected = expected_profile["questions"][q["code"]]
                if stats["answers"].get(q["code"], 0) != expected["answers"]:
                    raise ValueError(
                        f"{key}/{q['code']}: nombre de réponses différent du profil complet"
                    )
        verify_source(cursor, key, form_id, questions, stats)
        cursor.execute(
            "UPDATE gdn_import_runs SET completed=true,updated_at=now() WHERE source_key=%s", (key,)
        )
        connection.commit()
        print(f"{key}: import complet et contrôles OK", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", action="store_true")
    parser.add_argument("--directory", type=Path, default=ROOT / "data/gdn")
    parser.add_argument("--source", choices=list(SOURCES), action="append")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument(
        "--restart", action="store_true", help="Relire depuis le début, par upserts sans effacement"
    )
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size doit être positif")
    from app.db import engine

    if engine.dialect.name != "postgresql":
        parser.error("PostgreSQL est obligatoire")
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(hashtext('gdn_import'))")
            if not cursor.fetchone()[0]:
                raise ValueError("Un autre import Grand Débat est en cours")
            prepare_schema(cursor)
        connection.commit()
        for key in args.source or SOURCES:
            import_source(connection, key, args)
        with connection.cursor() as cursor:
            for table in (
                "authors",
                "contributions",
                "answers",
                "answer_options",
                "questions",
                "options",
            ):
                cursor.execute(f"ANALYZE {table}")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(hashtext('gdn_import'))")
        connection.commit()
        connection.close()


if __name__ == "__main__":
    main()
