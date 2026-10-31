"""Encode Codex's source reading before running frozen predictions on validation.
The explicit selections below are annotations, not extractor rules.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "docs/tools/1789-document-review"))
from reviewlib import Store
from segmentation import trim

plan = json.loads((HERE / "data/validation-plan.json").read_text())
s = Store()
# Indices refer to paragraphs in the preselected window, starting at zero.
selected = {
    "validation-v1-1": [6],  # 4°..8° and 1°..3° are internal lists under Art.9/10.
    "validation-v1-2": [0, 6],  # Art.3 follows Latin quotation inside p[10].
    "validation-v2-1": [0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11],
    "validation-v2-2": [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11],
    "validation-v3-1": list(range(1, 12)),
    "validation-v3-2": [0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11],
    "validation-v4-1": [11],
    "validation-v4-2": [],
    "validation-v5-1": list(range(1, 12)),
    "validation-v5-2": list(range(11)),
    "validation-v6-1": [0, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "validation-v6-2": [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11],
}
result = {}
complete = {}
for w in plan:
    src = s.sources[w["volume"]]
    bs = [src.span(src.node(x)) for x in w["xpaths"]]
    indices = selected[w["id"]]
    starts = []
    for i in indices:
        a, z = bs[i]
        a, z = trim(src.text, a, z)
        if w["id"] == "validation-v1-2" and i == 6:
            a = src.text.index("Art. 3.", a, z)
        starts.append(a)
    for k, (i, a) in enumerate(zip(indices, starts)):
        if k + 1 >= len(indices):
            continue  # Last article censored by the window, not scored for end.
        next_i = indices[k + 1]
        if next_i == i:
            continue
        end = bs[next_i - 1][1]
        if w["id"] == "validation-v1-2":
            end = starts[k + 1]  # Latin quotation ends Art.2 inside p[10].
        _, end = trim(src.text, a, end)
        complete[(w["document_id"], a)] = dict(document_id=w["document_id"], start=a, end=end)
    result[w["id"]] = dict(
        article_starts=starts,
        annotation_origin="Codex source inspection after rule freeze; not independent human validation",
        note="Subparagraph ordinals in Alençon remain internal lists; missing number in Colmar retained; A:rt.32 in Vic is an article despite OCR. Last end excluded where censored.",
    )
result["_complete_articles"] = list(complete.values())
path = HERE / "data/validation-reference.json"
if path.exists():
    raise ValueError("Reference already recorded")
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(
    "Reference:",
    sum(len(x["article_starts"]) for k, x in result.items() if not k.startswith("_")),
    "window starts;",
    len(complete),
    "complete articles (deduplicated)",
)
