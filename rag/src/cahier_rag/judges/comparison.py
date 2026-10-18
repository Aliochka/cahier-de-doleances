"""Accords ordinaux : les notes automatiques ne deviennent jamais des références humaines."""

from collections import Counter


def agreement(pairs):
    pairs = list(pairs)
    if any(
        type(a) is not int or type(b) is not int or not 0 <= a <= 3 or not 0 <= b <= 3
        for a, b in pairs
    ):
        raise ValueError("Notes d’accord invalides.")
    n = len(pairs)
    matrix = [[0] * 4 for _ in range(4)]
    for a, b in pairs:
        matrix[a][b] += 1
    if not n:
        return {
            "count": 0,
            "exact": None,
            "within_one": None,
            "binary": None,
            "confusion": matrix,
            "weighted_kappa": None,
        }
    left = Counter(a for a, _ in pairs)
    right = Counter(b for _, b in pairs)
    observed = sum(abs(a - b) / 3 for a, b in pairs) / n
    expected = sum(abs(a - b) / 3 * left[a] * right[b] for a in range(4) for b in range(4)) / (
        n * n
    )
    return {
        "count": n,
        "exact": sum(a == b for a, b in pairs) / n,
        "within_one": sum(abs(a - b) <= 1 for a, b in pairs) / n,
        "binary": sum((a >= 2) == (b >= 2) for a, b in pairs) / n,
        "major_disagreements": sum(abs(a - b) >= 2 for a, b in pairs),
        "binary_disagreements": sum((a >= 2) != (b >= 2) for a, b in pairs),
        "confusion": matrix,
        "weighted_kappa": 1 - observed / expected if expected else None,
        "kappa_weights": "linear |a-b|/3",
        "confusion_axes": "rows reference; columns prediction",
    }


def report(manifest, results, human_grades):
    # results : modèle -> input_hash -> résultat de cache, sans accès de l'inférence à human_grades.
    judges = sorted(results)
    if len(judges) != 2:
        raise ValueError("Deux juges indépendants requis.")
    output = {
        "version": 1,
        "judgment_origin": "llm",
        "human_reference_unchanged": True,
        "plan_hash": manifest["manifest_hash"],
        "models": {},
        "review": [],
        "warning": "Accord entre modèles non assimilable à une vérité ; référence humaine limitée et non représentative.",
    }
    entries = manifest["entries"]
    for model in judges:
        metrics = {}
        for subset in ("all", "calibration", "validation"):
            values = []
            for entry in entries:
                pair = entry["query_id"], entry["document_id"]
                value = results[model].get(entry["input_hash"])
                if (
                    (subset == "all" or entry["subset"] == subset)
                    and pair in human_grades
                    and value
                    and value["status"] == "valid"
                ):
                    values.append((human_grades[pair], value["judgment"]["grade"]))
            metrics[subset] = agreement(values)
        metrics["valid"] = sum(
            v is not None and v["status"] == "valid" for v in results[model].values()
        )
        metrics["invalid_or_missing"] = len(entries) - metrics["valid"]
        output["models"][model] = metrics
    inter = []
    categories = Counter()
    for entry in entries:
        pair = entry["query_id"], entry["document_id"]
        a, b = (results[m].get(entry["input_hash"]) for m in judges)
        valid = a and b and a["status"] == "valid" and b["status"] == "valid"
        reasons = []
        if not valid:
            reasons.append("invalid_or_missing_judge")
        else:
            ga, gb = a["judgment"]["grade"], b["judgment"]["grade"]
            inter.append((ga, gb))
            delta = abs(ga - gb)
            categories["exact" if delta == 0 else "one_point" if delta == 1 else "major"] += 1
            if delta >= 2:
                reasons.append("major_inter_judge_disagreement")
            if (ga >= 2) != (gb >= 2):
                categories["binary_disagreement"] += 1
                reasons.append("binary_inter_judge_disagreement")
            if a["judgment"]["uncertain"] or b["judgment"]["uncertain"]:
                reasons.append("judge_uncertainty")
            if pair in human_grades and any(abs(g - human_grades[pair]) >= 2 for g in (ga, gb)):
                reasons.append("major_human_disagreement")
            if pair in human_grades and any(
                (g >= 2) != (human_grades[pair] >= 2) for g in (ga, gb)
            ):
                reasons.append("binary_human_disagreement")
        if reasons:
            output["review"].append(
                {
                    "query_id": pair[0],
                    "document_id": pair[1],
                    "subset": entry["subset"],
                    "reasons": reasons,
                    "human_grade": human_grades.get(pair),
                    "judges": {
                        m: (results[m].get(entry["input_hash"]) or {}).get("judgment")
                        for m in judges
                    },
                }
            )
    output["inter_judge"] = agreement(inter)
    output["inter_judge_axes"] = {"rows": judges[0], "columns": judges[1]}
    output["disagreements"] = dict(categories)
    output["human_distribution"] = dict(sorted(Counter(human_grades.values()).items()))
    return output
