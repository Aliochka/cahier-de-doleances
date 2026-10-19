"""Adaptation des scores aux SearchResult existants, sans dépendance de modèle."""

from cahier_rag.reranking.contracts import validate_scores
from cahier_rag.search.lexical import SearchResult


def rerank_results(results, records):
    """records est le cache validé pour UNE requête et UNE recette."""
    ids = [r.document.document_id for r in results]
    if len(set(ids)) != len(ids):
        raise ValueError("Résultat documentaire dupliqué.")
    output = []
    for result in results:
        doc = result.document
        record = records.get(doc.document_id)
        if record is None or record["source_hash"] != doc.content_hash:
            raise ValueError("Score absent ou document modifié.")
        score = validate_scores([record["score"]], 1)[0]
        output.append(SearchResult(doc, score))
    return sorted(output, key=lambda r: (-r.score, r.document.document_id))
