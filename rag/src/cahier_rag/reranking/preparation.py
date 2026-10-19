"""Segmentation commune vérifiée par les tokenizers réels, sans perte ni nettoyage."""

import re

from cahier_rag.reranking.contracts import Pair, PreparationConfig


def contextualize(question, answer, config):
    return (
        answer
        if config.contextualization == "answer"
        else f"Question :\n{question}\n\nRéponse :\n{answer}"
    )


def segments(query_id, query, unit, backends, config=PreparationConfig()):
    if not backends:
        raise ValueError("Au moins un tokenizer requis.")
    prefix = contextualize(unit.question_text, "", config)
    if any(b.token_count(query, prefix) + 16 >= config.budget for b in backends):
        raise ValueError("Contexte de question/requête trop long ; aucune troncature.")
    start, index = 0, 0
    while start < len(unit.text):
        low, high = start + 1, min(len(unit.text), start + config.budget * 32)
        best = None
        while low <= high:
            middle = (low + high) // 2
            value = contextualize(unit.question_text, unit.text[start:middle], config)
            if all(b.token_count(query, value) <= config.budget for b in backends):
                best, low = middle, middle + 1
            else:
                high = middle - 1
        if best is None:
            raise ValueError("Aucun caractère ne tient dans le budget.")
        end = best
        if end < len(unit.text):
            boundaries = list(re.finditer(r"\n\s*\n|[.!?](?:\s+|$)", unit.text[start:end]))
            if boundaries and boundaries[-1].end() >= (end - start) // 2:
                end = start + boundaries[-1].end()
        value = contextualize(unit.question_text, unit.text[start:end], config)
        if any(b.token_count(query, value) > config.budget for b in backends):
            raise ValueError("Segmentation hors budget.")
        yield Pair(query_id, unit.document_id, unit.content_hash, query, value, start, end, index)
        if end == len(unit.text):
            break
        next_start = end - config.overlap_chars
        if next_start <= start or end <= start:
            raise ValueError("Segmentation sans progression.")
        start, index = next_start, index + 1
        if index >= 1000:
            raise ValueError("Plafond de 1000 segments par unité atteint.")
