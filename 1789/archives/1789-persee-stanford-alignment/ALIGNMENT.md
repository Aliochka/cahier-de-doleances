# Méthode et résultats du rapprochement

## Sélection et séparation des étapes

[Plan](sample-plan.json) :12 notices par volume, contrôles connus puis un type négatif par tome, complément par SHA-256 dans le catalogue METS hors thèmes. Les documents difficiles ne sont pas remplacés. Les 72 identifiants et raisons sont dans [sample.json](data/sample.json). Répartition :13 contrôles de développement,53 notices par empreinte,6 contrôles de types négatifs. Cette composition ne mesure pas la prévalence des difficultés du corpus complet.

B a été mis au point sur les 13 contrôles et [gelé](rules-freeze.json) **avant les packs Stanford nouveaux**. Les règles n’ont pas changé après leur examen. La lecture de validation voit les propositions : ni référence aveugle ni validation humaine indépendante. Certains documents du tirage peuvent avoir été rencontrés dans les anciens audits; ils ne sont pas tous des textes historiquement inconnus. Le caractère nouveau concerne leur emploi dans cette expérience d’alignement, pas une promesse d’indépendance de tout l’historique du projet.

La stratégie C a été formalisée après la lecture des packs des tomesI–III. Pour ne pas présenter cela comme une validation entièrement préalable, son [gel séparé](complementary-freeze.json) enregistre les 26 notices par empreinte des tomesIV–VI encore non examinées à ce moment. La comparaison C globale reste exploratoire; ce sous-lot est présenté séparément. Aucune règle de B ou C n’a été réajustée ensuite.

Un libellé de contrôle initial associait à tort la notice2915 de Soissons à une absence connue. C’est **le vrai cahier du clergé**; les cahiers manquants concernent d’autres ordres. L’identifiant sélectionné est resté le même et la correction de libellé est enregistrée avant gel. Il n’est pas compté comme test d’absence réussi. Le champ de protocole `control` de la normalisation initiale conserve son ancien libellé; il ne provient pas de Persée. `sample.json` et l’annotation explicite donnent la décision corrigée, sans réécrire la notice figée.

## A — Stanford seul

Réutilisation en lecture des 1 954 ancres V2 déjà archivées. La mesure vérifie si le document source identifié par le lecteur possède un parent admis V2, et avec quelles bornes/classes. **Ce n’est pas un nouvel algorithme de liaison aux identifiants Persée**; c’est une couverture conditionnelle du détecteur sur les documents du lot. Sa précision sur l’ensemble de ses hypothèses n’est pas réévaluée ici.

A admet53 des 56 documents cibles, dont51 comme autonomes et 2 comme associés; il manque notamment le parent d’Anjou et le début propre de Marseille. Les 53 admissions incluent Mirecourt et Courtiches dont le statut reste erroné. Le PV du Béarn n’est pas admis dans cette correspondance. Le nombre d’admissions n’équivaut donc pas à53 cahiers correctement qualifiés et délimités.

## B — Persée pour proposer l’identité, Stanford pour le texte

Le prototype [alignment.py](alignment.py) ne dépend pas de l’admission V2. Il cherche des ancres structurelles Stanford dans le bon tome et une fenêtre de pagination±1. Les titres sont comparés avec neutralisation de casse/accents et césures **pour la reconnaissance seulement**; le texte source reste intact. Les qualifications entre parenthèses servent au contexte plutôt qu’au recouvrement local. Ce choix peut perdre une distinction utile, telle paroisse/ville, et reste une limite de la recette gelée.

Score fixe :55 % recouvrement du titre local,10 % contexte territorial/éditorial et 35 % concordance exacte de page initiale. Les conflits clergé/noblesse sont pénalisés. La morphologie tolère quelques suffixes, sans résoudre `agenols`, `Vie` ou `Guérandepour` de façon générale. Le retrait du mot tiers dans les mots communs est particulièrement fragile : Besançon montre pourquoi les distinctions d’ordre doivent être mieux conservées. Les scores ne sont pas des probabilités.

Proposition à partir de0,62 et d’un recouvrement local minimal; proposition forte à partir de0,78 avec marge0,10. Pas de recherche automatique dans Persée lorsque le titre résiste. Les voisins du METS et le contenu sont examinés lors du contrôle, **pas dans un alignement global optimal de tous les catalogues**, qui n’a pas été implémenté.

Les limites proposées reprennent le conteneur source, les chapitres/pièces contigus compatibles avec les pages, et les redémarrages internes littéraux `CAHIER` avec une identité locale. Ce mécanisme restreint n’est pas une V3 exhaustive. La dernière page ne suffit pas à couper un texte : une fin trop longue reste proposée avec alerte ou doit être détectée lors de la lecture. Les propositions gardent `not_verified`.

**Pagination Stanford :** `pb@n` représente la pagination imprimée, tandis que le suffixe numérique du fichier-image est généralement un numéro de vue différent. Ces nombres n’ont pas été confondus. Les labels vides ne sont interpolés que si deux labels numériques voisins sont cohérents; les autres restent inconnus. L’origine de chaque page utilisée est conservée. Les blancs situés avant un premier `pb` interne ne déterminent pas à eux seuls la page du titre.

### Identités constatées

Sur72 notices :16 ne sont pas des cahiers cibles, dont2 listes pourtant `griev`;55 cahiers et 1 PV associé constituent le lot de56 documents. Les cas non ciblés sont conservés dans le registre, pas transformés en parents.

B propose 53 rapprochements sur 56 : **50 compatibles en identité (94,3 % des propositions),2 incertains (3,8 %),1 faux (1,9 %)**. Parmi les 53 propositions,43 sont fortes et toutes compatibles après le contrôle effectué. Les dix propositions ambiguës se répartissent en sept compatibles, deux identités/portées incertaines et le faux rapprochement de Besançon. Trois cibles donnent une abstention; leur meilleur candidat brut est correct à la lecture. Ce dernier résultat ne transforme pas ces abstentions en succès automatique.

Sur les 43 cibles du tirage nouveau :33 propositions fortes compatibles;8 ambiguës dont5 compatibles,2 incertaines et 1 fausse;2 abstentions. Soit38/41 propositions compatibles, **pas une précision globale sur tous les cahiers**.

## C — Métadonnées et candidats V2 complémentaires

Le prototype [complementary.py](complementary.py) garde les propositions fortes B; pour les autres, il expose les ancres des cinq meilleurs candidats qui sont déjà admises V2 et situées dans la plage de pages. Aucun seuil nouveau appris, aucun changement de V2. Les candidats ajoutés restent **à contrôler**, même lorsqu’ils sont uniques.

Résultat sur 56 :43 propositions fortes,11 candidats supplémentaires uniques,2 files multiples.52 propositions uniques sont compatibles,2 identités/portées restent incertaines, et les deux files contiennent le bon document **et une alternative erronée chacune**. Les 56 ancrages de référence sont présents dans cette file, pas nécessairement certifiés ou uniques. Ce n’est ni une précision100 %, ni un rappel exhaustif du corpus.

L’intérêt observé est de récupérer Domfront, Bugey et Guérande malgré une comparaison de titre trop faible, et de proposer le bon parent pour Besançon/Toulouse au lieu d’un voisin ou d’un pouvoir isolé. Les cas connus récupérés ne suffisent pas à prouver un gain de généralisation.

Dans les 26 notices encore inédites pour C :24 cahiers cibles,2 listes. B fournit20 propositions fortes compatibles et 4 propositions ambiguës. C garde les 20 fortes, fournit2 candidats uniques encore d’identité/portée incertaine et 2 files multiples. **Aucun gain confirmé d’identité unique ou de frontières n’est établi sur ce sous-lot**. Ce résultat limite la portée de la préférence opérationnelle pour C.

## Frontières : résultat distinct de l’identité

26 références de limites ont été examinées, dont13 contrôles de développement et 13 du tirage nouveau. La référence représente des limites Stanford et une politique explicite pour les pièces associées, **pas une égalité des zones de texte Persée**, auxquelles nous n’avons pas accédé. Le reste des longs corps n’a pas été collationné intégralement.

| Périmètre de frontières | A : V2 | B : métadonnées puis bornes source | C : complément |
|---|---:|---:|---:|
| 26 références examinées | 21/26 | 22/26 | 23/26 |
| 13 références du nouveau tirage | 10/13 | 10/13 | 10/13 |
| 10 références du sous-lot encore inédit pour C | 10/10 | 10/10 | 10/10 |


Sur l’ensemble des 26 références : A a24 propositions,23 débuts exacts et 21 fins exactes; B a25 propositions,24 débuts et 22 fins exacts; C a26 propositions,26 débuts et 23 fins exacts. Les manqués restent au dénominateur26. La hausse globale repose sur des cas de développement; sur les treize nouvelles références, les trois méthodes restent à10/13.

Les trois fins C incorrectes sont **Besançon** (commerce absorbé), **Libourne** (seule la déclaration préliminaire), **Marseille** (instructions/pouvoirs manquants). L’identité documentaire peut être bonne alors que le texte proposé est incomplet. Melun/Montarlot, dont la politique d’annexe reste incertaine, ne figure pas parmi les frontières certifiées.

## Intervention encore nécessaire

- 30 des 56 documents cibles n’ont pas de référence de frontières examinée ici.
- 3 fins incorrectes à corriger parmi les 26 contrôlés; les prédictions brutes sont conservées.
- 2 identités/portées incertaines : Fontenay-lès-Brüs et Toulouse (préfixe des pouvoirs).
- 2 files multiples à départager : Coudray/Courbevoie et Morsang/Saint-Germain-Desnoue.

Ces catégories peuvent se recouvrir. L’étude a examiné des ouvertures, demandes, clôtures, transitions et voisins; elle ne prétend pas à une collation des 72 corps documentaires ni des scans. Aucun lecteur humain indépendant, aucun temps humain chronométré, aucun gain de productivité humaine mesuré.

## Décision entre A, B, C

| Stratégie | Apport démontré | Risque / coût restant |
|---|---|---|
| A, Stanford seul | Source immuable; bonne couverture de nombreux cas nouveaux | Statuts et regroupements fragiles; nouvelles règles nécessaires pour les cas manqués |
| B, catalogue Persée puis texte Stanford | Identifiants/titres plus explicites; corrections de trois cas V2; pages et dossiers | `griev` trop large, OCR pour la liaison, frontières et annexes non résolues |
| C, complément | File de candidats plus couvrante dans l’essai global; ambiguïtés conservées | Alternatives fausses possibles; pas de gain de frontières sur le nouveau sous-lot; charge manuelle non mesurée |

**Préférence C, limitée à un registre de travail soumis à contrôle**, plutôt qu’une dépendance exclusive au catalogue ou une multiplication immédiate de règles V3. Ce choix repose sur la complémentarité documentaire observée, pas sur une supériorité automatique statistiquement démontrée. Prochaine étape recommandée : un petit lot réellement inédit, référence relue indépendamment et temps de validation mesuré, puis décision sur l’extraction plus large. Ne pas commencer cette étape ni une intégration pendant la présente mission.
