# Validations humaines — état réellement enregistré

## Méthode et unités de comptage

Journal figé de **346 événements sur dix cahiers**. Relecture avec le mécanisme existant de vérification de la chaîne de hachage, puis application des décisions dans leur ordre. Chaque parent et chaque unité conservent leur version. Les contrôles de couverture sont passés, sans décision périmée. La classification ci-dessous est une analyse documentaire exploratoire de Codex, distincte des décisions humaines, qui restent prioritaires.

**333 articles actuels ont un statut humain**, dont 308 acceptés sans changement et 25 corrigés ou créés. Le corpus initial de ces dix cahiers comportait 322 articles ; 14 de ces propositions ont été modifiées et 11 articles ont été ajoutés. La totalité du corpus courant compte donc 730 articles (719 initiaux + 11 ajouts), dont 397 encore sans examen humain.

« Accepté sans correction » signifie : même type, même numéro et mêmes plages que la proposition initiale, avec une décision humaine actuelle. Une correction de numéro seule compte comme modification, mais pas comme erreur de découpage. Les articles nouveaux ne sont pas réintroduits artificiellement dans le dénominateur des propositions initiales.

## Les deux groupes séparés

Les cinq premiers cahiers ont servi au développement ou ont été retenus pour leurs difficultés. Les cinq autres proviennent du tirage figé, graine **17892019**, parmi 24 cahiers sans décision préalable. Il ne s’agit pas de deux échantillons comparables de toute la collection.

| Groupe | Articles initiaux | Articles humains actuels | Sans changement | Corrigés/créés actuels | Propositions initiales modifiées | Ajouts |
|---|---:|---:|---:|---:|---:|---:|
| Cinq premiers, orientés développement/difficultés | 214 | 225 | 200 | 25 | 14 | 11 |
| Cinq tirés au sort | 108 | 108 | 108 | 0 | 0 | 0 |

Dans le premier groupe, 14/214 propositions ont changé (6,5 %, numéro seul inclus) ; cela ne constitue pas un taux d’erreur représentatif. Dans le lot aléatoire restreint, 108/108 articles ont été acceptés sans correction enregistrée. Leurs contenus se regroupent dans seulement cinq documents, dont 80 articles dans le seul clergé d’Anjou : ces observations ne sont pas 108 essais indépendants.

## Tableau par cahier

Fusions = cas dont un début d’article manqué est observable dans la transcription. « Autres » inclut les écarts de frontière, le paratexte, le numéro seul et les cas interprétatifs. Le cas sans numéro visible à Mirecourt est distingué des fusions démontrées.

| Cahier | Initiaux | Examinés actuels | Sans correction | Corrigés/créés | Fusions établies | Séparations à tort | Autres incidents | Incertains actuels |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Cahier du clergé de la sénéchaussée d'Agen | 70 | 71 | 69 | 2 | 0 | 0 | 2 | 0 |
| Cahier de la noblesse de la sénéchaussée d'Agen | 66 | 72 | 58 | 14 | 6 | 0 | 2 | 0 |
| Cahier de la communauté de Terre-Franche et du comté de Ribeaucourt (Bailliage de Douai) | 11 | 11 | 10 | 1 | 0 | 0 | 1 | 0 |
| Cahier de la noblesse du bailliage de Mirecourt | 25 | 28 | 22 | 6 | 2 | 0 | 1 | 0 |
| Cahier du clergé de Vic (Bailliage de Toul) | 42 | 43 | 41 | 2 | 1 | 0 | 0 | 0 |
| Cahier du clergé de la sénéchaussée d'Anjou | 80 | 80 | 80 | 0 | 0 | 0 | 0 | 0 |
| Cahier de Lawastine (Bailliage de Bailleul) | 5 | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| Cahier du clergé du bailliage de Mirecourt | 5 | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| Cahier de Pierrelez (Paris) | 9 | 9 | 9 | 0 | 0 | 0 | 0 | 0 |
| Cahier de Plessis-Secqueville (Paris) | 9 | 9 | 9 | 0 | 0 | 0 | 0 | 0 |

Le clergé de Mirecourt (notice 1744) est distinct de la noblesse (1745). Les identifiants complets, volumes et compteurs par opération figurent dans `data/cahiers.json`.

## Opérations, historique et passages C

- **317 opérations de validation**, toutes portant sur un article ; **aucune validation groupée** dans le journal réel. Elles touchent 312 identifiants distincts, dont certains ont ensuite été remplacés par des corrections. Cinq validations répètent un identifiant déjà validé. Additionner les clics ne donne donc pas le nombre d’articles validés actuels.
- **16 opérations `correct` et 11 opérations `missing`**, regroupées en 15 incidents documentaires ; deux corrections supplémentaires de numéro à Agen concernent des ajouts déjà comptés. Toutes les 27 opérations de modification sont rattachées à un incident.
- Deux articles du clergé d’Agen ont temporairement été laissés incertains (5 et 7). Les décisions ultérieures les ont validés : **aucun article actuellement incertain** dans ces dix dossiers. L’historique n’est pas effacé.
- Aucune opération `classify`, `merge` ou `split` explicite. Les séparations ont été réalisées par une réduction de l’article initial suivie d’un ajout depuis la plage C libérée. Il faut lire les positions, pas seulement le nom de l’action.
- Onze ajouts depuis des plages techniques : l’article 6 du clergé d’Agen était absent des articles initiaux ; les dix autres reprennent du texte initialement absorbé dans des articles existants. Cela ne signifie pas que onze passages C quelconques ont été reconnus comme onze nouveaux articles indépendants. Aucun classement explicite de C en paratexte, section ou passage revendicatif n’a été enregistré.

## Confrontation aux déclarations humaines

Le tirage comporte exactement **108 événements nouveaux**, tous `validate`, et aucun autre événement : le journal est cohérent avec « cinq cahiers, sans erreur constatée, environ 15 minutes ». La durée est une déclaration humaine, pas une mesure déduite du journal.

Pour Terre-Franche, Vic et la noblesse de Mirecourt, les traces montrent **cinq incidents** : trois fusions manifestes, une séparation interprétative d’une prose sans numéro 2 visible et une attribution de numéro seule. Cela précise les « quatre à cinq erreurs » signalées oralement ; ce ne sont pas cinq fusions OCR démontrées. La trentaine de minutes annoncée n’est pas contredite ni remplacée par les intervalles entre clics.

## Portée

Les validations humaines constituent ici la référence de travail. Leur journal ne démontre ni une vérification de chaque mot contre le fac-similé, ni l’absence de toute erreur restante. Les rubriques et métadonnées secondaires ne sont pas certifiées par l’acceptation du découpage. Aucune validation de frontière parentale n’est comptée comme validation d’article.
