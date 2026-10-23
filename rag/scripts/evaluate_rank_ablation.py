"""Ablation de pertinence RAG-019 : aucun modèle, juge ou chronométrage.

Depuis la racine :
.cache/search-cpu-venv/bin/python rag/scripts/evaluate_rank_ablation.py --output <nouveau>
Les URL RAG_SOURCE_DATABASE_URL et RAG_DATABASE_URL doivent être explicites.
"""

import argparse
import json
from collections import Counter
from contextlib import contextmanager
from fractions import Fraction
from itertools import groupby
from pathlib import Path

from sqlalchemy import text

from cahier_rag.__main__ import open_store
from cahier_rag.annotation.session import atomic_json
from cahier_rag.config import load_settings
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.evaluation import measure
from cahier_rag.search.flexible import FlexibleEngine
from cahier_rag.search.hybrid.multi.artifacts import file_hash, load_bundle
from cahier_rag.search.hybrid.multi.evaluation import historical_references

RANK = ":frequency_proximity*ts_rank_cd(v.search_vector,CAST(:query AS tsquery),32)::float8"
ORDER_LIMIT = 'ORDER BY score DESC,v.document_id COLLATE "C" ASC LIMIT :limit'
VARIANTS = ("original", "sans-rang", "ts-rank")


class Captured(Exception):
    pass


class CaptureConnection:
    def __init__(self, connection):
        self.connection = connection
        self.sql = self.params = None

    def execute(self, statement, params=None):
        sql = str(statement)
        if sql.startswith("WITH population AS MATERIALIZED"):
            self.sql, self.params = sql, dict(params)
            raise Captured()
        return (
            self.connection.execute(statement, params)
            if params is not None
            else self.connection.execute(statement)
        )


class CaptureGuard:
    """Capture l'appel final réel, sans toucher au moteur historique."""

    def __init__(self, guard):
        self.guard = guard
        self.capture = None

    @contextmanager
    def transaction(self):
        with self.guard.transaction() as (connection, source):
            self.capture = CaptureConnection(connection)
            yield self.capture, source


def candidate_sql(sql, variant):
    if variant not in VARIANTS or sql.count(RANK) != 1 or sql.count(ORDER_LIMIT) != 1:
        raise ValueError("SQL lexical inconnu ; ablation refusée.")
    # Garder le calcul, les CTE, filtres et casts ; récupérer tous les candidats
    # pour compter les groupes ex aequo à la frontière, sans couper à 50.
    prefix, _ = sql.split(")\n              SELECT u.*, r.score,m.content_hash AS indexed_hash", 1)
    prefix = prefix.replace(ORDER_LIMIT, "")
    if variant == "sans-rang":
        prefix = prefix.replace(" + " + RANK, "")
        if "ts_rank" in prefix:
            raise ValueError("Composante de rang résiduelle.")
    elif variant == "ts-rank":
        prefix = prefix.replace(RANK, RANK.replace("ts_rank_cd(", "ts_rank("))
    return (
        prefix
        + ') SELECT document_id,score FROM ranked ORDER BY score DESC,document_id COLLATE "C"'
    )


def rrf(lexical, vector):
    """Même RRF k=60, profondeur 50, fractions exactes et départage par ID."""
    scores = {}
    for ranking in (lexical[:50], vector[:50]):
        for rank, did in enumerate(ranking, 1):
            scores[did] = scores.get(did, Fraction()) + Fraction(1, 60 + rank)
    return sorted(scores, key=lambda did: (-scores[did], did))[:50]


def reverse_ties(rows):
    return [r for _, group in groupby(rows, key=lambda r: r[1]) for r in reversed(list(group))]


def tie_statistics(rows):
    groups = Counter(score for _, score in rows)
    result = {"candidates": len(rows), "distinct_scores": len(groups)}
    for k in (10, 50):
        top = rows[:k]
        if not top:
            continue
        boundary = top[-1][1]
        before = sum(score > boundary for _, score in rows)
        result[str(k)] = {
            "distinct_scores": len({s for _, s in top}),
            "positions_in_non_singleton_groups": sum(groups[s] > 1 for _, s in top),
            "boundary_group_size": groups[boundary],
            "boundary_group_selected": len(top) - before,
            "boundary_straddles_cutoff": groups[boundary] > len(top) - before,
        }
    return result


def evaluate_runs(runs, references):
    metrics = {}
    for model, records in references.items():
        grades, expected = {}, {}
        for (qid, did), value in records.items():
            expected.setdefault(qid, set()).add(did)
            if value["record"]["status"] == "valid":
                grades.setdefault(qid, {})[did] = value["record"]["judgment"]["grade"]
        metrics[model] = {
            method: {
                q: measure(ids, grades.get(q, {}), k=10, expected=expected[q])
                for q, ids in ranks.items()
            }
            for method, ranks in runs.items()
        }
    # Un même ensemble de requêtes pour les trois variantes ET les deux juges,
    # séparément par famille et métrique ; ne pas comparer des moyennes dépareillées.
    paired = {}
    for family in ("lexical", "hybrid"):
        methods = [family + ":" + v for v in VARIANTS]
        paired[family] = {}
        for metric in ("precision", "pooled_ndcg"):
            common = [
                q
                for q in runs[methods[0]]
                if all(metrics[m][n][q][metric] is not None for m in metrics for n in methods)
            ]
            paired[family][metric] = {
                "queries": common,
                "means": {
                    m: {
                        n: sum(metrics[m][n][q][metric] for q in common) / len(common)
                        if common
                        else None
                        for n in methods
                    }
                    for m in metrics
                },
            }
    return metrics, paired


def render(result):
    def f(x):
        return "—" if x is None else f"{x:.4f}"

    lines = [
        "# Ablation de pertinence du rang lexical H1",
        "",
        "20 requêtes de développement, corpus RAG-007 ; jugements Qwen3-8B/14B RAG-017/018 séparés. Aucun modèle ni juge relancé, aucun benchmark de performance.",
        "",
        "Original : 0,5 × couverture IDF + 0,3 × couverture des termes + 0,2 × ts_rank_cd(...,32). Sans rang : les deux premiers termes seuls, sans renormalisation. ts_rank : même formule avec ts_rank(...,32). RRF k=60, 50 candidats par branche, mêmes listes BGE-M3 archivées. Départage par identifiant COLLATE C.",
        "",
        "nDCG : gain 2**grade−1 et idéal du pool historique fixe RAG-017/018, non exhaustif. Aucun non-jugé assimilé à zéro. Les moyennes ci-dessous utilisent les mêmes requêtes pour les trois variantes et les deux juges ; leur effectif varie selon la métrique. Les variantes n'ont pas servi à enrichir le pool.",
        "",
        "| Famille | Métrique | Requêtes communes /20 | Juge | Original | Sans rang | ts_rank |",
        "|---|---|---:|---|---:|---:|---:|",
    ]
    for family, measures in result["paired"].items():
        for metric, data in measures.items():
            for model, means in data["means"].items():
                lines.append(
                    f"| {family} | {metric} | {len(data['queries'])} | {model} | "
                    + " | ".join(f(means[family + ":" + v]) for v in VARIANTS)
                    + " |"
                )
    lines += [
        "",
        "## Couverture des top 10 sur les 20 requêtes",
        "",
        "| Juge | Méthode | Jugés /200 | P@10 calculables /20 | nDCG@10 calculables /20 |",
        "|---|---|---:|---:|---:|",
    ]
    for model, methods in result["metrics"].items():
        for method, rows in methods.items():
            if method.endswith(":reverse-ties"):
                continue
            lines.append(
                f"| {model} | {method} | {sum(r['coverage']['judged'] for r in rows.values())} | {sum(r['precision'] is not None for r in rows.values())} | {sum(r['pooled_ndcg'] is not None for r in rows.values())} |"
            )
    lines += [
        "",
        "## Écarts par requête avec l'original",
        "",
        "Valeurs indéfinies marquées —. Ne pas comparer des moyennes calculées sur des sous-ensembles différents.",
        "",
        "| Juge | Famille | Requête | Variante | P@10 | Δ P@10 | nDCG@10 | Δ nDCG@10 | Non jugés /10 |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for model, methods in result["metrics"].items():
        for family in ("lexical", "hybrid"):
            for q in sorted(methods[family + ":original"]):
                base = methods[family + ":original"][q]
                for v in VARIANTS:
                    row = methods[family + ":" + v][q]

                    def delta(key):
                        return (
                            row[key] - base[key]
                            if row[key] is not None and base[key] is not None
                            else None
                        )

                    lines.append(
                        f"| {model} | {family} | {q} | {v} | {f(row['precision'])} | {f(delta('precision'))} | {f(row['pooled_ndcg'])} | {f(delta('pooled_ndcg'))} | {row['coverage']['unjudged']} |"
                    )
    lines += [
        "",
        "## Ex æquo",
        "",
        "Les groupes sont comptés sur tous les candidats admissibles (pas seulement les 50 premiers). Le test de sensibilité inverse uniquement l'ordre des identifiants à score lexical exactement égal, puis recalcule RRF avec les mêmes vecteurs. Ce scénario ne mesure ni l'espérance ni tous les ordres possibles.",
        "",
        "| Requête | Variante | Scores distincts top10 | Taille groupe frontière @10 | Places retenues | Groupe coupé @50 | Changement top10 lexical (IDs) | Changement top10 hybride (IDs) |",
        "|---|---|---:|---:|---:|---|---:|---:|",
    ]
    for q, variants in result["ties"].items():
        for v, row in variants.items():
            t = row["10"]
            lines.append(
                f"| {q} | {v} | {t['distinct_scores']} | {t['boundary_group_size']} | {t['boundary_group_selected']} | {row['50']['boundary_straddles_cutoff']} | {row['reverse_lexical_top10_changed']} | {row['reverse_hybrid_top10_changed']} |"
            )
    lines += [
        "",
        "Les classements inversés et leurs métriques par requête sont aussi conservés dans comparison.json (suffixe reverse-ties). Les changements comptent les identifiants remplacés, pas les permutations internes.",
        "",
        "## Intégrité",
        "",
        "Les top50 lexicaux originaux (identifiants ET scores) et les top50 H1 reproduisent exactement RAG-019 pour les 20 requêtes. SQL capturé sur FlexibleEngine historique ; seule la composante de rang varie. Les empreintes des sources et artefacts protégés sont inchangées après l'expérience. PostgreSQL ne reçoit que des lectures et réglages locaux. Aucun code de production modifié.",
        "",
        "Les documents hors pool figurent dans unjudged.json avec leurs origines et rangs ; aucune nouvelle annotation n'est exécutée. Les résultats détaillés locaux contiennent aussi les classements et scores de tous les candidats pour auditer les ex æquo.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    if output.exists():
        parser.error("Le répertoire de sortie doit être nouveau.")
    historic = root / "evaluation/local/rag019"
    bundle, frozen, scope, queries = load_bundle(
        root, historic / "configuration", historic / "development"
    )
    dev = [q for q in queries if q["split"] == "development"]
    protected = [root / p for p in frozen["inputs"]]
    protected += [root / "src/cahier_rag/search/flexible.py", Path(__file__).resolve()]
    protected += list((root / "evaluation/local/rag017").rglob("cache.sqlite3"))
    protected += list((root / "evaluation/local/rag018").rglob("cache.sqlite3"))
    hashes = {str(p.relative_to(root)): file_hash(p) for p in protected}
    output.mkdir(parents=True, mode=0o700)
    atomic_json(
        output / "protocol.json",
        {
            "variants": VARIANTS,
            "weights": [0.5, 0.3, 0.2],
            "normalization": 32,
            "rrf_k": 60,
            "depth": 50,
            "sample_hash": scope.sample_hash,
            "queries_hash": digest(dev),
            "historical_frozen_hash": frozen["frozen_hash"],
            "protected": hashes,
            "performance_benchmark": False,
        },
    )
    runs, candidates, ties, sqls = {}, {}, {}, {}
    for family in ("lexical", "hybrid"):
        for v in VARIANTS:
            runs[family + ":" + v] = {}
            runs[family + ":" + v + ":reverse-ties"] = {}
    with open_store(load_settings(env_file=args.env_file)) as store:
        for q in dev:
            qid = q["query_id"]
            guard = CaptureGuard(store.guard)
            try:
                FlexibleEngine(guard, scope).search(q["text"], limit=50, split="development")
            except Captured:
                pass
            if guard.capture.sql is None:
                raise ValueError("Requête vide ou SQL non capturé.")
            candidates[qid], ties[qid], sqls[qid] = {}, {}, {}
            vector = [r["document_id"] for r in bundle["sources"][qid]["vector"]]
            for variant in VARIANTS:
                sql = candidate_sql(guard.capture.sql, variant)
                sqls[qid][variant] = {"sql": sql, "params": guard.capture.params}
                with store.guard.target.connect().execution_options(postgresql_readonly=True) as c:
                    with c.begin():
                        c.execute(text("SET LOCAL statement_timeout='30s'"))
                        rows = [
                            (r[0], float(r[1])) for r in c.execute(text(sql), guard.capture.params)
                        ]
                if len(rows) != len({d for d, _ in rows}) or any(
                    d not in scope.documents or scope.documents[d]["split"] != "development"
                    for d, _ in rows
                ):
                    raise ValueError("Candidats dupliqués ou hors développement.")
                candidates[qid][variant] = rows
                ids = [d for d, _ in rows]
                reversed_ids = [d for d, _ in reverse_ties(rows)]
                for suffix, ranking in (("", ids), (":reverse-ties", reversed_ids)):
                    runs["lexical:" + variant + suffix][qid] = ranking[:50]
                    runs["hybrid:" + variant + suffix][qid] = rrf(ranking, vector)
                ties[qid][variant] = tie_statistics(rows)
                ties[qid][variant].update(
                    reverse_lexical_top10_changed=len(set(ids[:10]) - set(reversed_ids[:10])),
                    reverse_hybrid_top10_changed=len(
                        set(rrf(ids, vector)[:10]) - set(rrf(reversed_ids, vector)[:10])
                    ),
                )
            baseline = [(r["document_id"], r["score"]) for r in bundle["sources"][qid]["lexical"]]
            if (
                candidates[qid]["original"][:50] != baseline
                or runs["hybrid:original"][qid] != bundle["runs"]["H1"][qid][:50]
            ):
                raise ValueError("L'original ne reproduit pas exactement RAG-019.")
            print(qid, "classements vérifiés", flush=True)
    # Les notes ne sont ouvertes qu'après avoir figé tous les classements.
    atomic_json(output / "runs.json", runs)
    atomic_json(output / "candidates.json", candidates)
    atomic_json(output / "sql.json", sqls)
    references, metadata = historical_references(root, scope, queries)
    metrics, paired = evaluate_runs(runs, references)
    unknown = {}
    known = set(next(iter(references.values())))
    for method, rankings in runs.items():
        for q, ids in rankings.items():
            for rank, did in enumerate(ids, 1):
                if (q, did) not in known:
                    unknown.setdefault((q, did), []).append({"method": method, "rank": rank})
    unknown_rows = [
        {"query_id": q, "document_id": d, "origins": origins}
        for (q, d), origins in sorted(unknown.items())
    ]
    if any(file_hash(root / p) != h for p, h in hashes.items()):
        raise ValueError("Un artefact protégé a changé.")
    result = {
        "metrics": metrics,
        "paired": paired,
        "ties": ties,
        "historical_references": metadata,
        "protected_unchanged": True,
        "unjudged_pairs_top50_including_tie_sensitivity": len(unknown_rows),
        "runs_hash": digest(runs),
        "candidates_hash": digest(candidates),
    }
    atomic_json(output / "comparison.json", result)
    atomic_json(output / "unjudged.json", unknown_rows)
    (output / "report.md").write_text(render(result))
    print(json.dumps({"paired": paired, "unjudged_pairs": len(unknown_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
