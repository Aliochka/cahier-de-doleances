"""Sélection bornée sur un cadre documentaire explicite, sans conserver les corps."""

import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timezone

from cahier_rag.contracts import CONTRACT_VERSION, canonical_json

VERSION = 1


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def describe(document):
    return {
        "document_id": document.document_id,
        "content_hash": document.content_hash,
        "corpus_id": document.corpus_id,
        "contribution_id": str(document.contribution_id),
        "questionnaire_id": str(document.questionnaire_id),
        "text_hash": hashlib.sha256(document.text.encode()).hexdigest(),
        "length": len(document.text),
        "unit_type": document.unit_type.value,
    }


def select_sample(documents, **parameters):
    return select_described_sample((describe(document) for document in documents), **parameters)


def select_described_sample(
    documents, *, size, seed, method, frame, max_candidates=100_000, quotas=None, split_seed=1729
):
    if type(size) is not int or not 1 <= size <= 20_000:
        raise ValueError("Taille requise entre 1 et 20 000.")
    if type(split_seed) is not int:
        raise ValueError("Graine de partition invalide.")
    if type(seed) is not int or method not in {"random", "stratified"}:
        raise ValueError("Méthode ou graine invalide.")
    if type(max_candidates) is not int or not size <= max_candidates <= 100_000:
        raise ValueError("Cadre limité à 100 000 candidats.")
    rows = {}
    for scanned, description in enumerate(documents, 1):
        if scanned > 2 * max_candidates:
            raise ValueError("Trop de références candidates, y compris répétées.")
        item = dict(description)
        previous = rows.get(item["document_id"])
        if previous and previous != item:
            raise ValueError("Contenu incompatible pour un même identifiant.")
        rows[item["document_id"]] = item
        if len(rows) > max_candidates:
            raise ValueError("Cadre trop grand : choisir des extractions plus petites.")
    frame_hash = digest(sorted(rows.values(), key=lambda r: r["document_id"]))
    values = sorted(
        rows.values(), key=lambda r: (digest([seed, r["document_id"]]), r["document_id"])
    )
    by_text = defaultdict(set)
    by_contribution = Counter()
    for item in values:
        by_text[item["text_hash"]].add((item["corpus_id"], item["contribution_id"]))
        if item["unit_type"] == "open_answer":
            by_contribution[item["corpus_id"], item["contribution_id"]] += 1
    for item in values:
        labels = [f"form:{item['questionnaire_id']}"]
        if item["length"] <= 20:
            labels.extend(["short", "context_candidate"])
        if item["length"] > 2000:
            labels.append("long")
        if item["unit_type"] == "other_text":
            labels.append("other")
        if len(by_text[item["text_hash"]]) > 1:
            labels.append("duplicate")
        if (
            item["unit_type"] == "open_answer"
            and by_contribution[item["corpus_id"], item["contribution_id"]] > 1
        ):
            labels.append("multiple_units")
        item["strata"] = labels
    default_quotas = (
        {
            **{f"form:{f}": min(100, size // 8) for f in (4, 5, 7, 10)},
            **{
                s: min(100, size // 8)
                for s in (
                    "short",
                    "long",
                    "other",
                    "duplicate",
                    "context_candidate",
                    "multiple_units",
                )
            },
        }
        if method == "stratified"
        else {}
    )
    quotas = default_quotas if quotas is None else quotas
    if method == "random" and quotas:
        raise ValueError("Le tirage aléatoire ne prend pas de quotas.")
    if not isinstance(quotas, dict) or any(
        not isinstance(k, str) or type(q) is not int or q < 0 for k, q in quotas.items()
    ):
        raise ValueError("Quotas invalides.")
    chosen = {}
    counts = Counter()
    for label, quota in sorted(
        quotas.items(), key=lambda pair: sum(pair[0] in r["strata"] for r in values)
    ):
        for item in values:
            if counts[label] >= quota or len(chosen) >= size:
                break
            if label in item["strata"] and item["document_id"] not in chosen:
                bundle = [item]
                if label in {"duplicate", "multiple_units"}:
                    for peer in values:
                        related = (
                            peer["text_hash"] == item["text_hash"]
                            and (peer["corpus_id"], peer["contribution_id"])
                            != (item["corpus_id"], item["contribution_id"])
                            if label == "duplicate"
                            else peer["unit_type"] == "open_answer"
                            and (peer["corpus_id"], peer["contribution_id"])
                            == (item["corpus_id"], item["contribution_id"])
                        )
                        if related and peer["document_id"] != item["document_id"]:
                            bundle.append(peer)
                            break
                fresh = [p for p in bundle if p["document_id"] not in chosen]
                if len(chosen) + len(fresh) <= size:
                    for peer in fresh:
                        chosen[peer["document_id"]] = peer
                        counts.update(peer["strata"])
    for item in values:
        if len(chosen) >= size:
            break
        if item["document_id"] not in chosen:
            chosen[item["document_id"]] = item
            counts.update(item["strata"])
    selected = sorted(chosen.values(), key=lambda r: r["document_id"])
    # Components computed over the ENTIRE frame, including unselected bridge documents.
    parent = {r["document_id"]: r["document_id"] for r in values}

    def root(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    groups = {}
    for item in values:
        key = item["document_id"]
        for link in (
            ("contribution", item["corpus_id"], item["contribution_id"]),
            ("text", item["text_hash"]),
        ):
            if link in groups:
                a, b = root(key), root(groups[link])
                parent[max(a, b)] = min(a, b)
            groups[link] = key
    component_sizes = Counter(root(key) for key in parent)
    for item in selected:
        item["component_id"] = root(item["document_id"])
        item["split"] = (
            "evaluation"
            if int(digest([split_seed, item["component_id"]]), 16) % 5 == 0
            else "development"
        )
    return {
        "sample_version": VERSION,
        "contract_version": CONTRACT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "frame": frame,
        "method": method,
        "seed": seed,
        "requested_size": size,
        "candidate_count": len(values),
        "max_candidates": max_candidates,
        "quotas": quotas,
        "strata_definition": {
            "short_max_characters": 20,
            "long_min_exclusive_characters": 2000,
            "context_candidate": "short: validation humaine nécessaire",
            "multiple_units": "au moins deux réponses ouvertes dans le cadre",
        },
        "shortfalls": {k: q - counts[k] for k, q in quotas.items() if counts[k] < q},
        "size_shortfall": max(0, size - len(selected)),
        "selected_hash": digest(selected),
        "frame_hash": frame_hash,
        "split_seed": split_seed,
        "statistics": {
            "strata": dict(counts),
            "splits": dict(Counter(r["split"] for r in selected)),
            "largest_frame_component": max(component_sizes.values(), default=0),
        },
        "documents": selected,
        "scope": "Uniforme dans le cadre déclaré uniquement ; strates non représentatives.",
    }
