"""BM25 et Snowball : recette reprise du premier pilote, sans modification.

French est repris de1789-semantic-search/search.py pour éviter de réassocier
son module common à un autre dossier. Les scores sont contrôlés sur la référence.
"""

import collections
import ctypes
import ctypes.util
import re
import sys
import unicodedata

from common import HERE, ROOT

sys.path.insert(0, str(ROOT / "rag/src"))
from cahier_rag.search.preparation import tokenize  # noqa: E402


class French:
    def __init__(self):
        self.lib = ctypes.CDLL(ctypes.util.find_library("stemmer"))
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


def query_terms(queries, french):
    return [sorted(set(french.tokens(" ".join(tokenize(q["text"])["terms"])))) for q in queries]


def prepare_text(text, french, term_index):
    words = french.tokens(text)
    counts = collections.Counter(words)
    return len(words), [(term_index[t], v) for t, v in counts.items() if t in term_index]


def score(tf, lengths, indices):
    import numpy as np

    n = len(lengths)
    average = float(lengths.sum()) / n
    norm = 1.2 * (1 - 0.75 + 0.75 * lengths / average)
    result = np.zeros(n, dtype=np.float64)
    stats = []
    for index in indices:
        counts = tf[:, index]
        df = int(np.count_nonzero(counts))
        idf = float(np.log(1 + (n - df + 0.5) / (df + 0.5)))
        result += idf * counts * (1.2 + 1) / (counts + norm)
        stats.append(dict(term_index=index, df=df, idf=idf))
    return result, dict(n=n, average_length=average, terms=stats)
