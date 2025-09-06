# Helpers (mets-les au même endroit que _clean_snippet)
from __future__ import annotations
import re
import unicodedata
from typing import List


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

_slug_pat_keep = re.compile(r"[^a-z0-9\s-]")
_slug_pat_collapse = re.compile(r"[-\s]+")

def slugify(value: str | None, maxlen: int = 60) -> str:
    if not value:
        return ""
    # Ligatures FR courantes
    value = value.replace("œ", "oe").replace("Œ", "oe").replace("æ", "ae").replace("Æ", "ae")
    # Décomposition + suppression diacritiques
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    # Minuscule
    value = value.lower()
    # Retire ponctuation, garde lettres/chiffres/espaces/tirets
    value = _slug_pat_keep.sub(" ", value)
    # Espace/—/– → tiret unique
    value = _slug_pat_collapse.sub("-", value).strip("-")
    # Coupe propre
    if len(value) > maxlen:
        value = value[:maxlen].rstrip("-")
    return value or "contenu"


def clean_text_excerpt(text: str, max_chars: int = 300) -> str:
    """
    Génère un extrait propre de texte pour les métadonnées OG/Twitter
    - Supprime le HTML
    - Remplace les sauts de ligne par des espaces
    - Limite à max_chars caractères
    - Ajoute … si tronqué
    """
    if not text:
        return ""
    
    # Supprime les balises HTML basiques
    import re
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remplace les sauts de ligne et espaces multiples par un seul espace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Applique le post-processing existant pour nettoyer les boilerplates
    text = postprocess_excerpt(text)
    
    # Tronque proprement
    if len(text) <= max_chars:
        return text
    
    # Trouve la dernière phrase complète ou au moins le dernier mot complet
    truncated = text[:max_chars]
    
    # Essaie de couper à la fin d'une phrase
    last_sentence = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
    if last_sentence > max_chars * 0.7:  # Si on trouve une phrase dans les 70% finaux
        return truncated[:last_sentence + 1]
    
    # Sinon coupe au dernier espace pour ne pas couper un mot
    last_space = truncated.rfind(' ')
    if last_space > 0:
        return truncated[:last_space] + '…'
    
    return truncated + '…'


def highlight_text_python(text: str, query: str, max_words: int = 35, min_words: int = 15) -> str:
    """
    Highlighting en Python, plus rapide que ts_headline de PostgreSQL
    Trouve les mots de la requête dans le texte et les entoure de <mark>
    """
    if not text or not query.strip():
        return text[:1000]  # Limite pour l'affichage
    
    # Nettoyer et préparer la requête
    query_words = []
    # Diviser la requête en mots individuels
    for word in re.findall(r'\w+', query.lower()):
        if len(word) >= 2:  # Ignorer les mots trop courts
            query_words.append(word)
    
    if not query_words:
        return text[:1000]
    
    # Trouver les positions de tous les matches dans le texte
    matches = []
    text_lower = text.lower()
    
    for word in query_words:
        # Chercher toutes les occurrences de ce mot
        for match in re.finditer(r'\b' + re.escape(word) + r'\w*\b', text_lower):
            matches.append((match.start(), match.end(), word))
    
    if not matches:
        return text[:1000]
    
    # Trier les matches par position
    matches.sort(key=lambda x: x[0])
    
    # Trouver les meilleurs extraits autour des matches
    extracts = []
    
    for start_pos, end_pos, word in matches[:3]:  # Max 3 extraits
        # Trouver le début et la fin de l'extrait (par mots)
        words_before = text[:start_pos].split()
        words_after = text[end_pos:].split()
        
        # Prendre quelques mots avant et après
        context_before = words_before[-10:] if len(words_before) >= 10 else words_before
        context_after = words_after[:10] if len(words_after) >= 10 else words_after
        
        # Reconstituer l'extrait
        extract_start = len(' '.join(words_before[:-len(context_before)])) if context_before != words_before else 0
        extract_end = start_pos + len(' '.join(context_before)) + len(text[start_pos:end_pos]) + len(' '.join(context_after))
        
        extracts.append((extract_start, min(extract_end, len(text))))
    
    # Fusionner les extraits qui se chevauchent et créer le texte final
    if extracts:
        # Prendre le premier extrait pour simplifier
        start, end = extracts[0]
        excerpt = text[start:end]
        
        # Appliquer le highlighting sur cet extrait
        highlighted = excerpt
        for word in query_words:
            pattern = r'\b(' + re.escape(word) + r'\w*)\b'
            highlighted = re.sub(pattern, r'<mark>\1</mark>', highlighted, flags=re.IGNORECASE)
        
        return highlighted
    
    return text[:1000]


