"""Rapports fondés sur les sorties conservées et les décisions de lecture explicites."""

from lib import HERE, read, rows


def put(name, text):
    (HERE / name).write_text(text.strip() + "\n")


def table(headers, lines):
    def cell(x):
        return str(x).replace("|", " / ").replace("\n", " ")

    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]
        + ["| " + " | ".join(cell(x) for x in line) + " |" for line in lines]
    )


def main():
    m = read(HERE / "data/evaluation-metrics.json")
    f = read(HERE / "data/freeze.json")
    z = read(HERE / "data/zone-metrics.json")
    rr = rows(HERE / "data/registry.jsonl")
    checks = read(HERE / "data/checks.json")
    ann = rows(HERE / "data/annotations.jsonl")
    queue = rows(HERE / "data/review-queue.jsonl")
    put(
        "README.md",
        f"""
# Registre documentaire expérimental des Archives parlementaires, tomes I–VI

Étude locale du 27 octobre 2026. **Le registre des 1 305 entrées `griev` est construit. La stratégie C est utile pour l’inventaire, mais les frontières ne permettent pas encore une extraction systématique sans contrôle.** Ni l’application, ni PostgreSQL, ni les index n’ont été modifiés. Aucun article ni embedding nouveau n’a été produit. Aucun texte intégral Persée téléchargé.

## Résultats

{
            table(
                ["Objet", "Résultat"],
                [
                    (
                        "Notices METS rapprochées des notices OAI",
                        "1 305 / 1 305 ; six tomes ; aucune divergence titre/type entre ces deux descriptions",
                    ),
                    (
                        "Identités automatiques",
                        "964 fortes ; 182 probables ; 75 ambiguës ; 32 non retrouvées ; 52 hors périmètre retenu",
                    ),
                    (
                        "Nature documentaire automatique",
                        "1 227 cahiers autonomes probables ; 20 documents associés ; 4 PV ; 2 extraits ; 46 listes ; 1 autre document ; 5 notices d’absence",
                    ),
                    (
                        "Frontières automatiques",
                        "1 236 plages : 988 proposées sans alerte propre, 248 ambiguës ; 69 notices sans plage",
                    ),
                    (
                        "Contrôle inédit",
                        "100 notices : 69 identités compatibles, 3 fausses propositions, 1 identité incertaine ; 19 abstentions récupérables, 1 abstention non résolue, 1 exclusion erronée, 6 listes sans identité exhaustive examinée",
                    ),
                    (
                        "Frontières nouvellement contrôlées",
                        "52 conformes / 67 tranchées (77,6 %) ; 15 incorrectes ; 4 autres incertaines ; 29 non évaluées",
                    ),
                    (
                        "Références de frontières conservées",
                        "78 : 26 héritées + 52 nouveaux contrôles Codex ; aucune validation humaine indépendante",
                    ),
                    (
                        "Complément Stanford",
                        "92 hypothèses V2 admises sans ancre primaire équivalente Persée ; 55 hypothèses V2 incertaines conservées séparément",
                    ),
                    (
                        "File de contrôle des notices",
                        "189 hautes, 295 intermédiaires, 821 à contrôler par échantillonnage",
                    ),
                ],
            )
        }

Ces nombres décrivent des **hypothèses**, pas 1 227 cahiers historiquement certifiés. Les 100 cas surreprésentent les difficultés. Le résultat de 77,6 % ne mesure ni tous les documents ni la complétude de leur corps. Quatre frontières supplémentaires incertaines donnent seulement 52 conformes sur 71 examinées, sans assimiler les incertitudes à des réussites. Aucun taux global n’est extrapolé.

## Livrables

- [REGISTRY.md](REGISTRY.md) : schéma, statuts, identifiants et utilisation des plages.
- [ALIGNMENT.md](ALIGNMENT.md) : règles réutilisées, gel et exemples.
- [EVALUATION.md](EVALUATION.md) : référence exploratoire, erreurs et zones indépendantes du catalogue.
- [REVIEW.md](REVIEW.md) : contrôles classés et liste nominative.
- [COVERAGE.md](COVERAGE.md) : couverture et désaccords entre inventaires.
- [REPRODUCIBILITY.md](REPRODUCIBILITY.md) : scripts, empreintes, commandes et droits.
- `data/registry.jsonl.gz` : registre enrichi complet ; `data/registry-automatic.jsonl.gz` : prédictions inchangées.
- `data/annotations.jsonl`, `data/zone-annotations.jsonl` : décisions de lecture, séparées du calcul.

## Réponses aux dix questions

1. **Cahiers autonomes probables :** 1 227 selon la classification automatique ; leur autonomie reste à contrôler. Le titre seul ne permet pas de trancher tous les dossiers composites.
2. **Associés / hors périmètre :** 20 associés + 4 PV + 2 extraits, conservés ; 46 listes + 1 autre + 5 absences classés hors périmètre de recherche. Les contrôles montrent notamment que Turenne doit rester comme annexe et que l’absence du clergé de Chaumont ne vaut pas absence de sa noblesse. Les prédictions originales restent visibles.
3. **Rapprochements forts :** 964, non automatiquement vérifiés.
4. **Ambigus ou introuvables :** 75 + 32. Sur les 20 abstentions nouvelles contrôlées, 19 ont été localisées par une recherche documentaire complémentaire, sans changer l’algorithme. La vingtième reste non résolue, sans preuve d’absence du texte.
5. **Frontières proposées :** 1 236 ; 69 notices sans plage. Une plage peut être trop courte, trop longue ou viser un voisin.
6. **Exactitude contrôlée :** 52/67 frontières tranchées ; 4 incertaines. Contrôle des extrémités dans le TEI par Codex, sans collation intégrale ni validation humaine indépendante.
7. **Documents manquants :** 92 propositions V2 sans équivalent d’ancre, à examiner ; ce ne sont pas 92 omissions avérées de Persée. Les pouvoirs du clergé de Saintonge et le mémoire Goullin sont présents dans Stanford mais non identifiés comme unités dans le registre automatique. Voir les limites de catalogue/dossier dans COVERAGE.
8. **Vérification restante :** 189 notices prioritaires + 295 intermédiaires, puis contrôle stratifié des 821 autres ; ajouter le complément Stanford et les cas incertains. 1 227 notices n’ont aucune référence de frontières contrôlées. Aucun temps humain mesuré et aucune estimation en heures défendable.
9. **Obstacles à l’extraction des articles :** dossiers mêlés dans une division, pièces précédant/suivant le corps, titres internes manqués, homonymes sur une page, OCR et colonnes intercalées. Aucune segmentation massive d’articles n’a été lancée.
10. **Méthode recommandée :** conserver C pour le registre, corriger d’abord les parents prioritaires par décisions versionnées, séparer cahier et pièces liées, faire valider un lot stratifié par un lecteur indépendant, puis autoriser l’extraction des seuls parents dont le périmètre est établi. Garder des abstentions pour les autres. Le registre est exploitable comme outil documentaire, pas comme corpus intégral certifié.
""",
    )
    put(
        "REGISTRY.md",
        """
# Schéma du registre

Une ligne = une entrée Persée `griev`, sans suppression des listes ni fusion de deux notices. `id = ap1789-registry-p1:<identifiant Persée>` : l’identité ne change pas lors d’une correction de frontière. Les identifiants Persée sont bibliographiques ; les identifiants internes et `source_witness_id` sont techniques.

`metadata` conserve titre, genre METS/DC, volume, pages, citation, URL, ordre du catalogue, ancêtres METS, date d’édition, champs DC bruts, droits, identifiant OAI, datestamp et empreintes des témoins. **1879 désigne l’édition**, pas la rédaction. La date historique reste nulle tant qu’elle n’est pas extraite et vérifiée. Une localité ou un ordre contenus dans un titre ne deviennent pas silencieusement des métadonnées historiques certifiées.

`document_kind` est une hypothèse : `cahier_autonome_probable`, `document_associe`, `proces_verbal`, `extrait`, `liste`, `autre_document`, `notice_absence`, éventuellement `incertain`. Le type `griev` ne discrimine pas ces genres. La règle sur les groupes professionnels est conservatrice et doit être réexaminée : un cahier de corporation peut aussi constituer une unité autonome. Un PV peut contenir un vrai cahier. Le champ `document_kind_reference`, lorsqu’il existe, conserve le diagnostic de lecture distinct.

`alignment_status` : `fort`, `probable`, `ambigu`, `non_retrouve`, `hors_perimetre`. Ni le score ni la marge ne sont des probabilités. `alignment_verification` distingue la proposition et le contrôle Codex. Les erreurs observées ne sont pas corrigées en choisissant silencieusement une alternative.

`candidates` conserve jusqu’à cinq possibilités : XPath de division et d’ancre interne, positions, titres/contextes OCR, page et sa méthode, couvertures lexicales, conflit d’ordre, soutien V2 et score. La première proposition n’est pas nécessairement la bonne. `catalogue_neighbours` désigne les voisins du catalogue, sans les confondre avec les voisins physiques XML.

## Plages et frontières

`boundaries.proposal` est la prédiction d’origine avec `[start,end)`, divisions, pages et alertes. `boundaries.status` : `verifiees`, `proposees`, `ambigues`, `non_etablies`. `verification` indique l’origine du contrôle ; une frontière « vérifiée » signifie ici **extrémités examinées par Codex dans le TEI**, pas certification historique ni contrôle d’OCR.

Les 26 références héritées et 52 nouvelles références conformes sont dans `verified_reference`. Lorsqu’une référence héritée corrige une proposition, `active_reference_range` l’explicite ; la proposition n’est pas écrasée. Les 15 erreurs nouvelles restent sans plage corrigée certifiée. `source_slice_sha256` contrôle la plage **proposée**, même lorsqu’elle est incorrecte. Cette empreinte ne certifie pas son attribution documentaire.

Les offsets sont des points de code Unicode du flux décodé `itertext` reconstruit par le helper du pilote, **pas des octets XML**, ni des indices dans un texte dont les espaces ont été normalisés. La source, sa révision et son SHA-256 font partie du contrat. Pour retrouver le texte exact : charger le même objet `Source`, puis `source.text[start:end]`. Ne pas appliquer ces offsets à une autre version.

`locator` donne les éléments textuels voisins des extrémités ; la borne peut inclure de l’espace entre éléments. `page_references` conserve les `pb`, leurs identifiants et numéros disponibles ; `source.scan_url` donne la numérisation Stanford. Ne pas confondre le suffixe de l’image et la page imprimée. `structure_proposals` pointe les titres, notes XML, rubriques et indices de signatures/certifications sans réécrire leur texte. Les notes imprimées absorbées dans un `p` ne sont pas toutes reconnues.

## Compléments et compatibilité

- `stanford-comparison.jsonl.gz` : les 1 954 prédictions V2, avec correspondance d’ancre et inclusion dans une plage proposées séparément.
- `stanford-complement.jsonl` : 92 propositions autonomes/associées sans équivalence d’ancre. Inclusion dans une plage ne vaut pas identité.
- `stanford-uncertain.jsonl` : 55 hypothèses incertaines V2, y compris les pièces non admises.
- `id-crosswalk.jsonl` : liens vers les identifiants du pilote et des ancres V2.
- `previous-document-crosswalk.jsonl` : conservation explicite des 200 anciens identifiants documentaires, y compris ceux sans correspondance. `overlap_not_certified_identity` ne doit jamais servir de remplacement automatique.

Le modèle futur reste `Corpus → Document (cahier ou pièce associée) → Article/passage → Segment`. Les articles et segments **ne sont pas produits**. Leur futur identifiant pourra associer l’ID parent, l’empreinte source, la version du segmenteur et les bornes. Conserver ordre, ancre d’affichage et voisins à cette future étape. Une correction doit ajouter une décision et une correspondance d’anciennes bornes, pas modifier le texte historique ni supprimer les références précédentes.
""",
    )
    put(
        "ALIGNMENT.md",
        """
# Méthode de rapprochement

## Réutilisation et gel

Les six METS de l’étude précédente fournissent le cadre de 1 305 notices. Les 90 notices DC cibles déjà en cache ont été réutilisées, puis 73 requêtes OAI de métadonnées ont complété les champs (voir journal). Les pages `ListRecords` sont suivies avec le **jeton opaque retourné**, sans reconstruire un curseur ; un `GetRecord` ciblé complète la couverture résiduelle. 1 305 notices DC obtenues, toutes de type `griev`, titres cohérents avec METS après retrait des blancs externes. Aucune inférence depuis un HTML de portail ni récupération TEI.

La révision Stanford est `926fd3cd986a3c3d411e93d1845fff6475cb2602`. Sources locales vérifiées, aucune réécriture. Le helper `Source`, la construction des feuilles XML, l’index de pages, les scores titre/contexte et les propositions de frontières sont **réutilisés par import en lecture** depuis l’audit précédent. Aucun ancien `main()` exécuté.

Les adaptations du développement sont dans `registry_rules.py` : conservation du mot « tiers », conflit explicite entre ordres, ajout limité du début de corps pour un titre purement générique, soutien V2 seulement avec indice de titre/corps. Elles ne résolvent pas tous les titres internes. Les seuils restent 0,62 et 0,78, marge 0,10 ; score initial = 0,55 couverture titre + 0,10 contexte + 0,35 même page, avec pénalités d’ordre et de rubriques. Le contexte historique original n’est jamais modifié par cette normalisation de **comparaison**.

Les 72 cas antérieurs restent du développement. Règles, sources, paramètres, 100 identifiants et 12 zones sont figés dans `data/freeze.json` **avant ouverture des nouveaux packs**. Les règles n’ont pas été modifiées après lecture. Les corrections figurent seulement dans les annotations et localisations complémentaires.

## Décision et abstention

Le générateur conserve cinq alternatives, pas seulement la première trouvée. Une identité forte exige titre propre suffisamment couvert, score et marge concordants, sans conflit d’ordre. Les quasi-ex æquo restent ambigus ; un soutien V2 unique avec indice partiel peut proposer un résultat probable. Les pages réduisent l’espace de recherche, mais ne certifient jamais une identité. Les propositions partageant une même ancre sont signalées : 24 notices concernées, sans appariement un-à-un forcé.

Lors du repli sur V2, la marge conservée reste celle du classement initial avant repli : elle ne mesure pas l’écart du candidat substitué. Ne pas l’utiliser comme certification ni comme probabilité. Les scores et alternatives restent inspectables.

Le voisinage est conservé pour l’inspection, pas utilisé pour inventer des limites. Les entités homonymes restent à trancher, notamment Marolles et Marolles-en-Hurepoix sur la même page. La recherche de paragraphes internes exige encore des marqueurs documentaires et une longueur limitée ; des titres « Copie », « Déclaration » ou OCR trop abîmés peuvent échapper aux propositions.

## Frontières : traitement séparé

Le début proposé suit l’ancre XML ou le titre interne. La fin suit la feuille puis, dans certains cas, des sections voisines compatibles avec la pagination. Un nouveau titre littéral CAHIER peut arrêter la plage. Ce mécanisme est réutilisé tel quel avec ses limites : « SECONDE PARTIE » peut manquer, ou un CAHIER interne appartenant au dossier être pris pour une fin.

Les 1 236 plages se répartissent initialement en 988 proposées sans alerte et 248 ambiguës. **L’absence d’alerte n’est pas une preuve d’exactitude.** La fin d’Aix clergé absorbe la noblesse ; Châtellerault clergé s’arrête avant son propre cahier ; les deux parties Valenciennes ne sont pas réunies. L’identité peut être correcte dans chacun de ces cas.

Ni les annexes, ni les signatures, ni les notes ne sont supprimées. Les composants XML identifiables sont référencés ; la séparation définitive n’est pas prétendue résolue. Les colonnes intercalées en Artois ne se corrigent pas par un simple déplacement de borne.
""",
    )
    put(
        "EVALUATION.md",
        f"""
# Évaluation exploratoire après gel

## Échantillon et portée

Cadre éligible : {f["frame_size"]} notices après exclusion des 72 déjà étudiées et des feuilles effectivement examinées dans les pilotes/V1/V2. Les anciennes hypothèses seulement calculées, mais non lues, ne sont pas assimilées à des annotations. Les zones déjà lues, références de parents et témoins de développement sont exclus. Les localisations retrouvées après abstention ont également été contrôlées contre les anciens emplacements examinés : aucun de ces 14 emplacements complémentaires n’y figure.

Sélection déterministe par empreinte avec graine `document-registry-validation-2026-10-27-v1`, quotas par volume et alternance des strates. Répartition : I8, II18, III20, IV18, V18, VI18. Statuts : 23 forts, 23 probables, 22 ambigus, 20 abstentions, 12 hors périmètre. Difficultés volontairement surreprésentées ; pas de représentativité statistique revendiquée. Aucun cas difficile remplacé après lecture.

Le contrôle examine titres, ouvertures, clôtures, rubriques courtes et voisins. Des recherches de localité dans les pages concernées complètent les abstentions. Les bornes positives ont été examinées, **pas chaque ligne du corps** ; pas de nouvelle collation sur fac-similé. Les décisions Codex ne sont ni aveugles ni indépendantes humainement. Une référence annotée avec connaissance des propositions ne constitue pas un gold standard indépendant.

## Identité et abstention

{table(["Statut automatique", "Résultat des lectures nouvelles"], [(k, str(v)) for k, v in m["by_status"].items()])}

Parmi les 68 propositions de type fort/probable/ambigu, 64 compatibles, 3 erronées et 1 incertaine. Parmi les cas tranchés de ces trois strates : 64/67 (95,5 %), **précision conditionnelle exploratoire** ; elle exclut l’incertain, les abstentions et les exclus. Elle ne doit pas devenir un taux sur les 1 305 notices. Les cinq listes/autre document dont l’identité a aussi été reconnue portent le total des identités compatibles à 69. Six listes ont seulement un contrôle de genre, sans appariement exhaustif de leurs nombreuses divisions.

Les 20 « non retrouvés » donnent 19 localisations récupérables dans Stanford et un non résolu (Saint-Jean-des-Agneaux). Une abstention protège d’une fausse attribution, mais ne prouve pas que le document manque : le rejet de Landas, Messy, Lauris ou Naux tient à des titres/OCR ou des seuils. Les titres internes de Fourqueux, Gif, Bassigny et Gréasque demandent une autre approche de proposition. Aucune proposition n’a été réécrite pour faire disparaître ces échecs.

Cinq désaccords de classification observés : Brest, Massugas, Gréasque (PV contenant des doléances), Chaumont Vexin (fausse notice d’absence) et Turenne (annexe explicitement liée). Le reste est compatible avec le contrôle de genre effectué, sans certification de chaque statut d’autonomie.

## Frontières

52 conformes, 15 incorrectes, 4 incertaines, 29 non évaluées. **52/67 = 77,6 %** sur les extrémités tranchées ; 52/71 = 73,2 % sur toutes les frontières examinées si l’on ne compte que les conformes. Pas de taux global ni d’intervalle statistique extrapolé. Les propositions erronées ont des diagnostics et localisateurs ; toutes ne disposent pas d’une nouvelle plage complète certifiée.

Exemples d’erreurs conservées :

{table(["N° contrôle", "Document", "Diagnostic"], [(x["index"], next(r["metadata"]["title"] for r in rr if r["persee_id"] == x["persee_id"]), x["reason"]) for x in ann if x["boundary_judgment"] == "incorrect" or x["identity_judgment"] == "false_exclusion"])}

Les 26 références anciennes sont conservées à part des 52 nouvelles conformes : 78 frontières avec référence de contrôle dans le registre final. Aucune des 26 n’entre dans le score nouveau.

## Zones indépendantes du catalogue

Douze fenêtres continues, deux par volume, choisies par hash de positions Stanford, hors zones antérieurement lues et ancres primaires du nouvel échantillon. 115 624 caractères source examinés ; répertoires et tableaux non revendicatifs inclus. Les références concernent les débuts **à l’intérieur** de ces fenêtres ; les débuts extérieurs sont censurés. Les titres des alternatives ont pu être vus pendant le contrôle des 100 notices : cette lecture n’est pas un second test aveugle.

{table(["Mesure locale", "Résultat"], [(k, v) for k, v in z.items() if k not in {"no_global_recall_estimate"}])}

Il s’agit de dix débuts documentaires identifiables : six cahiers et quatre pièces revendicatives/associées, plus un bloc Avallon/Aunay incertain. V2 admis et registre avec ancre directe retrouvent chacun 8/10 unités, leur union également 8/10 : **aucun gain de couverture démontré dans ces petites fenêtres**. Les six débuts de cahiers identifiables sont présents ; deux pièces associées manquent aux listes admises. Le taux de 8/10 est une couverture locale de débuts, pas un rappel global, ni un test d’exactitude des fins.

Les pouvoirs Saintonge et le mémoire Goullin ne disposent pas d’une ancre de notice dans ce registre `griev`, ni d’une admission V2 ; ils restent des hypothèses `uncertain` V2. Cela n’établit pas une omission de tout le catalogue Persée : une pièce peut être incluse dans une notice plus large ou décrite sous un autre type non collecté ici.

Le corps Artois clergé mélange les deux colonnes avec celui de la noblesse, dès les articles 40 et suivants ; conserver chaque caractère Stanford ne garantit donc pas une attribution documentaire correcte. Le bloc Avallon commence par ce titre puis poursuit des demandes d’Aunay-la-Côte sans début d’article1. Ces cas sont signalés dans le registre sans certification de plage.

## Travail effectué et limite de coût

100 notices contrôlées, 12 zones continues lues, 14 emplacements complémentaires enregistrés après recherche, 15 frontières rejetées et 5 classifications divergentes. Aucun lecteur humain indépendant n’a participé ; **aucun temps humain n’a été mesuré**. Le temps machine de rapprochement est dans `build-summary.json` (environ15 secondes au premier passage, hors collecte et lecture). Il ne mesure pas l’effort documentaire et n’autorise aucune projection en heures pour 1 305 notices.
""",
    )
    coverage = []
    for v, counts in m["by_volume"].items():
        coverage.append([v, counts["notices"], counts["v2_admitted"], counts["v2_complement"]])
    put(
        "COVERAGE.md",
        f"""
# Couverture et désaccords

{table(["Tome", "Notices Persée griev", "Hypothèses V2 admises", "V2 admis sans ancre équivalente"], coverage)}

Les 1 954 prédictions V2 ne sont pas 1 954 cahiers : seules 1 240 sont admises comme autonomes/associées par ce détecteur ; les autres sont parties, mentions, incertitudes ou hors corpus. Le registre Persée ne reprend que le type `griev` : ses omissions apparentes peuvent correspondre à une notice d’un autre type. **Ni les 1 305 entrées ni les 1 240 admissions ne sont un décompte vérifié des cahiers de 1789.**

1 229 notices possèdent une ancre primaire retrouvée dans les prédictions V2 (y compris des V2 non admises), 76 n’en ont pas. Cette comparaison n’est pas une précision d’identité. Parmi les 1 229, 27 présentent une plage différente et 66 un désaccord de catégorie au sens de la comparaison technique. 24 notices partagent une ancre primaire avec une autre notice ; 185 commencent sur une page également initiale d’une autre notice. Les pages partagées restent distinctes ; aucun voisin n’est attribué sur ce seul critère.

Les 92 hypothèses V2 admises sans ancre équivalente sont dans `stanford-complement.jsonl`, sans fusion automatique. Le champ `contained_by_proposals` signale seulement une inclusion spatiale dans un dossier proposé. Des hypothèses sans notice peuvent être de vraies pièces manquantes, des doublons, des subdivisions ou de faux positifs ; elles ne deviennent pas 92 nouveaux cahiers. Les 55 V2 `uncertain` sont conservées dans un autre fichier et restent consultables dans la comparaison générale.

## Cas concrets

- **Marolles / Marolles-en-Hurepoix**, IV680 : notices2264 et2265 distinctes, faux rapprochement de la première vers le second cahier. La première correspond à `div3[230]`, le second à `div3[231]`. Une page commune et un bon score ne suffisent pas.
- **Uzent / Vicdessos**, IV285 : Uzent est intégré au bloc `div2[16]/div3[3]/p[129]` ; le résultat automatique désigne le cahier de Vicdessos suivant. Autre faux rapprochement malgré proximité de pages.
- **Riez / Digne**, III339–346 : le résultat vise des demandes particulières du chapitre de Riez dans Digne, puis s’arrête avant le cahier de la chambre ecclésiastique de Riez. Le nom du lieu ne suffit pas à l’identité d’ordre/dossier.
- **Chaumont Vexin**, II730–732 : la noblesse est présente dans la même division que l’annonce d’absence du clergé. Un filtre d’absence mal circonscrit peut supprimer un vrai document.
- **Pouvoirs Saintonge**, V `div2[24]/div3[2]`, et **mémoire Goullin**, VI `div2[17]/div3[28]` : références source repérées dans les zones continues mais non admises automatiquement. Goullin est explicitement annoncé comme pièce jointe par l’article 25 d’Eguilles. À rattacher comme pièce associée, sans fabriquer un deuxième cahier.
- **Avallon/Aunay** et **Artois clergé/noblesse** : anomalies de composition du texte Stanford ; les notices ne réparent pas les colonnes ou les continuations mal placées.

Aucun document n’est déclaré définitivement absent de Stanford sur un échec de l’appariement ; même les 32 abstentions initiales ne sont pas des lacunes prouvées. Les métadonnées apportent un inventaire stable et une distinction entre notices ; la fiabilité des plages doit être construite séparément.
""",
    )
    priority_counts = m["review_priority"]
    lines = []
    for x in sorted(
        queue,
        key=lambda x: (
            {"haute": 0, "intermediaire": 1, "echantillonnage": 2}[x["priority"]],
            x["volume"],
            x["persee_id"],
        ),
    ):
        if x["priority"] == "haute":
            lines.append(
                [
                    x["volume"],
                    f"[{x['persee_id'].split('_')[-1]}](https://www.persee.fr/doc/{x['persee_id']})",
                    x["title"],
                    ", ".join(x["reasons"]),
                ]
            )
    put(
        "REVIEW.md",
        f"""
# Vérification documentaire priorisée

**{priority_counts["haute"]} notices hautes, {priority_counts["intermediaire"]} intermédiaires, {priority_counts["echantillonnage"]} à contrôler par échantillonnage.** File exhaustive machine : `data/review-queue.jsonl`. Ces priorités ne changent aucun statut en validation.

1. Hautes : identités ambiguës ou absentes, erreurs observées, frontières V2 contradictoires, départs internes/composites, ancre commune, portée d’une notice d’absence. Corriger identité et périmètre dans deux décisions séparées. Certaines alertes sont corrélées et ne représentent pas autant d’erreurs indépendantes.
2. Intermédiaires : identités probables et frontières non établies/structurelles. Préserver les pièces associées et documenter la politique d’inclusion des listes, signatures, pouvoirs et annexes.
3. Échantillonnage : propositions fortes simples et contrôles des exclus. Tirer un lot stratifié par tome, longueur et pages partagées. Un bon contrôle de titre ne dispense pas du contrôle des fins.

Ajouter la file distincte de **92 hypothèses V2 sans équivalence d’ancre** et les **55 incertaines V2** ; ne pas additionner mécaniquement les volumes de travail, car certains cas sont déjà inclus dans un dossier ou se recouvrent. Les contrôles nouveaux signalent 15 erreurs de frontières ; ils ne fournissent pas tous des plages complètes corrigées. Un contrôle indépendant devrait prioriser ces erreurs et les anomalies de colonnes.

78 notices possèdent une référence de frontière examinée par Codex, donc 1 227 n’en possèdent pas. Cela ne signifie pas qu’il faille relire ces 1 227 documents intégralement : contrôler les transitions et les exceptions, puis mesurer sur un lot indépendant le risque résiduel. Ne pas convertir automatiquement une règle régulière en certification.

## Liste nominative haute priorité

{table(["Tome", "Persée", "Document", "Motifs"], lines)}

La liste intermédiaire complète est conservée dans `review-queue.jsonl` avec titre, volume, ID et motifs ; filtrer `priority == "intermediaire"`. Les vérifications Codex déjà réalisées sont consultables dans `annotations.jsonl`. Aucune validation humaine nouvelle ni durée humaine mesurée.
""",
    )
    put(
        "REPRODUCIBILITY.md",
        f"""
# Reproduction, provenance et droits

## Sources et isolement

Les sources Stanford sont les six XML déjà présents dans `../../sources/stanford/926fd3cd986a3c3d411e93d1845fff6475cb2602/`. La révision et les six empreintes figurent dans `data/freeze.json`. Les helpers antérieurs sont chargés par chemin et utilisés en lecture ; les commandes `main()` des anciens audits ne sont jamais exécutées. `prior-audits-sha256.json` contrôle {checks["previous_files_checked"]} fichiers antérieurs ; le contrôle final est dans `data/checks.json`.

L’expérience utilise Python 3.10.12 et lxml 4.8.0 locaux. Aucun paquet nouveau installé. Les données sources XML restent ignorées par Git. Les métadonnées brutes de réseau sont également en cache ignoré ; les champs normalisés nécessaires à la reproduction, y compris les déclarations de droits et les références OAI, sont conservés dans les fichiers comprimés. Les empreintes des réponses et les requêtes sont dans `data/access-log.json`. Les originaux METS réutilisés sont identifiés par leurs SHA et XPath dans `catalogue.jsonl.gz`.

## Fichiers et commandes

Les JSONL volumineux sont fournis en gzip, sans perte. `archive_manifest.json` associe empreintes comprimées et décomprimées. Le registre référence des plages, pas une nouvelle copie de tous les textes. Aucun TEI Persée dans les livrables.

Depuis la racine du dépôt :

```sh
/usr/bin/python3 1789/archives/1789-document-registry/materialize.py
/usr/bin/python3 1789/archives/1789-document-registry/build.py
/usr/bin/python3 1789/archives/1789-document-registry/evaluate_zones.py
/usr/bin/python3 1789/archives/1789-document-registry/finalize.py
/usr/bin/python3 1789/archives/1789-document-registry/audit_checks.py
```

Ces commandes utilisent les snapshots locaux et n’appellent pas de base. `collect.py` sert seulement à documenter et, si nécessaire, reproduire la collecte publique ; il n’est pas requis pour relire le registre. `prepare_review.py` a servi une fois à figer l’échantillon : **ne pas le relancer sur les annotations**. Il refuse d’écraser la sélection existante. Ne pas changer la graine ni remplacer les échecs.

`review_pack.py`, `brief_review.py`, `zone_pack.py` et `inspect_abstentions.py` permettent de revoir les emplacements ; ils n’attribuent pas de validation. `review_decisions.json` et `review_targets.json` sont les décisions explicites de lecture ; `annotations.jsonl` en est la projection, avec références et portée. `evaluate_zones.py` contient une référence de lecture écrite, distincte du détecteur. Les références positives de frontières se rapportent aux extrémités du TEI, sans garantie historique/OCR.

Le gel protège les octets des règles et échantillons ; trois fichiers gelés conservent leur ordre d’import initial (exception Ruff I001 uniquement). Aucun changement de règles après lecture. Les durées de calcul sont mesurées, les durées humaines ne le sont pas. Le SHA de l’automatique doit rester identique lors d’un second calcul ; seule la durée du résumé peut changer.

## Collecte complémentaire

[Documentation OAI Persée](https://www.persee.fr/entrepot-oai), [Identify](https://oai.persee.fr/oai?verb=Identify), ensemble `persee:serie-arcpa:doc`, `metadataPrefix=oai_dc`. Requêtes séquentielles avec pause de 1,2 s et délai de 30 s, pas de collecte des textes ni de contournement. 90 notices cibles réutilisées ; 73 requêtes supplémentaires enregistrées ; 1 305 notices obtenues. Jetons opaques suivis avec `verb=ListRecords&resumptionToken=...`, sans réenvoyer les autres paramètres. Le collecteur est borné et s’arrête sur erreur ; le journal conserve statuts HTTP, erreurs OAI et empreintes. L’année dans les identifiants n’est pas une date de rédaction.

## Conditions de réutilisation distinctes

**Métadonnées Persée.** Attribution : Persée — UAR 3602, ENS de Lyon/CNRS, notices des Archives parlementaires, liens documentaires dans chaque ligne. Identify annonce les métadonnées sous **CC BY-SA 3.0**. Les notices contiennent aussi une déclaration **CC BY-NC-SA 3.0 concernant les contenus**, et un avertissement générique. Ne pas appliquer ce dernier indistinctement aux métadonnées, ni transformer l’accès public en autorisation universelle. Les [CGU](https://www.persee.fr/cgu) distinguent services, jeux et contenus ; pour une republication publique pérenne du registre dérivé, confirmer avec Persée l’articulation et les obligations de licence/attribution. Les champs de droits originaux sont conservés. Aucun contact nouveau envoyé. La présente étude locale ne prétend pas accorder de droits sur les textes ou images Persée.

**Transcriptions Stanford.** [Dépôt à la révision figée](https://github.com/StanfordUniversityLibraries/ap_tei/tree/926fd3cd986a3c3d411e93d1845fff6475cb2602). Les audits précédents distinguent textes historiques/édition, TEI, métadonnées et images ; ils n’ont pas trouvé de fichier LICENSE autonome ni de `availability` explicite pour les six TEI. Le domaine public historique et la mention de volumes ne constituent pas une licence séparée de tous les enrichissements. Garder provenance et attribution ; clarifier les conditions avant republication massive. Images et plateformes ont leurs propres conditions. Cette mission ne republie aucun texte historique sur le site et ne redistribue pas d’images.
""",
    )
    print("Reports written")


if __name__ == "__main__":
    main()
