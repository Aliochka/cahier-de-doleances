# RAG-007 — Corpus expérimental constitué

## Résultat

**20 000 unités documentaires réelles distinctes sont disponibles dans PostgreSQL
local**, avec provenance, empreintes, partitions et manifestes de sélection.
Le corpus final est défini par `rag/evaluation/local/rag007/corpus.json`.
Aucun texte de contribution n’est reproduit ici.

| Ensemble | Unités distinctes |
|---|---:|
| Cadre extrait et stocké | 42 318 |
| Sélection aléatoire dans le cadre | 10 000 |
| Sélection stratifiée | 13 103 |
| Intersection des deux sélections | 3 103 |
| **Union expérimentale finale** | **20 000** |

Les unités du cadre sont stockées dans `cahier_rag.rag.text_units`, avec douze
manifestes et leurs associations/checkpoints. Les sélections sont des manifestes
JSON locaux ; aucune table supplémentaire n’est introduite. Les unités du cadre
non retenues restent disponibles en base et ne font pas partie des 20 000 unités
finales. Ne pas utiliser le nombre total de lignes de la base comme taille du corpus.

## Méthode et garde-fous

L’opération a commencé par vérifier l’espace disque : environ **1,4 To libres**.
La source configurée est `cahier_doleances_local`, la destination `cahier_rag`.
Les contrôles physiques RAG-005 ont été conservés. La source utilise les
transactions READ ONLY, fermées avant les écritures destination.

Pour chaque questionnaire détaillé, l’intervalle d’IDs des contributions est
découpé en quarante zones. Une graine explicite choisit une ancre par zone ;
une requête indexée prend au plus quarante contributions dans cette zone.
Sur 160 zones prévues, **116 sont non vides**. Aucun tirage SQL aléatoire, OFFSET,
tri des textes ou extraction intégrale des réponses n’est effectué.

| Questionnaire | Contributions sélectionnées | Zones non vides | Intervalle d’IDs sélectionnés |
|---|---:|---:|---|
| 4 | 1 560 | 39 | 1 827–117 020 |
| 5 | 800 | 20 | 119 312–229 226 |
| 7 | 720 | 18 | 239 544–415 041 |
| 10 | 1 560 | 39 | 426 227–577 003 |
| **Total** | **4 640** | **116** | |

Les contributions sont regroupées en douze listes explicites, de 500 IDs au
maximum. Chaque extraction reste plafonnée à **10 000 documents et 100 000
lignes retournées**, avec des lots de cent lignes. Les extractions ont toutes
terminé par `source_exhausted`, sans atteindre un plafond. Les compteurs totalisent
62 280 lignes sources retournées, relectures de curseurs partiels comprises.

L’adaptation ajoute uniquement le filtre optionnel `contribution_ids`, borné,
trié, unique, sérialisé sans perte BIGINT et vérifié à la lecture comme à
l’écriture. Il est inclus dans les paramètres et empreintes de reprise.
Son absence conserve exactement la forme des anciens manifestes. Les plafonds
RAG-005/006 ne sont pas relevés. Aucune migration n’est nécessaire.

Les requêtes de l’opération sont bornées par `statement_timeout=5s` et
`lock_timeout=2s`. Le plan est enregistré avant les extractions, puis les
checkpoints sont validés lot par lot avec les documents et leurs associations.

Le tirage aléatoire utilise la graine **20261018**, le stratifié **20261019**.
Une recherche déterministe de la taille stratifiée obtient une union de
20 000 IDs. Les deux sélections partagent le cadre complet et la graine de
partition **1729**, selon RAG-006. Version du contrat : 1 ; lecteur : gdn-v1 ;
pipeline : 1 ; sélection : 1. Version déclarée du corpus :
`gdn-2019-audit-2026-10-16`.

## Statistiques descriptives

| Questionnaire | Cadre | Aléatoire | Stratifié | Union finale |
|---|---:|---:|---:|---:|
| 4 — Services publics | 11 668 | 2 754 | 3 661 | 5 536 |
| 5 — Démocratie | 14 960 | 3 506 | 4 471 | 6 929 |
| 7 — Fiscalité | 4 041 | 982 | 1 307 | 1 978 |
| 10 — Écologie | 11 649 | 2 758 | 3 664 | 5 557 |

| Indicateur | Cadre | Aléatoire | Stratifié | Union finale |
|---|---:|---:|---:|---:|
| Réponses ouvertes | 41 216 | 9 739 | 12 751 | 19 461 |
| Textes « Autre » | 1 102 | 261 | 352 | 539 |
| Au plus 20 caractères | 5 283 | 1 281 | 1 681 | 2 536 |
| Moins de 60 caractères | 14 760 | 3 467 | 4 588 | 6 964 |
| Plus de 2 000 caractères | 203 | 53 | 100 | 124 |
| Occurrences textuelles excédentaires | 3 484 | 596 | 844 | 1 405 |
| Contributions avec plusieurs réponses ouvertes retenues | 3 952 | 2 414 | 2 960 | 3 522 |

Les courtes représentent **34,82 %** de l’union et les longues **0,62 %**.
Les textes « Autre » représentent **2,70 %**. Ces catégories peuvent se recouper.
L’union comprend 360 groupes de textes répétés, dont **267 groupes impliquant
plusieurs contributions**, soit 1 526 occurrences dans ces groupes transversaux.
Les occurrences ne sont pas fusionnées. Les 3 522 parents à réponses multiples
sont comptés parmi 4 072 contributions ayant une réponse ouverte retenue.

| Longueur en caractères, tous types | Aléatoire | Stratifié | Union |
|---|---:|---:|---:|
| Minimum | 1 | 1 | 1 |
| Moyenne | 181,92 | 188,86 | 182,60 |
| Médiane | 93 | 93 | 93 |
| P90 | 363 | 362 | 361 |
| P95 | 567 | 570 | 563 |
| P99 | 1 363 | 1 622 | 1 447 |
| Maximum | 56 257 | 56 257 | 56 257 |

Les quantiles locaux utilisent le rang inférieur `(N-1)*p/100` sur les longueurs
triées ; de petites différences avec d’autres conventions de quantile sont possibles.
Les 2 536 textes très courts sont des candidats à examiner avec leur question,
pas des jugements humains établissant un besoin de contexte.

### Quotas et partitions

Chaque quota stratifié vaut 100 : questionnaires 4/5/7/10, courtes, longues,
« Autre », doublons, réponses multiples et candidats contexte. **Aucun déficit.**
Le quota le plus contraignant est celui des longues : exactement 100 dans le
stratifié. Les autres comptes de strates du manifeste sont : 352 « Autre »,
1 162 unités appartenant à un groupe répété du cadre, 12 595 réponses de parents
multi-réponses et 1 681 courtes/candidats contexte. Les strates sont définies
par rapport au cadre et ne sont pas des catégories exclusives.

| Partition | Aléatoire | Stratifié | Union finale |
|---|---:|---:|---:|
| Développement | 8 817 | 11 545 | 17 612 |
| Évaluation | 1 183 | 1 558 | 2 388 |

Les liens de contribution et de texte exactement identique sont regroupés
transitivement sur **tout le cadre**, y compris les unités non sélectionnées.
La plus grande composante du cadre contient **18 041 unités**. La règle de
partition n’a pas été modifiée pour forcer 80/20 : l’union aboutit à 88,06/11,94.
Ce déséquilibre est une limite pour les premières évaluations. Les fichiers
RAG-006 d’un ancien cadre restent des diagnostics séparés, sans fusion avec ce
nouveau cadre gelé. Les quarante requêtes et leur séparation sont inchangées.

### Comparaison avec l’audit initial

Comparaison sur les seules réponses ouvertes, pour éviter de mélanger les
« Autre » avec les statistiques historiques des questions `text` :

| Indicateur | Corpus de l’audit | Réponses ouvertes de l’union |
|---|---:|---:|
| Moyenne | 196,13 | 184,39 |
| Médiane | 102 | 95 |
| P90 | 404 | 365 |
| P95 | 621 | 571 |
| P99 | 1 523 | 1 465 |
| Au plus 20 caractères | 11,50 % | 12,64 % |
| Moins de 60 caractères | 32,47 % | 34,58 % |
| Plus de 2 000 caractères | 0,61 % | 0,63 % |
| Occurrences excédentaires de textes identiques | 13,91 % | 7,13 % |
| Maximum | 350 874 | 56 257 |

L’échantillon conserve davantage de courtes et des longues grâce au quota,
mais ne couvre pas les textes les plus extrêmes. Un taux de doublons inférieur
est attendu dans une sélection partielle : les autres occurrences peuvent rester
en dehors du cadre ou de l’union. Cela ne prouve pas une moindre répétition
intrinsèque des opinions. Les bases historiques et définitions figurent dans
[les statistiques d’audit](../docs/audit-corpus-rag.md).

## Manifestes et vérifications

Les fichiers sont dans `rag/evaluation/local/rag007/`, ignoré par Git :
`plan.json`, `progress.json`, `random.json`, `stratified.json`, `corpus.json`,
`statistics.json`, `verification.json`, `source-verification.json`.
Ils occupent environ 20 Mo et ne contiennent pas les corps documentaires.
Les textes restent en PostgreSQL. Les IDs et empreintes ne sont pas une
anonymisation, notamment pour les textes courts : conserver ces fichiers localement.

Empreinte SHA256 de la liste finale, comprenant provenance minimale,
empreintes de contenu et partitions :

`d0173a371df7fc5d6b5d8ca393ea3f230349140b1cfb92a1ec4a2280200033cc`

- La reconstruction des deux sélections produit les mêmes IDs et empreintes.
- Toutes les unités du cadre ont été relues depuis PostgreSQL et restaurées
  avec vérification de l’identité documentaire et de l’empreinte de contenu.
- Les manifestes sont vérifiés contre le plan et les paramètres de reprise.
- Aucune contribution commune ni aucun texte exact commun ne traverse les
  partitions dans le corpus final ; les documents partagés par les sélections
  gardent la même partition.
- Douze unités, trois par questionnaire, ont été comparées directement à la
  source avec leur contexte et provenance : égalité exacte des objets JSON.
- Les 629 appels bornés à un lot ont réutilisé les checkpoints entre appels.
  Les tests PostgreSQL couvrent aussi interruption, reprise, rollback et
  reprise avec liste de contributions modifiée, qui est refusée.
- Les quarante requêtes ont conservé leur empreinte Git d’origine :
  `68d30e717840b45150aeb7534f256119d7f724b5baf441476d675f29925ef164`.

## Performances et qualité

La préparation des 160 fenêtres et du plan a pris environ **0,16 seconde**,
avec une requête de fenêtre au maximum à 15 ms, sur des données locales en cache.
Les 629 appels de lecture/persistance totalisent **44,60 secondes** : médiane
24 ms, P95 76 ms, maximum 2,99 s ; le premier lot a pris 35 ms. Ces durées
incluent les contrôles d’identité et les transactions, mais pas toute la gestion
locale des fichiers. Ce sont des observations de cette exécution, pas un benchmark.
Une vérification complète avec reconstruction des sélections a pris 13,60 s.

**208 tests réussis**, dont 34 intégrations PostgreSQL et 174 tests unitaires.
Les tests ajoutés couvrent filtre borné, identifiants BIGINT, compatibilité des
anciens manifestes, paramètres SQL liés, reprise, changement de périmètre,
sélection sur résumés et union synthétique de 20 000 unités sans fuite.
Ruff, formatage, `uv lock --check` et `git diff --check` sont conformes.

## Limites et usage

Les fenêtres prennent des petits groupes voisins dans l’ordre d’IDs importés,
pas des contributions indépendantes uniformes. Les bornes incluent parfois des
IDs isolés : certaines zones sont vides, surtout pour les questionnaires 5 et 7.
La fiscalité est sous-représentée dans ce cadre par rapport à la taille réelle
de son questionnaire ; le nombre de réponses par contribution crée aussi des
différences entre formulaires. La stratification enrichit volontairement le jeu.
Ni le cadre, ni l’union, ni la sélection aléatoire **dans ce cadre** ne sont
présentés comme statistiquement représentatifs du Grand Débat ou des Français.

La protection anti-fuite repose sur l’égalité exacte des textes et les parents,
pas sur les paraphrases, auteurs ou foyers. Elle peut produire de grands groupes
et un jeu final déséquilibré. Les besoins de contexte restent à juger humainement.
Aucun jugement réel de pertinence n’est créé et aucun score de moteur n’est publié.

La base source est restée en lecture seule. Aucun schéma source, backend,
frontend, secret, déploiement Wallace, modèle ou moteur n’a été modifié ou ajouté.
Aucune dépendance ni verrou n’a changé. Aucun commit ni push n’a été effectué.
La [procédure et les commandes](corpus-experimental.md) permettent de retrouver
les documents, vérifier l’opération et reprendre les extractions.

### Références des extractions PostgreSQL

Les UUID ci-dessous sont aussi présents avec leurs filtres et versions dans
chaque manifeste de sélection et dans `progress.json`.

| Questionnaire | Unités | UUID d’extraction |
|---|---:|---|
| 4 | 3917 | `0a60e338-c8b4-4233-841e-da7eb438da0a` |
| 4 | 3739 | `ba8d6415-83d6-47b9-b092-5260943c2b72` |
| 4 | 3590 | `7b827a7c-e894-4b23-825c-e729b23285ab` |
| 4 | 422 | `4e3c3ba1-d7c8-4254-97a4-2276bdb3e8db` |
| 5 | 9379 | `683c208e-0a9e-4969-946f-b0b480822231` |
| 5 | 5581 | `287fd8cc-f147-427d-bf1a-5e8eca71782b` |
| 7 | 2795 | `0653fdfe-d148-4bd1-aa25-75c32b389aba` |
| 7 | 1246 | `35829d2b-91f4-47e1-ad8d-989e361c604d` |
| 10 | 3842 | `d8c5ad2b-4819-4334-bda6-1e256e05a65b` |
| 10 | 3702 | `3dc550a1-7eef-4596-8da4-2e77b423dc62` |
| 10 | 3644 | `5bd74126-1639-4e73-8027-28f1d8be5f7d` |
| 10 | 461 | `b9001691-ade0-47ea-b9c3-65ba83322bb3` |
