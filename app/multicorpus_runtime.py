"""Controlled application integration, compact snapshots, unchanged H1 fallback."""

import asyncio
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from cahier_rag.search.service.control import InvalidQuery, SearchBusy, SearchNotReady
from cahier_rag.search.service.worker import SearchWorker
from fastapi import HTTPException

from app.documentary_access import (
    PUBLIC_ELIGIBLE,
    DocumentaryRepository,
    document_url,
    reference_text,
)
from app.helpers import slugify
from app.schemas.documentary import HistoricalSearchResult
from app.schemas.hybrid_search import (
    HybridAnswer,
    HybridForm,
    HybridQuestion,
    HybridSearchPage,
    HybridText,
    SearchWindow,
)
from app.services.search_snapshots import SnapshotExpired, query_hash
from multicorpus.adapters import DocumentaryAdapter, GdnAdapter
from multicorpus.core import MultiSearch


@dataclass(frozen=True)
class CommonCard:
    key: str
    corpus: str
    document_id: str
    rank: int
    witness: dict
    source_units: tuple


@dataclass(frozen=True)
class CommonSnapshot:
    query_hash: str
    page_size: int
    generation: dict
    recipe_hash: str
    recipe_version: str
    document_limit: int
    retrieval_depth: int
    cards: tuple[CommonCard, ...]


def card(item):
    keep = {
        "unit_id",
        "ordinal",
        "start_offset",
        "end_offset",
        "segment_index",
        "representation_id",
        "content_hash",
        "branch",
        "text_match",
        "metadata_match",
    }
    return CommonCard(
        item["key"],
        item["corpus"],
        item["document_id"],
        item["rank"],
        {k: v for k, v in item["witness"].items() if k in keep},
        tuple({k: v for k, v in u.items() if k != "text"} for u in item.get("source_units", [])),
    )


def present(item, repository):
    w = item["witness"]
    if item["corpus"] == "2019":
        m = item["metadata"]
        remaining = 1000
        texts = []
        truncated = False
        for u in item["source_units"]:
            value = u["text"][:remaining]
            remaining -= len(value)
            truncated |= len(value) < len(u["text"])
            texts.append(
                HybridText(unit_type=u["unit_type"], unit_index=u["unit_index"], text=value)
            )
        return HybridAnswer(
            answer_id=item["document_id"],
            contribution_id=m["contribution_id"],
            rank=item["rank"],
            texts=texts,
            is_truncated=truncated,
            question=HybridQuestion(
                id=m["question_id"],
                prompt=m["question"],
                url=f"/questions/{m['question_id']}-{slugify(m['question'] or 'question-' + m['question_id'])}",
            ),
            form=HybridForm(id=m["form_id"], name=m["form"], url=f"/forms/{m['form_id']}"),
            url=item["contribution_url"],
        )
    m = item["metadata"]
    original = m.get("original_metadata") or {}
    return HistoricalSearchResult(
        document_id=item["document_id"],
        release_id=item["release_id"],
        title=item["title"],
        source_title=item["source_title"],
        place=(m.get("origin") or {}).get("label"),
        orders=m.get("historical_orders", [])
        if m.get("historical_orders_status") == "explicit_in_metadata_title"
        else [],
        reference=reference_text(original.get("bibliographic_citation")),
        sources=[
            dict(label=label, url=url)
            for label, url in [
                ("Notice Persée", original.get("document_url")),
                ("Transcription Stanford", item["provenance"].get("scan_url")),
            ]
            if isinstance(url, str) and url.startswith("https://")
        ],
        warnings=[dict(code=k, message=v["message"]) for k, v in item["warnings"].items()],
        rank=item["rank"],
        excerpt=item["excerpt"],
        unit_id=w["unit_id"],
        start_offset=w["start_offset"],
        end_offset=w["end_offset"],
        match_origin=item.get("match_origin", "text"),
        url=document_url(item["document_id"], item["release_id"], w["unit_id"]),
    )


class CommonService:
    def __init__(self, backend, repository):
        self.backend, self.repository = backend, repository
        self.engines = {}
        self.closed = False

    @property
    def ready(self):
        return self.backend.worker.ready and self.repository.ready and not self.closed

    def close(self):
        self.closed = True

    def start(self):
        pass

    def engine(self, preview):
        if preview not in self.engines:
            h1 = self.backend.worker.service
            self.repository.query_snapshot = h1.encoder.backend.snapshot_hash
            adapter = DocumentaryAdapter(
                self.repository.destination,
                validator=lambda c: self.repository.search_gate(c, preview=preview),
                eligibility=(
                    "u.corpus_id=:corpus AND u.release_id=:release AND d.candidate AND u.searchable"
                    if preview
                    else PUBLIC_ELIGIBLE
                ),
            )
            self.engines[preview] = MultiSearch(
                [GdnAdapter(h1.reader, self.backend.hydrator.engine), adapter], h1.encoder
            )
        return self.engines[preview]

    def retrieve(self, payload, *, budget, question_id=None):
        ranking = payload["action"] == "search"
        if self.closed or not self.repository.ready or (ranking and not self.ready):
            raise SearchNotReady("Recherche multicorpus indisponible")
        h1 = self.backend.worker.service
        # Both workers share this existing model; never encode concurrently with H1.
        if ranking and not h1._lock.acquire(blocking=False):
            raise SearchBusy("Une recherche est déjà en cours")
        try:
            preview = payload["preview"]
            engine = self.engine(preview)
            if payload["action"] == "search":
                selection = payload["corpus"]
                available = (
                    self.repository.available(preview=preview) if selection != "2019" else False
                )
                if selection == "1789" and not available:
                    raise InvalidQuery("Corpus historique indisponible")
                effective = "2019" if selection == "tous" and not available else selection
                result = engine.search(payload["q"], corpus=effective, budget=budget)
                return dict(
                    items=[present(i, self.repository) for i in result["items"]],
                    cards=tuple(card(i) for i in result["items"]),
                    generation=result["publication"],
                    timings=result["timings"],
                    recipe="multicorpus-application-1",
                )
            snapshot = payload["snapshot"]
            adapters = {k: engine.adapters[k] for k in snapshot.generation}
            with budget.monitor(), budget.phase("hydration", 2):
                for k, a in adapters.items():
                    if a.identity(budget) != snapshot.generation[k]:
                        raise SnapshotExpired()
                items = {}
                for k, a in adapters.items():
                    cards = [c for c in payload["cards"] if c.corpus == k]
                    rows = [
                        dict(
                            key=c.key, corpus=c.corpus, document_id=c.document_id, witness=c.witness
                        )
                        for c in cards
                    ]
                    hydrated = a.hydrate(rows, budget)
                    for c in cards:
                        value = dict(
                            hydrated[c.key],
                            key=c.key,
                            corpus=c.corpus,
                            document_id=c.document_id,
                            rank=c.rank,
                            witness=c.witness,
                        )
                        if (
                            c.source_units
                            and tuple(
                                {k: v for k, v in u.items() if k != "text"}
                                for u in value["source_units"]
                            )
                            != c.source_units
                        ):
                            raise SnapshotExpired()
                        items[c.key] = present(value, self.repository)
                return [items[c.key] for c in payload["cards"]]
        except ValueError as exc:
            if not ranking:
                raise SnapshotExpired() from None
            if str(exc) == "Maximum 32 significant lexemes":
                raise InvalidQuery("Au plus 32 lexèmes significatifs") from None
            raise SearchNotReady("Génération documentaire incompatible") from None
        except KeyError:
            if ranking:
                raise SearchNotReady("Sources documentaires incompatibles") from None
            raise SnapshotExpired() from None
        except HTTPException as exc:
            if not ranking and exc.status_code == 404:
                raise SnapshotExpired() from None
            raise
        finally:
            if ranking:
                h1._lock.release()


class CommonIntegration:
    def __init__(self, backend, config):
        self.repository = DocumentaryRepository(backend.worker.service.reader.target, config)
        self.service = CommonService(backend, self.repository)
        self.worker = SearchWorker(self.service)
        self.cache = backend.cache
        self.read_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="documentary-read"
        )
        self.read_lock = threading.Lock()
        self.pending = 0

    async def start(self):
        await asyncio.to_thread(self.repository.start)

    async def read(self, fn):
        with self.read_lock:
            if self.pending >= 4:
                raise SearchBusy("Lecture documentaire occupée")
            self.pending += 1
        future = self.read_executor.submit(fn)

        def finished(_):
            with self.read_lock:
                self.pending -= 1

        future.add_done_callback(finished)
        return await asyncio.shield(asyncio.wrap_future(future))

    async def close(self):
        self.cache.clear()
        await self.worker.close()
        await asyncio.to_thread(self.read_executor.shutdown, wait=True, cancel_futures=True)

    async def calculate(self, query, size, cursor, selection, preview, budget, metrics):
        binding = json.dumps(dict(q=query, corpus=selection, preview=preview), sort_keys=True)
        sid = None
        position = 0
        expires = None
        if cursor:
            sid, snapshot, position, expires = self.cache.get(cursor, binding, size)
            payload = dict(
                action="page",
                preview=preview,
                snapshot=snapshot,
                cards=snapshot.cards[position : position + size],
            )
            items = await self.read(lambda: self.service.retrieve(payload, budget=budget))
            metrics["cache_hit"] = True
        else:
            result = await self.worker.retrieve(
                dict(action="search", preview=preview, corpus=selection, q=query), budget=budget
            )
            snapshot = CommonSnapshot(
                query_hash(binding),
                size,
                result["generation"],
                "multicorpus-application-1",
                result["recipe"],
                50,
                50,
                result["cards"],
            )
            items = result["items"][:size]
            metrics.update(cache_hit=False, **result["timings"])
            if snapshot.cards:
                sid, expires = self.cache.put(snapshot)
        count = len(snapshot.cards)
        has_next = position + size < count
        return HybridSearchPage(
            q=query,
            corpus=selection,
            preview=preview and "1789" in snapshot.generation,
            state="results" if items else "empty",
            recipe_version=snapshot.recipe_version,
            items=items,
            page_size=size,
            has_next=has_next,
            next_cursor=self.cache.cursor(sid, position + size) if has_next else None,
            previous_cursor=self.cache.cursor(sid, max(0, position - size)) if position else None,
            first_cursor=self.cache.cursor(sid, 0) if sid else None,
            expires_at=expires,
            window=SearchWindow(document_limit=50, retrieval_depth=50, answer_count=count),
            warnings=[],
        )


def configure(backend):
    path = os.environ.get("MULTICORPUS_CONFIG_FILE")
    if not path:
        return None
    config = json.loads(Path(path).read_text())
    if config.get("enabled") is not True:
        return None
    return CommonIntegration(backend, config)
