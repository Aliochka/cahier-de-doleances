"""Sélection de rang, extraits exacts et budget global contrôlé sur le JSON rendu."""

import re
import unicodedata
from collections import Counter

from cahier_rag.context.contracts import ContextConfig, ContextSource
from cahier_rag.contracts import canonical_json
from cahier_rag.evaluation.sampling import digest


def model_block(source, mode):
    value = {
        "reference": source.reference,
        "citizen_text": source.citizen_text,
        "technical": {
            "role": source.role,
            "start": source.start,
            "end": source.end,
            "original_length": len(source.unit.text),
        },
    }
    if mode != "P0":
        value["metadata"] = {
            "question": source.unit.question_text,
            "questionnaire": source.unit.questionnaire_name,
            "contribution_title": source.unit.contribution_title,
        }
    return value


def render(sources, mode, *, without_text=False):
    blocks = [model_block(s, mode) for s in sources]
    if without_text:
        for block in blocks:
            block["citizen_text"] = ""
    return canonical_json({"sources": blocks})


def prefix_end(text, counter, budget):
    if budget < 1:
        return 0
    lo, hi = 0, min(len(text), budget * 32 + 1024)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if counter.count(text[:mid]) <= budget:
            lo = mid
        else:
            hi = mid - 1
    if lo < len(text):
        boundaries = [
            m.end() for m in re.finditer(r"\n\s*\n|[.!?](?:\s+|$)", text[:lo]) if m.end() >= lo // 2
        ]
        if boundaries:
            lo = boundaries[-1]
    while lo and counter.count(text[:lo]) > budget:
        lo -= 1
    return lo


def segment_text(text, counter, *, budget=768):
    """Segmentation sans chevauchement ; la concaténation reconstruit la source."""
    start = 0
    while start < len(text):
        end = start + prefix_end(text[start:], counter, budget)
        if end <= start:
            raise ValueError("Impossible de segmenter sans dépassement.")
        yield start, end
        start = end


def similar(a, b, config):
    # La question définit le sens des réponses courtes, notamment « oui » et « non ».
    if (a.corpus_id, a.questionnaire_id, a.question_id) != (
        b.corpus_id,
        b.questionnaire_id,
        b.question_id,
    ):
        return None
    if a.text == b.text:
        return "exact"
    x = re.findall(r"\w+", unicodedata.normalize("NFKC", a.text).casefold())
    y = re.findall(r"\w+", unicodedata.normalize("NFKC", b.text).casefold())
    if not x or not y:
        return None
    if x == y:
        return "normalized_equal"
    negations = {"ne", "n", "pas", "non", "jamais", "sans", "aucun", "aucune", "ni"}
    if set(x) & negations != set(y) & negations or [v for v in x if v.isdecimal()] != [
        v for v in y if v.isdecimal()
    ]:
        return None
    if min(len(x), len(y)) < config.near_min_words:
        return None
    ratio = min(len(a.text), len(b.text)) / max(len(a.text), len(b.text))
    jaccard = len(set(x) & set(y)) / len(set(x) | set(y))
    return "near" if ratio >= config.near_length_ratio and jaccard >= config.near_jaccard else None


def fit_source(
    unit,
    sources,
    counter,
    config,
    cap,
    *,
    sample_hash,
    method,
    rank,
    role="primary",
    parent_document_id=None,
):
    end = prefix_end(unit.text, counter, config.excerpt_tokens)
    if not end:
        return None

    def source(n):
        return ContextSource(unit, sample_hash, 0, n, method, rank, role, parent_document_id)

    def fits(n):
        return counter.count(render([*sources, source(n)], config.parent_mode)) <= cap

    if not fits(end):
        lo, hi = 0, end
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if fits(mid):
                lo = mid
            else:
                hi = mid - 1
        end = lo
        if not end or counter.count(unit.text[:end]) < min(
            config.min_partial_tokens, counter.count(unit.text)
        ):
            return None
        # Toute coupe destinée au budget conserve ses positions ; aucune ellipse ajoutée.
    result = source(end)
    if not fits(end) or counter.count(result.citizen_text) > config.excerpt_tokens:
        raise ValueError("Budget de contexte incohérent.")
    return result


def assemble(query, ranked_ids, repository, counter, *, method, config=ContextConfig()):
    if query.get("split") != "development" or not query.get("text"):
        raise ValueError("Seules les requêtes de développement sont autorisées.")
    if not method or len(ranked_ids) > 50 or len(set(ranked_ids)) != len(ranked_ids):
        raise ValueError("Classement dupliqué ou supérieur au top 50.")
    docs = repository.fetch(ranked_ids) if ranked_ids else {}
    if set(docs) != set(ranked_ids):
        raise ValueError("Document classé manquant.")
    for unit in docs.values():
        repository.validate(unit)
    primary, excluded, duplicates = [], [], []
    primary_cap = (
        int(config.document_budget * (1 - config.expansion_fraction))
        if config.parent_mode == "P2"
        else config.document_budget
    )
    if counter.count(render([], config.parent_mode)) > primary_cap:
        raise ValueError("Budget insuffisant pour l’enveloppe documentaire.")
    for index, did in enumerate(ranked_ids):
        unit = docs[did]
        if len(primary) >= config.max_primary:
            excluded += [
                {"document_id": d, "rank": i + 1, "reason": "primary_limit"}
                for i, d in enumerate(ranked_ids)
                if i >= index
            ]
            break
        if config.selection == "S2" and any(
            (s.unit.corpus_id, s.unit.contribution_id) == (unit.corpus_id, unit.contribution_id)
            for s in primary
        ):
            excluded.append({"document_id": did, "rank": index + 1, "reason": "same_contribution"})
            continue
        duplicate = (
            next(((s, kind) for s in primary if (kind := similar(s.unit, unit, config))), None)
            if config.selection == "S3"
            else None
        )
        if duplicate:
            source, kind = duplicate
            duplicates.append(
                {
                    "representative_reference": source.reference,
                    "document_id": did,
                    "contribution_id": str(unit.contribution_id),
                    "document_hash": unit.content_hash,
                    "rank": index + 1,
                    "match": kind,
                }
            )
            excluded.append({"document_id": did, "rank": index + 1, "reason": "text_repetition"})
            continue
        source = fit_source(
            unit,
            primary,
            counter,
            config,
            primary_cap,
            sample_hash=repository.scope.sample_hash,
            method=method,
            rank=index + 1,
        )
        if source is None:
            excluded += [
                {"document_id": d, "rank": i + 1, "reason": "budget"}
                for i, d in enumerate(ranked_ids)
                if i >= index
            ]
            break
        primary.append(source)
    sources = list(primary)
    expansion = []
    primary_tokens = counter.count(render(primary, config.parent_mode))
    expansion_cap = min(
        config.document_budget,
        primary_tokens + int(config.document_budget * config.expansion_fraction),
    )
    added = {s.unit.document_id for s in primary}
    if config.parent_mode == "P2":
        for source in primary:
            for unit in repository.neighbors(source.unit, config.max_neighbors):
                repository.validate(unit)
                if (unit.corpus_id, unit.contribution_id, unit.questionnaire_id) != (
                    source.unit.corpus_id,
                    source.unit.contribution_id,
                    source.unit.questionnaire_id,
                ):
                    raise ValueError("Contexte complémentaire d’une autre contribution.")
                if unit.document_id in added:
                    expansion.append(
                        {
                            "document_id": unit.document_id,
                            "parent_document_id": source.unit.document_id,
                            "status": "already_present",
                        }
                    )
                    continue
                complement = fit_source(
                    unit,
                    sources,
                    counter,
                    config,
                    expansion_cap,
                    sample_hash=repository.scope.sample_hash,
                    method=method,
                    rank=None,
                    role="complementary",
                    parent_document_id=source.unit.document_id,
                )
                expansion.append(
                    {
                        "document_id": unit.document_id,
                        "parent_document_id": source.unit.document_id,
                        "status": "included" if complement else "budget",
                    }
                )
                if complement:
                    sources.append(complement)
                    added.add(unit.document_id)
    payload = render(sources, config.parent_mode)
    total = counter.count(payload)
    if (
        total > config.document_budget
        or total - primary_tokens > int(config.document_budget * config.expansion_fraction)
        and config.parent_mode == "P2"
    ):
        raise ValueError("Dépassement explicite du budget de contexte.")
    metadata_tokens = counter.count(render(sources, config.parent_mode, without_text=True))
    citations = {s.reference: s.to_dict() for s in sources}
    if len(citations) != len(sources):
        raise ValueError("Collision de référence de contexte.")
    for ref, row in citations.items():
        occurrences = [d for d in duplicates if d["representative_reference"] == ref]
        row["technical"]["observed_repetitions"] = {
            "scope": "examined prefix of this top50 list; lower bound, not corpus frequency",
            "units_including_representative": 1 + len(occurrences),
            "contributions_including_representative": len(
                {row["metadata"]["contribution_id"], *[d["contribution_id"] for d in occurrences]}
            ),
            "suppressed_occurrences": occurrences,
        }
    all_lengths = [len(s.unit.text) for s in primary]
    text_counts = Counter(s.unit.text for s in primary)
    result = {
        "version": 1,
        "query_id": query["query_id"],
        "query_hash": digest(query["text"]),
        "sample_hash": repository.scope.sample_hash,
        "method": method,
        "configuration": config.to_dict(),
        "tokenizer": counter.description,
        "model_document_payload": payload,
        "citation_map": citations,
        "excluded": excluded,
        "expansion": expansion,
        "budget": {
            "document_limit": config.document_budget,
            "document_used": total,
            "metadata_reference_tokens": metadata_tokens,
            "citizen_incremental_tokens": total - metadata_tokens,
            "instructions_reserved": config.instructions_reserved,
            "answer_reserved": config.answer_reserved,
            "envelope_reserved": config.envelope_reserved,
            "query_tokens": counter.count(query["text"]),
            "minimum_total_window": config.document_budget
            + config.instructions_reserved
            + config.answer_reserved
            + config.envelope_reserved
            + counter.count(query["text"]),
            "citation_map_out_of_band_tokens": counter.count(canonical_json(citations)),
            "expansion_incremental_tokens": total - primary_tokens,
        },
        "statistics": {
            "primary_documents": len(primary),
            "contributions": len({(s.unit.corpus_id, s.unit.contribution_id) for s in primary}),
            "complementary_documents": len(sources) - len(primary),
            "short_primary": sum(n < 60 for n in all_lengths),
            "long_primary": sum(n > 2000 for n in all_lengths),
            "excerpted_sources": sum(s.end < len(s.unit.text) for s in sources),
            "identical_primary_repeats": sum(v - 1 for v in text_counts.values()),
            "suppressed_repetitions": len(duplicates),
            "excluded_budget": sum(v["reason"] == "budget" for v in excluded),
            "questionnaires": len({s.unit.questionnaire_id for s in primary}),
            "questions": len({s.unit.question_id for s in primary}),
            "occupancy": total / config.document_budget,
        },
    }
    result["context_hash"] = digest(result)
    return result
