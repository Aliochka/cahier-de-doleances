"""Rapports issus des résultats archivés; aucune nouvelle requête réseau."""

from auditlib import HERE, read


def put(name, text):
    import re

    text = re.sub(r"\b(les|Les|des|sur|aux|soit|contre|parmi|Total|total|compte|comptent|propose|obtiennent|pages|pas|et)(?=\d)", r"\1 ", text)
    text = re.sub(r"(?m)^-(?=\d)", "- ", text)
    for a, b in {
        "le27octobre2026": "le 27 octobre 2026",
        "CC BY-SA3.0": "CC BY-SA 3.0",
        "CC BY-NC-SA3.0": "CC BY-NC-SA 3.0",
        "1,6Mo": "1,6 Mo",
        "UAR3602": "UAR 3602",
        "Python3.10.12": "Python 3.10.12",
        "lxml4.8.0": "lxml 4.8.0",
        "typegriev": "type `griev`",
        "sousgriev": "sous `griev`",
        "soit94,3": "soit 94,3",
        "n°0": "n° 0",
    }.items():
        text = text.replace(a, b)
    (HERE / name).write_text(text.strip() + "\n")


def main():
    metrics = read(HERE / "data/metrics.json")
    log = read(HERE / "data/access-log.json")
    cat = read(HERE / "data/catalogue-summary.json")
    nprior = len(read(HERE / "prior-audits-sha256.json"))
    put(
        "README.md",
        f"""# Rapprochement Persée–Stanford — étude de faisabilité

**Recommandation C : combiner les métadonnées Persée avec Stanford et conserver V2 comme instrument complémentaire, dans un processus soumis à validation.** Il est justifié de tester ce registre documentaire avant de multiplier les règles d’une V3 autonome. **Ni Persée seul ni le prototype combiné ne permettent encore de certifier automatiquement tous les parents et leurs frontières.**

## Expérience réalisée

72 notices, 12 par tome I–VI; six catalogues METS de volumes; pagination OAI suivie sur les deux ensembles fournis. 13 contrôles de développement, 53 notices tirées par empreinte et 6 contrôles de types non revendicatifs. Pas d’échantillon statistiquement représentatif.

Après examen : **55 cahiers, 1 procès-verbal revendicatif associé et 16 autres documents**. Parmi les 58 notices `griev`, deux sont des listes de comparants et une décrit le procès-verbal associé. Ce type n’est donc pas synonyme de cahier autonome complet.

| Observation | Résultat local |
|---|---:|
| Notices récupérées | 72/72, toutes avec titre et pagination |
| Documents ciblés, en incluant le PV associé | 56 |
| Rapprochements proposés par B (hors abstentions) | 53/56 |
| Parmi ces propositions : identité compatible après lecture Codex | 50/53, soit94,3 % |
| Identités encore ambiguës / faux rapprochement proposé | 2 / 1 |
| Propositions fortes B, contrôlées compatibles en identité | 43/43 |
| Abstentions sur des documents cibles | 3 : Domfront, Bugey, Guérande |
| Frontières exactes sur26 références de contrôle, A / B / C | 21 / 22 / 23 |
| Frontières sur13 références nouvelles, A / B / C | **10 / 10 / 10** |

Les trois abstentions ont néanmoins le bon passage parmi les candidats faibles : 53/56 premiers candidats sont compatibles au total, **sans que cela constitue 53 admissions automatiques**. Les scores sont heuristiques, pas des probabilités. Les appréciations sont effectuées par Codex en voyant les prédictions, **pas une validation humaine indépendante**.

C conserve 43 propositions fortes, fournit 11 candidats uniques supplémentaires à contrôler et 2 files de candidats multiples. Les ancrages retenus pour le contrôle apparaissent dans ces files pour les 56 documents cibles, dont deux identités/portées restent incertaines; cela **n’est pas un rappel exhaustif du corpus**. Les files multiples contiennent aussi deux alternatives erronées. Sur les 26 notices encore inédites lors de la formalisation de C, aucun gain de frontières n’est démontré : les trois approches obtiennent10/10 sur le sous-lot dont les limites ont été examinées.

## Les quatre problèmes V2

- **Anjou, clergé : solution documentaire démontrée dans le contrôle.** Une notice, pages30–32, rattache les trois chapitres Stanford; le détecteur V2 n’admettait pas le parent.
- **Mirecourt, noblesse : identification et correction de statut démontrées.** Persée nomme un cahier nobiliaire, pages1–6, incluant des pièces complémentaires. Les limites suivent une politique de dossier explicite.
- **Courtiches : correction de statut démontrée.** Un cahier de village, pages196–200, et non une pièce professionnelle.
- **Grasse : aide partielle.** La notice identifie le dossier général; elle ne donne pas d’identifiant distinct à la pièce commençant au `p[50]` que V2 manque. La structure interne reste à reconstruire.

## Ce qui reste à contrôler

Les métadonnées donnent des pages, pas des positions dans ces pages. Sur les 56 documents cibles, **30 n’ont pas de référence de frontières examinée dans ce test**. Parmi les 26 contrôlés, C conserve trois fins incorrectes : Besançon, Libourne, Marseille. Deux identités/portées restent incertaines et deux files demandent un choix entre candidats. Ces tâches se recouvrent : ne pas en faire une somme de documents ni une estimation de journées humaines. Aucun temps humain indépendant n’a été mesuré.

Les droits des métadonnées et du contenu sont annoncés différemment par l’entrepôt; les conditions du futur usage public doivent être rattachées explicitement aux ressources concernées. L’étude locale n’a publié aucun texte intégral Persée ni engagé de contact.

## Livrables et vérifications

- [METADATA.md](METADATA.md) : champs, pagination, couverture, limites et conditions constatées.
- [ALIGNMENT.md](ALIGNMENT.md) : algorithmes, gels, mesures, comparaison A/B/C et effort de vérification.
- [CASES.md](CASES.md) : quatre erreurs V2 et autres réussites/échecs concrets.
- [data/correspondences.jsonl](data/correspondences.jsonl) : notices, références Stanford, propositions, ambiguïtés et jugements séparés.
- [REPRODUCIBILITY.md](REPRODUCIBILITY.md) : scripts, versions, empreintes, cache et commandes de reproduction.
- [data/checks.json](data/checks.json) : contrôles effectivement exécutés.

Les six Stanford locaux restent à la révision `926fd3cd986a3c3d411e93d1845fff6475cb2602`, empreintes vérifiées. {nprior} fichiers des audits précédents sont surveillés par empreinte et restent inchangés. Aucun changement applicatif ou PostgreSQL, aucun embedding, aucune V3 et aucun déploiement.

## Réponses aux sept questions

1. **Inventaire exploitable ?** Oui comme catalogue de candidats documentaires. Les six METS comptent1 305 entrées `griev`, **pas1 305 cahiers complets certifiés**. Leurs titres/types doivent être confrontés au texte.
2. **Proportion rapprochée correctement ?** B propose53 des56 cibles :50 compatibles,2 incertaines,1 fausse. Les43 propositions fortes sont compatibles dans le contrôle effectué. Sur les43 cibles du nouveau tirage,38 propositions sont compatibles,2 incertaines,1 fausse et2 abstentions. Ne pas extrapoler ces proportions.
3. **Frontières retrouvables avec ces seules informations ?** Non. Les pages réduisent la zone; le XML et ses transitions déterminent les bornes. Les références de limites portent sur une politique Stanford déclarée, pas sur des zones de texte Persée que nous n’avons pas téléchargées.
4. **Erreurs V2 résolues ?** Trois cas connus sont effectivement aidés en identification/statut; Grasse reste partiellement résolu. Ce sont des contrôles de développement.
5. **Difficultés restantes ?** Pages partagées, titres OCR, noms territoriaux différents, qualifications d’ordre, dossiers composites, annexes, listes classées `griev`, portées éditoriales différentes.
6. **Vérifications supplémentaires ?** Au moins les30 frontières non examinées, les3 fins incorrectes et les4 cas d’identité/choix encore ouverts dans la file C, avec recouvrements possibles. Pas d’estimation de durée humaine disponible.
7. **Préférable à V3 seule ?** Oui comme prochaine piste limitée : un registre Persée–Stanford peut éviter certaines règles de découverte ad hoc. La supériorité automatique globale de C n’est pas démontrée; un nouveau test indépendant reste nécessaire avant généralisation.
""",
    )
    gt = "| Tome | `griev` du METS |\n|---|---:|\n"
    for v, d in cat["per_volume"].items():
        gt += f"| {v} | {d.get('griev', 0)} |\n"
    put(
        "METADATA.md",
        f"""# Métadonnées publiques Persée

## Accès observé le27octobre2026

Les deux points d’entrée fournis ont répondu HTTP200 en XML OAI via le client Python. L’outil de lecture web ne savait pas ouvrir ces URL XML; cet échec de client n’était pas une indisponibilité du serveur. Aucune restriction n’a été contournée.

- [Ensemble collection](https://oai.persee.fr/oai?verb=ListRecords&metadataPrefix=oai_dc&set=persee:serie-arcpa).
- [Ensemble documents](https://oai.persee.fr/oai?verb=ListRecords&metadataPrefix=oai_dc&set=persee:serie-arcpa:doc).
- [Identify](https://oai.persee.fr/oai?verb=Identify).
- [Documentation de moisson](https://www.persee.fr/entrepot-oai).

Le premier ensemble **n’est pas limité aux volumes** : sa première page contient la série puis19 notices de volumes. Les six tomes recherchés y figurent. Le second contient des documents de plusieurs tomes, y compris le tomeVII et ses tables. Les résultats ne sont ni des cahiers tous valides, ni un ordre de pagination historique fiable.

Le service livre20 notices par lot observé. `Identify` annonce une granularité UTC à la seconde et une gestion des suppressions `transient`; une collecte ultérieure devrait conserver les datestamps et distinguer notices supprimées, absentes et non parcourues. Les réponses `oai_dc` observées incluent aussi des extensions `dcterms` : elles ont été conservées, sans prétendre à une validation XSD complète. Un jeton a été suivi dans chaque ensemble : `verb=ListRecords&resumptionToken=...`, sans ajouter `set` ou `metadataPrefix`. Les secondes pages ont20 notices, un curseur20, aucun identifiant commun avec la première page et un autre jeton non vide. Arrêt volontaire après cette vérification : **la fin des listes et la durée de vie des jetons n’ont pas été testées**. Les jetons sont utilisés tels que reçus, sans décodage/reconstruction de leur état. Voir [pagination-check.json](data/pagination-check.json) et la [spécification OAI-PMH](https://www.openarchives.org/OAI/openarchivesprotocol.html#FlowControl).

## Collecte bornée

Deux pages de chaque ensemble, `Identify`, `robots.txt`, six `GetRecord persee_mets` de volumes et les DC des72 notices sélectionnées; quatre DC ont été repris des lots déjà obtenus. **{len(log)} requêtes HTTP journalisées, {sum(x.get("bytes", 0) for x in log):,} octets**, environ1,6Mo; toutes HTTP200. Un seul appel à la fois, cache, pause entre appels, arrêt sur erreur HTTP, sans relance en boucle. Les documentations ont aussi été consultées via l’outil web.

Les six METS sont des **métadonnées de tables des matières**, pas des textes TEI. Ils fournissent les titres, types, positions relatives et liens de notices. Leurs liens vers d’autres ressources n’ont pas été suivis automatiquement. Aucune transcription, image, PDF ou page de texte historique Persée téléchargée. Les réponses complètes restent dans `.cache/`, ignoré par Git; les72 notices normalisées sont conservées avec leur attribution.

`robots.txt` interdit l’indexation web générale. Nous avons limité les appels à l’API OAI explicitement communiquée par le producteur et documentée pour la moisson, sans exploration de pages du portail. Cette lecture du périmètre est explicitée ici; elle ne vaut pas autorisation générale de crawler les autres services.

## Champs effectivement présents dans le lot

| Information | Champ / provenance | Limite |
|---|---|---|
| Identifiant OAI | `header/identifier`, `oai:persee:article/...` | Identifiant de notice, pas d’article numéroté du cahier |
| Identifiant documentaire | suffixe `arcpa_..._num_...` | Distinct de l’identifiant technique Stanford |
| Titre | `dc:title` | Intitulé éditorial de catalogue, pas nécessairement titre imprimé littéral |
| Volume | `dcterms:isPartOf` et identifiant structuré du volume | Pas déduit artificiellement du titre; références croisées contrôlées |
| Pages | `dc:coverage`, `pp. x-y` / `p. x` | Pages imprimées, aucune borne intra-page |
| Nombre de pages | `dcterms:extent` | Pas nombre de pages manuscrites du cahier original |
| Date | `dc:date=1879` pour les72 notices | **Année d’édition**, pas date de rédaction en1789 |
| Mise à jour | OAI `datestamp` | Date de notice, pas révision du texte OCR |
| Type | `dc:type` / METS `TYPE` | `griev` est une catégorie large, pas certificat de cahier autonome |
| URL | `dc:identifier`, HTTPS du portail | Aucun offset textuel Stanford |
| Bibliographie | `dcterms:bibliographicCitation`, `dc:description` | Référence d’édition à conserver comme telle |
| Langue / diffuseur / droits | `dc:language`, `dc:publisher`, `dc:rights`, `dcterms:accessRights` | Déclarations de portées différentes, ne pas réduire à « libre » |
| Localité, ordre, territoire | Titres et ancêtres METS | Pas de champs systématiques de commune normalisée, d’ordre ou de date historique dans les DC observés |

Les72 notices ont un titre et une plage de pages, et les identifiants structurés les rattachent aux six tomes. **Aucune notice réellement dépourvue de ces trois informations n’a été rencontrée dans ce lot** : le comportement sur ces manques reste à tester; on ne simule pas un résultat observé. Les dates historiques et les limites intra-page sont en revanche absentes comme champs structurés dédiés.

## Couverture de catalogue, pas décompte historique

{gt}

Total1 305 entrées `griev`. Dans les72 notices testées :58 `griev`,7 `article`,4 `table`,1 `index`,1 `edito`,1 `liminaire`. Les listes de nobles du Poitou et d’Autun sont elles-mêmes `griev`; le procès-verbal du Béarn est également dans cette catégorie. Les entités `theme` organisent les territoires et n’ont pas été tirées comme documents individuels. Un identifiant et un type ne prouvent ni présence intégrale du cahier, ni absence de pièces associées.

## Réutilisation : déclarations observées

[Identify](https://oai.persee.fr/oai?verb=Identify) annonce les **métadonnées sous CC BY-SA3.0**. Les notices portent aussi une déclaration concernant les **contenus sous CC BY-NC-SA3.0**, plus un texte générique de droits. Ces périmètres doivent rester distincts. Les [CGU](https://www.persee.fr/cgu), notamment§5 et§12.2.1, décrivent l’usage non commercial des services/jeux de données et l’attribution à Persée avec origine et lien. La [documentation OAI](https://www.persee.fr/entrepot-oai) distingue métadonnées publiques et contenu réservé à des utilisateurs identifiés.

Le registre attribue ses notices à **Persée — UAR3602, ENS de Lyon/CNRS**, conserve les déclarations et leurs URL. Pour une reprise publique pérenne, confirmer le périmètre applicable au jeu dérivé, l’articulation des déclarations et les obligations de licence; aucune autorisation de republication des textes ou images n’est déduite de cet accès. Aucun contact envoyé pendant cette étude.
""",
    )
    bt = """| Périmètre de frontières | A : V2 | B : métadonnées puis bornes source | C : complément |
|---|---:|---:|---:|
"""
    for key, label in [
        ("all", "26 références examinées"),
        ("new_hash", "13 références du nouveau tirage"),
        ("complementary_unexamined_subset", "10 références du sous-lot encore inédit pour C"),
    ]:
        s = metrics[key]
        bt += f"| {label} | {s['boundaries']['A']['both_correct']}/{s['boundary_reviewed']} | {s['boundaries']['B']['both_correct']}/{s['boundary_reviewed']} | {s['boundaries']['C']['both_correct']}/{s['boundary_reviewed']} |\n"
    put(
        "ALIGNMENT.md",
        f"""# Méthode et résultats du rapprochement

## Sélection et séparation des étapes

[Plan](sample-plan.json) :12 notices par volume, contrôles connus puis un type négatif par tome, complément par SHA-256 dans le catalogue METS hors thèmes. Les documents difficiles ne sont pas remplacés. Les72 identifiants et raisons sont dans [sample.json](data/sample.json). Répartition :13 contrôles de développement,53 notices par empreinte,6 contrôles de types négatifs. Cette composition ne mesure pas la prévalence des difficultés du corpus complet.

B a été mis au point sur les13 contrôles et [gelé](rules-freeze.json) **avant les packs Stanford nouveaux**. Les règles n’ont pas changé après leur examen. La lecture de validation voit les propositions : ni référence aveugle ni validation humaine indépendante. Certains documents du tirage peuvent avoir été rencontrés dans les anciens audits; ils ne sont pas tous des textes historiquement inconnus. Le caractère nouveau concerne leur emploi dans cette expérience d’alignement, pas une promesse d’indépendance de tout l’historique du projet.

La stratégie C a été formalisée après la lecture des packs des tomesI–III. Pour ne pas présenter cela comme une validation entièrement préalable, son [gel séparé](complementary-freeze.json) enregistre les26 notices par empreinte des tomesIV–VI encore non examinées à ce moment. La comparaison C globale reste exploratoire; ce sous-lot est présenté séparément. Aucune règle de B ou C n’a été réajustée ensuite.

Un libellé de contrôle initial associait à tort la notice2915 de Soissons à une absence connue. C’est **le vrai cahier du clergé**; les cahiers manquants concernent d’autres ordres. L’identifiant sélectionné est resté le même et la correction de libellé est enregistrée avant gel. Il n’est pas compté comme test d’absence réussi. Le champ de protocole `control` de la normalisation initiale conserve son ancien libellé; il ne provient pas de Persée. `sample.json` et l’annotation explicite donnent la décision corrigée, sans réécrire la notice figée.

## A — Stanford seul

Réutilisation en lecture des1 954 ancres V2 déjà archivées. La mesure vérifie si le document source identifié par le lecteur possède un parent admis V2, et avec quelles bornes/classes. **Ce n’est pas un nouvel algorithme de liaison aux identifiants Persée**; c’est une couverture conditionnelle du détecteur sur les documents du lot. Sa précision sur l’ensemble de ses hypothèses n’est pas réévaluée ici.

A admet53 des56 documents cibles, dont51 comme autonomes et2 comme associés; il manque notamment le parent d’Anjou et le début propre de Marseille. Les53 admissions incluent Mirecourt et Courtiches dont le statut reste erroné. Le PV du Béarn n’est pas admis dans cette correspondance. Le nombre d’admissions n’équivaut donc pas à53 cahiers correctement qualifiés et délimités.

## B — Persée pour proposer l’identité, Stanford pour le texte

Le prototype [alignment.py](alignment.py) ne dépend pas de l’admission V2. Il cherche des ancres structurelles Stanford dans le bon tome et une fenêtre de pagination±1. Les titres sont comparés avec neutralisation de casse/accents et césures **pour la reconnaissance seulement**; le texte source reste intact. Les qualifications entre parenthèses servent au contexte plutôt qu’au recouvrement local. Ce choix peut perdre une distinction utile, telle paroisse/ville, et reste une limite de la recette gelée.

Score fixe :55 % recouvrement du titre local,10 % contexte territorial/éditorial et35 % concordance exacte de page initiale. Les conflits clergé/noblesse sont pénalisés. La morphologie tolère quelques suffixes, sans résoudre `agenols`, `Vie` ou `Guérandepour` de façon générale. Le retrait du mot tiers dans les mots communs est particulièrement fragile : Besançon montre pourquoi les distinctions d’ordre doivent être mieux conservées. Les scores ne sont pas des probabilités.

Proposition à partir de0,62 et d’un recouvrement local minimal; proposition forte à partir de0,78 avec marge0,10. Pas de recherche automatique dans Persée lorsque le titre résiste. Les voisins du METS et le contenu sont examinés lors du contrôle, **pas dans un alignement global optimal de tous les catalogues**, qui n’a pas été implémenté.

Les limites proposées reprennent le conteneur source, les chapitres/pièces contigus compatibles avec les pages, et les redémarrages internes littéraux `CAHIER` avec une identité locale. Ce mécanisme restreint n’est pas une V3 exhaustive. La dernière page ne suffit pas à couper un texte : une fin trop longue reste proposée avec alerte ou doit être détectée lors de la lecture. Les propositions gardent `not_verified`.

**Pagination Stanford :** `pb@n` représente la pagination imprimée, tandis que le suffixe numérique du fichier-image est généralement un numéro de vue différent. Ces nombres n’ont pas été confondus. Les labels vides ne sont interpolés que si deux labels numériques voisins sont cohérents; les autres restent inconnus. L’origine de chaque page utilisée est conservée. Les blancs situés avant un premier `pb` interne ne déterminent pas à eux seuls la page du titre.

### Identités constatées

Sur72 notices :16 ne sont pas des cahiers cibles, dont2 listes pourtant `griev`;55 cahiers et1 PV associé constituent le lot de56 documents. Les cas non ciblés sont conservés dans le registre, pas transformés en parents.

B propose53 rapprochements sur56 : **50 compatibles en identité (94,3 % des propositions),2 incertains (3,8 %),1 faux (1,9 %)**. Parmi les53 propositions,43 sont fortes et toutes compatibles après le contrôle effectué. Les dix propositions ambiguës se répartissent en sept compatibles, deux identités/portées incertaines et le faux rapprochement de Besançon. Trois cibles donnent une abstention; leur meilleur candidat brut est correct à la lecture. Ce dernier résultat ne transforme pas ces abstentions en succès automatique.

Sur les43 cibles du tirage nouveau :33 propositions fortes compatibles;8 ambiguës dont5 compatibles,2 incertaines et1 fausse;2 abstentions. Soit38/41 propositions compatibles, **pas une précision globale sur tous les cahiers**.

## C — Métadonnées et candidats V2 complémentaires

Le prototype [complementary.py](complementary.py) garde les propositions fortes B; pour les autres, il expose les ancres des cinq meilleurs candidats qui sont déjà admises V2 et situées dans la plage de pages. Aucun seuil nouveau appris, aucun changement de V2. Les candidats ajoutés restent **à contrôler**, même lorsqu’ils sont uniques.

Résultat sur56 :43 propositions fortes,11 candidats supplémentaires uniques,2 files multiples.52 propositions uniques sont compatibles,2 identités/portées restent incertaines, et les deux files contiennent le bon document **et une alternative erronée chacune**. Les56 ancrages de référence sont présents dans cette file, pas nécessairement certifiés ou uniques. Ce n’est ni une précision100 %, ni un rappel exhaustif du corpus.

L’intérêt observé est de récupérer Domfront, Bugey et Guérande malgré une comparaison de titre trop faible, et de proposer le bon parent pour Besançon/Toulouse au lieu d’un voisin ou d’un pouvoir isolé. Les cas connus récupérés ne suffisent pas à prouver un gain de généralisation.

Dans les26 notices encore inédites pour C :24 cahiers cibles,2 listes. B fournit20 propositions fortes compatibles et4 propositions ambiguës. C garde les20 fortes, fournit2 candidats uniques encore d’identité/portée incertaine et2 files multiples. **Aucun gain confirmé d’identité unique ou de frontières n’est établi sur ce sous-lot**. Ce résultat limite la portée de la préférence opérationnelle pour C.

## Frontières : résultat distinct de l’identité

26 références de limites ont été examinées, dont13 contrôles de développement et13 du tirage nouveau. La référence représente des limites Stanford et une politique explicite pour les pièces associées, **pas une égalité des zones de texte Persée**, auxquelles nous n’avons pas accédé. Le reste des longs corps n’a pas été collationné intégralement.

{bt}

Sur l’ensemble des26 références : A a24 propositions,23 débuts exacts et21 fins exactes; B a25 propositions,24 débuts et22 fins exacts; C a26 propositions,26 débuts et23 fins exacts. Les manqués restent au dénominateur26. La hausse globale repose sur des cas de développement; sur les treize nouvelles références, les trois méthodes restent à10/13.

Les trois fins C incorrectes sont **Besançon** (commerce absorbé), **Libourne** (seule la déclaration préliminaire), **Marseille** (instructions/pouvoirs manquants). L’identité documentaire peut être bonne alors que le texte proposé est incomplet. Melun/Montarlot, dont la politique d’annexe reste incertaine, ne figure pas parmi les frontières certifiées.

## Intervention encore nécessaire

-30 des56 documents cibles n’ont pas de référence de frontières examinée ici.
-3 fins incorrectes à corriger parmi les26 contrôlés; les prédictions brutes sont conservées.
-2 identités/portées incertaines : Fontenay-lès-Brüs et Toulouse (préfixe des pouvoirs).
-2 files multiples à départager : Coudray/Courbevoie et Morsang/Saint-Germain-Desnoue.

Ces catégories peuvent se recouvrir. L’étude a examiné des ouvertures, demandes, clôtures, transitions et voisins; elle ne prétend pas à une collation des72 corps documentaires ni des scans. Aucun lecteur humain indépendant, aucun temps humain chronométré, aucun gain de productivité humaine mesuré.

## Décision entre A, B, C

| Stratégie | Apport démontré | Risque / coût restant |
|---|---|---|
| A, Stanford seul | Source immuable; bonne couverture de nombreux cas nouveaux | Statuts et regroupements fragiles; nouvelles règles nécessaires pour les cas manqués |
| B, catalogue Persée puis texte Stanford | Identifiants/titres plus explicites; corrections de trois cas V2; pages et dossiers | `griev` trop large, OCR pour la liaison, frontières et annexes non résolues |
| C, complément | File de candidats plus couvrante dans l’essai global; ambiguïtés conservées | Alternatives fausses possibles; pas de gain de frontières sur le nouveau sous-lot; charge manuelle non mesurée |

**Préférence C, limitée à un registre de travail soumis à contrôle**, plutôt qu’une dépendance exclusive au catalogue ou une multiplication immédiate de règles V3. Ce choix repose sur la complémentarité documentaire observée, pas sur une supériorité automatique statistiquement démontrée. Prochaine étape recommandée : un petit lot réellement inédit, référence relue indépendamment et temps de validation mesuré, puis décision sur l’extraction plus large. Ne pas commencer cette étape ni une intégration pendant la présente mission.
""",
    )
    put(
        "CASES.md",
        """# Cas concrets

Les jugements sont exploratoires et effectués par Codex sur le XML Stanford. Aucun texte historique Persée n’a été téléchargé. Les liens Persée ci-dessous identifient les notices; les textes et offsets viennent de Stanford figé. Les différences de portée documentaire restent visibles.

## Les quatre erreurs V2

| Cas | Notice Persée / pages | Source Stanford | Apport observé | Limite restante |
|---|---|---|---|---|
| Anjou, clergé | [1563](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1563),30–32 | II `div2[2]/div3[1–3]`, `[212002,227226)` | Une identité commune à trois chapitres; B propose les limites de référence alors que V2 exclut le parent comme incertain | Vérification source nécessaire; pas un découpage fourni par le DC |
| Mirecourt, noblesse | [1745](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_1745),1–6 | IV `div2[1]/div3[2–4]`, `[7726,49457)` | Identité nobiliaire, et non professionnelle; rattachement des demandes de Lorraine et du travail des commissaires | Distinguer cahier principal et dossier de pièces associées; le typegriev seul n’explique pas cette hiérarchie |
| Courtiches | [1861](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1861),196–200 | III `div2[22]/div3[12]`, `[1775540,1811142)` | Le titre désigne un village. L’ouverture et les signatures confirment une assemblée municipale; correction de l’interprétation professionnelle V2 | Persée aide le statut, pas la segmentation des articles |
| Grasse | [1924](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1924),267–272 | III `div2[24]/div3[3]`, pièce distincte au `p[50]` | Le dossier général clergé Grasse/Vence est retrouvable | **Aide partielle** : pas d’identifiant Persée séparé àp50. La nouvelle pièce « Demandes et doléances… auxquelles les curés… n’ont pas souscrit » nécessite toujours une décision de structure |

Ces quatre documents sont des contrôles connus. Ils ne sont pas utilisés comme preuve de généralisation à de nouveaux cahiers.

## Besançon : même page, mauvais ordre et cahier absent

[Notice1658](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1658), tomeII,337–343. B propose `[2317027,2317244)` : `div2[23]/div3[2]`, **cahier de la noblesse introuvable**, pas le cahier du tiers recherché. La référence d’identité est `div3[3]`, commençant `[2317251,... )`. La vraie fin du corps principal précède le `p[167]` « Doléances particulières du commerce de Besançon », à2355387. Le commerce possède sa propre notice1659.

Le score élevé/ex-aequo repose sur Besançon et la page, avec une perte de la distinction du tiers dans les mots communs du prototype. Le titre et la page ne suffisent pas. C retrouve le bon début via V2, mais garde une fin trop longue absorbant le commerce. Les prédictions ne sont pas corrigées rétroactivement.

## Libourne : bon clergé, texte incomplet

[Notice1981](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1981), III,503–506. B vise `div2[37]/div3[2]`, déclaration du11mars, `[4575837,4577597)`. Le véritable cahier suivant dit expressément que cette délibération lui est annexée : l’identité du dossier est compatible, mais B ne fournit que son préambule documentaire.

Le contrôle de dossier retient cette déclaration et le cahier de `div3[3]` jusqu’avant `p[63]`, à4603654. Celui-ci ouvre les pouvoirs de la noblesse. A absorbe trop de documents voisins; B et C restent trop courts. **L’identification ne certifie pas la complétude.**

## Marseille : deux notices voisines et une pièce à rattacher

[Notice2033](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_2033), III,702–712. Le METS distingue le cahier de la ville2493 et celui du tiers2033. Le premier correspond au titre `p[46]`; le second commence `p[55]`, à6315437, dans `div2[50]/div3[5]`.

B identifie le second, mais s’arrête à6390731 (page710). Les instructions/pouvoirs de `div3[6]` prolongent son dossier jusqu’à6413748 (page712). La pagination signale une insuffisance, mais ne fournit pas ce rattachement ni l’offset final. Ce n’est pas une raison pour fusionner les deux cahiers antérieurs.

## Gometz-la-Ville : plusieurs cahiers dans une division

[Notice2200](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2200), IV,583–584. `div2[18]/div3[170]` commence par Gometz-la-Ville, mais continue avec Gonesse (`p[40]–p[41]`), puis Gournay (`p[66]–p[67]`). La limite `[5378071,5389567)` avant le nouveau titre `CAHIER` est correctement proposée par B et confrontée aux signatures `p[39]`.

L’inspection du seul dernier paragraphe de la division aurait montré Gournay et fait croire à un cahier beaucoup plus long. La reconstruction doit porter sur la plage proposée, pas sur une équivalence `div3=document`.

## Toulouse : cahier et pouvoirs sur la même page

[Notice2503](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2503), VI,35–38. B hésite entre les pouvoirs `div2[2]/div3[3]`, `[310648,316936)`, et le cahier `div3[4]`, `[316957,340736)`. Les pouvoirs sont datés du4avril; le cahier rapporte les délibérations30mars–1avril.

La portée exacte du préfixe des pouvoirs dans la notice n’est pas certifiable avec ces métadonnées. Le cahier proprement dit est localisé; la proposition B est certainement incomplète si elle s’arrête aux pouvoirs. C propose son corps, mais le lien de dossier reste soumis à examen. Ce cas n’est pas compté comme référence de frontières exactes Persée–Stanford.

## Deux listes pourtant typées griev

- [Poitou2823](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2823), V,397–406 : liste nominative des nobles comparants ou représentés; les divisions de listes suivent le cahier de noblesse distinct.
- [Autun2684](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2684), VI,484–486 : liste des comparants de la noblesse, entre listes du clergé et du tiers.

Leur classement sousgriev n’est pas une preuve d’erreur du catalogue : sa catégorie est plus large que notre définition de cahier. Elles restent dans le registre et sont exclues des cahiers cibles après examen.

## Autres limites conservées

Bugey/Belley, Dax/Lannes et Guérande/`Guérandepour` montrent les écarts territoriaux ou OCR. Fontenay-lès-Brüs conserve une identité incertaine en raison d’un titre très abîmé et de l’absence de répétition locale lisible dans le contrôle du corps. Montlhéry paroisse/ville, Coudray/Courbevoie et Morsang/Saint-Germain-Desnoue montrent pourquoi les voisins et qualificatifs doivent rester dans le dossier de contrôle.

À Melun, une nouvelle pièce de Montarlot apparaît dans le même conteneur et sur la dernière page750 de la notice2043, sans entrée séparée trouvée dans le catalogue consulté. Sa portée d’annexe n’a pas été résolue : aucune frontière n’est inventée pour la faire entrer dans les métriques.
""",
    )
    put(
        "REPRODUCIBILITY.md",
        """# Reproduction et périmètre des fichiers

Python3.10.12, lxml4.8.0 disponibles via `/usr/bin/python3`. Scripts autonomes, sans bibliothèque applicative ni base. Les primitives de provenance sont reprises en lecture des audits précédents, sans les modifier.

Les entrées durables nécessaires pour rejouer l’alignement sont `data/metadata.jsonl`, `data/sample.json`, les six Stanford figés dans le cache V2 et les hypothèses V2 archivées. Les réponses OAI brutes sont conservées localement dans `.cache/`; elles ne sont pas indispensables à la réévaluation des correspondances enregistrées.

```sh
/usr/bin/python3 docs/audits/1789-persee-stanford-alignment/alignment.py
/usr/bin/python3 docs/audits/1789-persee-stanford-alignment/complementary.py
/usr/bin/python3 docs/audits/1789-persee-stanford-alignment/evaluate.py
/usr/bin/python3 docs/audits/1789-persee-stanford-alignment/checks.py
```

Ces commandes sont locales, sans réseau. Les empreintes des règles, paramètres, notices et annotations sont vérifiées. Ne pas relancer la sélection ou la création des annotations en écrasant le plan et les gels : assertions anti-écrasement. Les sorties initiales restent réexaminables sans refaire la collecte.

`fetch_metadata.py` et `collect_sample.py` documentent la collecte bornée déjà exécutée. Ils réutilisent le cache; ne pas lancer une moisson exhaustive à partir des jetons. Après perte du cache, une nouvelle collecte peut avoir d’autres datestamps/empreintes : elle constituerait une nouvelle observation, pas une reproduction binaire du service. Aucun format TEI n’est autorisé par le client.

- `metadata.jsonl` : métadonnées Persée, producteurs, champs bruts, droits, empreintes et bibliographie. Volume issu de l’identifiant structuré, pas du titre.
- `alignment-predictions.jsonl` : prédictions initiales B; scores, cinq candidats, XPath, offsets, bornes proposées et source figée.
- `complementary-predictions.jsonl` : file C, y compris ambiguïtés et limites V2 sans certification.
- `annotations.jsonl` : décisions documentaires explicites. Les citations de contrôle sont les extrémités de la **division englobante**, qui peut contenir plusieurs cahiers; elles ne remplacent pas les références de limites.
- `comparisons.jsonl` et `correspondences.jsonl` : vues comparées et registre consolidé, sans correction silencieuse des prédictions.
- `page-index.json` : labels imprimés et origine des rares interpolations. Ne pas utiliser le numéro du fichier-image comme numéro de page.
- `access-log.json`, `pagination-check.json`, gels et empreintes : preuve de collecte/version et contrôles.

Les offsets sont des positions Unicode semi-ouvertes dans `itertext()` du XML décodé. Ce ne sont pas des offsets d’octets XML. Le fichier et son SHA-256, la révision Stanford, le XPath et le lien de numérisation permettent le retour à la source. Aucune transcription Persée intégrale ni nouveau corpus d’articles n’est créé.

L’évaluation distingue propositions fortes, files de candidats, identité compatible, identité incertaine, faux rapprochement et référence de frontières. Aucun résultat « fort » n’est automatiquement marqué vérifié. Les rôles de contrôle connus et nouveaux restent séparés. La validation indépendante et son temps humain restent à réaliser.

Ruff passe avec exceptions explicites de style sur `auditlib.py` et `annotations.py`, dont les octets ont été gelés avant évaluation. La syntaxe et les relectures des sorties sont vérifiées. Un conflit initial de résolution du nom `evaluate` a relancé le script de l’audit V2; le seul fichier dont les octets avaient changé (champs de chronométrage) a été restauré avec son SHA-256 original. Les vérifications avant et après reproduction confirment désormais les448 fichiers antérieurs inchangés. Le contrôle charge les scripts locaux par chemin explicite; voir [replay-incident.json](data/replay-incident.json).
""",
    )


if __name__ == "__main__":
    main()
