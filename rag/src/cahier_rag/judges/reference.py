"""Référence humaine figée, privée, sans commentaires et jamais lue par l'inférence."""

from cahier_rag.evaluation.sampling import digest


def freeze(manifest, reference):
    if (
        manifest["kind"] != "human60"
        or manifest["source_hashes"]["human_sources"] != reference["sources"]
        or reference["conflicts"]
    ):
        raise ValueError("Référence humaine incompatible avec le plan figé.")
    selected = {(e["query_id"], e["document_id"]) for e in manifest["entries"]}
    rows = [
        {
            key: row[key]
            for key in ("query_id", "document_id", "grade", "evaluator", "judged_at", "version")
        }
        for row in reference["judgments"]
        if (row["query_id"], row["document_id"]) in selected
    ]
    value = {
        "version": 1,
        "origin": "human",
        "plan_hash": manifest["manifest_hash"],
        "source_hashes": manifest["source_hashes"],
        "judgments": rows,
    }
    value["reference_hash"] = digest(value)
    grades(manifest, value)
    return value


def grades(manifest, value):
    body = dict(value)
    claimed = body.pop("reference_hash")
    if (
        digest(body) != claimed
        or value["origin"] != "human"
        or value["version"] != 1
        or value["plan_hash"] != manifest["manifest_hash"]
        or value["source_hashes"] != manifest["source_hashes"]
    ):
        raise ValueError("Référence humaine figée modifiée ou incompatible.")
    result = {}
    for row in value["judgments"]:
        pair = row["query_id"], row["document_id"]
        if pair in result or type(row["grade"]) is not int or not 0 <= row["grade"] <= 3:
            raise ValueError("Note humaine ou couple dupliqué invalide.")
        result[pair] = row["grade"]
    if set(result) != {(e["query_id"], e["document_id"]) for e in manifest["entries"]}:
        raise ValueError("Référence humaine incomplète.")
    return result
