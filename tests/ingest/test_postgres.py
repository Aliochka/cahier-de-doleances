import base64
import io
import json
import os
import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import create_engine

from app.choice_stats import choice_statistics
from ingest.postgres import compile_mapping, prepare_schema, process_batch, provision, stage_record
from ingest.structured_sources import iter_records


def fixture():
    question_id = base64.b64encode(b"Question:1").decode()
    column = "Q" + question_id + " - Quels déplacements ?"
    mapping = {
        "form": {"name": "Test transactionnel", "version": "test"},
        "questions": [
            {
                "code": "Q1",
                "prompt": "Quels déplacements ?",
                "type": "multi_choice",
                "position": 1,
                "source_column": column,
                "delimiter": "|",
                "allow_other_text": True,
                "options": [
                    {"code": "velo", "label": "Vélo", "position": 1},
                    {"code": "bus", "label": "Bus", "position": 2},
                ],
            }
        ],
    }
    row = {
        "id": "fixture",
        "authorId": "test-author-" + uuid.uuid4().hex,
        "authorZipCode": "00100",
        "publishedAt": "2019-01-01 12:00:00",
        "responses": [
            {
                "questionId": question_id,
                "questionTitle": "Quels déplacements ?",
                "value": json.dumps(
                    {"labels": ["Vélo", "Bus", "Vélo"], "other": "Taxi|Train\nUne précision"},
                    ensure_ascii=False,
                ),
            }
        ],
    }
    questions = compile_mapping(mapping, ["id", "authorId", "publishedAt", column])
    questions[0]["id"] = 1
    return mapping, row, questions


class StructuredSourceTests(unittest.TestCase):
    def test_json_records_cross_chunk_boundaries(self):
        records = [{"value": 'é\n|"}' * 200}, {"value": "second"}]
        self.assertEqual(
            list(iter_records(io.StringIO(json.dumps(records)), chunk_size=7)), records
        )

    def test_truncation_and_trailing_junk_are_rejected(self):
        for payload in ['[{"a":1}', '[{"a":1},]', '[{"a":1}] unexpected', '{"a":1}']:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                list(iter_records(io.StringIO(payload), chunk_size=3))

    def test_known_official_missing_array_end_does_not_allow_truncated_records(self):
        self.assertEqual(
            list(iter_records(io.StringIO('[{"a":1}'), allow_missing_array_end=True)), [{"a": 1}]
        )
        for payload in ['[{"a":', '[{"a":1},', '[{"a":1},]']:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                list(iter_records(io.StringIO(payload), allow_missing_array_end=True))

    def test_multi_choice_preserves_other_text_without_splitting_it(self):
        _, row, questions = fixture()
        record = stage_record("fixture", row, questions)
        answers = json.loads(record[-1])
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]["selected_codes"], ["velo", "bus"])
        self.assertEqual(answers[0]["value_json"]["other_text"], ["Taxi|Train\nUne précision"])
        self.assertEqual(json.loads(record[-2]), row)

    def test_incorrect_choice_type_and_missing_question_are_rejected(self):
        _, row, questions = fixture()
        questions[0]["type"] = "single_choice"
        with self.assertRaisesRegex(ValueError, "Plusieurs choix"):
            stage_record("fixture", row, questions)

    def test_nul_is_normalized_for_display_but_kept_in_raw_source(self):
        _, row, questions = fixture()
        questions[0]["type"] = "text"
        row["responses"][0]["value"] = "Avant\x00après"
        record = stage_record("fixture", row, questions)
        answer = json.loads(record[-1])[0]
        self.assertEqual(answer["body"], "Avant\ufffdaprès")
        self.assertEqual(answer["value_json"]["normalizations"]["nul_characters"], 1)
        self.assertEqual(json.loads(record[-2]), row)
        row["responses"] = []
        with self.assertRaisesRegex(ValueError, "Couverture"):
            stage_record("fixture", row, questions)


@unittest.skipUnless(
    os.getenv("GDN_IMPORT_TEST_DATABASE_URL"),
    "Définir GDN_IMPORT_TEST_DATABASE_URL pour PostgreSQL",
)
class PostgresImportTests(unittest.TestCase):
    def test_reimport_keeps_one_answer_and_replaces_choices_atomically(self):
        engine = create_engine(os.environ["GDN_IMPORT_TEST_DATABASE_URL"])
        db = engine.connect()
        connection = db.connection.driver_connection
        key = "test_" + uuid.uuid4().hex
        try:
            with connection.cursor() as cursor, patch.dict("ingest.postgres.SOURCES", {key: key}):
                prepare_schema(cursor)
                mapping, row, questions = fixture()
                form_id = provision(cursor, key, mapping, questions)
                record = stage_record(key, row, questions)
                process_batch(cursor, key, form_id, [record])
                process_batch(cursor, key, form_id, [record])
                cursor.execute(
                    "SELECT a.id FROM answers a JOIN contributions c ON c.id=a.contribution_id WHERE c.form_id=%s",
                    (form_id,),
                )
                ids = cursor.fetchall()
                self.assertEqual(len(ids), 1)
                answer_id = ids[0][0]
                cursor.execute(
                    "SELECT count(*) FROM answer_options WHERE answer_id=%s", (answer_id,)
                )
                self.assertEqual(cursor.fetchone()[0], 2)
                cursor.execute(
                    "SELECT answers_count FROM question_stats WHERE question_id=%s",
                    (questions[0]["id"],),
                )
                self.assertEqual(cursor.fetchone()[0], 1)
                result = choice_statistics(db, questions[0]["id"])
                self.assertEqual(result["total_answers"], 1)
                self.assertEqual(result["total_selections"], 3)
                self.assertEqual([s["percentage"] for s in result["stats"]], [100, 100, 100])
                row["responses"][0]["value"] = json.dumps({"labels": ["Bus"], "other": None})
                process_batch(cursor, key, form_id, [stage_record(key, row, questions)])
                cursor.execute(
                    "SELECT count(*) FROM answer_options WHERE answer_id=%s", (answer_id,)
                )
                self.assertEqual(cursor.fetchone()[0], 1)
                cursor.execute(
                    "SELECT count(*) FROM answers WHERE question_id=%s", (questions[0]["id"],)
                )
                self.assertEqual(cursor.fetchone()[0], 1)
                result = choice_statistics(db, questions[0]["id"])
                self.assertEqual(result["total_answers"], 1)
                self.assertEqual(result["total_selections"], 1)
                self.assertEqual(
                    [(s["label"], s["count"]) for s in result["stats"]], [("Vélo", 0), ("Bus", 1)]
                )
                cursor.execute("SELECT valid_count FROM answer_valid_stats WHERE id=1 FOR UPDATE")
                valid_before = cursor.fetchone()[0]
                cursor.execute(
                    "UPDATE answers SET text=%s WHERE id=%s",
                    ("Une longue réponse " * 10, answer_id),
                )
                cursor.execute("SELECT valid_count FROM answer_valid_stats WHERE id=1")
                self.assertEqual(cursor.fetchone()[0], valid_before + 1)
                cursor.execute(
                    "INSERT INTO questions(form_id,question_code,prompt,type) VALUES (%s,'Q2','Texte','text') RETURNING id",
                    (form_id,),
                )
                other_question_id = cursor.fetchone()[0]
                cursor.execute("DELETE FROM answer_options WHERE answer_id=%s", (answer_id,))
                cursor.execute(
                    "UPDATE answers SET question_id=%s WHERE id=%s", (other_question_id, answer_id)
                )
                cursor.execute(
                    "SELECT answers_count FROM question_stats WHERE question_id=%s",
                    (questions[0]["id"],),
                )
                self.assertEqual(cursor.fetchone()[0], 0)
                cursor.execute(
                    "SELECT answers_count FROM question_stats WHERE question_id=%s",
                    (other_question_id,),
                )
                self.assertEqual(cursor.fetchone()[0], 1)
                cursor.execute("DELETE FROM answers WHERE id=%s", (answer_id,))
                cursor.execute(
                    "SELECT answers_count FROM question_stats WHERE question_id=%s",
                    (other_question_id,),
                )
                self.assertEqual(cursor.fetchone()[0], 0)
                cursor.execute("SELECT valid_count FROM answer_valid_stats WHERE id=1")
                self.assertEqual(cursor.fetchone()[0], valid_before)
                questions[0]["type"] = "text"
                cursor.execute(
                    "UPDATE questions SET type='text' WHERE id=%s", (questions[0]["id"],)
                )
                row["responses"][0]["value"] = "Avant\x00après"
                process_batch(cursor, key, form_id, [stage_record(key, row, questions)])
                cursor.execute(
                    "SELECT a.text,c.raw_json FROM answers a JOIN contributions c ON c.id=a.contribution_id WHERE a.question_id=%s",
                    (questions[0]["id"],),
                )
                displayed, stored = cursor.fetchone()
                self.assertEqual(displayed, "Avant\ufffdaprès")
                self.assertEqual(json.loads(stored), row)
        finally:
            db.rollback()
            db.close()
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
