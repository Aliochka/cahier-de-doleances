# Helpers (mets-les au même endroit que _clean_snippet)

import re

MAX_TEXT_LEN = 20_000

_BOILERPLATE_PREFIXES = [
    r"^\s*titre\s*:\s*",
    r"^\s*titre\s+de\s+la\s+contribution\s*[:\-–]?\s*",
    r"^\s*objet\s*:\s*",
    r"^\s*th[eé]matique\s*:\s*",
]
_boiler_re = re.compile("|".join(_BOILERPLATE_PREFIXES), re.IGNORECASE)

def _strip_boilerplate(s: str) -> str:
    # retire les boilerplates uniquement en TÊTE, une ou deux fois si répété
    before = s
    for _ in range(2):
        s = _boiler_re.sub("", s, count=1)
        s = s.lstrip(" -–—:")  # ponctuation d’entête résiduelle
    # si ça n’a rien enlevé, on rend la chaîne initiale
    return s if s != before else before

def _dedupe_snippet_segments(s: str) -> str:
    """
    snippet() renvoie des segments séparés par '…' ; on supprime les doublons consécutifs,
    on merge proprement avec ' … ' et on compacte espaces/ponctuation.
    """
    parts = [p.strip() for p in s.split("…") if p.strip()]
    dedup = []
    prev = None
    for p in parts:
        if p != prev:
            dedup.append(p)
            prev = p
    out = " … ".join(dedup)
    # compactage léger
    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(r"\s+([,;:.!?])", r"\1", out)
    return out

def postprocess_excerpt(html_or_text: str) -> str:
    # 1) coupe dur si trop long (sécurité)
    s = html_or_text[:MAX_TEXT_LEN]
    # 2) dédoublonne les segments de snippet si présent
    if "…" in s:
        s = _dedupe_snippet_segments(s)
    # 3) enlève les boilerplates en tête
    s = _strip_boilerplate(s)
    # 4) trim final
    return s.strip()
