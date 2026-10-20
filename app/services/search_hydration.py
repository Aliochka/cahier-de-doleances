"""Hydratation applicative en un lot ; les documents RAG ne sont jamais affichés."""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from cahier_rag.search.service.control import SearchBusy, SearchTimeout, SearchUnavailable
from cahier_rag.search.service.reader import ReadConnection
from cahier_rag.sources.gdn import ANSWER_SELECT, row_to_documents
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError

from app.helpers import slugify
from app.schemas.hybrid_search import HybridAnswer, HybridForm, HybridQuestion, HybridText


class MetadataUnavailable(SearchUnavailable):
    pass


def public_card(card, row):
    if row is None:
        return None
    try:
        originals = {d.document_id: d for d in row_to_documents(row, "gdn-2019")}
        texts = []
        remaining, truncated = 1000, False
        for ref in sorted(card.units, key=lambda r: (r.unit_index, r.document_id)):
            original = originals.get(ref.document_id)
            if (
                original is None
                or original.content_hash != ref.content_hash
                or (
                    original.answer_id,
                    original.question_id,
                    original.contribution_id,
                    original.questionnaire_id,
                )
                != (ref.answer_id, ref.question_id, ref.contribution_id, ref.form_id)
            ):
                return None
            value = original.text[:remaining]
            remaining -= len(value)
            truncated |= len(value) < len(original.text)
            # Conserver l'identité de chaque champ Autre, même si son extrait est vide.
            texts.append(HybridText(unit_type=ref.unit_type, unit_index=ref.unit_index, text=value))
        first = card.units[0]
        return HybridAnswer(
            answer_id=str(first.answer_id),
            contribution_id=str(first.contribution_id),
            rank=card.rank,
            texts=texts,
            is_truncated=truncated,
            question=HybridQuestion(
                id=str(first.question_id),
                prompt=row["question_text"],
                url=f"/questions/{first.question_id}-{slugify(row['question_text'] or f'question-{first.question_id}')}",
            ),
            form=HybridForm(
                id=str(first.form_id), name=row["questionnaire_name"], url=f"/forms/{first.form_id}"
            ),
            url=f"/forms/{first.form_id}/contributions/{first.contribution_id}#answer-{first.answer_id}",
        )
    except (ValueError, TypeError, KeyError):
        return None


class Hydrator:
    def __init__(self, engine):
        self.engine = engine
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="search-hydration")
        self.lock = threading.Lock()
        self.pending = 0

    def _read(self, cards, budget):
        started = time.monotonic()
        with budget.phase("metadata", 2), budget.monitor():
            try:
                budget.check()
                with self.engine.connect() as raw:
                    raw = raw.execution_options(postgresql_readonly=True)
                    with budget.connection(raw.connection.driver_connection), raw.begin():
                        connection = ReadConnection(raw, budget)
                        rows = (
                            connection.execute(
                                text(ANSWER_SELECT + " WHERE a.id=ANY(:ids)"),
                                {"ids": list({card.units[0].answer_id for card in cards})},
                            )
                            .mappings()
                            .all()
                        )
                budget.check()
            except DBAPIError as exc:
                budget.check()
                if getattr(exc.orig, "pgcode", None) == "57014":
                    raise SearchTimeout("metadata") from None
                if isinstance(exc, OperationalError):
                    raise MetadataUnavailable("Hydratation indisponible.") from None
                raise
            except SQLAlchemyError:
                budget.check()
                raise MetadataUnavailable("Hydratation indisponible.") from None
            by_id = {row["answer_id"]: row for row in rows}
            items = [public_card(card, by_id.get(card.units[0].answer_id)) for card in cards]
        return items, time.monotonic() - started

    async def read(self, cards, budget):
        if not cards:
            return [], 0.0
        with self.lock:
            if self.pending >= 4:
                raise SearchBusy("Hydratation saturée.")
            self.pending += 1
        try:
            future = self.executor.submit(self._read, cards, budget)
        except RuntimeError:
            with self.lock:
                self.pending -= 1
            raise SearchUnavailable("Hydratation arrêtée.") from None

        def finished(_):
            with self.lock:
                self.pending -= 1

        future.add_done_callback(finished)
        wrapped = asyncio.wrap_future(future)
        wrapped.add_done_callback(lambda f: None if f.cancelled() else f.exception())
        try:
            while not wrapped.done():
                budget.check()
                await asyncio.wait({wrapped}, timeout=min(0.025, max(0, budget.remaining())))
            return wrapped.result()
        except BaseException:
            budget.cancellation.set()
            future.cancel()
            raise

    async def close(self):
        await asyncio.to_thread(self.executor.shutdown, wait=True, cancel_futures=True)
        self.engine.dispose()
