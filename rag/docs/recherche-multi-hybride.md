# Comparaison multi-hybride — RAG-019

L'extension `search/hybrid/multi/` ajoute la fusion pondérée sans modifier
`search/hybrid/core.py`, les moteurs, les index ou les artefacts historiques.
Elle réutilise les `SearchResult` et `TextUnit` existants. Les modules de fusion,
rejeu et évaluation n'imposent aucune dépendance GPU.

## Configurations figées

| Profil | Sources et poids |
|---|---|
| H1 | lexical pondéré 1 ; BGE-M3 1 |
| H2 | BM25-A 1 ; BGE-M3 1 |
| H3 | BM25-B 1 ; BGE-M3 1 |
| H4 | lexical pondéré 1 ; BM25-A 1 ; BGE-M3 1 |
| H5 | lexical pondéré 1/4 ; BM25-A 1/4 ; BGE-M3 1/2 |

Chaque source fournit **50 candidats** ; `k=60`, rangs à partir de 1.
Le score est `Σ poids_source / (60 + rang_source)`. Les poids ne sont pas
renormalisés si une liste est vide. Les scores des sources sont conservés
dans les traces, mais ne sont jamais additionnés entre moteurs.

Le calcul et le tri utilisent des fractions exactes. Les égalités sont
départagées par l'identifiant documentaire, dans l'ordre binaire. Un doublon
dans une même liste ne contribue qu'au premier rang rencontré ; les rangs
suivants conservent leurs positions originales, comme dans RAG-014. Deux
identifiants distincts contenant le même texte restent deux occurrences.
Un contenu différent pour un identifiant commun est refusé.

H5 équilibre le **poids d'entrée** lexical/vectoriel, pas nécessairement la
répartition des résultats ou la somme des contributions dans les top k :
les rangs et recouvrements interviennent aussi. H4 conserve le double poids
lexical total demandé ; aucune correction a posteriori des poids n'est appliquée.

Le gel `evaluation/local/rag019/configuration/frozen.json` contient ces
paramètres, les empreintes de la fusion, des listes sources, des index BM25,
du corpus et des requêtes. Il est créé avant la comparaison de pertinence.
Toute modification d'un élément gelé bloque le chargement.

## Modules et API

| Module | Responsabilité |
|---|---|
| `core.py` | Profils versionnés, fusion pondérée, récupération mutualisée et filtres |
| `live.py` | Adaptateurs des quatre moteurs existants, chargement unique de BGE-M3 |
| `artifacts.py` | Gel, vérification des empreintes, restitution locale des candidats |
| `experiments.py` | Passage réel, rejeu de fusion, mesures et statistiques |
| `evaluation.py` | Références en lecture seule, complément et comparaison commune |
| `markdown.py` | Rapport lisible reproductible, sans textes citoyens |
| `cli.py` | Commandes locales, aucun serveur HTTP |

`MultiHybridEngine` reçoit des fonctions `search(query, limit, split,
questionnaire_id, unit_type)`. Il applique les mêmes filtres aux sources puis
vérifie les contenus, partitions, questionnaires et types retournés avant fusion.
Les moteurs filtrent **avant** leur top-k ; le rejeu des listes non filtrées
n'est pas utilisé pour simuler une nouvelle recherche filtrée.

Les cinq profils partagent une seule récupération par source et par requête.
L'encodage BGE-M3 n'est effectué qu'une fois par requête dans le passage réel.
Les segments sont déjà regroupés par le moteur vectoriel historique ; la fusion
travaille sur les unités originales, sans compter chaque segment séparément.

L'API peut retourner jusqu'à 100 résultats fusionnés depuis l'union des listes
de 50. Il s'agit d'un top 100 **à profondeur source 50**, pas d'une expérience
à 100 candidats par moteur. Les références individuelles gardent ici 50 résultats.
Les listes profondes historiques RAG-018 ne sont pas modifiées.

## Mesure réelle et rejeu

Le passage réel chronomètre chaque source, ses contrôles et chaque fusion.
Il exécute les seuls 20 textes de requête de développement et vérifie :

- l'égalité des listes sources avec les préfixes RAG-018 ;
- l'égalité du top 50 H1 avec RAG-014 ;
- le périmètre exact RAG-007 et ses partitions ;
- la stabilité des poids avant tout calcul de pertinence.

Les totaux par configuration sont **reconstitués à partir des étapes
chronométrées d'une même requête** : sources concernées, contrôles et fusion.
Ils ne sont pas cinq latences observées dans cinq recherches indépendantes.
Le temps total de la session partagée (quatre sources et cinq fusions) est
également conservé. Les médianes des composantes ne s'additionnent pas.

Le rejeu restaure les seuls candidats depuis la copie SQLite BM25-A, en lecture
seule, vérifie leurs empreintes, puis refait les fusions sur les scores et rangs
sauvegardés. Il ne se connecte pas à PostgreSQL et ne charge aucun modèle.
Seul le temps de fusion est interprété comme tel ; la restauration des candidats
n'est pas présentée comme un temps de récupération réel.

Les statistiques exportées couvrent les recouvrements des sources, leurs candidats
exclusifs, les contributions citoyennes distinctes, les réponses courtes et « Autre ».
Dans les top 10 et 50, chaque source possède un effectif de présence, un effectif
exclusif et une part arithmétique de la somme RRF. Les présences se recouvrent ;
la part RRF n'est pas une mesure causale de pertinence.

## Commandes

Depuis `rag/`, utiliser l'environnement léger existant pour le rejeu et les rapports.
Les variables de connexion sont uniquement celles du RAG, ou un `--env-file`
explicitement sélectionné. Les options globales précèdent la sous-commande.

```bash
# Uniquement pour créer un NOUVEAU gel dans un dossier absent :
.venv/bin/python -m cahier_rag.search.hybrid.multi.cli \
  --frozen evaluation/local/NOUVEAU_GEL freeze

# Mesure réelle : GPU pour BGE-M3, PostgreSQL local et index existants :
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.cache/embeddings-venv/bin/python -m cahier_rag.search.hybrid.multi.cli \
  development --output evaluation/local/NOUVEAU_PASSAGE

# Rejeu CPU sur les listes compatibles déjà calculées :
.venv/bin/python -m cahier_rag.search.hybrid.multi.cli replay \
  --experiment evaluation/local/rag019/development \
  --output evaluation/local/NOUVEAU_REJEU

# Diagnostic réel, toujours sur le développement :
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.cache/embeddings-venv/bin/python -m cahier_rag.search.hybrid.multi.cli \
  search 'transports ruraux' --profile H5 --limit 10
```

Le diagnostic affiche des textes et traces, pour un usage local uniquement.
Il accepte `--questionnaire-id` et `--unit-type`. La CLI ne lance pas le jeu de
requêtes réservé ; l'API conserve une partition explicite pour les futurs usages.

Les dossiers de sortie sont créés exclusivement : aucune expérience existante
n'est écrasée. Toutes les sorties réelles restent sous `evaluation/local/`,
ignoré par Git. Aucune nouvelle dépendance ni migration n'est nécessaire.

## Réutilisation et complément d'annotation

```bash
.venv/bin/python -m cahier_rag.search.hybrid.multi.cli pool \
  --experiment evaluation/local/rag019/development \
  --output evaluation/local/NOUVEAU_POOL
```

Le pool cible déduplique l'union des top 50 des cinq hybrides et des quatre
références. Il conserve méthodes et rangs dans `targets.json`. `pool.json`
contient seulement les nouveaux couples absents des plans RAG-017/018.
Les anciens échecs connus ne sont pas réannotés.

Dans l'expérience RAG-019, les **2 673 couples cibles sont déjà référencés** :
le complément est vide. Cela découle aussi du périmètre de fusion : tous les
résultats proviennent des top 50 individuels déjà couverts. Aucun modèle juge
n'est donc chargé, aucun nouveau cache ou faux jugement n'est créé. Le manifeste
de complément existe avec `new_pairs=0` et `plan_hash=null`.

Si une expérience future produit réellement des nouveaux couples, l'outil
prépare un sous-dossier `plan/` compatible avec la campagne v2 existante, en
conservant le plafond contrôlé de 3 000. Il faut alors précontrôler et exécuter
successivement les deux juges sur ce seul plan avec une limite égale à son
nombre d'entrées. Le cache sera local au nouveau pool, jamais RAG-017 ou RAG-018.
Les métadonnées de moteurs ne sont pas incluses dans les messages des juges.

## Comparaison de pertinence

```bash
.venv/bin/python -m cahier_rag.search.hybrid.multi.cli report \
  --experiment evaluation/local/rag019/development \
  --pool evaluation/local/rag019/complement \
  --output evaluation/local/NOUVEAU_RAPPORT
```

Les caches historiques sont ouverts strictement avec `mode=ro`. Le rapport
vérifie les empreintes des plans, entrées, recettes et sorties valides. Les deux
référentiels restent séparés et portent `judgment_origin: llm`. Aucune session
humaine n'est lue par ces outils ; aucun ancien jugement n'est réparé.

Les métriques de RAG-017/018 sont réutilisées : pertinence binaire 2–3,
Precision@5/10/20/50, MRR@50 et nDCG poolée aux mêmes profondeurs. L'IDCG utilise
le pool cumulé commun, pour la requête et le juge. Il ne représente pas tout le
corpus. Aucun Recall exhaustif. Toutes les métriques sont recalculées pour les
neuf méthodes ; aucune nDCG n'est copiée d'un rapport historique.

Les moyennes principales portent sur les **mêmes 17 requêtes entièrement jugées
par les deux modèles**. Les trois requêtes affectées par les échecs historiques
restent exclues de cet ensemble ; les couvertures et métriques calculables des
20 requêtes sont également publiées. Un non-jugé n'est jamais noté zéro.

Les rapports JSON et Markdown conservent les écarts par requête, les agrégations
par domaine et catégorie, les divergences entre juges, et les contributions des
sources. Les exports de jugements sont compatibles avec les listes RAG-006 et
gardent la provenance de leurs campagnes d'origine, sans fusion humaine implicite.

## Tests et limites

```bash
uv run --locked --no-sync pytest
uv run --locked --no-sync ruff check .
uv lock --check
```

Les tests unitaires utilisent des documents et juges synthétiques. Les intégrations
utilisent uniquement les bases `_test` déjà prévues par le projet. Le gel, les
corruptions d'artefacts, les compléments vides/non vides, la préservation des caches,
les BIGINT et les métriques indéfinies sont vérifiés.

La profondeur 50 et le pooling bornent les conclusions. Les deux branches
lexicales peuvent renforcer des erreurs corrélées ; les deux juges Qwen partagent
une famille de modèles. Les résultats de développement ne constituent pas une
validation finale indépendante. Les résultats, poids et requêtes réservées ne
sont pas ajustés dans cette tâche.
