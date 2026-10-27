"""Diagnostic secondaire apparié, uniquement avec vecteurs A/B déjà disponibles."""

import collections
import datetime

from common import HERE, PRIOR, ROOT, read, rows, sha, write, write_rows


def main():
    import numpy as np

    write(
        HERE / "data/context-control-protocol.json",
        dict(
            status="secondary exploratory diagnostic; not preregistered primary experiment",
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            reason="Previously computed paired2019 A/B embeddings discovered in RAG012; test representation effect without new encoding",
            selection="same full-answer single-segment units present in both caches; no query-dependent selection",
            main_rankings_changed=False,
        ),
    )
    root = ROOT / "rag/evaluation/local/rag012/gpu-bge-m3"
    manifest = read(root / "manifest.json")
    assert manifest["model"] == read(PRIOR / "data/encoding.json")["model"]
    assert manifest["precision"] == "bfloat16" and manifest["normalized"]
    vectors = {}
    sources = {}
    fingerprints = {str((root / "manifest.json").relative_to(ROOT)): sha(root / "manifest.json")}
    for v in ("A", "B"):
        metadata = read(root / f"documents-{v}-bs8.json")
        assert metadata["vectors_sha256"] == sha(root / f"documents-{v}-bs8.f32")
        arr = np.fromfile(root / f"documents-{v}-bs8.f32", dtype="<f4").reshape(-1, 1024)
        assert arr.shape[0] == len(metadata["rows"])
        prepared_path = ROOT / f"rag/evaluation/local/rag011/final-trial-{v}/representations.jsonl"
        byrep = {r["representation_id"]: r for r in rows(prepared_path)}
        count = collections.Counter(
            byrep[r["input_id"]]["primary"]["document_id"] for r in metadata["rows"]
        )
        source = {}
        vec = {}
        for i, r in enumerate(metadata["rows"]):
            d = byrep[r["input_id"]]
            did = d["primary"]["document_id"]
            if count[did] != 1 or d["segment"]["start"] != 0 or d["segment"]["index"] != 0:
                continue
            source[did] = d
            vec[did] = arr[i]
        vectors[v] = vec
        sources[v] = source
        for p in (prepared_path, root / f"documents-{v}-bs8.json", root / f"documents-{v}-bs8.f32"):
            fingerprints[str(p.relative_to(ROOT))] = sha(p)
    paired = []
    for did in sorted(vectors["A"].keys() & vectors["B"].keys()):
        a, b = sources["A"][did], sources["B"][did]
        assert a["segment"] == b["segment"]
        assert a["segment"]["end"] == len(a["embedding_text"])
        assert (
            b["embedding_text"]
            == f"Question :\n{b['context']['question_text']}\n\nRéponse :\n{a['embedding_text']}"
        )
        paired.append(
            dict(
                id=did,
                text=a["embedding_text"],
                question=b["context"]["question_text"],
                primary=a["primary"],
                a_rep=a["representation_id"],
                b_rep=b["representation_id"],
            )
        )
    ids = [d["id"] for d in paired]
    query = np.load(PRIOR / "vectors/queries.npy", allow_pickle=False)
    h = np.load(PRIOR / "vectors/historical_A.npy", allow_pickle=False)
    hist = [d for d in rows(PRIOR / "data/corpus.jsonl") if d["status"] == "A"]
    hm = {d["id"]: i for i, d in enumerate(hist)}
    hsegments = [
        hm[r["unit_id"]]
        for r in rows(PRIOR / "data/historical-segments.jsonl")
        if r["variant"] == "A"
    ]
    scores = {v: query @ np.asarray([vectors[v][did] for did in ids]).T for v in ("A", "B")}
    witnesses = rows(HERE / "data/witnesses.jsonl")
    result = []
    globalids = [d["id"] for d in hist] + ids
    from rank import ordered_scores

    tie = np.asarray(sorted(range(len(globalids)), key=lambda i: globalids[i]))
    for qi, q in enumerate(read(HERE / "queries.json")["queries"]):
        hs = np.full(269, -np.inf, dtype=np.float32)
        np.maximum.at(hs, hsegments, h @ query[qi])
        ranks = {v: ordered_scores(np.concatenate([hs, scores[v][qi]]), tie)[1] for v in ("A", "B")}
        ww = [w for w in witnesses if w["query_id"] == q["id"]]
        result.append(
            dict(
                query_id=q["id"],
                mean_modern_cosine_A=float(scores["A"][qi].mean()),
                mean_modern_cosine_B=float(scores["B"][qi].mean()),
                mean_delta_B_minus_A=float((scores["B"][qi] - scores["A"][qi]).mean()),
                witnesses=[
                    dict(
                        g=w["g"],
                        rank_modern_A=int(ranks["A"][w["g"]]),
                        rank_modern_B=int(ranks["B"][w["g"]]),
                    )
                    for w in ww
                ],
            )
        )
    delta = scores["B"] - scores["A"]
    np.savez_compressed(HERE / "data/context-control-scores.npz", A=scores["A"], B=scores["B"])
    write_rows(HERE / "data/context-control-documents.jsonl", paired)
    write(
        HERE / "data/context-control.json",
        dict(
            paired_units=len(paired),
            single_full_answer=True,
            same_questionnaire_answer_text_and_model=True,
            precision="both GPU bfloat16",
            new_embeddings=0,
            mean_delta_B_minus_A=float(delta.mean()),
            median_delta=float(np.median(delta)),
            positive_delta_fraction=float((delta > 0).mean()),
            queries=result,
            source_sha256=fingerprints,
            limitation="Small prior enriched trial cohort; shows context effect, not proof of unfairness or global calibration at1M; primary ranks unchanged",
        ),
    )
    print("Paired context control:", len(paired), "mean cosine delta", float(delta.mean()))


if __name__ == "__main__":
    main()
