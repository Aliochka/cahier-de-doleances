"""BM25, cosinus exact et fusion RRF globale ; ni index public ni connexion."""

import collections
import ctypes
import ctypes.util
import math
import os
import re
import sys
import time
import unicodedata
from types import SimpleNamespace

os.environ["OPENBLAS_NUM_THREADS"] = "1"
from common import HERE, ROOT, read, rows, sha, write, write_rows  # noqa: E402

sys.path.insert(0, str(ROOT / "rag/src"))
from cahier_rag.search.hybrid.core import fuse  # noqa: E402
from cahier_rag.search.lexical import SearchResult  # noqa: E402
from cahier_rag.search.preparation import tokenize  # noqa: E402


class French:
    def __init__(self):
        self.path = ctypes.util.find_library("stemmer")
        if not self.path:
            raise RuntimeError("System French Snowball libstemmer required")
        self.lib = ctypes.CDLL(self.path)
        self.lib.sb_stemmer_new.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self.lib.sb_stemmer_new.restype = ctypes.c_void_p
        self.lib.sb_stemmer_stem.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self.lib.sb_stemmer_stem.restype = ctypes.c_void_p
        self.lib.sb_stemmer_length.argtypes = [ctypes.c_void_p]
        self.lib.sb_stemmer_length.restype = ctypes.c_int
        self.lib.sb_stemmer_delete.argtypes = [ctypes.c_void_p]
        self.stemmer = self.lib.sb_stemmer_new(b"french", b"UTF_8")
        assert self.stemmer
        self.stop = set((HERE / "data/french.stop").read_text().split())
        self.cache = {}

    def tokens(self, text):
        words = re.findall(r"[^\W\d_]+", unicodedata.normalize("NFC", text.casefold()), re.UNICODE)
        output = []
        for w in words:
            if w in self.stop:
                continue
            if w not in self.cache:
                b = w.encode()
                p = self.lib.sb_stemmer_stem(self.stemmer, b, len(b))
                self.cache[w] = ctypes.string_at(
                    p, self.lib.sb_stemmer_length(self.stemmer)
                ).decode()
            output.append(self.cache[w])
        return output

    def close(self):
        self.lib.sb_stemmer_delete(self.stemmer)


class BM25:
    def __init__(self, documents, french, k1=1.2, b=0.75):
        self.documents = documents
        self.french, self.k1, self.b = french, k1, b
        self.tf = [collections.Counter(french.tokens(d["text"])) for d in documents]
        self.lengths = [sum(t.values()) for t in self.tf]
        self.mean = sum(self.lengths) / len(self.lengths)
        self.df = collections.Counter(t for tf in self.tf for t in tf)

    def search(self, query):
        prepared = tokenize(query)
        terms = sorted(set(self.french.tokens(" ".join(prepared["terms"]))))
        n = len(self.documents)
        idf = {t: math.log(1 + (n - self.df[t] + 0.5) / (self.df[t] + 0.5)) for t in terms}
        results = []
        for d, tf, length in zip(self.documents, self.tf, self.lengths):
            score = sum(
                idf[t]
                * tf[t]
                * (self.k1 + 1)
                / (tf[t] + self.k1 * (1 - self.b + self.b * length / self.mean))
                for t in terms
                if tf[t]
            )
            if score > 0:
                results.append(dict(id=d["id"], score=score))
        return sorted(results, key=lambda r: (-r["score"], r["id"])), terms


def vector_rank(query, matrix, segments, allowed):
    import numpy as np

    similarities = matrix @ query
    best = {}
    for i, (r, score) in enumerate(zip(segments, similarities)):
        did = r["unit_id"]
        if did not in allowed:
            continue
        if did not in best or float(score) > best[did][0]:
            best[did] = (float(score), i)
    assert len(best) == len(allowed)
    result = [
        dict(
            id=did,
            score=score,
            segment_index=segments[i]["segment_index"],
            segment_start=segments[i]["start"],
            segment_end=segments[i]["end"],
        )
        for did, (score, i) in best.items()
    ]
    assert np.isfinite(similarities).all()
    return sorted(result, key=lambda r: (-r["score"], r["id"]))


def hybrid(lexical, vector, documents):
    rankings = {}
    for key, rr in (("lexical", lexical), ("vector", vector)):
        rankings[key] = [
            SearchResult(
                SimpleNamespace(
                    document_id=r["id"], content_hash=documents[r["id"]]["source_text_sha256"]
                ),
                r["score"],
            )
            for r in rr[:50]
        ]
    fused, trace = fuse(rankings, k=60)
    return [
        dict(id=r.document.document_id, score=r.score, trace=trace[r.document.document_id])
        for r in fused
    ]


def main():
    import numpy as np

    assert sha(HERE / "queries.json") == read(HERE / "preregistration.json")["queries_sha256"]
    corpus = rows(HERE / "data/corpus.jsonl")
    documents = {d["id"]: d for d in corpus}
    queries = read(HERE / "queries.json")["queries"]
    enc = read(HERE / "data/encoding.json")
    assert all(sha(HERE / "vectors" / name) == h for name, h in enc["vector_files"].items())
    historical = rows(HERE / "data/historical-segments.jsonl")
    modern = rows(HERE / "data/contemporary-segments.jsonl")
    qvec = np.load(HERE / "vectors/queries.npy", allow_pickle=False)
    matrices, refs = {}, {}
    mvec = np.load(HERE / "vectors/contemporary.npy", allow_pickle=False)
    for variant in ("A", "B"):
        matrices[variant] = np.concatenate(
            [np.load(HERE / f"vectors/historical_{variant}.npy", allow_pickle=False), mvec]
        )
        refs[variant] = [r for r in historical if r["variant"] == variant] + modern
        assert matrices[variant].shape == (len(refs[variant]), 1024)
        assert np.max(np.abs(np.linalg.norm(matrices[variant], axis=1) - 1)) < 1e-5
    french = French()
    output, pool = [], {}
    timings = []
    for population in ("historical", "mixed"):
        selected = [d for d in corpus if population == "mixed" or d["status"] == "A"]
        allowed = {d["id"] for d in selected}
        started = time.perf_counter()
        bm25 = BM25(selected, french)
        index_seconds = time.perf_counter() - started
        for qi, q in enumerate(queries):
            started = time.perf_counter()
            lex, terms = bm25.search(q["text"])
            lexical_ms = (time.perf_counter() - started) * 1000
            runs = {"lexical": lex}
            run_ms = {"lexical": lexical_ms}
            for variant in ("A", "B"):
                started = time.perf_counter()
                runs[f"vector_{variant}"] = vector_rank(
                    qvec[qi], matrices[variant], refs[variant], allowed
                )
                run_ms[f"vector_{variant}"] = (time.perf_counter() - started) * 1000
                started = time.perf_counter()
                runs[f"hybrid_{variant}"] = hybrid(lex, runs[f"vector_{variant}"], documents)
                run_ms[f"hybrid_{variant}"] = (time.perf_counter() - started) * 1000
            timings.append(
                dict(
                    population=population,
                    query_id=q["id"],
                    query_encoding_ms=enc["query_encoding_seconds"][qi] * 1000,
                    index_seconds=index_seconds,
                    ms=run_ms,
                )
            )
            for method, results in runs.items():
                for r in results[:10]:
                    pool[q["id"], r["id"]] = dict(query=q, document=documents[r["id"]])
                output.append(
                    dict(
                        query_id=q["id"],
                        query=q["text"],
                        population=population,
                        method=method,
                        score_kind="BM25"
                        if method == "lexical"
                        else "RRF"
                        if method.startswith("hybrid")
                        else "cosine_similarity",
                        query_lexemes=terms if method == "lexical" else None,
                        results=[dict(rank=i, **r) for i, r in enumerate(results[:50], 1)],
                    )
                )
    french.close()
    write_rows(HERE / "data/rankings.jsonl", output)
    write_rows(HERE / "data/review-pool.jsonl", [pool[k] for k in sorted(pool)])
    write(HERE / "data/search-timings.json", timings)
    print(f"{len(output)} rankings; {len(pool)} query-passage pairs in top10 pool")
    print(collections.Counter(k[0] for k in pool))


if __name__ == "__main__":
    main()
