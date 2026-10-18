"""Segmentation sans perte : offsets [début, fin), chevauchement exact."""

import re

SENTENCE_END = re.compile(r"[.!?](?:[ \t]+|\n+)")


def segment_offsets(text: str, *, size: int, overlap: int):
    if (
        type(size) is not int
        or size < 8
        or type(overlap) is not int
        or not 0 <= overlap <= size // 2
    ):
        raise ValueError("Taille ou chevauchement invalide.")
    if not text:
        raise ValueError("Texte vide.")
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            lower = start + max(size // 2, overlap + 1)
            paragraph = text.rfind("\n\n", lower, end)
            if paragraph >= 0:
                end = paragraph + 2
            else:
                boundary = None
                for match in SENTENCE_END.finditer(text, lower, end):
                    boundary = match.end()
                if boundary is not None:
                    end = boundary
        yield start, end
        if end == len(text):
            break
        start = end - overlap
