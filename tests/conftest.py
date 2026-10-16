"""HTTP tests use a migrated PostgreSQL database and roll back every fixture."""

import os
from datetime import datetime
from importlib import import_module
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session")
def test_engine():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Define TEST_DATABASE_URL pointing to a migrated PostgreSQL test database")
    engine = create_engine(url)
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "remove_runtime_caches"
        )
    yield engine
    engine.dispose()


@pytest.fixture
def web_data(test_engine, monkeypatch):
    from app.models import Answer, AnswerOption, Author, Contribution, Form, Option, Question

    with test_engine.connect() as connection:
        transaction = connection.begin()
        factory = sessionmaker(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        for module in (
            "app.db",
            "app.routers.api_forms",
            "app.routers.api_questions",
            "app.routers.api_search",
            "app.routers.api_contributions",
            "app.routers.seo",
            "app.routers.bookmarks",
            "app.services.auth",
        ):
            monkeypatch.setattr(import_module(module), "SessionLocal", factory)
        with factory() as db:
            form = Form(name="Formulaire de contrôle", source=f"test:{uuid4().hex}")
            author = Author(name="Auteur de contrôle", is_anonymous=True)
            db.add_all([form, author])
            db.flush()
            free = Question(
                form_id=form.id,
                question_code="Q1",
                prompt="Comment soutenir la culture ?",
                type="text",
                position=1,
            )
            multi = Question(
                form_id=form.id,
                question_code="Q2",
                prompt="Quels déplacements ?",
                type="multi_choice",
                position=2,
            )
            db.add_all([free, multi])
            db.flush()
            bike = Option(question_id=multi.id, code="velo", label="Vélo", position=1)
            bus = Option(question_id=multi.id, code="bus", label="Bus", position=2)
            db.add_all([bike, bus])
            db.flush()
            text_ids = []
            for index in range(23):
                contribution = Contribution(
                    form_id=form.id,
                    author_id=author.id,
                    submitted_at=datetime(2019, 3, 1),
                    title=f"Contribution {index}",
                )
                db.add(contribution)
                db.flush()
                answer = Answer(
                    contribution_id=contribution.id,
                    question_id=free.id,
                    position=1,
                    text=f"Culture numéro {index}. Les bibliothèques et les musées doivent être accessibles à tous. <script>alert('source')</script>",
                )
                db.add(answer)
                db.flush()
                text_ids.append(answer.id)
                if index < 2:
                    choice = Answer(
                        contribution_id=contribution.id,
                        question_id=multi.id,
                        position=1,
                        text="Vélo\nBus" if index == 0 else "Bus",
                        value_json='{"other_text":[]}',
                    )
                    db.add(choice)
                    db.flush()
                    db.add(AnswerOption(answer_id=choice.id, option_id=bus.id))
                    if index == 0:
                        db.add(AnswerOption(answer_id=choice.id, option_id=bike.id))
                        choice_id = choice.id
            db.commit()
            data = {
                "form": form.id,
                "multi": multi.id,
                "text_question": free.id,
                "choice_answer": choice_id,
                "bike": bike.id,
                "text_ids": text_ids,
                "factory": factory,
            }
        try:
            yield data
        finally:
            transaction.rollback()


@pytest.fixture
def client(web_data):
    from app.app import app
    from app.config import settings

    with TestClient(app, headers={"Origin": settings.BASE_URL}) as client:
        yield client
