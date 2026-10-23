# RAG-009 — Recherche lexicale souple et pondérée

## Résultat

Deux méthodes lexicales sont disponibles à côté de RAG-008 : correspondance
partielle et pondération explicite des termes. Le corpus expérimental reste
celui des 20 000 unités RAG-007 ; les vecteurs, le GIN, les représentations et
les partitions sont réutilisés sans migration ou nouvelle dépendance.

Sur les vingt requêtes de développement, la baseline stricte retourne des
résultats pour **6 requêtes**, les nouvelles méthodes pour **20**. Après gel,
un **seul passage** de la candidate pondérée sur les vingt requêtes réservées
a retourné des résultats pour **20 requêtes**. Ces nombres décrivent la couverture
lexicale ; aucun jugement humain ni score de pertinence n’a été produit.

## Méthodes et préparation

- **Strict** : délégation directe au moteur RAG-008, sur la requête originale,
  sans préparation supplémentaire ni changement de paramètres.
- **Partial** : termes significatifs combinés en OR, puis `ts_rank_cd(...,32)`.
- **Weighted** : mêmes candidats, avec 50 % de couverture IDF, 30 % de couverture
  en nombre de termes distincts et 20 % de fréquence/proximité PostgreSQL.

Les requêtes nouvelles passent par une préparation française légère : NFC,
guillemets français, séparation des expressions/exclusions et suppression
facultative d’une liste fermée d’interrogatifs et consignes. Les lexèmes sont
ensuite normalisés par PostgreSQL. La liste exacte, les versions et paramètres
sont conservés dans les manifestes. Les termes cités ne sont pas supprimés par
la liste générique ; les phrases restent obligatoires. `--keep-generic` permet
une recherche précise sur un mot de cette liste. Les requêtes sans lexème utile
ou purement négatives donnent une liste vide ; aucun repli caché n’élargit le corpus.

L’IDF est `ln(1 + (N-df+0,5)/(df+0,5))`. N et df sont calculés dans la partition,
la représentation et les filtres de recherche. Les statistiques de développement
ne mélangent pas les documents réservés. Les égalités gardent l’ordre documentaire
sous collation C. Les scores servent au classement, sans interprétation probabiliste.

Les trois représentations sont conservées : réponse seule, réponse + question,
réponse + question + titre. Pour limiter les combinaisons, cinq expériences ont
été menées : stricte réponse, souple réponse, puis pondérée sur les trois
représentations. Aucun produit cartésien de réglages n’a été exploré.

Code ajouté : `search/preparation.py`, `flexible.py`, `experiments.py`,
`flexible_cli.py`, et `scripts/prepare_lexical_candidates.py`. Le moteur strict
`search/lexical.py` n’a pas été modifié. L’interface restitue les mêmes
`SearchResult` et `TextUnit`, avec BIGINT sans perte et provenance inchangée.

## Comparaison sur le développement

Limite commune : dix résultats par requête ; vingt requêtes, sans annotation.
Les proportions portent sur les occurrences de résultats, et non les documents
uniques ou la fréquence d’opinions dans le corpus.

| Configuration | Requêtes avec résultats | Résultats | Contributions distinctes globales | Médiane | P95 |
|---|---:|---:|---:|---:|---:|
| Stricte, réponse | 6/20 | 8 | 4 | 5,79 ms | 6,90 ms |
| Souple, réponse | 20/20 | 200 | 56 | 27,98 ms | 39,87 ms |
| Pondérée, réponse | 20/20 | 200 | 117 | 164,67 ms | 253,66 ms |
| Pondérée, question | 20/20 | 200 | 122 | 216,44 ms | 385,70 ms |
| Pondérée, titre | 20/20 | 200 | 123 | 232,04 ms | 403,94 ms |

La diversité globale de la pondération indique moins de réutilisation des mêmes
parents entre requêtes. Par requête, la moyenne est de **9,65 contributions**
pour le OR simple et **9,60** pour les variantes pondérées : il n’y a pas de gain
observé de diversité à l’intérieur de chaque classement. La moyenne stricte de
0,40 inclut les quatorze requêtes sans résultat.

Aucun résultat de moins de 60 caractères n’apparaît dans ces top 10 naturels.
Les textes « Autre » représentent 0,5 % des occurrences en souple, 1 % en pondérée
réponse et question, 0,5 % en pondérée titre. Les tests contrôlés confirment que
les réponses courtes restent recherchables ; cette sous-représentation dans les
classements doit être examinée humainement, pas masquée par la couverture 20/20.

Les expressions citées restent obligatoires dans les méthodes nouvelles. Les
recherches contrôlées `TVA`, `l’école` et `"taxe carbone"` conservent l’ordre de
la baseline sur le corpus synthétique. Les nouveaux mots-clés non cités sont
souples : pour exiger l’AND historique, utiliser `strict`.

## Choix et gel

La **pondération sur réponse seule** est retenue comme candidate provisoire :

- Couverture des vingt requêtes, avec une pondération interprétable des termes.
- Diversité globale de 117 contributions contre 56 en OR simple.
- Coût inférieur aux variantes contextualisées, pour une couverture identique.
- Réponse seule limitant les correspondances apportées uniquement par question
  ou titre ; leur utilité devra être évaluée avec les jugements humains.

Le OR simple reste beaucoup plus rapide. Le choix ne constitue pas une preuve
de meilleure pertinence. Les poids n’ont pas fait l’objet d’une optimisation
sur jugements et la préparation n’a pas été isolée par une ablation quantitative.

Le gel `evaluation/local/rag009/frozen.json` enregistre paramètres/versions,
raison, date UTC, index PostgreSQL, corpus/requêtes, rapport de développement et
empreintes de cinq modules, y compris le moteur strict inchangé.
Son empreinte est :

`cf6be3518bb8be1c17ab75d785d2b8f618102f22d4a47786c166c5f95d920073`

Un marqueur exclusif `frozen.evaluation-claimed.json` a été créé avant le passage
réservé. La commande refuse une autre exécution sur ce gel. Aucun code de
classement ni paramètre n’a été modifié après gel ; documentation, contrôles de conformité
et rejeux du développement ont suivi.

## Évaluation gelée : description seulement

Un seul passage réel sur les vingt requêtes, sans ajustement ultérieur :

| Indicateur | Candidate pondérée, réponse |
|---|---:|
| Requêtes avec résultat | 20/20 |
| Occurrences de résultats, dix au maximum par requête | 200 |
| Contributions distinctes globales | 114 |
| Réponses de moins de 60 caractères | 2 occurrences — 1 % |
| Textes « Autre » | 1 occurrence — 0,5 % |
| Latence médiane | 125,60 ms |
| P95 | 171,77 ms |

La partition d’évaluation est plus petite que le développement ; les latences
ne sont pas directement comparables entre partitions. Les fichiers `results.json`
et `report.json` sont compatibles avec RAG-006. Aucun Precision, Recall, MRR ou
nDCG n’a été calculé sur ces données sans jugements. L’évaluation n’a pas été
relancée pour vérifier la reproductibilité ; ses artefacts ont été contrôlés
hors ligne et le développement a été rejoué à l’identique.

## PostgreSQL et BM25

Aucune écriture dans les tables documentaires, les vecteurs ou la base source.
Aucun nouvel index, extension ou schéma. Les valeurs sont liées ; les fragments
SQL variables sont des constantes internes. Le GIN existant sert aux candidats
et aux fréquences documentaires. La population et les statistiques sont bornées
au corpus et aux filtres, avec les délais PostgreSQL de cinq secondes/deux secondes.

Trois plans `EXPLAIN (ANALYZE, BUFFERS)` de développement ont été conservés :

| Requête de développement | Temps SQL observé | GIN présent |
|---|---:|---|
| fiscalite-01 | 262,02 ms | Oui |
| democratie-03 | 165,26 ms | Oui |
| ecologie-06 | 233,92 ms | Oui |

Ce sont des sondes, pas un benchmark de charge. Le classement pondéré examine
les termes de tous les candidats d’une requête OR ; les demandes larges peuvent
couvrir une grande partie des 17 612 documents de développement. Le comptage N
parcourt leurs métadonnées. Le surcoût observé est explicite : aucun parcours
massif des millions de réponses sources n’est effectué.

**BM25 n’est pas ajouté.** Une version SQL fiable demanderait des fréquences et
longueurs normalisées, des moyennes et df par représentation/partition, avec une
stratégie de stockage ou de calcul adaptée. Les positions des tsvector actuels
sont plafonnées et ne fournissent pas toutes les fréquences. Des tables dérivées
ou une extension imposeraient migrations, indexation et validation supplémentaires.
Sans jugements, le bénéfice n’est pas établi ; le biais de longueur observé rend
cette piste intéressante à réexaminer après annotation. La pondération actuelle
n’est pas une implémentation de BM25. Voir les
[références et la discussion technique](recherche-souple.md#postgresql-et-bm25).

## Pool pour les annotations

Le pool de développement contient **400 paires**, vingt par requête :

- 236 documents distincts ; aucun doublon de paire requête/document.
- 266 paires avec plusieurs méthodes d’origine conservées.
- 220 paires ont au moins une provenance de rang supérieur à dix.
- 40 témoins pseudo-aléatoires, deux par requête, graine 20261019.

Les candidats proviennent de classements jusqu’au rang trente, avec alternance
des tranches 1–3, 4–10, 11–20, 21–30. Le plafond et la profondeur sont configurables.
Les méthodes/rangs sont conservés y compris pour les documents communs.
Les témoins sont tirés hors des candidats déjà choisis, sans supprimer une
éventuelle provenance lexicale. Les occurrences originales ne sont pas fusionnées.

Les lignes comportent IDs documentaire/corpus/contribution/réponse/question/
questionnaire, empreinte, méthodes/rangs et marqueur aléatoire. Les BIGINT sont
des chaînes. Texte et contexte restent consultables par les références PostgreSQL.
Les champs note, justification, date et évaluateur restent nuls. Aucun résultat
réservé n’a servi à fabriquer ce pool et aucun jugement n’a été inventé.

## Artefacts et vérifications

Sous `rag/evaluation/local/rag009/`, ignoré par Git :

```text
history-hashes.json                  Historique RAG-008, corpus et requêtes protégés
development/<configuration>/         results.json et report.json, cinq configurations
plans-development.json               Plans SQL et buffers des trois sondes
annotations/                         runs.json, pool.json, manifest.json
frozen.json                          Configuration candidate figée
frozen.evaluation-claimed.json        Marqueur du passage réservé
evaluation/                          Classements et rapport descriptif uniques
verification.json                    Contrôles hors ligne et rejeu du développement
```

**250 tests réussis**, dont 53 intégrations PostgreSQL et 197 tests unitaires.
Cas vérifiés : questions longues, correspondance partielle, pondération,
expressions, accents/apostrophes, mots vides/génériques, limites, courtes,
« Autre », filtres, égalités, partitions, BIGINT, provenance, pooling, gel et
refus d’une seconde évaluation. Les imports restent isolés du backend et des modèles.
Ruff, formatage, `uv lock --check` et `git diff --check` sont conformes.

La baseline stricte de développement est exactement égale aux exports RAG-008.
Les empreintes de 26 fichiers historiques/corpus/requêtes sont inchangées.
Le rejeu de la candidate sur le développement et le pooling à partir des runs
archivés sont identiques. Les références, partitions et empreintes de l’évaluation
ont été vérifiées sans nouvelle recherche réservée. Aucun corps documentaire
n’est affiché dans ce rapport ni ajouté à Git.

## Limites et commandes

La correspondance OR augmente le risque de résultats peu liés à l’intention.
Les questions et titres peuvent introduire du contexte utile ou des correspondances
superficielles. La liste générique peut supprimer un mot utile hors guillemets ;
la configuration permet de la désactiver. Les synonymes, paraphrases et ambiguïtés
sémantiques restent hors portée. Les longues réponses sont favorisées par la
couverture multi-termes, et la fréquence/proximité hérite des limites PostgreSQL.
L’échantillon reste non représentatif et ses partitions déséquilibrées.

L’annotation humaine est la prochaine condition pour comparer la pertinence.
Le protocole, les formules et commandes sont décrits dans
[recherche-souple.md](recherche-souple.md). Aucun backend, frontend, Wallace,
modèle, dépendance GPU ou LLM n’est modifié ou ajouté. Aucun commit ni push effectué.
