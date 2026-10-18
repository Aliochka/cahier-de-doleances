"""Pool complémentaire non jugé : rangs variés, origines et contributions distinctes."""

from collections import Counter

from cahier_rag.evaluation.sampling import digest

METHODS = ("lexical", "vector", "hybrid")


def validate_experiment(bundle, scope):
    report = bundle["report"]
    if report["split"] != "development" or report["sample_hash"] != scope.sample_hash:
        raise ValueError("Expérience compatible de développement requise.")
    for key in ("runs", "rankings", "diagnostics", "documents"):
        if digest(bundle[key]) != report[key + "_hash"]:
            raise ValueError("Artefact expérimental modifié.")
    queries = set(bundle["runs"]["lexical"])
    for method in METHODS:
        if set(bundle["runs"][method]) != queries:
            raise ValueError("Requêtes différentes entre moteurs.")
        for qid, ids in bundle["runs"][method].items():
            if len(ids) != len(set(ids)) or len(ids) > report["configuration"]["depth"]:
                raise ValueError("Classement dupliqué ou profondeur dépassée.")
            for did in ids:
                expected = scope.documents.get(did)
                metadata = bundle["documents"].get(did)
                if (
                    not expected
                    or expected["split"] != "development"
                    or not metadata
                    or expected["content_hash"] != metadata["content_hash"]
                    or expected["contribution_id"] != metadata["contribution_id"]
                ):
                    raise ValueError("Candidat hors corpus ou provenance modifiée.")
                trace = bundle["diagnostics"][qid][did]
                trace_key = "rrf" if method == "hybrid" else method
                if trace[trace_key]["rank"] != ids.index(did) + 1:
                    raise ValueError("Rang source incohérent.")
    return queries


def prepare_pool(bundle, scope, previous_pairs, *, per_query=20, seed=20261021):
    if type(per_query) is not int or not 1 <= per_query <= 100:
        raise ValueError("Entre 1 et 100 candidats par requête requis.")
    if type(seed) is not int:
        raise ValueError("Graine entière explicite requise.")
    qids = validate_experiment(bundle, scope)
    rows, counts = [], Counter()
    for qid in sorted(qids):
        provenance = {}
        for method in METHODS:
            for rank, did in enumerate(bundle["runs"][method][qid], 1):
                trace = bundle["diagnostics"][qid][did]["rrf" if method == "hybrid" else method]
                provenance.setdefault(did, []).append(
                    {"method": method, "rank": rank, "score": trace["score"]}
                )

        def origin(did):
            methods = {p["method"] for p in provenance[did]}
            return (
                "common"
                if {"lexical", "vector"} <= methods
                else ("lexical_only" if "lexical" in methods else "vector_only")
            )

        def band(rank):
            return "top_1_10" if rank <= 10 else "middle_11_25" if rank <= 25 else "deep_26_plus"

        categories = {
            (did, p["method"], band(p["rank"]))
            for did, values in provenance.items()
            for p in values
        }
        tags = {
            did: sorted({origin(did)} | {b for d, _, b in categories if d == did})
            for did in provenance
        }
        # D'abord les nouveaux couples ; diversité parentale et tours entre catégories ensuite.
        selected, parents = [], set()
        groups = sorted({(origin(did), method, b) for did, method, b in categories})
        for already in (False, True):
            eligible = {did for did in provenance if ((qid, did) in previous_pairs) == already}
            while eligible and len(selected) < per_query:
                progressed = False
                for group in groups:
                    fresh = {
                        did
                        for did in eligible
                        if (
                            bundle["documents"][did]["corpus_id"],
                            bundle["documents"][did]["contribution_id"],
                        )
                        not in parents
                    }
                    available = [
                        did
                        for did in (fresh or eligible)
                        if origin(did) == group[0] and (did, group[1], group[2]) in categories
                    ]
                    if not available:
                        continue

                    def key(did):
                        meta = bundle["documents"][did]
                        parent = meta["corpus_id"], meta["contribution_id"]
                        return parent in parents, digest([seed, qid, did]), did

                    did = min(available, key=key)
                    eligible.remove(did)
                    selected.append(did)
                    meta = bundle["documents"][did]
                    parents.add((meta["corpus_id"], meta["contribution_id"]))
                    progressed = True
                    if len(selected) >= per_query:
                        break
                if not progressed:
                    break
        for did in selected:
            meta = bundle["documents"][did]
            row = {key: value for key, value in meta.items() if key != "length"}
            row.update(
                query_id=qid,
                found_by=provenance[did],
                selection_tags=tags[did],
                origin=origin(did),
                already_in_rag010=(qid, did) in previous_pairs,
                grade=None,
                justification=None,
                evaluator=None,
                judged_at=None,
                version="rag014-candidates-v1",
            )
            rows.append(row)
            counts[origin(did)] += 1
            counts["already_in_rag010"] += row["already_in_rag010"]
        counts["deficit"] += max(0, per_query - len(selected))
    manifest = {
        "version": 1,
        "sample_hash": scope.sample_hash,
        "split": "development",
        "seed": seed,
        "per_query": per_query,
        "candidate_count": len(rows),
        "queries": len(qids),
        "pool_hash": digest(rows),
        "runs_hash": bundle["report"]["runs_hash"],
        "previous_pairs_hash": digest(sorted(previous_pairs)),
        "statistics": dict(counts),
        "judgments_created": False,
        "policy": "new pairs first; distinct available parents first; round robin source/method/rank band",
    }
    return rows, manifest
