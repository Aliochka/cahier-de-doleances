"""Explicit historical laboratory preparation; no publication and no HNSW."""

import hashlib
import json
import math
import struct
import time
from pathlib import Path

from sqlalchemy import text

from .artifacts import DECISIONS, Artifacts, canonical, sha
from .editorial import load_decisions
from .storage import SCOPE, WHERE, verify

MODELS = Path(__file__).resolve().parents[1] / "rag/models"
LEXICAL_RECIPE = {
    "version": "historical-lexical-1",
    "config": "pg_catalog.french",
    "weights": [0.5, 0.3, 0.2],
    "beta": 0.25,
    "statistics": "eligible passage union document metadata lexemes",
}
ELIGIBLE = """u.corpus_id=:corpus AND u.release_id=:release AND d.candidate AND u.searchable"""
JOIN = (
    "documentary.search_unit u JOIN documentary.document d USING(corpus_id,release_id,document_id)"
)


def gate(c):
    release = (
        c.execute(text(f"SELECT * FROM documentary.release WHERE {WHERE}"), SCOPE).mappings().one()
    )
    if release["state"] != "verified" or release["publication_authorized"]:
        raise ValueError("Explicit verified, non-public laboratory release required")
    if (
        c.execute(
            text("SELECT active_release_id FROM documentary.corpus WHERE corpus_id=:corpus"), SCOPE
        ).scalar_one()
        is not None
    ):
        raise ValueError("Laboratory must not use an active public corpus")
    if c.execute(
        text(
            f"SELECT count(*) FROM documentary.document WHERE {WHERE} AND (readable OR searchable OR catalogue_visible)"
        ),
        SCOPE,
    ).scalar_one():
        raise ValueError("Public document permissions must remain false")
    # Compare policy identity on every operation; do not trust an old preparation flag.
    expected = sha(canonical(load_decisions(DECISIONS)))
    if release["editorial_hash"] != expected:
        raise ValueError("Laboratory editorial policy differs from the approved local bundle")
    counts = c.execute(
        text(
            f"SELECT count(*),count(u.search_vector),count(u.embedding) FROM {JOIN} WHERE {ELIGIBLE}"
        ),
        SCOPE,
    ).one()
    if release["statistics_ready"] and (
        counts[0] != release["lexical_statistics"]["units"] or counts[1] != counts[0]
    ):
        raise ValueError("Laboratory population changed; revalidate and rebuild statistics")
    if release["representations_ready"] and counts[2] != counts[0]:
        raise ValueError("Vector preparation flag does not match eligible representations")
    return release


def population(c):
    return c.execute(text(f"SELECT count(*) FROM {JOIN} WHERE {ELIGIBLE}"), SCOPE).scalar_one()


def metadata_fields(doc, meta, title):
    """The only allowed metadata representation, shared by preparation and checking."""
    territories = [
        v.strip()
        for v in meta.get("territorial_context", [])
        if v.strip() not in {"Cahiers", "États généraux", "États Généraux"}
        and not v.startswith("Archives Parlementaires")
    ]
    place = (meta.get("origin") or {}).get("label") or ""
    orders = (
        meta.get("historical_orders", [])
        if meta.get("historical_orders_status") == "explicit_in_metadata_title"
        else []
    )
    words = "\n".join(dict.fromkeys([meta["title"], title, place] + territories + orders))
    return words, {"volume": doc["volume"], "place": place, "orders": orders}


def prepare_lexical(destination):
    artifacts = Artifacts()
    with destination.transaction() as c:
        c.execute(text("SELECT pg_advisory_xact_lock(1789,1)"))
        verify(c, artifacts, load_decisions(DECISIONS), phase1=False)
        release = gate(c)
        c.execute(
            text(
                f"UPDATE documentary.document SET metadata_vector=NULL,filter_metadata='{{}}'::jsonb WHERE {WHERE} AND NOT candidate"
            ),
            SCOPE,
        )
        for key, doc in artifacts.documents.items():
            if doc["document_kind"] != "cahier_autonome_probable":
                continue
            row = c.execute(
                text(
                    f"SELECT display_title FROM documentary.document WHERE {WHERE} AND document_id=:id"
                ),
                dict(SCOPE, id=key),
            ).scalar_one()
            words, filters = metadata_fields(doc, artifacts.metadata[key], row)
            c.execute(
                text(f"""UPDATE documentary.document SET metadata_vector=to_tsvector('pg_catalog.french',:words),
                filter_metadata=CAST(:filters AS jsonb) WHERE {WHERE} AND document_id=:id"""),
                dict(SCOPE, id=key, words=words, filters=canonical(filters)),
            )
        c.execute(
            text(f"""UPDATE documentary.search_unit u SET search_vector=to_tsvector('pg_catalog.french',
            substring(d.full_text FROM u.start_offset+1 FOR u.end_offset-u.start_offset))
            FROM documentary.document d WHERE u.corpus_id=d.corpus_id AND u.release_id=d.release_id
            AND u.document_id=d.document_id AND {ELIGIBLE}"""),
            SCOPE,
        )
        # Excluded/non-candidate units never enter this representation or its statistics.
        c.execute(text(f"DELETE FROM documentary.lexical_term_statistics WHERE {WHERE}"), SCOPE)
        c.execute(
            text(f"""INSERT INTO documentary.lexical_term_statistics
            SELECT :corpus,:release,term,count(*) FROM {JOIN}
            CROSS JOIN LATERAL unnest(tsvector_to_array(u.search_vector || d.metadata_vector)) term
            WHERE {ELIGIBLE} GROUP BY term"""),
            SCOPE,
        )
        n = population(c)
        stats = c.execute(
            text(
                f"SELECT count(*),sum(document_frequency) FROM documentary.lexical_term_statistics WHERE {WHERE}"
            ),
            SCOPE,
        ).one()
        info = {
            "units": n,
            "terms": stats[0],
            "sum_df": int(stats[1]),
            "editorial_hash": release["editorial_hash"],
        }
        c.execute(
            text(f"""UPDATE documentary.release SET lexical_recipe=CAST(:recipe AS jsonb),
            lexical_statistics=CAST(:stats AS jsonb),statistics_ready=true WHERE {WHERE}"""),
            dict(SCOPE, recipe=canonical(LEXICAL_RECIPE), stats=canonical(info)),
        )
        for name in ("document", "search_unit", "lexical_term_statistics"):
            c.execute(text("ANALYZE documentary." + name))
        return info


def encoder(*, threads=4, precision="bfloat16"):
    from cahier_rag.embeddings.core import EmbeddingEngine
    from cahier_rag.embeddings.registry import MODELS as REGISTRY
    from cahier_rag.embeddings.transformers_backend import TransformersBackend

    class HistoricalCpuBackend(TransformersBackend):
        """Historical CPU experiment supports explicit bf16; H1 backend is unchanged."""

        def load(self):
            super().load()
            if precision == "bfloat16":
                self.model.to(self.torch.bfloat16)
            self.precision = precision

    if precision not in {"float32", "bfloat16"}:
        raise ValueError("Explicit historical CPU precision required")
    return EmbeddingEngine(HistoricalCpuBackend(REGISTRY["bge-m3"], MODELS, threads=threads))


def embedding_recipe(engine, *, batch_size, workers):
    import torch
    import transformers

    return {
        "version": "historical-bge-1",
        "model": engine.backend.spec.to_dict(),
        "snapshot_hash": engine.backend.snapshot_hash,
        "input": "exact technical passage only",
        "pooling": "cls",
        "normalize": "L2 float64 then float32 storage",
        "storage": "vector(1024) float32",
        "precision": engine.backend.precision,
        "device": "cpu",
        "threads": engine.backend.threads,
        "batch_size": batch_size,
        "workers": workers,
        "seed": 42,
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "truncation": False,
        "order": "token_count then unit_id; round-robin shards",
    }


def vector_hash(values):
    return hashlib.sha256(struct.pack("<1024f", *values)).hexdigest()


def embed(destination, *, threads=4, batch_size=16, precision="bfloat16", workers=1, shard=0):
    from cahier_rag.embeddings.core import EmbeddingInput

    if not 1 <= workers <= 8 or not 0 <= shard < workers:
        raise ValueError("Invalid embedding shard")
    artifacts = Artifacts()
    engine = encoder(threads=threads, precision=precision)
    engine.load()
    recipe = embedding_recipe(engine, batch_size=batch_size, workers=workers)
    try:
        with destination.transaction() as c:
            c.execute(text("SELECT pg_advisory_xact_lock(1789,1)"))
            verify(c, artifacts, load_decisions(DECISIONS), phase1=False)
            release = gate(c)
            if release["embedding_recipe"] and release["embedding_recipe"] != recipe:
                raise ValueError("Existing vector recipe differs; no silent overwrite")
            c.execute(
                text(
                    f"UPDATE documentary.release SET embedding_recipe=CAST(:r AS jsonb) WHERE {WHERE}"
                ),
                dict(SCOPE, r=canonical(recipe)),
            )
            items = (
                c.execute(
                    text(f"""SELECT u.unit_id,u.text_sha256,u.embedding_hash,
                (u.source_metadata->>'token_count')::int AS tokens FROM {JOIN}
                WHERE {ELIGIBLE} ORDER BY tokens,u.unit_id COLLATE "C" """),
                    SCOPE,
                )
                .mappings()
                .all()
            )
        pending = [
            r
            for index, r in enumerate(items)
            if index % workers == shard and r["embedding_hash"] is None
        ]
        started = time.perf_counter()
        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            inputs = [
                EmbeddingInput(
                    r["unit_id"], artifacts.units[r["unit_id"]]["text"], r["text_sha256"]
                )
                for r in batch
            ]
            vectors = next(engine.encode_documents(inputs, batch_size=batch_size))
            with destination.transaction() as c:
                c.execute(text("SELECT pg_advisory_xact_lock(1789,1)"))
                # Policy or recipe changes during computation invalidate this batch.
                current = (
                    c.execute(
                        text(
                            f"SELECT editorial_hash,embedding_recipe FROM documentary.release WHERE {WHERE} FOR SHARE"
                        ),
                        SCOPE,
                    )
                    .mappings()
                    .one()
                )
                if (
                    current["editorial_hash"] != release["editorial_hash"]
                    or current["embedding_recipe"] != recipe
                ):
                    raise ValueError("Publication recipe/policy changed during encoding")
                for item, values in zip(batch, vectors.vectors, strict=True):
                    literal = "[" + ",".join(str(v) for v in values) + "]"
                    updated = c.execute(
                        text(f"""UPDATE documentary.search_unit u SET
                        embedding=CAST(:vector AS public.vector),embedding_hash=:hash
                        FROM documentary.document d WHERE u.corpus_id=d.corpus_id AND u.release_id=d.release_id
                        AND u.document_id=d.document_id AND {ELIGIBLE} AND u.unit_id=:id AND u.embedding IS NULL"""),
                        dict(SCOPE, vector=literal, hash=vector_hash(values), id=item["unit_id"]),
                    )
                    if updated.rowcount != 1:
                        raise ValueError("Concurrent or ineligible vector write refused")
            print(
                json.dumps(
                    {
                        "shard": shard,
                        "encoded": min(start + batch_size, len(pending)),
                        "pending": len(pending),
                        "seconds": round(time.perf_counter() - started, 2),
                    }
                ),
                flush=True,
            )
        with destination.transaction() as c:
            c.execute(text("SELECT pg_advisory_xact_lock(1789,1)"))
            c.execute(
                text(f"""UPDATE documentary.release SET representations_ready=NOT EXISTS (
                SELECT 1 FROM {JOIN} WHERE {ELIGIBLE} AND u.embedding IS NULL) WHERE {WHERE}"""),
                SCOPE,
            )
        return {
            "recipe": recipe,
            "computed": len(pending),
            "reused": sum(
                index % workers == shard and row["embedding_hash"] is not None
                for index, row in enumerate(items)
            ),
            "shard": shard,
        }
    finally:
        engine.close()


def verify_representations(destination):
    artifacts = Artifacts()
    with destination.transaction(readonly=True) as c:
        source = verify(c, artifacts, load_decisions(DECISIONS), phase1=False)
        release = gate(c)
        expected = []
        titles = dict(
            c.execute(
                text(f"SELECT document_id,display_title FROM documentary.document WHERE {WHERE}"),
                SCOPE,
            ).all()
        )
        for key, doc in artifacts.documents.items():
            words, filters = (
                metadata_fields(doc, artifacts.metadata[key], titles[key])
                if doc["document_kind"] == "cahier_autonome_probable"
                else (None, {})
            )
            expected.append({"id": key, "words": words, "filters": filters})
        bad_metadata = c.execute(
            text("""SELECT count(*) FROM documentary.document d
            JOIN jsonb_array_elements(CAST(:expected AS jsonb)) r ON d.document_id=r->>'id'
            WHERE d.corpus_id=:corpus AND d.release_id=:release AND
            (d.metadata_vector IS DISTINCT FROM to_tsvector('pg_catalog.french',r->>'words')
            OR d.filter_metadata IS DISTINCT FROM r->'filters')"""),
            dict(SCOPE, expected=canonical(expected)),
        ).scalar_one()
        if bad_metadata:
            raise ValueError("Document metadata representations differ from allowed source fields")
        invalid = c.execute(
            text(f"""SELECT count(*) FROM {JOIN} WHERE {ELIGIBLE} AND
            (u.search_vector IS DISTINCT FROM to_tsvector('pg_catalog.french',substring(d.full_text FROM u.start_offset+1 FOR u.end_offset-u.start_offset))
            OR u.embedding IS NULL)"""),
            SCOPE,
        ).scalar_one()
        if invalid or not release["statistics_ready"] or not release["representations_ready"]:
            raise ValueError("Historical representations incomplete")
        delta = c.execute(
            text(f"""WITH expected AS (
            SELECT term,count(*)::bigint AS df FROM {JOIN}
            CROSS JOIN LATERAL unnest(tsvector_to_array(u.search_vector || d.metadata_vector)) term
            WHERE {ELIGIBLE} GROUP BY term), stored AS (
            SELECT term,document_frequency AS df FROM documentary.lexical_term_statistics WHERE {WHERE})
            SELECT count(*) FROM expected FULL JOIN stored USING(term) WHERE expected.df IS DISTINCT FROM stored.df"""),
            SCOPE,
        ).scalar_one()
        if delta or population(c) != release["lexical_statistics"]["units"]:
            raise ValueError("Lexical DF or population mismatch")
        count = 0
        for row in c.execute(
            text(
                f"SELECT public.vector_send(u.embedding),u.embedding_hash FROM {JOIN} WHERE {ELIGIBLE}"
            ),
            SCOPE,
        ):
            raw = bytes(row[0])
            if struct.unpack("!HH", raw[:4]) != (1024, 0):
                raise ValueError("Unexpected vector shape")
            values = struct.unpack("!1024f", raw[4:])
            if (
                vector_hash(values) != row[1]
                or not all(math.isfinite(v) for v in values)
                or abs(math.sqrt(sum(v * v for v in values)) - 1) > 1e-5
            ):
                raise ValueError("Vector fingerprint or norm mismatch")
            count += 1
        excluded = c.execute(
            text(
                f"SELECT count(*) FROM {JOIN} WHERE u.corpus_id=:corpus AND u.release_id=:release AND (NOT d.candidate OR NOT u.searchable) AND (u.embedding IS NOT NULL OR u.search_vector IS NOT NULL)"
            ),
            SCOPE,
        ).scalar_one()
        if excluded:
            raise ValueError("Out-of-scope representations present")
        return {
            "source_integrity": source,
            "vectors": count,
            "statistics": release["lexical_statistics"],
            "embedding_recipe": release["embedding_recipe"],
            "lexical_recipe": release["lexical_recipe"],
        }
