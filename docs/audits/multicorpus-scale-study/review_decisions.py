"""Annotations exploratoires explicites, après lecture des230 nouveaux couples."""

from common import HERE, read, rows, sha, write

GROUPS = {
    "q01": [
        (
            3,
            "55798 154949 156176 171328 192533 201485 205437 236639 323855 619033 672701 714640 729976 781604 784977 832492 853497 883868 908684 931590",
            "Répond directement à l'opportunité de baisser les impôts, par une demande, un refus ou des conditions explicites ; l'opposition n'est pas hors sujet.",
        ),
        (
            2,
            "169795",
            "Réduire d'abord les types d'impôts : simplification du nombre, sans baisse nécessaire du montant, comme le témoin historique d'Ermenonville.",
        ),
    ],
    "q02": [
        (
            3,
            "58542 178458 242378 313890 336816 403943 576334 601568 734733 739533 771834 817211 837808 849673 896101",
            "Répartition de l'effort fiscal explicitement discutée ; les réponses courtes héritent ici de la question fiscale réellement disponible.",
        ),
        (
            2,
            "343794 495794 630172 907551",
            "Redistribution des richesses/recettes ou autre articulation fiscale ; préoccupation voisine, pas toujours répartition du prélèvement entre contribuables.",
        ),
        (
            1,
            "614517",
            "Redistribuer les allocations n'est pas une proposition sur la répartition de l'impôt.",
        ),
        (0, "974263", "Répartir des migrants, pas la charge fiscale : faux rapprochement lexical."),
    ],
    "q03": [
        (
            3,
            "21356 21785 77402 151432 168397 250799 324321 325621 370307 552634 600837 689981 704553 731291 746064 767965 798724 876231 896851 956572 998680",
            "Contrôle, transparence ou justification des dépenses publiques explicitement demandés ; contrôle direct, parlementaire ou indépendant distingués dans le texte.",
        ),
        (
            2,
            "157206",
            "Questionne les justificatifs des dépenses des élus ; préoccupation pertinente, sans dispositif de contrôle citoyen aussi explicite.",
        ),
    ],
    "q06": [
        (
            3,
            "12292 133681 180898 396874 450288 474797 591332 961239 978076",
            "Frais de justice, coût des procédures, soutien aux personnes sans moyens ou accès gratuit explicitement discutés. Le propos cité reste celui du contributeur.",
        ),
        (
            2,
            "366523",
            "Financer la justice par les justiciables pour économiser aux contribuables : thème des frais réellement abordé, mais proposition opposée à leur allégement.",
        ),
        (
            2,
            "421578 940134",
            "Complexité/coût de fonctionnement judiciaire et justiciable démuni : lien réel mais pas réduction explicite des frais individuels.",
        ),
        (
            1,
            "23463 48120 209421 281487 285837 574221 588564 630039 774693 945255",
            "Justice ou moindre coût général ; ne traite pas précisément du coût d'accès aux procès. Les questions Pourquoi/Si oui ne suffisent pas à inventer un contexte judiciaire.",
        ),
        (
            0,
            "66461 357674",
            "Moindre coût des transports ou réparations d'appareils : aucun lien avec les frais judiciaires.",
        ),
    ],
    "q07": [
        (
            3,
            "1998 62391 63564 106304 199746 241111 242284 277397 286972 327624 475563 575665 672220 697936 713643 731382 776462 777518 838591 840646 870965 937725 979864 988305",
            "Reddition des comptes, respect du mandat, sanctions ou révocation des représentants explicitement demandés.",
        ),
        (
            2,
            "704246",
            "Rendre des comptes est explicite, mais le sujet ils reste indéterminé dans la seule question Si oui, comment ? disponible.",
        ),
    ],
    "q10": [
        (
            3,
            "32324 65487 72370 94956 180079 241333 297342 298218 340362 409622 603997 627811 670232 676118 682283 731332 787836 881364 974801",
            "Liberté de parole/presse, protection des locuteurs ou limites légales expressément discutées ; noter la pertinence ne valide ni les affirmations légales ni les opinions.",
        ),
        (
            2,
            "124994 135240 232569 317083 957574",
            "Limites, diagnostic d'atteinte, parole d'assemblées ou anonymat en ligne : même préoccupation, proposition ou contexte partiellement différent.",
        ),
    ],
    "q19": [
        (
            3,
            "48115 71503 98042 162587 205775 222589 228788 262910 273810 287710 377802 407148 409915 557224 600101 825801 947357",
            "Nombre d'élèves par classe, limites chiffrées ou dédoublement explicitement demandés ; correspondance scolaire forte.",
        ),
        (
            2,
            "93109 381357 417849 421318",
            "Petites classes, moyens enseignants ou organisation scolaire apparentée, sans même plafond explicite d'élèves par classe.",
        ),
        (
            1,
            "308547 721318 751408",
            "Taille d'établissement ou classes sociales, pas les effectifs d'une classe.",
        ),
        (
            0,
            "126147 543813 902311",
            "Taille des villes, voitures ou cabinets : faux ami hors sujet scolaire.",
        ),
    ],
    "q22": [
        (
            3,
            "31120 212907 222542 362890",
            "Coopération entre pays ou États explicitement demandée, sur l'environnement ou les migrations.",
        ),
        (
            1,
            "90195 106869 234671 342462 343327 598086 675270 766882 767084 771547 778234 784547 796705 807611 854081 881636 905899 999460",
            "Coopération interne État/collectivités/entreprises ou organisation nationale ; ne répond pas à la coopération entre États souverains. La disparition du1789 ne suffit donc pas à garantir la pertinence.",
        ),
    ],
    "q25": [
        (
            3,
            "51397 71387 142269 184672 190373 238229 276887 280074 516327 629185 732662 847072 927533",
            "Déploiement de fibre/internet dans les campagnes, territoires isolés ou partout explicitement demandé.",
        ),
        (
            2,
            "75818 254234 274275 522065 746694 764706 864297 912094",
            "Fibre optique/déploiement explicitement présent, mais sans priorité rurale ou modalité aussi précise.",
        ),
        (
            1,
            "78468",
            "Réseaux en campagne dans une question de mobilité : aucune fibre optique explicitement identifiable.",
        ),
    ],
    "q28": [
        (
            3,
            "45912 540711 705772 778727",
            "Sécurité informatique, exfiltration, cyber-guerre, hackers, virus ou protection technique des usagers directement abordés.",
        ),
        (
            2,
            "437639",
            "Cybercriminalité, prévention et protection en ligne ; domaine plus large, comprenant arnaques et fausses informations.",
        ),
        (
            1,
            "334355 368798 660884 730853 958630",
            "Harcèlement/fake news/anonymat ou police en ligne : proximité numérique, pas réponse technique aux cyberattaques.",
        ),
        (
            0,
            "452 106463 141853 286813 342091 448280 462528 705263 712715 877776 913728 928786",
            "Lutte contre fraude fiscale, pauvreté, climat ou réseaux d'influence ; aucun objet informatique correspondant à la requête.",
        ),
    ],
}


def main():
    pool = read(HERE / "data/qualitative-pool.json")
    documents = {d["g"]: d for d in rows(HERE / "data/qualitative-documents.jsonl")}
    expected = {(r["query_id"], r["g"]) for r in pool if r["needs_new_judgment"]}
    explicit = {}
    for qid, groups in GROUPS.items():
        for grade, identifiers, reason in groups:
            for raw in identifiers.split():
                g = int(raw)
                assert (qid, g) not in explicit
                explicit[qid, g] = (grade, reason)
    assert set(explicit) == expected, (expected - set(explicit), set(explicit) - expected)
    judgments = []
    for r in pool:
        qid, g = r["query_id"], r["g"]
        if r["prior_judgment"] is not None:
            j = r["prior_judgment"]
            judgments.append(
                dict(
                    query_id=qid,
                    g=g,
                    unit_id=r["unit_id"],
                    grade=j["grade"],
                    reason=j["reason"],
                    source="inherited_1789_semantic_search",
                    original_judgment=j,
                )
            )
        else:
            grade, reason = explicit[qid, g]
            judgments.append(
                dict(
                    query_id=qid,
                    g=g,
                    unit_id=r["unit_id"],
                    grade=grade,
                    reason=reason,
                    source="Codex_exploratory_scale_study_non_independent",
                    evidence_text=documents[g]["text"],
                )
            )
    write(
        HERE / "data/qualitative-judgments.json",
        dict(
            pool_sha256=sha(HERE / "data/qualitative-pool.json"),
            new_pairs=230,
            inherited_pairs=215,
            judgments=judgments,
            annotation_policy="Initial reading of full texts in packs without scores; same Codex author as experiment, not blind independent validation. Prior judgments preserved exactly. No automatic grade based on words/scores.",
        ),
    )
    print("445 judgments:215 inherited unchanged,230 new exploratory")


if __name__ == "__main__":
    main()
