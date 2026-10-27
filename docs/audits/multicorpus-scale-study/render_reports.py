"""Tableaux et galerie calculés, séparés des observations et recommandations."""

import gzip
import json

from common import HERE, read, rows


def gzrows(name):
    return [json.loads(line) for line in gzip.open(HERE / f"data/{name}.jsonl.gz", "rt")]


def main():
    summary = read(HERE / "data/summary.json")
    growth = summary["growth"]

    def cell(count):
        return f"{count} ({100 * count / 270:.1f} %)"

    lines = [
        "# Croissance et rappel des témoins connus\n\n270 associations requête–article de note ≥2 héritées, couvrant 135 articles distincts et 21 requêtes. Ce n'est pas un rappel exhaustif. Les neuf requêtes sans témoin historique n'ajoutent pas de dénominateur artificiel.\n\n| Réponses 2019 | Méthode | Top10 | Top20 | Top50 | Top100 |\n|---:|---|---:|---:|---:|---:|\n"
    ]
    for r in growth:
        if r["strategy"] == "global" and (r["method"] != "hybrid" or r["depth"] == 50):
            label = {"lexical": "BM25", "vector": "BGE-M3 A exact", "hybrid": "RRF globale50"}[
                r["method"]
            ]
            lines.append(
                f"| {r['size']:,} | {label} | "
                + " | ".join(cell(r["witnesses_at"][str(k)]) for k in (10, 20, 50, 100))
                + " |\n"
            )
    lines.append(
        "\n## Composition de la première page\n\nMoyenne sur les 30 requêtes, résultats historiques de tout niveau de pertinence. Une baisse de cette part ne constitue pas en soi une erreur.\n\n| Réponses 2019 | BM25 | Vectoriel A | RRF globale50 | Distribuée50 |\n|---:|---:|---:|---:|---:|\n"
    )
    for size in read(HERE / "protocol.json")["stages"]:
        select = [
            ("lexical", None, "global"),
            ("vector", None, "global"),
            ("hybrid", 50, "global"),
            ("hybrid", 50, "distributed_global_ranks"),
        ]
        vals = [
            next(
                r["mean_historical_at"]["10"]
                for r in growth
                if (r["size"], r["method"], r["depth"], r["strategy"]) == (size, m, d, s)
            )
            for m, d, s in select
        ]
        lines.append(f"| {size:,} | " + " | ".join(f"{v:.2f}" for v in vals) + " |\n")
    lines.append(
        "\n![Rappel aux quatre profondeurs](figures/02-known-witness-recall.png)\n\nSources : [métriques agrégées](data/summary.json), [par requête](data/per-query-metrics.json), [suivi complet](data/witness-tracking.jsonl.gz).\n"
    )
    (HERE / "GROWTH.md").write_text("".join(lines))
    lines = [
        "# Profondeur et récupération distribuée\n\nLa distribuée prend L candidats par corpus et par branche, puis conserve les rangs globaux originaux dans RRF. Aucun rang de corpus n'est remis à 1. Les rangs globaux exacts sont disponibles ici grâce au calcul exhaustif : c'est un oracle expérimental, pas une capacité acquise pour une fédération d'index distants.\n\n## Au million de réponses\n\n| Stratégie | L | Témoins candidats /270 | Top10 /270 | Top20 /270 | Top50 /270 | Top100 /270 | Candidats moyens | Fusion moyenne (ms) |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    ]
    for r in growth:
        if r["size"] != 1000000 or r["method"] != "hybrid":
            continue
        cost = next(
            c
            for c in summary["costs"]
            if (c["size"], c["depth"], c["strategy"]) == (r["size"], r["depth"], r["strategy"])
        )
        lines.append(
            f"| {r['strategy']} | {r['depth']} | {r['candidate_witnesses']} | "
            + " | ".join(str(r["witnesses_at"][str(k)]) for k in (10, 20, 50, 100))
            + f" | {cost['mean_union_candidates']:.1f} | {cost['mean_fusion_ms']:.2f} |\n"
        )
    lines.append(
        "\n## Tous les paliers, tous les budgets\n\n| Réponses 2019 | Stratégie | L | Témoins candidats | Top10 | Top100 |\n|---:|---|---:|---:|---:|---:|\n"
    )
    for r in growth:
        if r["method"] == "hybrid":
            lines.append(
                f"| {r['size']:,} | {r['strategy']} | {r['depth']} | {r['candidate_witnesses']} | {r['witnesses_at']['10']} | {r['witnesses_at']['100']} |\n"
            )
    lines.append(
        "\nÀ L égal, le budget total de la distribuée est plus élevé. Au million, distribuée50 utilise 168,4 candidats moyens contre 95,1 pour globale50 ; globale100 utilise 190,3. Comparer seulement un taux de couverture à L égal surestimerait la spécificité du gain. Les témoins ajoutés ne sont pas nécessairement mieux classés face à tous les contemporains exclus du petit pool.\n\n![Effet des budgets](figures/04-candidate-depth.png)\n"
    )
    (HERE / "DEPTHS.md").write_text("".join(lines))
    perf = read(HERE / "data/performance.json")
    lines = [
        "# Coûts expérimentaux mesurés\n\nFichiers locaux, calcul exact, quatre threads BLAS, aucune nouvelle inférence. Médianes sur q01/q06/q25. Les temps ne sont pas une mesure du service PostgreSQL/ANN en production. L'export SQL est hors ligne.\n\n| Réponses 2019 | Segments existants | Vecteurs bruts (Mio) | Préparation du sous-tableau (ms) | Cosinus + agrégation (ms) | Tri vectoriel complet (ms) | BM25 (ms) | Tri lexical (ms) | RSS après palier (Gio) |\n|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    ]
    for r in perf["per_stage"]:
        m = r["median_ms"]
        lines.append(
            f"| {r['size']:,} | {r['modern_segments']:,} | {r['raw_vector_bytes'] / 1024**2:.2f} | {r['subset_preparation_seconds'] * 1000:.2f} | {m['vector_dot_aggregation_ms']:.2f} | {m['vector_full_sort_ms']:.2f} | {m['lexical_score_ms']:.2f} | {m['lexical_full_sort_ms']:.2f} | {r['rss_bytes'] / 1024**3:.2f} |\n"
        )
    lines.append(
        f"\nExport local : {perf['sql_export_seconds']:.2f}s pour 1 003 055 vecteurs existants ; tokenisation/statistiques préparées en {perf['lexical_preparation_seconds']:.2f}s ; 30 requêtes vectorielles calculées en {perf['full_30_query_vector_score_seconds']:.2f}s hors tri. Cache de travail : {perf['cache_bytes'] / 1024**3:.2f}Gio. Les fenêtres SQL de 1 000 documents sont bornées à 15 s ; les durées observées restent sous la seconde. Pas d'encodage de requête ni de chargement de modèle dans ces temps.\n"
    )
    lines.append(
        "\nLes RSS sont des observations du processus après chaque palier, avec pages mappées et caches déjà chauds ; ce ne sont pas des pics mémoire indépendants par requête. Le cache lexical ne conserve que les fréquences des termes des30 requêtes, mais les longueurs et les IDF sont calculés sur tous les documents : c'est une optimisation de calcul exacte, pas un index lexical général.\n"
    )
    (HERE / "PERFORMANCE.md").write_text("".join(lines))
    qmetrics = read(HERE / "data/qualitative-metrics.json")
    lines = [
        "# Pertinence des textes réellement relus\n\nDix requêtes fixées avant le nouveau classement : fiscalité, équité, dépenses, justice, responsabilité, expression et quatre contre-exemples. 445 couples relus ou réutilisés : 215 jugements antérieurs inchangés, 230 nouveaux jugements exploratoires Codex. Aucune indépendance historique/statistique. Toute configuration incomplètement jugée reste sans moyenne exacte.\n\n| Réponses 2019 | Méthode | Stratégie | L | Note@10 /3 | Utiles /100 | Hors sujet /100 |\n|---:|---|---|---:|---:|---:|---:|\n"
    ]
    for r in qmetrics["summary"]:
        if (
            r["subset"] == "all10"
            and r["unknown"] == 0
            and (r["method"] != "hybrid" or r["depth"] in (50, 1000))
        ):
            lines.append(
                f"| {r['size']:,} | {r['method']} | {r['strategy']} | {r['depth'] or '—'} | {r['mean_grade10']:.2f} | {r['useful_count']} | {r['off_topic_count']} |\n"
            )
    lines.append(
        "\n## Quatre contre-exemples\n\n| Réponses 2019 | Méthode | Stratégie | L | Note@10 /3 | Résultats historiques /40 | Utiles /40 |\n|---:|---|---|---:|---:|---:|---:|\n"
    )
    for r in qmetrics["summary"]:
        if (
            r["subset"] == "counterexamples4"
            and r["unknown"] == 0
            and (r["method"] != "hybrid" or r["depth"] == 50)
        ):
            lines.append(
                f"| {r['size']:,} | {r['method']} | {r['strategy']} | {r['depth'] or '—'} | {r['mean_grade10']:.3f} | {r['historical_count']} | {r['useful_count']} |\n"
            )
    lines.append(
        "\nLes tableaux ne valent pas pour les 20 autres requêtes au million. Les notes 0 et 1 sont distinguées ; une proximité superficielle n'est pas un résultat utile. [Notes, textes justificatifs et origines](data/qualitative-judgments.json).\n"
    )
    (HERE / "QUALITY.md").write_text("".join(lines))
    gallery()


def gallery():
    hist = rows(HERE / "data/history.jsonl")
    track = gzrows("witness-tracking")
    lookup = {
        (r["size"], r["query_id"], r["g"], r["depth"], r["strategy"]): r
        for r in track
        if r["method"] == "hybrid"
    }
    queries = {q["id"]: q for q in read(HERE / "queries.json")["queries"]}
    cases = [
        (
            "Une revendication historique reste première",
            "q13",
            168,
            "La suppression des aides et gabelles reste première en vectoriel et RRF au million. Le petit corpus n'est donc pas exclu par une règle de date ou par un quota.",
        ),
        (
            "Concurrence contemporaine pertinente",
            "q07",
            132,
            "Les demandes de comptes des élus de 2019 sont souvent directement pertinentes pour cette formulation. La régression de Mirecourt est compatible avec une concurrence réelle ; la note 3 ne permet pas de prouver que chaque contemporain est strictement meilleur.",
        ),
        (
            "Concurrence et exclusion des candidats",
            "q02",
            258,
            "Albertas passe du rang vectoriel 13 à 33 692. Il ne peut plus entrer dans la RRF globale50. Les nouvelles réponses fiscales du top 10 sont fréquemment fortes ; l'exclusion technique et la concurrence peuvent coexister.",
        ),
        (
            "Une faiblesse déjà présente dans la référence",
            "q01",
            203,
            "Pierrelez n'était déjà pas candidat global50 à 240 réponses (vectoriel 92). La croissance aggrave son accessibilité ; elle n'a pas créé à elle seule ce défaut initial.",
        ),
        (
            "Un article très court reste loin derrière",
            "q06",
            196,
            "Abrégé des frais de procédure : le rang vectoriel passe de 15 à 18 570. Le texte ne change pas. Beaucoup de nouveaux documents sont pertinents, mais ce texte bref et historiquement formulé reste très mal récupéré.",
        ),
        (
            "Un article long d'accès à une défense abordable",
            "q06",
            268,
            "Beaurecueil est encore candidat vectoriel 48 à 240 réponses puis 112 dès 1 000, et 71 999 au million. La longueur et le contenu multithématique sont des facteurs possibles, pas une causalité isolée par cette croissance.",
        ),
        (
            "Responsabilité ministérielle : disparition précoce",
            "q03",
            63,
            "Le Beaujolais est déjà 62e en vectoriel à 240, puis 228 395e au million. Il est conservé comme témoin malgré cet échec, sans prétendre qu'il était bien récupéré au départ.",
        ),
        (
            "Candidats présents, fusion discutable",
            "q06",
            137,
            "Mirecourt, frais de procès : vectoriel 28 au million, mais RRF 53. Un résultat sur le coût des transports, annoté 0, est 7e en RRF grâce à son rang lexical 3. Ce cas documente un classement défectueux selon les notes, sans attribuer la faute au seul ratio des corpus.",
        ),
        (
            "Récupéré plus profondément, sans retrouver les premières pages",
            "q10",
            158,
            "La presse de Ferrières reste première à 240 en vectoriel, mais 703e au million. Global1000 la récupère puis la classe 1 289e en RRF : gagner des candidats n'est pas gagner le top 100.",
        ),
        (
            "Gain réel de profondeur à un palier intermédiaire",
            "q14",
            254,
            "À 20 000 réponses, ce passage de répartition fiscale est absent de globale50 mais atteint le rang 76 en globale1000. Un gain existe ; il n'est ni universel ni maintenu au million.",
        ),
        (
            "OCR conservé, sans réparation opportuniste",
            "q14",
            116,
            "L'article de Montigny avec caractères dégradés passe du rang vectoriel 21 à 53 763. L'expérience ne corrige pas l'OCR et ne mesure pas séparément son effet.",
        ),
    ]
    lines = [
        "# Galerie documentaire et causes observées\n\nLes textes exacts et références sont conservés dans [history.jsonl](data/history.jsonl) et [les documents contemporains relus](data/qualitative-documents.jsonl). Blancs réduits uniquement pour affichage ; les longs textes ci-dessous sont explicitement abrégés. Les notes historiques sont héritées et non indépendantes. Les causes peuvent se cumuler : exclusion d'un pool fini et concurrence pertinente ne sont pas deux populations disjointes.\n"
    ]
    for number, (title, qid, g, comment) in enumerate(cases, 1):
        d = hist[g]
        grade = next(r["original_grade"] for r in track if r["query_id"] == qid and r["g"] == g)
        text = d["text"]
        excerpt = " ".join(text[:900].split()) + (" […]" if len(text) > 900 else "")
        lines.append(
            f"\n## {number}. {title}\n\n**{queries[qid]['text']}** · {d['title']} · {d['label']} · note héritée {grade}/3.\n\n> {excerpt}\n\n{comment}\n\n| Réponses 2019 | Rang lexical | Rang vectoriel | Global50 | Global1000 | Distribuée50 |\n|---:|---:|---:|---:|---:|---:|\n"
        )
        for size in read(HERE / "protocol.json")["stages"]:
            a = lookup[size, qid, g, 50, "global"]
            b = lookup[size, qid, g, 1000, "global"]
            c = lookup[size, qid, g, 50, "distributed_global_ranks"]
            values = [
                a["lexical_rank"],
                a["vector_rank"],
                a["final_rank"],
                b["final_rank"],
                c["final_rank"],
            ]
            lines.append(
                f"| {size:,} | " + " | ".join(str(v) if v else "Absent" for v in values) + " |\n"
            )
        ref = d["references"]
        pages = ", ".join(x["n"] or x["id"] + " (pagination absente)" for x in ref["pages"])
        lines.append(
            f"\nCosinus A constant : `{a['vector_score']:.6f}`. Référence : AP, t.{ref['volume']}, p./vue{pages}. [Volume numérisé]({ref['scan_url']}). Identifiant `{d['id']}`, parent `{d['parent_id']}`, ancre `{ref['anchor']}`.\n"
        )
    docs = {d["g"]: d for d in rows(HERE / "data/qualitative-documents.jsonl")}
    grades = {
        (j["query_id"], j["g"]): j
        for j in read(HERE / "data/qualitative-judgments.json")["judgments"]
    }
    ranks = gzrows("rankings")
    lines.append(
        "\n## Concurrents contemporains vérifiés\n\n"
        "Ces exemples complètent les témoins historiques ci-dessus. Les notes nouvelles "
        "sont exploratoires. Les questions font partie du contexte de lecture ; "
        "elles sont distinctes des réponses exactes. Les identifiants et liens "
        "permettent de retrouver la contribution source.\n"
    )
    for qid, selected in (
        ("q02", [896101, 849673]),
        ("q07", [1998, 575665]),
        ("q06", [66461, 357674]),
    ):
        run = next(
            r
            for r in ranks
            if r["size"] == 1000000
            and r["query_id"] == qid
            and r["method"] == "hybrid"
            and r["depth"] == 50
            and r["strategy"] == "global"
        )
        lines.append(f"\n### {queries[qid]['text']}\n")
        for g in selected:
            d = docs[g]
            result = next(r for r in run["results"] if r["g"] == g)
            grade = grades[qid, g]
            excerpt = " ".join(d["text"].split())
            lines.append(
                f"\nRRF globale 50 : rang **{result['rank']}**, note **{grade['grade']}/3**, "
                f"`{d['id']}`. Question : {d['question']}\n\n"
                f"> {excerpt}\n\n{grade['reason']} "
                f"[Contexte documentaire](https://cahierdedoleances.fr{d['references']['context_path']}).\n"
            )
    lines.append(
        "\n## Quatre contre-exemples : les textes modernes comptent aussi\n\nLes faux amis historiques disparaissent du top 10 au million pour ces quatre requêtes. Cela ne suffit pas à déclarer les nouveaux résultats pertinents : coopération interne et lutte fiscale restent de mauvais rapprochements.\n"
    )
    for qid in ("q19", "q22", "q25", "q28"):
        lines.append(
            f"\n### {queries[qid]['text']}\n\n| Méthode au million | Rang | Identifiant expérimental | Note | Texte réel |\n|---|---:|---|---:|---|\n"
        )
        for method in ("lexical", "vector", "hybrid"):
            run = next(
                r
                for r in ranks
                if r["size"] == 1000000
                and r["query_id"] == qid
                and r["method"] == method
                and (method != "hybrid" or r["depth"] == 50 and r["strategy"] == "global")
            )
            for r in run["results"][:3]:
                d = docs[r["g"]]
                text = " ".join(d["text"][:450].split()).replace("|", "\\|") + (
                    " […]" if len(d["text"]) > 450 else ""
                )
                lines.append(
                    f"| {method} | {r['rank']} | g{r['g']} | {grades[qid, r['g']]['grade']} | {text} |\n"
                )
    lines.append(
        "\n## Représentation : diagnostic apparié séparé\n\nSur 510 mêmes réponses 2019 complètes disposant déjà de vecteurs A/B, l'ajout de la question change le score moyen de +0,00687. Parmi 270 couples témoins, 121 reculent, 124 avancent et 25 sont stables ; leur rang moyen passe de 83,26 à 85,29. L'effet de recette existe, mais n'est pas un avantage uniforme du contemporain. Cohorte de développement non représentative, ajoutée comme diagnostic secondaire après observation des classements principaux ; aucun résultat principal modifié. [Scores et références du contrôle](data/context-control.json).\n"
    )
    (HERE / "GALLERY.md").write_text("".join(lines))


if __name__ == "__main__":
    main()
