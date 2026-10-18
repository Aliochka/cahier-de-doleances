"""Transformations pures ; aucun accès PostgreSQL ni annotation humaine."""

from cahier_rag.contracts import TextUnit
from cahier_rag.representations.contracts import (
    PreparationConfig,
    PreparedContext,
    PreparedRepresentation,
    SourceReference,
    SourceSpan,
    Strategy,
)
from cahier_rag.representations.segmentation import segment_offsets


def structural_key(unit: TextUnit):
    return (
        unit.question_position is None,
        unit.question_position or 0,
        unit.question_id,
        unit.answer_position,
        unit.answer_id,
        unit.unit_index,
        unit.document_id,
    )


def prepare_unit(
    unit: TextUnit,
    *,
    config: PreparationConfig,
    sample_hash: str,
    split: str,
    parent: tuple[TextUnit, ...] = (),
    parent_unit_ids: tuple[str, ...] = (),
):
    if split not in {"development", "evaluation"}:
        raise ValueError("Partition inconnue.")
    if len({p.document_id for p in parent}) != len(parent):
        raise ValueError("Contexte dupliqué.")
    for neighbor in parent:
        if (neighbor.corpus_id, neighbor.contribution_id, neighbor.questionnaire_id) != (
            unit.corpus_id,
            unit.contribution_id,
            unit.questionnaire_id,
        ):
            raise ValueError("Contexte d’une autre contribution ou questionnaire.")
    if not parent_unit_ids:
        parent_unit_ids = tuple(sorted({unit.document_id, *(p.document_id for p in parent)}))
    if unit.document_id not in parent_unit_ids or not set(p.document_id for p in parent) <= set(
        parent_unit_ids
    ):
        raise ValueError("Contexte extérieur aux références parentes.")
    ordered = sorted({p.document_id: p for p in (*parent, unit)}.values(), key=structural_key)
    index = next(i for i, p in enumerate(ordered) if p.document_id == unit.document_id)
    neighbors = []
    if config.strategy == Strategy.D and len(unit.text) < config.short_chars:
        indices = sorted(
            (i for i in range(len(ordered)) if i != index), key=lambda i: (abs(i - index), i)
        )[: config.max_neighbors]
        neighbors = [ordered[i] for i in indices]
    primary_reference = SourceReference.from_unit(unit)
    source_references = (primary_reference, *(SourceReference.from_unit(p) for p in neighbors))
    primary_context = PreparedContext.from_unit(unit)
    for segment_index, (start, end) in enumerate(
        segment_offsets(unit.text, size=config.segment_chars, overlap=config.overlap_chars)
    ):
        if segment_index >= 1000:
            raise ValueError("Plus de 1000 segments pour une unité ; revoir les paramètres.")
        parts, spans = [], []
        length = 0

        def literal(text):
            nonlocal length
            parts.append(text)
            length += len(text)

        def source(document, field, begin, stop, role):
            begin_output = length
            literal(getattr(document, field)[begin:stop])
            spans.append(
                SourceSpan(document.document_id, field, begin, stop, begin_output, length, role)
            )

        if config.strategy != Strategy.A:
            literal("Question :\n")
            source(unit, "question_text", 0, len(unit.question_text), "primary-question")
            literal("\n\nRéponse :\n")
        source(unit, "text", start, end, "primary-answer")
        for neighbor in neighbors:
            literal("\n\nContexte — autre réponse de la même contribution :\nQuestion :\n")
            source(neighbor, "question_text", 0, len(neighbor.question_text), "neighbor-question")
            literal("\nRéponse (extrait) :\n")
            source(
                neighbor,
                "text",
                0,
                min(len(neighbor.text), config.neighbor_chars),
                "neighbor-answer",
            )
        yield PreparedRepresentation(
            config=config,
            sample_hash=sample_hash,
            split=split,
            primary=primary_reference,
            context=primary_context,
            parent_unit_ids=tuple(sorted(parent_unit_ids)),
            segment_index=segment_index,
            segment_start=start,
            segment_end=end,
            embedding_text="".join(parts),
            sources=source_references,
            spans=tuple(spans),
            enriched=bool(neighbors),
        )
