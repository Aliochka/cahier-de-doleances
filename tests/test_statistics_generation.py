"""Persistent publication, source freshness, failure fencing, no visitor recomputation."""

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.services.published_statistics import read_published
from app.services.statistics_generation import GenerationError, generate

pytestmark = pytest.mark.integration


def publish(data, **kwargs):
    with data["factory"]() as db:
        result = generate(db, **kwargs)
        db.commit()
        return result


def test_absent_available_and_stale(client, web_data):
    path = f"/api/v1/forms/{web_data['form']}"
    initial = client.get(path).json()
    assert initial["statistics_availability"]["status"] == "unavailable"
    assert all(q["answers_count"] is None for q in initial["questions"])
    assert client.get(path + "/stats").status_code == 503
    generation = publish(web_data)
    available = client.get(path).json()
    assert available["statistics_availability"]["generation_id"] == generation["generation_id"]
    assert all(q["answers_count"] is not None for q in available["questions"])
    with web_data["factory"]() as db:
        db.execute(
            text("UPDATE answers SET text=text WHERE id=:id"), {"id": web_data["choice_answer"]}
        )
        db.commit()
    stale = client.get(path).json()
    assert stale["statistics_availability"]["reason"] == "incompatible"
    assert all(q["answers_count"] is None for q in stale["questions"])
    assert client.get(f"/api/v1/questions/{web_data['multi']}/stats").status_code == 503
    publish(web_data)
    assert client.get(path + "/stats").status_code == 200


@pytest.mark.parametrize("phase", ["source", "aggregated", "validated", "prepared", "published"])
def test_failure_keeps_previous_complete_generation(web_data, phase):
    previous = publish(web_data)

    def interrupt(current):
        if current == phase:
            raise RuntimeError("injected interruption")

    with pytest.raises(RuntimeError):
        publish(web_data, checkpoint=interrupt)
    with web_data["factory"]() as db:
        availability, values = read_published(db, form_id=web_data["form"])
        assert availability.status == "available"
        assert availability.generation_id == previous["generation_id"]
        assert len(values) == 2
        assert db.execute(text("SELECT count(*) FROM statistics_generations")).scalar_one() == 1


def test_reproducible_and_hash_checked(web_data):
    first, second = publish(web_data), publish(web_data)
    assert first["generation_id"] != second["generation_id"]
    assert first["content_hash"] == second["content_hash"]
    with web_data["factory"]() as db:
        db.execute(
            text(
                "UPDATE question_statistics_snapshots SET answers_count=answers_count+1 WHERE generation_id=:g"
            ),
            {"g": second["generation_id"]},
        )
        assert read_published(db, form_id=web_data["form"])[0].reason == "incomplete"


def test_missing_row_and_method_mismatch(web_data):
    result = publish(web_data)
    with web_data["factory"]() as db:
        db.execute(
            text(
                "DELETE FROM question_statistics_snapshots WHERE generation_id=:g AND question_id=:q"
            ),
            {"g": result["generation_id"], "q": web_data["multi"]},
        )
        assert read_published(db, form_id=web_data["form"])[0].reason == "incomplete"
        db.rollback()
    with web_data["factory"]() as db:
        db.execute(
            text("UPDATE statistics_generations SET method_version='unsupported' WHERE id=:g"),
            {"g": result["generation_id"]},
        )
        assert read_published(db, form_id=web_data["form"])[0].reason == "incompatible"


def test_concurrent_generator_excluded(web_data, test_engine):
    publish(web_data)  # advisory transaction lock is retained by outer fixture transaction
    with Session(test_engine) as other, pytest.raises(GenerationError, match="déjà"):
        generate(other)


def test_source_change_during_repeatable_read_cannot_publish(test_engine):
    # Real committed concurrent transactions, exclusively on the isolated _test DB.
    assert test_engine.url.database.endswith("_test")
    engine = test_engine.execution_options(isolation_level="REPEATABLE READ")

    def mutate(phase):
        if phase == "validated":
            with test_engine.begin() as writer:
                writer.execute(text("UPDATE statistics_source SET revision=revision+1 WHERE id=1"))

    with Session(engine) as db, pytest.raises(DBAPIError), db.begin():
        generate(db, checkpoint=mutate)


def test_public_queries_do_not_read_answer_tables(client, web_data):
    publish(web_data)
    statements = []
    engine = web_data["factory"].kw["bind"].engine

    def capture(conn, cursor, sql, params, context, many):
        statements.append(sql)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        for _ in range(2):
            assert client.get(f"/api/v1/forms/{web_data['form']}").status_code == 200
            assert client.get(f"/api/v1/forms/{web_data['form']}/stats").status_code == 200
            assert client.get(f"/api/v1/questions/{web_data['multi']}/stats").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert not any("FROM answers" in sql or "JOIN answer_options" in sql for sql in statements)


def test_bad_counter_and_bad_relations_rejected(web_data):
    previous = publish(web_data)
    with web_data["factory"]() as db:
        db.execute(
            text("UPDATE question_stats SET answers_count=answers_count+1 WHERE question_id=:q"),
            {"q": web_data["multi"]},
        )
        db.commit()
    with pytest.raises(GenerationError, match="Compteur"):
        publish(web_data)
    with web_data["factory"]() as db:
        assert (
            str(
                db.execute(
                    text("SELECT published_generation FROM statistics_source WHERE id=1")
                ).scalar_one()
            )
            == previous["generation_id"]
        )
        assert read_published(db)[0].status == "unavailable"


def test_other_only_response_kept_as_its_own_category(client, web_data):
    from app.models import Answer

    with web_data["factory"]() as db:
        source = db.get(Answer, web_data["text_ids"][-1])
        db.add(
            Answer(
                question_id=web_data["multi"],
                contribution_id=source.contribution_id,
                position=1,
                text="synthetic",
                value_json='{"other_text":["synthetic"]}',
            )
        )
        db.commit()
    publish(web_data)
    stats = client.get(f"/api/v1/questions/{web_data['multi']}/stats").json()
    assert stats["total_answers"] == 3
    assert stats["other_text_answers_count"] == 1
    assert stats["total_option_selections"] == 3
    assert stats["total_selections"] == 4
    assert stats["categories"][-1]["percentage"] == 33.33


def test_cross_form_relation_prevents_publication(web_data):
    from app.models import Form

    with web_data["factory"]() as db:
        other = Form(name="Synthetic", source="synthetic")
        db.add(other)
        db.flush()
        db.execute(
            text(
                "UPDATE contributions SET form_id=:fid WHERE id=(SELECT contribution_id FROM answers WHERE id=:aid)"
            ),
            {"fid": other.id, "aid": web_data["choice_answer"]},
        )
        db.commit()
    with pytest.raises(GenerationError, match="Relations"):
        publish(web_data)


def test_http_read_is_repeatable_read_only_and_pool_is_reset(test_engine):
    from app.services.published_statistics import consistent_read

    with Session(test_engine) as reader:
        consistent_read(reader)
        assert reader.execute(text("SHOW transaction_isolation")).scalar_one() == "repeatable read"
        assert reader.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
        before = reader.execute(
            text("SELECT revision FROM statistics_source WHERE id=1")
        ).scalar_one()
        with test_engine.begin() as writer:
            writer.execute(text("UPDATE statistics_source SET revision=revision+1 WHERE id=1"))
        assert (
            reader.execute(text("SELECT revision FROM statistics_source WHERE id=1")).scalar_one()
            == before
        )
    with test_engine.begin() as writer:
        assert writer.execute(text("SHOW transaction_read_only")).scalar_one() == "off"
