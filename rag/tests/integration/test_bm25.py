"""Normalisation réelle, lecture seule et absence de plafonds tsvector."""

import os

import pytest
from sqlalchemy import text

from cahier_rag.config import load_settings
from cahier_rag.db import create_rag_engine, source_connection
from cahier_rag.search.bm25.tokenizer import FrenchTokenizer


@pytest.mark.integration
def test_french_exact_counts_accents_and_stopwords():
    url = os.getenv("RAG_STORAGE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Base de test RAG absente")
    settings = load_settings(environ={"RAG_DATABASE_URL": url})
    if not settings.require_rag_url().database.endswith("_test"):
        pytest.fail("Base de test exclusivement")
    engine = create_rag_engine(settings)
    try:
        tokenizer = FrenchTokenizer(engine)
        assert tokenizer.encode(["écoles", "école", "l'école", "l’école"]) == [["écol"]] * 4
        assert tokenizer.encode(["et de la", "oui " * 20000]) == [[], ["oui"] * 20000]
        terms, phrases, excluded = tokenizer.query(
            'Comment améliorer les écoles "transports ruraux" -taxe'
        )
        assert (
            "comment" not in terms and phrases == [["transport", "rural"]] and excluded == [["tax"]]
        )
        with source_connection(engine) as connection:
            assert connection.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
    finally:
        engine.dispose()
