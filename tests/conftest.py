# tests/conftest.py
import os
import pytest
import tempfile
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Import application
from app.app import app
from app.db import SessionLocal
from app.models import Base


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine with PostgreSQL"""
    import os
    
    test_db_url = os.getenv("TEST_DATABASE_URL")
    if not test_db_url:
        raise RuntimeError(
            "TEST_DATABASE_URL environment variable is required. "
            "Please set it to your PostgreSQL test database URL, e.g.:\n"
            "export TEST_DATABASE_URL='postgresql:///test_cahier_doleances'"
        )
    
    print(f"🐳 Using PostgreSQL test database: {test_db_url}")
    engine = create_engine(test_db_url, echo=False)
    
    # Test connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    
    # Create schema
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create test database session"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(test_db):
    """Create test client with test database"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    # Override the database dependency
    from app.db import get_db
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def sample_data(test_db):
    """Create sample data for tests"""
    from app.models import Form, Question, Option, Author, Contribution, Answer, AnswerOption
    
    # Create form
    form = Form(name="Test Form", version="1.0", source="test")
    test_db.add(form)
    test_db.flush()
    
    # Create questions
    q1 = Question(
        form_id=form.id,
        question_code="Q1", 
        prompt="What is your favorite color?",
        type="single_choice",
        position=1
    )
    q2 = Question(
        form_id=form.id,
        question_code="Q2",
        prompt="Describe your experience",
        type="text", 
        position=2
    )
    test_db.add_all([q1, q2])
    test_db.flush()
    
    # Create options for single choice question
    opt1 = Option(question_id=q1.id, code="RED", label="Rouge", position=1)
    opt2 = Option(question_id=q1.id, code="BLUE", label="Bleu", position=2)
    opt3 = Option(question_id=q1.id, code="GREEN", label="Vert", position=3)
    test_db.add_all([opt1, opt2, opt3])
    test_db.flush()
    
    # Create authors with unique hashes to avoid conflicts
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    author1 = Author(name="Test User 1", email_hash=f"hash1_{unique_id}", zipcode="75001")
    author2 = Author(name="Test User 2", email_hash=f"hash2_{unique_id}", zipcode="75002")
    test_db.add_all([author1, author2])
    test_db.flush()
    
    # Create contributions
    contrib1 = Contribution(
        author_id=author1.id,
        form_id=form.id,
        source="test",
        title="Test Contribution 1"
    )
    contrib2 = Contribution(
        author_id=author2.id,
        form_id=form.id, 
        source="test",
        title="Test Contribution 2"
    )
    test_db.add_all([contrib1, contrib2])
    test_db.flush()
    
    # Create answers
    # Single choice answers (no text, will use AnswerOption relations)
    answer1 = Answer(
        contribution_id=contrib1.id,
        question_id=q1.id,
        text="",  # Empty text for single_choice, relation via AnswerOption
        position=1
    )
    answer2 = Answer(
        contribution_id=contrib2.id,
        question_id=q1.id,
        text="", 
        position=1
    )
    
    # Text answers
    answer3 = Answer(
        contribution_id=contrib1.id,
        question_id=q2.id,
        text="J'ai eu une expérience très positive avec ce service. Les équipes sont à l'écoute et réactives.",
        position=1
    )
    answer4 = Answer(
        contribution_id=contrib2.id,
        question_id=q2.id,
        text="Le service pourrait être amélioré, notamment au niveau de la rapidité de traitement des dossiers.",
        position=1
    )
    
    test_db.add_all([answer1, answer2, answer3, answer4])
    test_db.flush()
    
    # Create AnswerOption relations for single_choice answers
    answer_opt1 = AnswerOption(answer_id=answer1.id, option_id=opt1.id)  # answer1 -> Rouge
    answer_opt2 = AnswerOption(answer_id=answer2.id, option_id=opt2.id)  # answer2 -> Bleu
    test_db.add_all([answer_opt1, answer_opt2])
    
    test_db.commit()
    
    return {
        "form": form,
        "questions": [q1, q2],
        "options": [opt1, opt2, opt3], 
        "authors": [author1, author2],
        "contributions": [contrib1, contrib2],
        "answers": [answer1, answer2, answer3, answer4]
    }


@pytest.fixture
def cache_test_data(test_db):
    """Create specific data for cache testing"""
    from app.models import SearchStats, SearchCache
    
    # Create search stats for popularity-based caching with unique terms
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    stats = [
        SearchStats(query_text=f"cache_test_{unique_id}", search_count=10),
        SearchStats(query_text=f"popular_test_{unique_id}", search_count=25),
        SearchStats(query_text=f"rare_test_{unique_id}", search_count=1),
    ]
    test_db.add_all(stats)
    
    # Create some cache entries
    cache_entries = [
        SearchCache(
            cache_key=f"search:popular_test_{unique_id}:",
            results_json='{"answers": [], "has_next": false, "next_cursor": null}',
            search_count=25
        ),
    ]
    test_db.add_all(cache_entries)
    test_db.commit()
    
    return {"stats": stats, "cache": cache_entries}


# Markers for test categories
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "cache: marks tests as cache-related")
    config.addinivalue_line("markers", "scroll: marks tests as infinite scroll related")