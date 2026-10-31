# Segmentation des articles — amélioration expérimentale

La nouvelle extension retrouve **les six débuts manqués responsables des fusions corrigées dans la noblesse d’Agen**, ainsi que **l’article 6 du clergé d’Agen**, anciennement pris pour une rubrique. Elle sépare aussi un `5tt` entre 4 et 6 dans le clergé d’Alençon, examiné après gel des règles. Aucun texte ni journal humain n’a été modifié.

Cette amélioration est livrée comme **propositions comparables dans l’outil local**, sans remplacer les unités existantes. Les décisions humaines gardent leurs identifiants et leur priorité.

## Résultats

| Mesure | Ancien segmenteur V2 | Extension figée |
|---|---:|---:|
| Débuts des 6 articles fusionnés corrigés à Agen | 0/6 | 6/6 |
| Article 6 du clergé d’Agen | absent | retrouvé |
| Plages de corrections humaines reproduites exactement | 0/16 | 10/16 |
| Même mesure après retrait des blancs aux extrémités, pour comparaison seulement | 0/16 | 15/16 |
| Débuts corrects dans la validation distincte | 83/84 | 83/84 |
| Faux débuts dans cette validation | 0 | 0 |
| Articles complets correctement bornés, tolérance de position de 3 caractères | 73/74 | 73/74 |

Les 16 plages concernent **uniquement des corrections**, pas un échantillon de tous les articles. Les chiffres d’Agen mesurent le développement. La validation distincte comprend 12 fenêtres dans six autres cahiers, une par volume, avec deux fenêtres par cahier. Elles contiennent 91 occurrences de débuts, soit **84 distincts** après déduplication du chevauchement à Périgny. Codex a établi cette référence après gel, avant calcul des prédictions ; ce n’est pas une validation humaine indépendante.

## Corpus et limites de la comparaison

- Le corpus initial contient toujours **719 articles, dont 217 A** ; il n’est pas régénéré par cette mission.
- La réexécution brute de V2 en retrouve **718**, l’extension propose **726 unités B**, avec **8 nouveaux débuts** : sept à Agen et un à Alençon.
- **709/718 plages V2 restent exactement identiques**. Les neuf autres correspondent aux séparations et à deux absorptions de prose/rubrique corrigées à Agen.
- Comparée directement au corpus initial, la proposition conserve **708/719 plages**, dont **215/217 A**. Les deux A non reproduits sont les articles 10 et 11 de Terre-Franche : leur fusion est déjà présente dans la réexécution V2, et reste non résolue par l’extension. Les deux unités originales sont conservées dans l’interface et les exports existants.
- Un seul marqueur suspect est détecté automatiquement : `56` à Mirecourt. Cela **ne signifie pas qu’il ne reste qu’une seule fusion**. `A:rt. 32.` à Vic et `i lfl` à Terre-Franche sont des contre-exemples connus non reconnus par les nouvelles règles.

## Dans l’interface

Relancer le serveur local avec la commande habituelle, puis recharger la page. Dans **Articles**, ouvrir **« Comparer les nouvelles propositions de segmentation »**. Le panneau montre les marqueurs, leurs indices et les anciennes/nouvelles plages.

- Les nouvelles propositions ne modifient aucune unité.
- **« Préparer une séparation à vérifier »** ouvre l’éditeur avec la position proposée. Il faut encore prévisualiser et confirmer explicitement.
- Une proposition située dans un article déjà validé humainement reste consultable, sans bouton de remplacement automatique.
- Une fusion suspecte dans un article non validé est signalée dans ses anomalies : elle bloque la validation groupée tant qu’elle n’a pas été examinée individuellement.
- Les cahiers et les exports restent fondés sur le corpus initial et les décisions humaines, pas sur le fichier de comparaison.

## Recommandation

Reprendre la validation par groupes pour les suites régulières, en examinant les alertes de fusion. **Ne pas recommencer les deux cahiers d’Agen déjà examinés** : leurs corrections sont prioritaires. Contrôler spécifiquement Mirecourt, Vic et Terre-Franche. Conserver les limites A héritées comme contraintes avant toute future régénération globale ; les propositions de cette mission ne sont pas un corpus de remplacement certifié.

Aucune précision globale sur les 719 articles n’est démontrée : les nouvelles variantes OCR restent un risque. Aucun temps humain n’a été mesuré. La seule nouvelle référence documentaire est une lecture exploratoire de Codex.

Voir [DIAGNOSIS.md](DIAGNOSIS.md), [EVALUATION.md](EVALUATION.md), [SUSPECTS.md](SUSPECTS.md) et [DATA.md](DATA.md).
