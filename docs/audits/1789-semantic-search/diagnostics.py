"""Diagnostics complémentaires et galerie référencée, sans modifier les rangs."""

import collections
import statistics

from common import HERE, read, rows, write

EXAMPLES = [
    (
        "réussite",
        "q02",
        "h259",
        "La répartition équitable retrouve « égale répartition dans la taxe des impôts ». Le terme fiscalité n'est pas nécessaire. Aucun résultat lexical dans les50 conservés.",
    ),
    (
        "réussite",
        "q03",
        "h064",
        "Les ministres comptables aux États généraux répondent à la préoccupation de contrôle des finances. Ce contrôle représentatif historique n'est pas identique à un contrôle direct par tous les citoyens.",
    ),
    (
        "réussite",
        "q06",
        "h197",
        "« Abrégé des frais de procédure » répond au coût de la justice sans contenir justice ou justiciables. C'est un gain vectoriel concret hors des50 résultats lexicaux.",
    ),
    (
        "réussite",
        "q10",
        "h159",
        "Liberté de la presse et de la parole : correspondance forte. Le lexical trouve aussi cet article, au6e rang ; le vectoriel le promeut en tête.",
    ),
    (
        "réussite",
        "q08",
        "h005",
        "Limitation du pouvoir arbitraire par abolition des lettres de cachet et remise au juge. Le contexte B retrouve cette garantie au4e rang historique, contre une récupération A moins favorable.",
    ),
    (
        "réussite",
        "q07",
        "h133",
        "Rendre des comptes / être comptable de son administration : lien solide. Des ministres historiques ne sont pas pour autant les mêmes acteurs que des élus contemporains.",
    ),
    (
        "partiel",
        "q01",
        "h187",
        "Réduire tous les impôts à un seul en change le nombre, pas nécessairement le montant. Premier résultat vectoriel A, mais note2 seulement ; aucune baisse globale ne doit être inférée.",
    ),
    (
        "échec",
        "q22",
        "h129",
        "États généraux et coopération entre États souverains sont deux objets différents. Similarité élevée sans pertinence utile : un cosinus n'est pas une probabilité.",
    ),
    (
        "échec",
        "q19",
        "h217",
        "« Première classe » décrit des terres, pas un effectif scolaire. Le premier résultat lexical est trompeur ; les résultats vectoriels historiques ne trouvent pas davantage de réponse utile.",
    ),
    (
        "échec",
        "q25",
        "h194",
        "Un bail de biens de campagne ne répond pas au déploiement de la fibre optique. Premier résultat vectoriel A et hybride A dans le sous-corpus historique.",
    ),
    (
        "échec",
        "q28",
        "h026",
        "Poursuivre des écrivains jugés irréligieux n'est pas lutter contre une cyberattaque. Le modèle retrouve une notion d'attaque/répression sans l'objet technique de la requête.",
    ),
    (
        "partiel",
        "q27",
        "h265",
        "Les voitures sont ici attelées de mulets ou chevaux. Le lexical place ce passage en tête historique ; aucune propulsion électrique ni subvention n'existe dans ce texte.",
    ),
    (
        "manqué",
        "q09",
        "h254",
        "L'article pertinent sur des bureaux de district est présent mais reste14e en vectoriel A et36e en B. L'échec du top10 ne vient donc pas de l'absence documentaire.",
    ),
    (
        "manqué",
        "q01",
        "h204",
        "La modération des impositions de Pierrelez est directement pertinente, mais n'arrive qu'au26e rang A et28e rang B, hors top10 de toutes les méthodes.",
    ),
    (
        "manqué",
        "q06",
        "h269",
        "Un défenseur indépendant sans paiement pour les petites communautés répond à l'accès économique à la justice. Il demeure28e en A et32e en B, avec une longue unité multithématique.",
    ),
]


def main():
    import numpy as np

    corpus = rows(HERE / "data/corpus.jsonl")
    by_id = {d["id"]: d for d in corpus}
    by_short = {d["short_id"]: d for d in corpus}
    rankings = rows(HERE / "data/rankings.jsonl")
    lookup = {(r["query_id"], r["population"], r["method"]): r["results"] for r in rankings}
    judgments = {
        (j["query_id"], j["unit_id"]): j for j in read(HERE / "annotations.json")["judgments"]
    }
    questions = {q["id"]: q for q in read(HERE / "queries.json")["queries"]}
    # Cached/re-encoded precision check: only these16 entries are changed, diagnostically.
    from search import vector_rank

    modern = rows(HERE / "data/contemporary-segments.jsonl")
    historical = rows(HERE / "data/historical-segments.jsonl")
    reused = np.load(HERE / "vectors/contemporary.npy", allow_pickle=False)
    fp32 = np.load(HERE / "vectors/precision-check-fp32.npy", allow_pickle=False)
    checked = read(HERE / "data/encoding.json")["precision_check"]
    altered = reused.copy()
    indices = {r["unit_id"]: i for i, r in enumerate(modern)}
    for row, check in zip(fp32, checked):
        altered[indices[check["unit_id"]]] = row
    qvec = np.load(HERE / "vectors/queries.npy", allow_pickle=False)
    precision_changes = []
    for variant in ("A", "B"):
        matrix = np.concatenate(
            [np.load(HERE / f"vectors/historical_{variant}.npy", allow_pickle=False), altered]
        )
        refs = [r for r in historical if r["variant"] == variant] + modern
        for i, qid in enumerate(questions):
            result = vector_rank(qvec[i], matrix, refs, set(by_id))
            old = [r["id"] for r in lookup[qid, "mixed", f"vector_{variant}"][:10]]
            new = [r["id"] for r in result[:10]]
            precision_changes.append(
                dict(
                    variant=variant,
                    query_id=qid,
                    top10_set_changes=len(set(old) ^ set(new)) // 2,
                    order_changed=old != new,
                )
            )
    timing = rows(HERE / "data/rankings.jsonl")  # Force all ranking records to remain readable.
    assert len(timing) == 300
    timings = read(HERE / "data/search-timings.json")
    costs = []
    for population in ("historical", "mixed"):
        rr = [r for r in timings if r["population"] == population]
        for method in read(HERE / "protocol.json")["methods"]:
            search, with_query = [], []
            for r in rr:
                ms = r["ms"][method]
                if method.startswith("hybrid"):
                    ms += r["ms"]["lexical"] + r["ms"]["vector_" + method[-1]]
                search.append(ms)
                with_query.append(ms + (r["query_encoding_ms"] if method != "lexical" else 0))
            costs.append(
                dict(
                    population=population,
                    method=method,
                    mean_search_ms=statistics.mean(search),
                    median_search_ms=statistics.median(search),
                    max_search_ms=max(search),
                    mean_including_query_ms=statistics.mean(with_query),
                )
            )
    shared = []
    for qid in questions:
        selected = lookup[qid, "mixed", "vector_A"][:10]
        hist = [
            r
            for r in selected
            if by_id[r["id"]]["status"] == "A" and judgments[qid, r["id"]]["grade"] >= 2
        ]
        modern_hits = [
            r
            for r in selected
            if by_id[r["id"]]["status"] != "A" and judgments[qid, r["id"]]["grade"] >= 2
        ]
        if hist and modern_hits:
            shared.append(
                dict(
                    query_id=qid,
                    historical=[by_id[r["id"]]["short_id"] for r in hist],
                    contemporary=[by_id[r["id"]]["short_id"] for r in modern_hits],
                )
            )
    coverage = []
    for qid, q in questions.items():
        hist_j = [
            j for (qid2, did), j in judgments.items() if qid2 == qid and by_id[did]["status"] == "A"
        ]
        modern_j = [
            j for (qid2, did), j in judgments.items() if qid2 == qid and by_id[did]["status"] != "A"
        ]
        coverage.append(
            dict(
                query_id=qid,
                historical_useful_known=sum(j["grade"] >= 2 for j in hist_j),
                contemporary_useful_known=sum(j["grade"] >= 2 for j in modern_j),
                historical_absence="No useful historical passage identified after reading all269; not evidence of absence in1789 overall"
                if not any(j["grade"] >= 2 for j in hist_j)
                else None,
            )
        )
    write(
        HERE / "data/diagnostics.json",
        dict(
            costs=costs,
            precision_sensitivity_16_only=precision_changes,
            mixed_vector_A_both_corpora_useful=shared,
            coverage=coverage,
            contemporary_theme_literal_counts={
                name: sum(
                    any(w in d["text"].casefold() for w in words)
                    for d in corpus
                    if d["status"] != "A"
                )
                for name, words in {
                    "fiscalite": ["impôt", "impot", "fiscal", "tva"],
                    "justice": ["justice", "judiciaire", "tribun"],
                    "representation": ["déput", "deput", "élu", "élection"],
                    "inegalites": ["inégal", "pauvre", "riche"],
                    "ecologie": ["écolo", "climat", "pollution"],
                }.items()
            },
            lengths_by_corpus={
                label: dict(
                    units=len(ds),
                    min_chars=min(len(d["text"]) for d in ds),
                    median_chars=statistics.median(len(d["text"]) for d in ds),
                    max_chars=max(len(d["text"]) for d in ds),
                )
                for label, ds in (
                    ("1789", [d for d in corpus if d["status"] == "A"]),
                    ("2019", [d for d in corpus if d["status"] != "A"]),
                )
            },
        ),
    )
    lines = [
        "# Galerie de résultats réels\n\nJugements exploratoires Codex, non indépendants. Blancs réduits uniquement dans cette galerie ; textes exacts dans [le corpus](data/corpus.jsonl) et [les résultats détaillés](data/results.jsonl). Chaque rang se rapporte à la population indiquée ; « >50 / absent » ne distingue pas rang inférieur et absence de correspondance lexicale. Les scores sont des cosinus, BM25 ou RRF, pas des probabilités.\n"
    ]
    for number, (kind, qid, short, comment) in enumerate(EXAMPLES, 1):
        d = by_short[short]
        j = judgments[qid, d["id"]]
        lines.append(
            f"\n## {number}. {kind} — {questions[qid]['text']}\n\n{d['title']} · {d.get('label', '')} · note **{j['grade']}/3**.\n\n> {' '.join(d['text'].split())}\n\n{comment}\n\n| Population | Méthode | Rang | Score |\n|---|---|---:|---:|\n"
        )
        for population in ("historical", "mixed"):
            for method in read(HERE / "protocol.json")["methods"]:
                r = next((r for r in lookup[qid, population, method] if r["id"] == d["id"]), None)
                rank = str(r["rank"]) if r else ">50 / absent"
                score = f"{r['score']:.6f}" if r else "—"
                lines.append(f"| {population} | {method} | {rank} | {score} |\n")
        refs = d["references"]
        pages = ", ".join(p["n"] or f"pagination absente, vue {p['id']}" for p in refs["pages"])
        lines.append(
            f"\nRéférence : AP, tome{refs['volume']}, p.{pages}. [Volume numérisé]({refs['scan_url']}). [Source TEI figée]({refs['source_url']}). Identifiant `{d['id']}`, parent `{d['parent_id']}`, ancre `{refs['anchor']}`.\n"
        )
    lines.append(
        "\n## Une liste commune réellement calculée\n\nPour « Les représentants doivent-ils rendre des comptes aux citoyens ? », les dix premiers résultats de vector_A mélangent les deux corpus sans quota. Les propositions restent distinctes : révocation ou promesses des élus en2019, responsabilité des ministres en1789.\n\n| Rang | Corpus | Passage | Note | Cosinus |\n|---:|---|---|---:|---:|\n"
    )
    for r in lookup["q07", "mixed", "vector_A"][:10]:
        d = by_id[r["id"]]
        lines.append(
            f"| {r['rank']} | {d['corpus']} | {d['short_id']} : {' '.join(d['text'].split())} | {judgments['q07', d['id']]['grade']} | {r['score']:.6f} |\n"
        )
    (HERE / "GALLERY.md").write_text("".join(lines))
    print(f"Gallery: {len(EXAMPLES)} cases; mixed shared-useful queries: {len(shared)}")
    print(
        "Precision sensitivity:",
        collections.Counter(
            (r["top10_set_changes"], r["order_changed"]) for r in precision_changes
        ),
    )


if __name__ == "__main__":
    main()
