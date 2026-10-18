"""Rapport lisible reproductible ; aucune reproduction des contributions citoyennes."""

from collections import Counter


def render(result):
    def fmt(value):
        return "—" if value is None else f"{value:.3f}"

    models = sorted(result["metrics"])
    lines = [
        "# RAG-017 — Comparaison exploratoire sur jugements LLM v2",
        "",
        "**Références automatiques distinctes, aucune note consensuelle ni référence humaine.**",
        "",
        f"Pool : **{result['pool_size']} couples**, {result['unique_documents']} unités documentaires et {result['unique_contributions']} contributions.",
        f"Plan : `{result['plan_hash']}`.",
        "",
        f"Sélection : `{result['pool_selection']}`.",
        f"Origines (recouvrements autorisés) : `{dict(sorted(result['origin_counts'].items()))}`.",
        "",
        "Les top 50 évalués sont ceux gelés de RAG-014. Les profondeurs supplémentaires servent uniquement à enrichir le pool, sans remplacer ces classements.",
        "",
        "## Conventions et couverture",
        "",
        "Pertinent binaire = notes 2–3. Precision@k conserve le dénominateur k. MRR est limité au top 50 fourni. Le gain nDCG vaut `2**grade-1` avec décote logarithmique. Son idéal est constitué de toutes les notes du pool de cette requête pour ce juge : **nDCG poolée, pas exhaustive sur les 20 000 documents**. Elle exige ici une annotation complète du pool de la requête. Aucun Recall exhaustif n’est calculé. Un non-jugé ne vaut jamais zéro ; les métriques impossibles sont indiquées par —.",
        "",
        "| Juge | Moteur | k | P@k | nDCG poolée@k | MRR@50 | Fraction pertinente | Jugés / retournés | Requêtes P / nDCG |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model in models:
        for method, method_result in result["metrics"][model].items():
            for k in ("5", "10", "20", "50"):
                agg = method_result["aggregates"]["all"][k]
                rows = [q[k] for q in method_result["per_query"].values()]
                known = sum(r["coverage"]["judged"] for r in rows)
                total = sum(r["coverage"]["returned"] for r in rows)
                lines.append(
                    f"| {model} | {method} | {k} | {fmt(agg['precision']['mean'])} | {fmt(agg['pooled_ndcg']['mean'])} | {fmt(agg['mrr']['mean'])} | {fmt(agg['relevant_fraction']['mean'])} | {known}/{total} | {agg['precision']['defined_queries']}/{agg['precision']['total_queries']} / {agg['pooled_ndcg']['defined_queries']}/{agg['pooled_ndcg']['total_queries']} |"
                )
    lines += [
        "",
        "Les moyennes sont des macro-moyennes des requêtes calculables ; les nombres de requêtes définies figurent dans `comparison.json`. Les distributions par note, requête, moteur et k y sont conservées.",
        "",
        "## Comparaison sur les mêmes requêtes entièrement jugées",
        "",
        f"Sous-ensemble commun aux deux juges : {len(result['common_complete_queries'])} requêtes dont tous les couples du pool sont valides. Les requêtes exclues ne sont ni complétées ni notées zéro. Ce sous-ensemble peut lui-même être biaisé par les échecs.",
        "",
        "| Juge | Moteur | P@10 | nDCG poolée@10 | P@50 | nDCG poolée@50 | MRR@50 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for model in models:
        for method, data in result["common_complete_metrics"][model].items():
            agg = data["aggregates"].get("all", {})
            def mean(k, metric):
                return fmt(agg.get(k, {}).get(metric, {}).get("mean"))

            lines.append(
                f"| {model} | {method} | {mean('10', 'precision')} | {mean('10', 'pooled_ndcg')} | {mean('50', 'precision')} | {mean('50', 'pooled_ndcg')} | {mean('50', 'mrr')} |"
            )
    lines += [
        "",
        "## Juges et ressources",
        "",
        "| Juge | Notes 0 / 1 / 2 / 3 | Incertains | Temps cumulé (s) | Chargements cumulés (s) | VRAM PyTorch max (Gio) | RAM max (Gio) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for model in models:
        run = result["execution"][model]
        distribution = result["grade_distributions"][model]
        counts = " / ".join(str(distribution.get(i, distribution.get(str(i), 0))) for i in range(4))
        lines.append(
            f"| {model} | {counts} | {result['uncertainty'][model]} | {run['seconds']:.2f} | {run['load_seconds']:.2f} | {run['peak_allocated_bytes'] / 2**30:.2f} | {run['peak_rss_bytes'] / 2**30:.2f} |"
        )
    lines += [
        "",
        "Les durées additionnent les passages de même plan et recette, reprises comprises, sans compter deux fois le dernier passage. Les pics RAM/VRAM sont les maxima des passages. Les tentatives, tokens et débits cumulés sont dans `comparison.json`. Les deux modèles sont exécutés successivement sur GPU, sans API distante.",
        "",
        f"Accords sur {result['valid_common']} couples valides communs :",
        "",
        f"- Exact : {fmt(result['agreement']['exact'])} ; à ±1 : {fmt(result['agreement']['within_one'])} ; binaire : {fmt(result['agreement']['binary'])}.",
        f"- Kappa pondéré linéaire : {fmt(result['agreement']['weighted_kappa'])}.",
        f"- Écarts ≥2 : {result['agreement'].get('major_disagreements', 0)} ; divergences binaires : {result['agreement'].get('binary_disagreements', 0)}.",
        f"- Incertitudes et désaccords à examiner : {len(result['review'])} couples (catégories pouvant se recouvrir).",
        "",
        f"Matrice de confusion : lignes `{result['agreement_axes'][0]}`, colonnes `{result['agreement_axes'][1]}` ; notes 0, 1, 2, 3.",
        "",
        "```text",
    ]
    lines += [" ".join(f"{n:5d}" for n in row) for row in result["agreement"]["confusion"]]
    lines += [
        "```",
        "",
        "## Résultats par thématique",
        "",
        "| Juge | Domaine | Moteur | P@10 | nDCG poolée@10 | MRR@50 |",
        "|---|---|---|---:|---:|---:|",
    ]
    for model in models:
        for method, data in result["metrics"][model].items():
            for group, ks in data["aggregates"].items():
                if group.startswith("domain:"):
                    r = ks["10"]
                    lines.append(
                        f"| {model} | {group[7:]} | {method} | {fmt(r['precision']['mean'])} | {fmt(r['pooled_ndcg']['mean'])} | {fmt(r['mrr']['mean'])} |"
                    )
    lines += ["", "## Résultats par requête", ""]
    for model in models:
        lines += [
            f"### {model}",
            "",
            "| Requête | P@10 lexical / vector / hybride | nDCG poolée@10 lexical / vector / hybride | MRR@50 lexical / vector / hybride |",
            "|---|---|---|---|",
        ]
        for qid in sorted(result["pool_per_query"]):
            values = {
                metric: " / ".join(
                    fmt(result["metrics"][model][m]["per_query"][qid]["10"][metric])
                    for m in ("lexical", "vector", "hybrid")
                )
                for metric in ("precision", "pooled_ndcg", "mrr")
            }
            lines.append(
                f"| {qid} | {values['precision']} | {values['pooled_ndcg']} | {values['mrr']} |"
            )
    contradicted = sorted({r["query_id"] for r in result["contradictions"]})
    lines += [
        "",
        "## Conclusions contradictoires entre juges",
        "",
        f"{len(contradicted)} requêtes présentent au moins une inversion stricte d’ordre entre deux moteurs : "
        + ", ".join(contradicted)
        + ".",
        f"Inversions par métrique et k : `{dict(Counter((r['metric'], r['k']) for r in result['contradictions']))}`.",
        "Les écarts stricts et leurs signes sont exportés dans `comparison.json`. Les égalités ne sont pas transformées en gagnants.",
        "",
        "## Exemples de désaccords importants",
        "",
        "| Requête | Document | Motifs | Notes des deux juges |",
        "|---|---|---|---|",
    ]
    selected = sorted(
        result["review"],
        key=lambda r: ("major" not in r["reasons"], r["query_id"], r["document_id"]),
    )[:15]
    for row in selected:
        notes = " / ".join(
            str(row["grades"][m]["grade"]) if row["grades"][m] else "invalide"
            for m in result["agreement_axes"]
        )
        lines.append(
            f"| {row['query_id']} | `{row['document_id']}` | {', '.join(row['reasons'])} | {notes} |"
        )
    lines += [
        "",
        "Les justifications complètes restent dans les fichiers privés locaux ; aucun texte citoyen n’est reproduit ici.",
        "",
        "## Limites et préparation du reranking",
        "",
        "Ce jeu est un ensemble de pseudo-jugements de deux modèles de même famille, sans validation humaine v2 indépendante. Leur accord peut refléter un biais commun. Les requêtes sont celles du développement, le corpus est un échantillon expérimental, et le pooling dépend des moteurs comparés : aucune conclusion sur la population ou la fréquence des opinions. Les 20 requêtes réservées restent intactes.",
        "",
        "Pour RAG-018 : geler ces deux références séparées ; comparer le reranker sur les mêmes candidats et rangs, sans utiliser les notes comme entrées ; publier les résultats selon chacun des deux juges ; contrôler humainement les désaccords et un échantillon des accords ; réserver une validation humaine nouvelle pour les conclusions finales. Toute sortie de recherche hors du pool exige de nouveaux jugements. Aucun réglage de moteur ni reranker n’est effectué par RAG-017.",
        "",
    ]
    return "\n".join(lines)
