"""Rapport reproductible, sans citation de textes ni de jugements humains."""

from cahier_rag.search.hybrid.multi.core import CONFIGURATIONS


def render(result, bundle):
    def fmt(v):
        return "—" if v is None else f"{v:.3f}"

    lines = [
        "# RAG-019 — Comparaison hybride",
        "",
        "Références LLM v2 séparées, aucun consensus ni vérité humaine déduite.",
        "",
        f"Gel : `{result['frozen_hash']}`. Même ensemble de **{len(result['common_complete_queries'])} requêtes** calculables pour les deux juges et les neuf méthodes.",
        "",
        "k=60 ; profondeur 50 par moteur ; égalités départagées par identifiant documentaire. Les top 100 hybrides sont issus de ces mêmes candidats, sans passage à profondeur 100 par source.",
        "",
        "| Configuration | Poids |",
        "|---|---|",
    ]
    lines += [f"| {name} | {dict(weights)} |" for name, weights in CONFIGURATIONS.items()]
    lines += [
        "",
        "## Pertinence sur les mêmes requêtes complètes",
        "",
        "Pertinence binaire 2–3 ; gain nDCG 2**grade-1. IDCG sur le pool cumulé commun de chaque requête pour le juge, jamais sur une référence exhaustive du corpus. Un non-jugé ne vaut pas zéro. Recall exhaustif non calculé. Les métriques historiques ne sont pas reprises : toutes sont recalculées.",
        "",
        "| Juge | Méthode | k | Precision@k | nDCG poolée@k | MRR@50 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for model, methods in result["common_complete_metrics"].items():
        for name, data in methods.items():
            for k in ("5", "10", "20", "50"):
                row = data["aggregates"].get("all", {}).get(k, {})

                def mean(metric):
                    return fmt(row.get(metric, {}).get("mean"))

                lines.append(
                    f"| {model} | {name} | {k} | {mean('precision')} | {mean('pooled_ndcg')} | {mean('mrr')} |"
                )
    lines += [
        "",
        "## Couverture réelle des 20 requêtes au top 50",
        "",
        "Les moyennes ci-dessus excluent les requêtes au pool incomplet ; les couvertures ci-dessous portent sur les 20 requêtes. Les détails aux autres seuils et les notes par moteur figurent dans comparison.json.",
        "",
        "| Juge | Méthode | Jugés / retournés |",
        "|---|---|---:|",
    ]
    for model, methods in result["metrics"].items():
        for name, data in methods.items():
            rows = [v["50"]["coverage"] for v in data["per_query"].values()]
            lines.append(
                f"| {model} | {name} | {sum(v['judged'] for v in rows)}/{sum(v['returned'] for v in rows)} |"
            )
    lines += [
        "",
        "## Récupération et fusion",
        "",
        "Chaque moteur est exécuté une seule fois par requête dans le passage réel ; les cinq fusions partagent les mêmes candidats. Les totaux par configuration sont reconstitués à partir des étapes chronométrées (sources + contrôles + fusion) de la même requête, pas de cinq recherches complètes indépendantes. Les médianes ne s'additionnent pas.",
        "",
        "| Étape | Médiane (ms) | P95 (ms) |",
        "|---|---:|---:|",
    ]
    latency = bundle["report"]["latency"]
    for name, values in latency.get("sources_ms", {}).items():
        lines.append(f"| Source {name} | {values['median']:.2f} | {values['p95']:.2f} |")
    for name, values in latency["fusion_ms"].items():
        lines.append(f"| Fusion {name} | {values['median']:.2f} | {values['p95']:.2f} |")
    for name, values in latency.get("attributable_sequential_ms", {}).items():
        lines.append(f"| Total attribuable {name} | {values['median']:.2f} | {values['p95']:.2f} |")
    lines += [
        "",
        "Les replays mesurent uniquement la fusion sur candidats déjà calculés : aucune assimilation à une latence de recherche complète. Chargement du modèle et vérifications globales exclus des latences par requête.",
        "",
        "## Diversité et sources des résultats",
        "",
        "| Méthode | k | Contributions distinctes | Réponses <60 caractères | Textes Autre | Retournés |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, data in bundle["statistics"]["methods"].items():
        for k in ("10", "50"):
            row = data["totals"][k]
            lines.append(
                f"| {name} | {k} | {row['unique_contributions']} | {row['short_lt60']} | {row['other_text']} | {row['returned']} |"
            )
    lines += [
        "",
        "### Contribution effective des sources",
        "",
        "Présent = document retrouvé par la source ; exclusif = absent des autres sources de cette configuration à profondeur 50. Les présences se recouvrent. La part RRF est une contribution arithmétique au score, pas une mesure causale de pertinence.",
        "",
        "| Configuration | k | Source | Présent | Exclusif | Part de la somme RRF |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for name in CONFIGURATIONS:
        for k in ("10", "50"):
            for source, row in bundle["statistics"]["methods"][name]["totals"][k][
                "sources"
            ].items():
                share = "—" if row["rrf_share"] is None else f"{100 * row['rrf_share']:.2f} %"
                lines.append(
                    f"| {name} | {k} | {source} | {row['present']} | {row['exclusive']} | {share} |"
                )
    lines += [
        "",
        "## Écarts par requête face à H1",
        "",
        "Les valeurs — correspondent à une métrique non calculable ; les valeurs 0 sont des égalités calculées. Le rapport JSON conserve tous les seuils et les méthodes individuelles.",
        "",
        "| Juge | Requête | Méthode | Δ P@10 | Δ nDCG poolée@10 |",
        "|---|---|---|---:|---:|",
    ]
    for model, queries in result["deltas_from_H1"].items():
        for q, methods in queries.items():
            for name in ("H2", "H3", "H4", "H5"):
                row = methods[name]["10"]
                lines.append(
                    f"| {model} | {q} | {name} | {fmt(row['precision'])} | {fmt(row['pooled_ndcg'])} |"
                )
    lines += [
        "",
        "## Par thématique, mêmes requêtes complètes",
        "",
        "| Juge | Domaine | Méthode | P@10 | nDCG poolée@10 |",
        "|---|---|---|---:|---:|",
    ]
    for model, methods in result["common_complete_metrics"].items():
        for name, data in methods.items():
            for group, ks in data["aggregates"].items():
                if group.startswith("domain:"):
                    row = ks["10"]
                    lines.append(
                        f"| {model} | {group[7:]} | {name} | {fmt(row['precision']['mean'])} | {fmt(row['pooled_ndcg']['mean'])} |"
                    )
    inversions = result["judge_inversions"]
    lines += [
        "",
        "## Divergences et limites",
        "",
        f"{len(inversions)} inversions strictes entre deux configurations hybrides selon les juges, sur {len({r['query_id'] for r in inversions})} requêtes. Les détails, métriques et seuils sont exportés dans comparison.json ; les égalités ne deviennent pas des gagnants.",
        "",
        f"Réutilisation : `{result['reuse']}`.",
        "",
        "Deux modèles de même famille peuvent partager des erreurs. Aucun ajustement des poids, aucune validation sur les requêtes réservées, aucun nouveau jugement humain. Les répétitions de contenu conservent leurs identités ; le recouvrement de deux branches lexicales peut renforcer leurs erreurs corrélées. Le pool reste dépendant des moteurs et le sous-ensemble complet peut être biaisé par les échecs historiques.",
        "",
    ]
    return "\n".join(lines)
