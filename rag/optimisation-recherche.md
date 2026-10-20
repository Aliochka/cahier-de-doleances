# Recherche locale — RAG-027

Le corpus complet conserve 5 172 356 unités et 5 187 190 segments BGE-M3.
Le rapport [RAG-027](rapport-rag-027.md) distingue équivalence lexicale,
approximation vectorielle et validation du parcours personnel.

## Démarrer et arrêter

Depuis `rag/`, avec les environnements existants de RAG-012/016 :

```bash
export RAG_SOURCE_DATABASE_URL=postgresql:///cahier_doleances_local
export RAG_DATABASE_URL=postgresql:///cahier_rag
.cache/judges-venv/bin/python -m cahier_rag.personal.cli serve \
  --corpus rag026 --search-profile rag027 --ann --port 8770
```

Ouvrir <http://127.0.0.1:8770>. Arrêter par **Ctrl+C** dans ce terminal.
La génération reste `generation-fr-v6-personal`, avec les mêmes modèles.
Le chargement des modèles et le reranking rendent une réponse beaucoup plus
lente que la seule recherche. Le premier parcours mesuré prend environ 100 s.

`--search-profile rag027` utilise les statistiques lexicales exactes matérialisées
et, avec `--ann`, HNSW `ef_search=1000`, 400 candidats avant agrégation,
`strict_order`, `max_scan_tuples=20000`, `scan_mem_multiplier=1`.
Ce compromis ANN **ne satisfait pas tous les seuils de recouvrement préfixés**.
Il ne garantit pas les voisins exacts, notamment pour les requêtes très courtes.

Pour privilégier l'exactitude vectorielle, omettre `--ann` :

```bash
.cache/judges-venv/bin/python -m cahier_rag.personal.cli serve \
  --corpus rag026 --search-profile rag027 --port 8770
```

Pour reproduire la recherche historique RAG-026 :

```bash
.cache/judges-venv/bin/python -m cahier_rag.personal.cli serve \
  --corpus rag026 --search-profile rag026 --ann --port 8770
```

Pour revenir au corpus expérimental de 20 000 unités :

```bash
.cache/judges-venv/bin/python -m cahier_rag.personal.cli serve \
  --corpus rag007 --port 8770
```

Les nouveaux caches/questions libres du corpus complet sont isolés sous
`evaluation/local/rag027/personal/<search_profile>/`. Les anciens artefacts
RAG-026 ne sont pas écrasés. Le cache personnel RAG-007 reste celui de RAG-025.
Un seul calcul par serveur ; éviter plusieurs inférences GPU simultanées.

## Préparer les statistiques et reproduire les mesures

L'environnement léger `.venv/` suffit pour PostgreSQL et les rapports :

```bash
uv run --locked python -m cahier_rag schema-upgrade
uv run --locked python -m cahier_rag.tuning.cli statistics
```

La migration `rag_0007` ajoute uniquement `rag_tuning.statistics` et
`rag_tuning.term_statistics`. Elle passe par les contrôles d'identité des bases.
La matérialisation lit les `tsvector` déjà présents ; elle ne touche ni aux
vecteurs, ni aux tables sources, ni aux index existants. Le corpus doit être
vérifié. Une statistique incompatible est refusée, sans remplacement implicite.

Le jeu versionné `evaluation/performance-rag027.json` contient 32 requêtes :
20 de développement et 12 exploratoires. Aucune requête réservée n'est exécutée.

```bash
# Seulement les embeddings des 32 requêtes, cache local vérifié :
.cache/embeddings-venv/bin/python -m cahier_rag.tuning.cli encode
# Mesures lexicales et ANN/exact, checkpoints JSON après chaque unité de travail :
uv run --locked python -m cahier_rag.tuning.cli lexical
uv run --locked python -m cahier_rag.tuning.cli vectors
# Rapport descriptif sur les mesures existantes, sans PostgreSQL ni modèle :
uv run --locked python -m cahier_rag.tuning.cli report
# Enregistrement explicite du compromis mesuré, qualification ANN signalée false :
uv run --locked python -m cahier_rag.tuning.cli select
```

Les commandes longues reprennent les mesures déjà terminées avec la même recette.
Une recette/code/périmètre incompatible est refusé ; choisir un nouveau répertoire
avec `--directory` pour une nouvelle expérience. Pour une mesure historique
séparée : `tuning.cli lexical --reference --directory <nouveau-répertoire>`.
Ne pas utiliser le répertoire des résultats optimisés pour cette référence.
Ne pas mélanger statistiques de froid et premières exécutions observées : aucun
cache système n'a été vidé. Le rapport indique des P95 empiriques, sans benchmark
de concurrence.

## Interface Python et filtres

`TunedSearch(store).lexical(...)` accepte les mêmes filtres et contrats que
`FullSearch`. Sans filtre, les DF sont matérialisées ; avec filtre, les DF sont
recalculées sur la population filtrée pour conserver la formule historique.
La variante `prefilter=1000` est une approximation diagnostique, pas le profil retenu.

`cahier_rag.tuning.retrieval.search_vector(store, vector, ann=True, ...)` retourne
les `SearchResult` et une trace. Sans filtre, elle utilise le profil ANN explicite ;
avec filtre, elle utilise un parcours exact distinct. Une expression de tri
`distance + 0.0` interdit l'utilisation d'HNSW comme substitut à l'exact, tout en
laissant les index relationnels disponibles. Le délai reste borné à 30 s et une
expiration est une erreur, jamais un classement présenté comme complet.

Attention : les parcours exacts filtrés restent trop lents dans plusieurs cas
réels. L'appel bas niveau `tuning.vector.ann_search` sert aussi aux diagnostics :
il peut épuiser son budget de parcours et retourner moins de résultats qu'il
n'existe de documents éligibles. Ne pas interpréter cela comme une absence de
sources pertinentes. L'interface personnelle n'ajoute pas de filtres interactifs.

## Vérifications

```bash
uv run --locked pytest
uv run --locked ruff check src tests
uv lock --check
```

Les intégrations nécessitent les variables de **bases de test isolées** documentées
dans le README. Ne jamais leur fournir le corpus réel pour les fixtures d'écriture.
Les tests GPU optionnels ont besoin de l'environnement lourd existant.
