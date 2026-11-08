"""Read-only candidate adapters. Local ranks never enter global scoring."""

import hashlib
import time
from contextlib import contextmanager

from cahier_rag.search.service.control import SearchTimeout, SearchUnavailable
from cahier_rag.search.service.reader import ReadConnection
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from documentary.representations import ELIGIBLE, JOIN, LEXICAL_RECIPE, gate
from documentary.search import FILTERS as HISTORICAL_FILTERS
from documentary.search import group
from documentary.storage import SCOPE

from .core import score_expression


def candidate(corpus, row, branch):
    row = dict(row)
    return dict(row, corpus=corpus, key=f"{corpus}:{row['document_id']}", branch=branch)


class DocumentaryAdapter:
    corpus = "1789"
    capabilities = ("lexical", "exact-vector", "volume", "estate", "place", "full-reader")

    def __init__(
        self, destination, *, corpus="1789", scope=None, validator=gate, eligibility=ELIGIBLE
    ):
        self.scope = dict(SCOPE if scope is None else scope)
        if self.scope != SCOPE and validator is gate:
            raise ValueError(
                "A different documentary release requires its explicit publication validator"
            )
        self.corpus, self.validator = corpus, validator
        self.eligibility = eligibility
        self.destination = destination
        self.last_sql = {}
        self.pinned_identity = None

    @contextmanager
    def connection(self, budget):
        try:
            with self.destination.transaction(readonly=True) as raw:
                with budget.connection(raw.connection.driver_connection):
                    yield ReadConnection(raw, budget)
            budget.check()
        except DBAPIError as exc:
            budget.check()
            if getattr(exc.orig, "pgcode", None) == "57014":
                raise SearchTimeout(budget.stage) from None
            raise SearchUnavailable("Local documentary database unavailable") from None

    def identity(self, budget):
        with self.connection(budget) as c:
            release = self.validator(c)
            if (
                not release["statistics_ready"]
                or not release["representations_ready"]
                or release["lexical_recipe"] != LEXICAL_RECIPE
            ):
                raise ValueError("Historical laboratory representations unavailable")
            self.recipe = release["embedding_recipe"]
            identity = dict(
                corpus_id=self.scope["corpus"],
                release_id=self.scope["release"],
                editorial_hash=release["editorial_hash"],
                source_manifest_hash=release["source_manifest_hash"],
                embedding_recipe=self.recipe,
                lexical_statistics=release["lexical_statistics"],
                publication_authorized=bool(release["publication_authorized"]),
                active=bool(release["publication_authorized"]),
                laboratory_only=not release["publication_authorized"],
            )
            if self.pinned_identity is not None and self.pinned_identity != identity:
                raise ValueError(
                    "Documentary generation changed; restart and revalidate laboratory"
                )
            self.pinned_identity = identity
            return identity

    def parse(self, query, budget):
        with self.connection(budget) as c:
            return parse(c, query)

    def statistics(self, terms, budget):
        with self.connection(budget) as c:
            release = self.validator(c)
            return release["lexical_statistics"]["units"], dict(
                c.execute(
                    text("""
                SELECT term,document_frequency FROM documentary.lexical_term_statistics
                WHERE corpus_id=:corpus AND release_id=:release AND term=ANY(:terms)"""),
                    dict(self.scope, terms=terms),
                ).all()
            )

    def lexical(self, terms, weights, depth, filters, budget):
        params = dict(self.scope, **filters)
        score = score_expression(terms, weights, params, "u.search_vector", "d.metadata_vector")
        sql = f"""SELECT u.document_id,u.unit_id,u.ordinal,u.start_offset,u.end_offset,
            u.text_sha256 AS content_hash,d.display_title AS title,
            {score} AS score,u.search_vector @@ CAST(:query AS tsquery) AS text_match,
            d.metadata_vector @@ CAST(:query AS tsquery) AS metadata_match
            FROM {JOIN} WHERE {self.eligibility} {HISTORICAL_FILTERS}
            AND (u.search_vector @@ CAST(:query AS tsquery) OR d.metadata_vector @@ CAST(:query AS tsquery))"""
        self.last_sql["lexical"] = sql, dict(params)
        with self.connection(budget) as c:
            rows = c.execute(text(sql), params).mappings().all()
        begin = time.perf_counter()
        result = [candidate(self.corpus, r, "lexical") for r in group(rows, depth)]
        return result, dict(
            matched_units=len(rows),
            documents=len(result),
            exact=True,
            grouping_seconds=time.perf_counter() - begin,
        )

    def vector(self, vector, depth, filters, budget):
        params = dict(self.scope, **filters, vector=literal(vector))
        sql = f"""SELECT u.document_id,u.unit_id,u.ordinal,u.start_offset,u.end_offset,
            u.text_sha256 AS content_hash,d.display_title AS title,
            1-(u.embedding <=> CAST(:vector AS public.vector)) AS score
            FROM {JOIN} WHERE {self.eligibility} {HISTORICAL_FILTERS} AND u.embedding IS NOT NULL"""
        self.last_sql["vector"] = sql, dict(params)
        with self.connection(budget) as c:
            rows = c.execute(text(sql), params).mappings().all()
        begin = time.perf_counter()
        result = [candidate(self.corpus, r, "vector") for r in group(rows, depth, vector=True)]
        return result, dict(
            scored_units=len(rows),
            documents=len(result),
            exact=True,
            grouping_seconds=time.perf_counter() - begin,
        )

    def hydrate(self, ranked, budget, query=None):
        if not ranked:
            return {}
        with self.connection(budget) as c:
            rows = {
                r["unit_id"]: dict(r)
                for r in c.execute(
                    text(f"""
                SELECT u.unit_id,d.display_title,d.source_metadata->'metadata' AS metadata,
                d.provenance,d.warnings,d.source_title,d.text_sha256 AS document_hash,d.source_metadata,
                substring(d.full_text FROM u.start_offset+1 FOR u.end_offset-u.start_offset) AS passage,
                CASE WHEN CAST(:headline AS text) IS NOT NULL THEN ts_headline('pg_catalog.french',
                    substring(d.full_text FROM u.start_offset+1 FOR u.end_offset-u.start_offset),
                    CAST(:headline AS tsquery),'StartSel="", StopSel="", MaxFragments=1, MinWords=18, MaxWords=70') END AS snippet
                FROM {JOIN} WHERE {self.eligibility} AND u.unit_id=ANY(:ids)"""),
                    dict(self.scope, ids=[r["witness"]["unit_id"] for r in ranked], headline=query),
                ).mappings()
            }
        out = {}
        for r in ranked:
            w = r["witness"]
            d = rows[w["unit_id"]]
            if (
                w.get("content_hash")
                and hashlib.sha256(d["passage"].encode()).hexdigest() != w["content_hash"]
            ):
                raise ValueError("Historical witness no longer matches its immutable fingerprint")
            metadata_only = w["branch"] == "lexical" and not w["text_match"]
            out[r["key"]] = dict(
                title=d["display_title"],
                source_title=d["source_title"],
                document_hash=d["document_hash"],
                metadata=d["metadata"],
                provenance=d["provenance"],
                warnings=d["warnings"],
                excerpt=" ".join(
                    (d["passage"] if metadata_only else d["snippet"] or d["passage"]).split()
                )[:850],
                match_origin="metadata" if metadata_only else "text",
                url="/document?unit=" + w["unit_id"],
                content_kind="historical_document",
                corpus_id=self.scope["corpus"],
                release_id=self.scope["release"],
                publication_authorized=bool(
                    (self.pinned_identity or {}).get("publication_authorized", False)
                ),
            )
        return out


GDN_FILTERS = "d.space_id='full' AND (:question IS NULL OR CAST(d.record->>'question_id' AS bigint)=:question)"


class GdnAdapter:
    corpus = "2019"
    capabilities = ("lexical", "ann-vector", "question", "complete-answer")

    def __init__(self, reader, source=None):
        self.reader = reader
        self.source = source or reader.source
        self.last_sql = {}

    @contextmanager
    def connection(self, budget):
        with self.reader.store(budget).guard.transaction() as (c, _):
            yield c

    def identity(self, budget):
        generation = self.reader.validate(budget)
        published = getattr(self.reader, "publication", None) is not None
        return dict(
            corpus_id="gdn-2019",
            generation=generation,
            publication_authorized=True if published else None,
            publication_basis="validated signed H1 publication"
            if published
            else "verified local index; no public authorization inferred",
            laboratory_only=not published,
        )

    def parse(self, query, budget):
        with self.connection(budget) as c:
            return parse(c, query)

    def statistics(self, terms, budget):
        with self.connection(budget) as c:
            n = c.execute(
                text("SELECT documents FROM rag_tuning.statistics WHERE space_id='full'")
            ).scalar_one()
            df = dict(
                c.execute(
                    text(
                        "SELECT term,documents FROM rag_tuning.term_statistics WHERE space_id='full' AND term=ANY(:terms)"
                    ),
                    dict(terms=terms),
                ).all()
            )
            return n, df

    def lexical(self, terms, weights, depth, filters, budget):
        params = dict(question=filters["question"], depth=depth)
        score = score_expression(terms, weights, params, "d.search_vector")
        # Complete matching population: no TextUnit top-N approximation before answer grouping.
        sql = f"""WITH winners AS (
            SELECT DISTINCT ON(d.answer_id) d.answer_id,d.document_id AS unit_id,
                d.document_id COLLATE "C" AS tie_id,{score} AS score
            FROM rag_full.documents d WHERE {GDN_FILTERS}
                AND d.search_vector @@ CAST(:query AS tsquery)
            ORDER BY d.answer_id,score DESC,d.document_id COLLATE "C")
            SELECT answer_id::text AS document_id,unit_id,score
            FROM winners ORDER BY score DESC,answer_id::text COLLATE "C" LIMIT :depth"""
        self.last_sql["lexical"] = sql, dict(params)
        begin = time.perf_counter()
        with self.connection(budget) as c:
            rows = c.execute(text(sql), params).mappings().all()
        return [candidate(self.corpus, r, "lexical") for r in rows], dict(
            documents=len(rows),
            exact=True,
            grouping="SQL DISTINCT ON answer_id before LIMIT",
            sql_and_grouping_seconds=time.perf_counter() - begin,
            prefilter=None,
        )

    @staticmethod
    def configure_vector(c):
        for key, value in [
            ("ef_search", "1000"),
            ("iterative_scan", "strict_order"),
            ("max_scan_tuples", "20000"),
            ("scan_mem_multiplier", "1"),
        ]:
            c.execute(
                text("SELECT set_config(:key,:value,true)"),
                dict(key="hnsw." + key, value=value),
            )
        c.execute(text("SET LOCAL enable_seqscan=off"))

    def vector(self, vector, depth, filters, budget):
        params = dict(
            question=filters["question"], depth=depth, vector=literal(vector), candidates=400
        )
        with self.connection(budget) as c:
            self.configure_vector(c)
            exact_question = False
            if filters["question"] is not None:
                count = c.execute(
                    text(
                        f"SELECT count(*) FROM (SELECT 1 FROM rag_full.documents d WHERE {GDN_FILTERS} LIMIT 5001) p"
                    ),
                    params,
                ).scalar_one()
                exact_question = count <= 5000
            attempts = []
            while True:
                # Small question scope follows existing bounded exact-question protection.
                if exact_question:
                    source = f"""eligible AS MATERIALIZED (
                        SELECT d.space_id,d.document_id,d.answer_id FROM rag_full.documents d WHERE {GDN_FILTERS}),"""
                    join = "eligible d JOIN rag_full.segments s USING(space_id,document_id)"
                    where = "TRUE"
                    order = '(s.embedding <=> CAST(:vector AS public.vector))+0.0,s.document_id COLLATE "C",s.segment_index'
                else:
                    source = ""
                    join = (
                        "rag_full.segments s JOIN rag_full.documents d USING(space_id,document_id)"
                    )
                    where = GDN_FILTERS
                    order = "s.embedding <=> CAST(:vector AS public.vector)"
                sql = f"""WITH {source} nearest AS MATERIALIZED (
                    SELECT d.answer_id,s.document_id AS unit_id,s.segment_index,s.representation_id,
                        s.start_offset,s.end_offset,s.embedding <=> CAST(:vector AS public.vector) AS distance
                    FROM {join} WHERE {where} ORDER BY {order} LIMIT :candidates),
                    winners AS (SELECT DISTINCT ON(answer_id) * FROM nearest
                        ORDER BY answer_id,distance,unit_id COLLATE "C",segment_index,representation_id COLLATE "C")
                    SELECT answer_id::text AS document_id,unit_id,segment_index,representation_id,
                        start_offset,end_offset,1-distance AS score,(SELECT count(*) FROM nearest) AS scanned
                    FROM winners ORDER BY distance,answer_id::text COLLATE "C" LIMIT :depth"""
                self.last_sql["vector"] = sql, dict(params)
                rows = c.execute(text(sql), params).mappings().all()
                scanned = rows[0]["scanned"] if rows else 0
                attempts.append(
                    dict(requested=params["candidates"], returned=scanned, answers=len(rows))
                )
                if (
                    len(rows) >= depth
                    or scanned < params["candidates"]
                    or params["candidates"] >= 50000
                ):
                    break
                params["candidates"] = min(50000, params["candidates"] * 2)
        return [candidate(self.corpus, r, "vector") for r in rows], dict(
            documents=len(rows),
            attempts=attempts,
            segments_returned_total=sum(a["returned"] for a in attempts),
            retrieved_segments=scanned,
            requested_segments=params["candidates"],
            segment_cap=50000,
            cap_reached=params["candidates"] == 50000,
            mode="exact-question" if exact_question else "ann",
            exact=exact_question,
            ef_search=1000,
            max_scan_tuples=20000,
            exhausted_or_ann_limited=scanned < params["candidates"],
        )

    def label_candidates(self, rows, budget):
        if not rows:
            return
        with self.connection(budget) as c:
            titles = dict(
                c.execute(
                    text(
                        "SELECT document_id, record->'context'->>'question_text' FROM rag_full.documents WHERE space_id='full' AND document_id=ANY(:ids)"
                    ),
                    dict(ids=list({r["unit_id"] for r in rows})),
                ).all()
            )
        for r in rows:
            r["title"] = titles[r["unit_id"]]

    def answer(self, answer_id, budget):
        from cahier_rag.sources.gdn import ANSWER_SELECT, row_to_documents

        if not answer_id.isascii() or not answer_id.isdecimal() or not 0 < int(answer_id) < 2**63:
            raise ValueError("Positive answer ID required")
        guard = self.reader.store(budget).guard
        with guard._connect(self.source) as c:
            row = (
                c.execute(text(ANSWER_SELECT + " WHERE a.id=:id"), dict(id=int(answer_id)))
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise ValueError("Answer not found")
        units = row_to_documents(row, "gdn-2019")
        return dict(
            answer_id=answer_id,
            title=row["question_text"],
            form=row["questionnaire_name"],
            text="\n\n".join(u.text for u in units),
            contribution_url=f"/forms/{row['questionnaire_id']}/contributions/{row['contribution_id']}#answer-{answer_id}",
        )

    def hydrate(self, ranked, budget, query=None):
        if not ranked:
            return {}
        from cahier_rag.sources.gdn import ANSWER_SELECT, row_to_documents
        from cahier_rag.storage import restore_document

        with self.connection(budget) as c:
            units = {
                r["document_id"]: restore_document(r["record"])
                for r in c.execute(
                    text(
                        "SELECT document_id,record FROM rag_full.documents WHERE space_id='full' AND document_id=ANY(:ids)"
                    ),
                    dict(ids=[r["witness"]["unit_id"] for r in ranked]),
                ).mappings()
            }
        answers = [int(r["document_id"]) for r in ranked]
        # Source reads remain distinct from the search index. Existing reader role only.
        guard = self.reader.store(budget).guard
        with guard._connect(self.source) as c:
            rows = {
                str(r["answer_id"]): dict(r)
                for r in c.execute(
                    text(ANSWER_SELECT + " WHERE a.id=ANY(:ids)"),
                    dict(ids=answers),
                ).mappings()
            }
        out = {}
        for r in ranked:
            d = rows.get(r["document_id"])
            if not d:
                raise ValueError("Source answer unavailable")
            originals = {u.document_id: u for u in row_to_documents(d, "gdn-2019")}
            d.update(
                answer_id=str(d["answer_id"]),
                question=d["question_text"],
                form=d["questionnaire_name"],
                form_id=str(d["questionnaire_id"]),
                question_id=str(d["question_id"]),
                contribution_id=str(d["contribution_id"]),
            )
            w = r["witness"]
            unit = units[w["unit_id"]]
            if str(unit.answer_id) != r["document_id"]:
                raise ValueError("Witness/answer identity mismatch")
            if (
                unit.document_id not in originals
                or originals[unit.document_id].content_hash != unit.content_hash
            ):
                raise ValueError("Source content differs from indexed answer")
            start, end = w.get("start_offset", 0), w.get("end_offset", len(unit.text))
            if not 0 <= start < end <= len(unit.text):
                raise ValueError("Invalid witness offsets")
            w.update(start_offset=start, end_offset=end, content_hash=unit.content_hash)
            excerpt = unit.text[start:end]
            full_text = "\n\n".join(u.text for u in originals.values())
            out[r["key"]] = dict(
                title=d["question"],
                metadata={
                    k: d[k]
                    for k in (
                        "answer_id",
                        "contribution_id",
                        "question_id",
                        "question",
                        "form_id",
                        "form",
                    )
                },
                text=full_text,
                source_units=[
                    dict(
                        unit_id=u.document_id,
                        content_hash=u.content_hash,
                        unit_type=u.unit_type.value,
                        unit_index=u.unit_index,
                        text=u.text,
                    )
                    for u in originals.values()
                ],
                excerpt=" ".join(excerpt.split())[:850],
                warnings={},
                url=f"/2019/answer?id={d['answer_id']}",
                content_kind="questionnaire_answer",
                corpus_id="gdn-2019",
                publication_authorized=None,
                source_unit_id=w["unit_id"],
                contribution_url=f"/forms/{d['form_id']}/contributions/{d['contribution_id']}#answer-{d['answer_id']}",
            )
        return out


def parse(c, query):
    terms = c.execute(
        text("SELECT tsvector_to_array(to_tsvector('pg_catalog.french',:q))"), dict(q=query)
    ).scalar_one()
    quoted = (
        c.execute(
            text("SELECT quote_literal(t) FROM unnest(CAST(:terms AS text[])) t"), dict(terms=terms)
        )
        .scalars()
        .all()
    )
    return terms, quoted


def literal(vector):
    from cahier_rag.embeddings.core import validate_vectors

    values = validate_vectors([vector], expected_rows=1, dimension=1024, normalize=False)[0]
    return "[" + ",".join(str(v) for v in values) + "]"
