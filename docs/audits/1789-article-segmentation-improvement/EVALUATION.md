# Évaluation et limites

## Protocole

1. Copie privée du journal humain et empreintes des audits précédents et des six XML.
2. Sélection déterministe des fenêtres de validation, avant développement : deux fenêtres de douze paragraphes dans chacun de six cahiers hors Agen. Identifiants, XPath et positions enregistrés dans `data/validation-plan.json`.
3. Développement exclusivement sur les corrections d’Agen et des cas synthétiques.
4. Gel du code `segmentation.py` et du plan : `data/freeze.json`. Les règles n’ont pas été retouchées après lecture de la validation.
5. Lecture des 144 occurrences de paragraphes sélectionnées, y compris les continuations, listes internes, signatures, notes et prose sans numérotation. Référence explicite enregistrée par `make_reference.py`, avant calcul des prédictions de validation.
6. Comparaison des mêmes fenêtres pour V2 et l’extension. Déduplication des sept débuts communs aux deux fenêtres de Périgny.
7. Calcul sur les 29 cahiers à titre descriptif, puis examen ponctuel du nouveau `5tt` d’Alençon et du suspect de Mirecourt, **sans ajustement ultérieur des règles**.

La référence est établie par Codex : séparation du développement, mais ni test humain indépendant, ni validation aveugle indépendante. Les six cahiers proviennent d’un corpus déjà étudié ; seules ces fenêtres sont distinctes des corrections humaines utilisées pour régler l’extension. Ce n’est pas un échantillon aléatoire représentatif de tous les cahiers de Stanford.

## Validation distincte

| Tome | Cahier | Débuts attendus distincts | V2 corrects | Extension corrects | Faux débuts ajoutés |
|---:|---|---:|---:|---:|---:|
| I | Noblesse d’Alençon | 3 | 3 | 3 | 0 |
| II | Clergé d’Anjou | 22 | 22 | 22 | 0 |
| III | Colmar | 22 | 22 | 22 | 0 |
| IV | Aubervilliers | 1 | 1 | 1 | 0 |
| V | Périgny-en-Brie | 15 | 15 | 15 | 0 |
| VI | Clergé de Vic | 21 | 20 | 20 | 0 |
| **Total** | | **84** | **83** | **83** | **0** |

Sur ces débuts uniquement : précision observée 83/83 ; rappel 83/84 (98,8 %), identiques pour les deux méthodes. Ce ne sont pas des performances générales sur les 719 articles, encore moins sur six volumes complets. Les fenêtres ne contiennent pas de nouveau marqueur dégradé que l’extension corrige : **aucun gain de rappel indépendant du développement n’est démontré**.

La référence conserve comme article le `Art. Que personne…` sans numéro à Colmar ; elle ne lui invente pas « 28 ». Les `1°`, `2°`, etc. sous les articles 9 et 10 d’Alençon sont des énumérations internes, pas des articles autonomes supplémentaires. Les fenêtres d’Aubervilliers incluent de longs textes sans article et des montants : aucun faux découpage relevé.

Sur 74 articles dont début et fin sont observables dans les fenêtres, 73 sont correctement reconstitués pour les deux versions. Le cas manqué est `A:rt. 32.` à Vic, position 157031. Il fusionne avec l’article précédent ; ce défaut n’a pas été corrigé après découverte dans la validation. Le score des fins reste donc limité : les derniers articles de fenêtre dont la fin n’est pas assurée ne sont pas comptés. Le fichier métrique contient les plages et les résultats individuels, avec une tolérance de position de trois caractères explicitement indiquée.

## Développement sur les décisions humaines

Six débuts retrouvés parmi les six fusions identifiées dans la noblesse d’Agen ; le manque `ART. 6.` du clergé est également résolu. Deux absorptions de prose/rubrique sont corrigées. La correction des guillemets et du préfixe OCR `h` autour des articles 3/4 n’est pas reproduite.

Sur les 16 plages distinctes issues des corrections/ajouts :

| Comparaison aux décisions | V2 | Extension |
|---|---:|---:|
| Positions strictement identiques | 0 | 10 |
| Identiques après retrait des seuls blancs aux extrémités | 0 | 15 |

Ce retrait des blancs sert **uniquement à comparer les limites**. Les textes, positions et décisions stockés ne sont jamais normalisés. Des écarts d’un caractère final ou de 25 blancs initiaux existent notamment pour l’article 6 : ils restent visibles dans les résultats détaillés. Les performances calculées sur les corrections ne doivent pas être présentées comme une précision globale.

## Stabilité et régression héritée

- Réexécution brute V2 : 718 articles ; extension : 726 propositions.
- 709 plages V2 exactement inchangées ; huit nouveaux débuts ; neuf anciennes plages modifiées par les séparations ou retraits de prose/rubrique.
- Corpus initial : 719 articles ; 708 plages identiques dans les nouvelles propositions, dont 215 des 217 A.
- Les deux A non reproduits sont les articles 10/11 de Terre-Franche. V2 réexécuté les fusionnait déjà ; l’extension n’ajoute pas cette régression, mais ne la résout pas. Le corpus existant conserve les deux unités A.
- Aucun A ni B, et aucune décision humaine, n’est remplacé par les résultats de comparaison. A signifie examen antérieur par Codex, pas validation humaine.

Le gain net de huit propositions n’est pas une mesure de huit articles nouvellement certifiés. Sept reproduisent des ajouts humains de développement ; le huitième (`5tt`) a été contrôlé exploratoirement après prédiction. Le corpus actuel et la sortie brute restent deux objets distincts.

## Contrôles logiciels

- 34 tests Python réussis : 23 préexistants et 11 nouveaux, dont neuf cas synthétiques du segmenteur, conservation du journal et priorité humaine, blocage d’une validation groupée contenant une nouvelle alerte.
- Scénario navigateur préexistant : Pierrelez, Ferrières, séparation à l’intérieur d’un paragraphe, fusion, classement C, ajout, annulation, persistance, clavier, 320/375/768/1280 px et texte à 200 %.
- Nouveau scénario navigateur : comparaison sans écriture, préparation d’une séparation sans écriture, priorité d’une décision humaine explicite dans un journal synthétique, rechargement, clavier, mêmes largeurs et agrandissement. Aucune erreur JavaScript relevée.
- Vérification des tranches sources, limites parentales, unicité des identifiants et absence de chevauchement entre propositions.
- Vérification des empreintes des 663 fichiers inventoriés dans les anciens audits/sources et des préfixes des journaux humains figés. Les éventuels nouveaux événements légitimes peuvent être ajoutés par l’utilisateur sans invalider cette protection du préfixe.

Les tests n’écrivent que dans des journaux temporaires synthétiques. Aucun faux événement humain n’est inséré dans le journal réel.

Le calcul des propositions sur les 29 parents prend environ **0,22 seconde**, hors chargement initial des XML et des objets de l’outil. Ce n’est pas un temps de validation humaine. Aucun temps humain supplémentaire n’a été mesuré.

## Signalements documentaires après évaluation

Les deux échecs connus `A:rt. 32.` et `i lfl` sont également exposés dans le panneau à partir de `data/review-notes.json`. Leur origine **« signalement documentaire de Codex après évaluation »** est distincte d’une détection automatique. Ils ne modifient ni les règles gelées, ni les prédictions brutes, ni les scores ci-dessus. Ces annotations aident seulement à retrouver les points à contrôler dans l’éditeur. Terre-Franche est déjà séparé dans le corpus conservé.
