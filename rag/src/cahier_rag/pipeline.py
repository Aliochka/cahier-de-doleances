"""Relier le lecteur GDN à un stockage atomique, sans transaction source prolongée."""

from uuid import UUID

from cahier_rag.extraction import ExtractionError, ExtractionSpec
from cahier_rag.sources.gdn import GdnReader
from cahier_rag.storage import ExtractionState, RagStore


def run_extraction(
    store: RagStore,
    extraction_id: UUID,
    *,
    expected_spec: ExtractionSpec | None = None,
    max_batches: int | None = None,
) -> ExtractionState:
    if max_batches is not None and (type(max_batches) is not int or max_batches < 1):
        raise ExtractionError("max_batches doit être strictement positif.")
    state = store.get_state(extraction_id)
    spec = expected_spec or state.spec
    source = store.guard.source_identity()
    store.validate_resume(state, source, spec)
    reader = GdnReader(
        store.guard.source,
        corpus_id=spec.corpus_id,
        batch_size=spec.batch_size,
        questionnaire_id=spec.questionnaire_id,
        contribution_id=spec.contribution_id,
        unit_type=spec.unit_type,
    )
    batches = 0
    while state.status != "completed":
        reader.batch_size = min(spec.batch_size, spec.max_source_rows - state.source_row_count)
        batch = reader.read_batch(
            after=state.cursor,
            max_documents=min(spec.batch_size, spec.limit - state.document_count),
        )
        # read_batch a déjà fermé sa transaction et rendu sa connexion au pool.
        state = store.persist_batch(
            extraction_id,
            batch,
            expected_revision=state.revision,
            expected_spec=spec,
        )
        batches += 1
        if max_batches is not None and batches >= max_batches:
            break
    return state
