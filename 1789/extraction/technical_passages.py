"""Mechanical source slices, XML-first boundaries, exact offline BGE-M3 counts."""

import bisect
import re

SENTENCE = re.compile(r"""[.!?…][»”"')\]]*(?=\s|$)""")
WORDS = re.compile(r"\S+")


def split(text, paragraph_ends, counter, config):
    """Return exact half-open Unicode slices; historical segmentation is never consulted."""
    if not text.strip():
        return []
    maximum, target = config["maximum_tokens"], config["target_tokens"]
    minimum = config["minimum_preferred_tokens"]
    offsets = counter.tokenizer.encode(text, add_special_tokens=False).offsets
    token_ends = [z for _, z in offsets]
    paragraphs = sorted({p for p in paragraph_ends if 0 < p <= len(text)} | {len(text)})
    sentences = [m.end() for m in SENTENCE.finditer(text)]
    words = [m.start() for m in WORDS.finditer(text)]

    def count(a, z):
        return counter.count(text[a:z])

    def nearby(points, a, low, high):
        first = bisect.bisect_right(token_ends, a)
        left = offsets[min(first + low - 1, len(offsets) - 1)][0]
        right = offsets[min(first + high + 1, len(offsets) - 1)][1]
        return points[
            bisect.bisect_left(points, max(a + 1, left)) : bisect.bisect_right(points, right)
        ]

    result = []
    start = 0
    while start < len(text):
        if not text[start:].strip():
            # Trailing whitespace remains in the previous exact slice.
            result[-1]["end"] = len(text)
            result[-1]["tokens"] = count(result[-1]["start"], len(text))
            break
        remaining = len(offsets) - bisect.bisect_right(token_ends, start)
        if remaining <= maximum + 4 and count(start, len(text)) <= maximum:
            end, reason = len(text), "document_end"
        else:
            end = None
            for points, label in [(paragraphs, "XML_paragraph_end"), (sentences, "sentence_end")]:
                choices = [
                    (p, count(start, p)) for p in nearby(points, start, minimum - 8, maximum + 8)
                ]
                choices = [(p, n) for p, n in choices if minimum <= n <= maximum]
                if choices:
                    end, _ = min(choices, key=lambda pair: (abs(pair[1] - target), pair[0]))
                    reason = label
                    break
            if end is None:
                # Extremely long sentences: use an existing word boundary, else Unicode position.
                choices = [
                    (p, count(start, p)) for p in nearby(words, start, minimum - 8, maximum + 8)
                ]
                choices = [(p, n) for p, n in choices if 0 < n <= maximum and text[start:p].strip()]
                if choices:
                    end, _ = min(choices, key=lambda pair: (abs(pair[1] - target), pair[0]))
                    reason = "word_boundary_long_sentence"
                else:
                    first = bisect.bisect_right(token_ends, start)
                    end = offsets[min(first + target - 1, len(offsets) - 1)][1]
                    end = max(start + 1, end)
                    while end > start + 1 and count(start, end) > maximum:
                        end -= 1
                    reason = "Unicode_boundary_exceptional_run"
        assert start < end <= len(text) and text[start:end].strip()
        n = count(start, end)
        assert 0 < n <= maximum
        result.append(dict(start=start, end=end, tokens=n, end_reason=reason))
        if end == len(text):
            break
        # At most 80 tokens repeated; paragraph/sentence boundary if reasonably close to 60.
        first = max(0, bisect.bisect_left(token_ends, end) - config["overlap_maximum_tokens"] - 8)
        low = max(start + 1, offsets[first][0])
        candidates = sorted(
            set(
                paragraphs[
                    bisect.bisect_left(paragraphs, low) : bisect.bisect_left(paragraphs, end)
                ]
                + sentences[bisect.bisect_left(sentences, low) : bisect.bisect_left(sentences, end)]
            )
        )
        choices = [(p, count(p, end)) for p in candidates]
        choices = [(p, n) for p, n in choices if 20 <= n <= config["overlap_maximum_tokens"]]
        if not choices:
            candidates = words[bisect.bisect_left(words, low) : bisect.bisect_left(words, end)]
            choices = [(p, count(p, end)) for p in candidates if p > start]
            choices = [(p, n) for p, n in choices if 0 < n <= config["overlap_maximum_tokens"]]
        next_start = (
            min(
                choices, key=lambda pair: (abs(pair[1] - config["overlap_target_tokens"]), pair[0])
            )[0]
            if choices
            else end
        )
        assert start < next_start <= end
        start = next_start
    return result
