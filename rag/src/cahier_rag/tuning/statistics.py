"""Matérialisation exacte des DF depuis les tsvector existants, indépendante des embeddings."""

from sqlalchemy import text


def build_statistics(store):
    state = store.state()
    if not state["verified"]:
        raise ValueError("Corpus vérifié requis.")
    with store.guard.transaction() as (c, _):
        c.execute(text("SET LOCAL statement_timeout='10min'"))
        c.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": "rag027-stats-" + store.space},
        )
        row = (
            c.execute(
                text("SELECT * FROM rag_tuning.statistics WHERE space_id=:space"),
                {"space": store.space},
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            if row["corpus_hash"] != state["chain_hash"] or row["documents"] != state["documents"]:
                raise ValueError(
                    "Statistiques existantes incompatibles ; nouvelle recette nécessaire."
                )
            return dict(row) | {"created_at": str(row["created_at"])}
        # Fixed SQL only; space is validated by FullStore. ts_stat counts each
        # lexeme once per document, exactly like the reference GIN count query.
        c.execute(
            text("""INSERT INTO rag_tuning.statistics(space_id,corpus_hash,documents,lexemes,version)
           VALUES(:space,:hash,:n,0,1)"""),
            dict(space=store.space, hash=state["chain_hash"], n=state["documents"]),
        )
        query = "SELECT search_vector FROM rag_full.documents WHERE space_id='" + store.space + "'"
        c.execute(
            text("""INSERT INTO rag_tuning.term_statistics(space_id,term,documents)
            SELECT :space,word,ndoc FROM ts_stat(:query)"""),
            dict(space=store.space, query=query),
        )
        n = c.execute(
            text("SELECT count(*) FROM rag_tuning.term_statistics WHERE space_id=:space"),
            {"space": store.space},
        ).scalar_one()
        c.execute(
            text("UPDATE rag_tuning.statistics SET lexemes=:n WHERE space_id=:space"),
            dict(space=store.space, n=n),
        )
    return dict(lexemes=n, documents=state["documents"], corpus_hash=state["chain_hash"])
