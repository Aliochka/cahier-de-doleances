"""Public identifiers and author identity shared by API and SEO."""

from __future__ import annotations

import re
import unicodedata

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


def public_author(author_id: int | None, name: str | None, is_anonymous: bool | None) -> dict:
    """Project an author for display without changing the stored identity.

    Only an explicitly non-anonymous author may expose a stored name.
    """
    label = name if is_anonymous is False and name else None
    label = label or (f"Auteur #{author_id}" if author_id is not None else "Auteur anonyme")
    return {
        "id": author_id,
        "name": label,
        "slug": slugify(label),
        "is_anonymous": is_anonymous is not False,
    }
