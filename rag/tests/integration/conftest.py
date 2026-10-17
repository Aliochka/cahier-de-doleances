"""Données synthétiques dans une base de test déjà migrée ; aucune création de schéma."""

import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from cahier_rag.config import load_settings
from cahier_rag.contracts import MAX_BIGINT
from cahier_rag.db import create_source_engine


@pytest.fixture
def pg_source():
    raw = os.getenv("RAG_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Définir RAG_TEST_DATABASE_URL vers une base de test déjà migrée")
    settings = load_settings(environ={"RAG_SOURCE_DATABASE_URL": raw})
    url = settings.require_source_url()
    if not url.database.endswith("_test"):
        pytest.fail("La base RAG_TEST_DATABASE_URL doit porter un nom terminé par _test")
    writer = create_engine(url, hide_parameters=True)
    source = create_source_engine(settings)
    # Pas de séquence modifiée. Les IDs documentaires sont supérieurs à 2^53.
    base = MAX_BIGINT - uuid4().int % 1_000_000_000 - 100
    f1, f2 = base, base + 1
    c1, c2, title_only = base + 2, base + 3, base + 4
    # Le schéma migré possède question_stats.question_id INTEGER : conserver
    # des IDs de question compatibles avec ses déclencheurs, sans les modifier.
    qbase = 1_000_000_000 + uuid4().int % 100_000_000
    q1, q2, q3, q4 = (qbase + i for i in range(4))
    answer_ids = [base + 10 + i for i in range(8)]
    prepared = False
    try:
        with writer.connect() as connection:
            assert (
                connection.execute(text("SELECT current_database()")).scalar_one() == url.database
            )
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "remove_runtime_caches"
            )
            assert (
                connection.execute(
                    text(
                        "SELECT data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='answers' AND column_name='id'"
                    )
                ).scalar_one()
                == "bigint"
            )
        with writer.begin() as connection:
            connection.execute(
                text("INSERT INTO forms(id,name,version,source) VALUES (:id,:name,'2019',:source)"),
                [
                    {"id": f1, "name": "Questionnaire synthétique A", "source": f"rag004:{base}:A"},
                    {"id": f2, "name": "Questionnaire synthétique B", "source": f"rag004:{base}:B"},
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO questions(id,form_id,question_code,prompt,section,position,type) VALUES (:id,:form,:code,:prompt,'Section',:position,:type)"
                ),
                [
                    {
                        "id": q1,
                        "form": f1,
                        "code": "Q1",
                        "prompt": "Pourquoi ?",
                        "position": 1,
                        "type": "text",
                    },
                    {
                        "id": q2,
                        "form": f1,
                        "code": "Q2",
                        "prompt": "Quels choix ?",
                        "position": 2,
                        "type": "multi_choice",
                    },
                    {
                        "id": q3,
                        "form": f2,
                        "code": "Q3",
                        "prompt": "Texte long ?",
                        "position": 1,
                        "type": "text",
                    },
                    {
                        "id": q4,
                        "form": f1,
                        "code": "Q4",
                        "prompt": "Un seul choix ?",
                        "position": 3,
                        "type": "single_choice",
                    },
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO contributions(id,form_id,title,source,source_contribution_id,submitted_at) VALUES (:id,:form,:title,'rag004:synthetic',:external,'2019-02-01 12:00:00')"
                ),
                [
                    {"id": c1, "form": f1, "title": "Titre A", "external": f"000:{base}:A"},
                    {"id": c2, "form": f2, "title": None, "external": f"000:{base}:B"},
                    {
                        "id": title_only,
                        "form": f1,
                        "title": "Un titre sans réponse",
                        "external": f"000:{base}:C",
                    },
                ],
            )
            values = [
                (c1, q1, 1, "Non", None),
                (c1, q1, 2, "Non", None),
                (
                    c1,
                    q2,
                    1,
                    "Bus\nAutre A\nAutre B",
                    json.dumps({"labels": ["Bus"], "other_text": ["", "Autre A", "Autre B"]}),
                ),
                (c1, q2, 2, "Bus", '{"other_text":[]}'),
                (c1, q1, 3, " \n\t", None),
                (c2, q3, 1, "École\n" * 60_000, None),
                (c1, q1, 4, None, None),
                (c1, q4, 1, "Oui\nAutre unique", '{"other_text":["Autre unique"]}'),
            ]
            connection.execute(
                text(
                    "INSERT INTO answers(id,contribution_id,question_id,position,text,value_json) VALUES (:id,:contribution,:question,:position,:text,:json)"
                ),
                [
                    dict(
                        zip(
                            ("id", "contribution", "question", "position", "text", "json"),
                            (identity, *value),
                            strict=True,
                        )
                    )
                    for identity, value in zip(answer_ids, values, strict=True)
                ],
            )
        prepared = True
        yield dict(
            writer=writer,
            engine=source,
            forms=(f1, f2),
            contributions=(c1, c2, title_only),
            questions=(q1, q2, q3, q4),
            answers=answer_ids,
        )
    finally:
        # Uniquement les IDs synthétiques de cette fixture, sur la base validée.
        try:
            if prepared:
                with writer.begin() as connection:
                    connection.execute(
                        text("DELETE FROM answers WHERE contribution_id IN (:c1,:c2,:c3)"),
                        {"c1": c1, "c2": c2, "c3": title_only},
                    )
                    connection.execute(
                        text("DELETE FROM question_stats WHERE question_id IN (:q1,:q2,:q3,:q4)"),
                        {"q1": q1, "q2": q2, "q3": q3, "q4": q4},
                    )
                    connection.execute(
                        text("DELETE FROM questions WHERE form_id IN (:f1,:f2)"),
                        {"f1": f1, "f2": f2},
                    )
                    connection.execute(
                        text("DELETE FROM contributions WHERE id IN (:c1,:c2,:c3)"),
                        {"c1": c1, "c2": c2, "c3": title_only},
                    )
                    connection.execute(
                        text("DELETE FROM forms WHERE id IN (:f1,:f2)"), {"f1": f1, "f2": f2}
                    )
        finally:
            source.dispose()
            writer.dispose()
