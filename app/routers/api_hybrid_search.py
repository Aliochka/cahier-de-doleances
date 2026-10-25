"""Unique contrat de recherche générale, utilisé par React SSR."""

import asyncio
import time
import unicodedata
from contextlib import suppress
from dataclasses import replace
from uuid import uuid4

from cahier_rag.search.service.control import (
    Budget,
    InvalidQuery,
    SearchBusy,
    SearchCancelled,
    SearchNotReady,
    SearchTimeout,
    SearchUnavailable,
)
from cahier_rag.search.service.core import SearchRecipe, validate_query
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

from app.hybrid_runtime import observe
from app.schemas.hybrid_search import (
    HybridErrorDetail,
    HybridErrorEnvelope,
    HybridSearchPage,
    HybridWarning,
    SearchWindow,
)
from app.schemas.questions import QueryId
from app.services.search_hydration import MetadataUnavailable
from app.services.search_snapshots import (
    CursorError,
    Snapshot,
    SnapshotExpired,
    group_hits,
    query_hash,
)

router = APIRouter(prefix="/api/v1", tags=["Hybrid search"])
HEADERS = {"Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, follow"}


def failure(request, status, code, message, retryable=False):
    request_id = getattr(request.state, "search_request_id", None) or uuid4().hex
    envelope = HybridErrorEnvelope(
        error=HybridErrorDetail(code=code, message=message, retryable=retryable),
        request_id=request_id,
    )
    headers = {**HEADERS, "X-Request-ID": request_id, "X-Robots-Tag": "noindex, nofollow"}
    if code == "search_busy":
        headers["Retry-After"] = "1"
    return JSONResponse(envelope.model_dump(), status_code=status, headers=headers)


def check_sources(backend, items):
    missing = sum(item is None for item in items)
    # Heuristique opérationnelle explicite, pas une certification exhaustive.
    if len(items) >= 5 and missing * 2 >= len(items):
        backend.cache.clear()
        backend.worker.service.ready = False
        raise SearchNotReady("Incohérence globale des sources.")
    return missing


def page(
    query,
    size,
    snapshot,
    items,
    *,
    sid=None,
    position=0,
    expires=None,
    cache=None,
    warnings=0,
    state=None,
):
    count = len(snapshot.cards)
    next_position = position + size
    has_next = next_position < count
    return HybridSearchPage(
        q=query,
        state=state or ("results" if items else "sources_unavailable"),
        recipe_version=snapshot.recipe_version,
        items=items,
        page_size=size,
        has_next=has_next,
        next_cursor=cache.cursor(sid, next_position) if has_next else None,
        previous_cursor=cache.cursor(sid, max(0, position - size)) if position else None,
        first_cursor=cache.cursor(sid, 0) if sid else None,
        expires_at=expires,
        window=SearchWindow(
            document_limit=snapshot.document_limit,
            retrieval_depth=snapshot.retrieval_depth,
            answer_count=count,
        ),
        warnings=[HybridWarning(count=warnings)] if warnings else [],
    )


async def calculate(backend, query, size, cursor, budget, metrics, question_id=None):
    if cursor is not None:
        sid, snapshot, position, expires = backend.cache.get(cursor, query, size, question_id)
        current = backend.worker.service
        if (
            snapshot.generation != current.reader.generation
            or snapshot.recipe_hash != current.recipe.fingerprint
        ):
            backend.cache.clear()
            raise SnapshotExpired()
        cards = snapshot.cards[position : position + size]
        items, seconds = await backend.hydrator.read(cards, budget)
        missing = check_sources(backend, items)
        metrics.update(cache_hit=True, hydration=seconds)
        return page(
            query,
            size,
            snapshot,
            [i for i in items if i is not None],
            sid=sid,
            position=position,
            expires=expires,
            cache=backend.cache,
            warnings=snapshot.omitted + missing,
        )

    filters = {"question_id": question_id} if question_id is not None else {}
    ranking = await backend.worker.retrieve(query, budget=budget, **filters)
    metrics.update(
        cache_hit=False,
        validation=ranking.timings.validation,
        encoding=ranking.timings.encoding,
        lexical=ranking.timings.lexical,
        vector=ranking.timings.vector,
        fusion=ranking.timings.fusion,
    )
    cards = group_hits(ranking.hits)
    items, seconds = await backend.hydrator.read(cards, budget)
    missing = check_sources(backend, items)
    metrics["hydration"] = seconds
    valid_cards, valid_items = [], []
    for card, item in zip(cards, items, strict=True):
        if item is not None:
            rank = len(valid_cards) + 1
            valid_cards.append(replace(card, rank=rank))
            valid_items.append(item.model_copy(update={"rank": rank}))
    recipe = backend.worker.service.recipe
    snapshot = Snapshot(
        query_hash(query, question_id),
        size,
        ranking.generation,
        ranking.recipe_hash,
        ranking.recipe_version,
        recipe.result_limit,
        recipe.depth,
        tuple(valid_cards),
        missing,
    )
    if not valid_cards:
        return page(
            query,
            size,
            snapshot,
            [],
            warnings=missing,
            state="sources_unavailable" if cards else "empty",
        )
    budget.check()
    sid, expires = backend.cache.put(snapshot)
    return page(
        query,
        size,
        snapshot,
        valid_items[:size],
        sid=sid,
        expires=expires,
        cache=backend.cache,
        warnings=missing,
    )


@router.get(
    "/search",
    response_model=HybridSearchPage,
    operation_id="search_public_hybrid",
    summary="Recherche hybride de réponses citoyennes classées par pertinence",
    description="Recherche naturelle, sans syntaxe booléenne globale promise. La fenêtre est bornée "
    "par la recette (initialement top 50 documentaire) et ne constitue pas un total exhaustif. "
    "Les curseurs authentifiés parcourent cette sélection pendant 10 minutes sans recalcul H1.",
    responses={status: {"model": HybridErrorEnvelope} for status in (410, 422, 500, 503, 504)},
)
async def search_hybrid(
    request: Request,
    q: str = Query(default="", max_length=512),
    page_size: int = Query(default=20, ge=1, le=20),
    cursor: str | None = Query(default=None, min_length=1, max_length=1024),
    question_id: QueryId | None = None,
):
    started = time.monotonic()
    request.state.search_request_id = uuid4().hex
    budget = Budget(18)
    metrics = {"cache_hit": False}
    watcher = None
    backend = getattr(request.app.state, "hybrid_search", None)
    try:
        allowed = {"q", "page_size", "cursor", "question_id"}
        if any(
            k not in allowed or len(request.query_params.getlist(k)) != 1
            for k in request.query_params
        ):
            raise InvalidQuery("Paramètre inconnu ou répété.")
        question_id = int(question_id) if question_id is not None else None
        query = unicodedata.normalize("NFC", q).strip()
        if not query:
            if cursor is not None:
                raise CursorError()
            recipe = backend.worker.service.recipe if backend else SearchRecipe()
            result = page(
                query,
                page_size,
                Snapshot(
                    query_hash(query, question_id),
                    page_size,
                    "",
                    "",
                    recipe.version,
                    recipe.result_limit,
                    recipe.depth,
                    (),
                ),
                [],
                state="idle",
            )
        else:
            query = validate_query(q)
            if backend is None:
                raise SearchNotReady("Recherche indisponible.")

            async def watch_disconnect():
                while True:
                    if await request.is_disconnected():
                        budget.cancellation.set()
                        return
                    await asyncio.sleep(0.05)

            watcher = asyncio.create_task(watch_disconnect())
            result = await calculate(
                backend, query, page_size, cursor, budget, metrics, question_id
            )
        with budget.phase("serialization"):
            content = result.model_dump_json()
        metrics["total"] = time.monotonic() - started
        observe(metrics)
        return Response(
            content,
            media_type="application/json",
            headers={**HEADERS, "X-Request-ID": request.state.search_request_id},
        )
    except (InvalidQuery, CursorError) as exc:
        return failure(
            request,
            422,
            "invalid_cursor" if isinstance(exc, CursorError) else "invalid_query",
            "Requête ou curseur invalide. Vérifiez la saisie et les paramètres.",
        )
    except SnapshotExpired:
        return failure(
            request, 410, "search_expired", "Cette sélection a expiré. Relancez la recherche."
        )
    except SearchTimeout as exc:
        code = {
            "metadata": "search_metadata_timeout",
            "encoding": "search_encoding_timeout",
            "sql": "search_sql_timeout",
        }.get(exc.stage, "search_timeout")
        return failure(
            request,
            504,
            code,
            "La recherche a pris trop de temps. Réessayez ou précisez votre question.",
            True,
        )
    except SearchBusy:
        return failure(
            request,
            503,
            "search_busy",
            "La recherche est très sollicitée. Réessayez dans un instant.",
            True,
        )
    except SearchNotReady:
        if backend is not None:
            backend.cache.clear()
        return failure(
            request,
            503,
            "search_not_ready",
            "La recherche est momentanément indisponible. Réessayez plus tard.",
            True,
        )
    except MetadataUnavailable:
        return failure(
            request,
            503,
            "search_metadata_unavailable",
            "Les réponses ne peuvent pas être consultées momentanément. Réessayez plus tard.",
            True,
        )
    except SearchUnavailable:
        return failure(
            request,
            503,
            "search_unavailable",
            "La recherche est momentanément indisponible. Réessayez plus tard.",
            True,
        )
    except SearchCancelled:
        return failure(request, 504, "search_cancelled", "La recherche a été interrompue.", True)
    except asyncio.CancelledError:
        budget.cancellation.set()
        raise
    except Exception:
        return failure(
            request, 500, "search_internal_error", "La recherche n’a pas pu aboutir.", True
        )
    finally:
        if watcher is not None:
            watcher.cancel()
            with suppress(asyncio.CancelledError):
                await watcher
