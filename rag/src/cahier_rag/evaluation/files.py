"""Fichiers locaux bornés, jugements humains et candidats sans notes inventées."""

import json
from datetime import datetime
from pathlib import Path

from cahier_rag.contracts import canonical_json

MAX_BYTES = 64 * 1024 * 1024


def load_json(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Fichier trop volumineux.")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Clé JSON dupliquée.")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def write_json(path, value):
    payload = canonical_json(value) + "\n"
    if len(payload.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Fichier trop volumineux.")
    # Exclusive creation prevents accidental replacement of human judgments.
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(payload)


def load_queries(path):
    rows = load_json(path)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("Liste de requêtes requise.")
    seen = set()
    families = {}
    for row in rows:
        if (
            not isinstance(row.get("version"), str)
            or not row["version"]
            or not isinstance(row.get("query_id"), str)
            or row["query_id"] in seen
            or not isinstance(row.get("text"), str)
            or not row["text"].strip()
            or row.get("split") not in {"development", "evaluation"}
            or not all(
                isinstance(row.get(k), str) and row[k] for k in ("category", "domain", "family")
            )
        ):
            raise ValueError("Requête invalide ou dupliquée.")
        if families.setdefault(row["family"], row["split"]) != row["split"]:
            raise ValueError("Une famille de requêtes traverse les partitions.")
        seen.add(row["query_id"])
    return rows


def load_judgments(path, queries, sample):
    rows = load_json(path)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("Liste de jugements requise.")
    query_index = {q["query_id"]: q for q in queries}
    doc_index = {d["document_id"]: d for d in sample["documents"]}
    seen = set()
    versions = set()
    output = {}
    for row in rows:
        qid, did = row.get("query_id"), row.get("document_id")
        grade = row.get("grade")
        if qid not in query_index or did not in doc_index:
            raise ValueError("Référence de jugement inconnue.")
        if query_index[qid]["split"] != doc_index[did]["split"]:
            raise ValueError("Jugement entre partitions différentes.")
        if type(grade) is not int or not 0 <= grade <= 3:
            raise ValueError("Note humaine entière entre 0 et 3 requise.")
        if not isinstance(row.get("version"), str) or not row["version"]:
            raise ValueError("Version de jugement requise.")
        if not isinstance(row.get("evaluator"), str) or not row["evaluator"]:
            raise ValueError("Évaluateur requis.")
        if row.get("justification") is not None and not isinstance(row["justification"], str):
            raise ValueError("Justification invalide.")
        try:
            stamp = datetime.fromisoformat(row["judged_at"])
            if stamp.tzinfo is None:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise ValueError("Date avec fuseau requise.") from None
        if (qid, did) in seen:
            raise ValueError(
                "Plusieurs jugements : choisir une version et un évaluateur adjudicataire."
            )
        seen.add((qid, did))
        versions.add(row["version"])
        output.setdefault(qid, {})[did] = grade
    if len(versions) > 1:
        raise ValueError("Versions de jugements mélangées.")
    return rows, output


def candidates(queries, sample, *, per_query=20):
    if type(per_query) is not int or not 1 <= per_query <= 500:
        raise ValueError("Nombre de candidats entre 1 et 500 requis.")
    from cahier_rag.evaluation.sampling import digest

    rows = []
    for query in queries:
        eligible = [d for d in sample["documents"] if d["split"] == query["split"]]
        eligible.sort(key=lambda d: digest([sample["seed"], query["query_id"], d["document_id"]]))
        for document in eligible[:per_query]:
            rows.append(
                {
                    "query_id": query["query_id"],
                    "document_id": document["document_id"],
                    "grade": None,
                    "justification": None,
                    "judged_at": None,
                    "version": "v1",
                    "evaluator": None,
                }
            )
    return rows
