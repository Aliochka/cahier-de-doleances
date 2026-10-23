# RAG-014 — Recherche hybride RRF locale

Le moteur combine exclusivement la recette **RAG-009 pondérée, réponse seule**
et **RAG-013 BGE-M3 dense, représentation B**. Il n'ajoute ni index, ni migration,
ni dépendance. Le corpus reste le manifeste RAG-007 de 20 000 unités.

## Fusion et interface Python

```python
from cahier_rag.search.hybrid import HybridConfig, HybridEngine

# lexical : FlexibleEngine existant ; vector : VectorEngine déjà chargé.
engine = HybridEngine(lexical, vector, scope, HybridConfig(k=60, depth=50))
results = engine.search("Comment améliorer les services publics ?", limit=10,
                        split="development", questionnaire_id=None, unit_type=None)
# results : list[SearchResult], documents et provenance inchangés.
diagnostics = engine.last_retrieval
```

Chaque moteur récupère au maximum `depth` unités avec les mêmes filtres.
Les recherches sont séquentielles pour limiter la concurrence PostgreSQL.
Le modèle est chargé explicitement une seule fois par session, puis réutilisé
pour toutes les requêtes. `HybridEngine` ne charge pas lui-même de modèle.

La fusion utilise les rangs de base 1 et des poids égaux :

```text
RRF(document) = somme, sur les moteurs présents, de 1 / (k + rang)
```

Le défaut est `k=60`, sans réglage automatique ni calibration des scores.
Les scores sources ne sont jamais comparés ou additionnés. Le calcul utilise
des fractions exactes, puis expose un score `float` dans `SearchResult`.
Les égalités sont départagées par identifiant documentaire (ordre compatible C).
Un document présent une seule fois contribue une fois ; un doublon interne au
moteur conserve son premier rang sans renuméroter les suivants. Un même ID
avec des contenus différents est une erreur. Deux réponses citoyennes distinctes
contenant le même texte restent deux documents.

`engine.retrieve(...)` retourne les listes lexicales, vectorielles et hybrides
jusqu'à la profondeur demandée, les traces de chaque candidat et les mesures.
Les traces donnent les rangs/scores originaux et la contribution RRF de chaque
moteur. Le meilleur segment par unité a déjà été agrégé par RAG-013 : la fusion
ne traite pas des segments comme des réponses distinctes.

Les garde-fous sont `1 <= k <= 10000`, `1 <= depth <= 100` et
`1 <= limit <= depth`. Le plafond de profondeur reprend celui du moteur
vectoriel existant, qui n'est pas modifié. Une liste source vide est acceptée ;
un moteur indisponible provoque une erreur plutôt qu'une expérience partielle
présentée sous la même configuration. Une requête blanche est refusée.

## CLI

Depuis `rag/`, les variables de connexion sont explicites :

```bash
export RAG_SOURCE_DATABASE_URL=postgresql:///cahier_doleances_local
export RAG_DATABASE_URL=postgresql:///cahier_rag

# Environnement optionnel RAG-012/013 existant, sans toucher à l'annotation :
.cache/embeddings-venv/bin/python -m cahier_rag.search.hybrid.cli \
  --depth 50 --k 60 --limit 10 search 'Comment rendre la fiscalité plus juste ?'

# Mêmes profondeur, filtres et top-k pour les trois méthodes :
.cache/embeddings-venv/bin/python -m cahier_rag.search.hybrid.cli \
  --depth 50 --k 60 --limit 10 development \
  --output evaluation/local/rag014/nouvel-essai

# Pool hors ligne, sans GPU, connexion PostgreSQL ou dépendances ML :
.venv/bin/python -m cahier_rag.search.hybrid.cli pool \
  --experiment evaluation/local/rag014/development-replay \
  --output evaluation/local/rag014/nouveau-pool \
  --per-query 20 --seed 20261021
```

Les options globales (`--depth`, `--k`, `--limit`, `--env-file`, `--sample`,
`--frozen`, `--queries`, `--vector-directory`, `--models`, `--questionnaire-id`,
`--unit-type`) précèdent la sous-commande. Les sorties doivent être de nouveaux
dossiers ; aucun artefact existant n'est écrasé.
Le point d'entrée `cahier-rag-hybrid` est aussi disponible après installation
ou synchronisation du projet. `python -m` fonctionne immédiatement dans les
environnements éditables existants, sans synchroniser la session d'annotation.

Le diagnostic `search` affiche volontairement texte, provenance et traces des
moteurs. Ne pas en partager la sortie si elle contient des informations
personnelles. Les commandes d'expérimentation affichent uniquement des
statistiques. Aucun texte n'est envoyé à un service externe.

## Vérifications et exports

La CLI vérifie l'empreinte et la configuration gelées RAG-009, les empreintes
de ses cinq modules historiques, le manifeste RAG-007, la configuration de
l'index lexical et la compatibilité de l'espace BGE-M3 RAG-013. L'intégrité
vectorielle complète est vérifiée au chargement. Les résultats sont également
contrôlés contre les documents, filtres et partitions du manifeste.

La CLI est exclusivement en **développement** : elle ne propose pas de commande
exécutant les requêtes réservées. L'API Python exige une partition valide et
peut prendre en charge ultérieurement une évaluation explicitement organisée.
La comparaison exécute chaque moteur une seule fois par requête et réutilise
ces listes pour la configuration hybride. Elle exporte :

- `lexical-rankings.json`, `vector-rankings.json`, `hybrid-rankings.json` :
  objets `query_id -> [document_id,...]`, directement compatibles RAG-006.
- `rankings.json` : regroupement des trois top-k.
- `runs.json` : listes sources et hybrides à la profondeur de candidats.
- `diagnostics.json` : rangs, scores sources et contributions RRF.
- `documents.json` : identifiants/provenance nécessaires au futur pool, sans texte.
- `report.json` : recettes, filtres, versions, empreintes, mesures et références
  aux baselines gelées. Aucune métrique de pertinence n'est calculée.

Les latences distinguent lexical, vectoriel, validation des documents, fusion
et total. Le rapport agrège médiane et P95 (rang supérieur sur les observations).
Les chargements initiaux et vérifications globales sont hors temps par requête.
Recouvrement et origine des résultats sont relatifs à la profondeur de candidats,
pas à tous les documents qu'un moteur pourrait retrouver.

## Pool complémentaire

La commande `pool` vérifie les empreintes de l'expérience et les références des
candidats au corpus. Pour détecter les anciens couples, elle lit uniquement
`rag009/annotations/pool.json` et son manifeste, fichiers sources non annotés
également utilisés pour RAG-010. Elle ne lit ni la session ni les jugements.
La présence dans ce pool indique « déjà proposé », pas « déjà noté ».

La sélection est déterministe pour une graine donnée :

1. Privilégier les couples absents de l'ancien pool.
2. Privilégier les contributions encore absentes, tant qu'il en reste parmi ces
   couples. Réutiliser ensuite les contributions si nécessaire pour remplir.
3. Faire tourner les catégories d'origine (commun, lexical seul, vectoriel seul),
   méthodes et tranches de rangs 1–10, 11–25 et 26+.
4. Départager les possibilités par empreinte de la graine, requête et document.

Cette sélection est un pool d'annotation volontaire, sans représentativité
statistique ni quota universel garanti pour chaque catégorie. Les déficits de volume sont conservés dans les statistiques ; les origines et
tranches effectivement présentes sont traçables par candidat. Les tranches
peuvent se chevaucher entre moteurs pour un même document.

Le résultat `pool.json` contient les références et empreintes originales,
`found_by` (méthodes/rangs/scores), les motifs de sélection et
`already_in_rag010`. Les champs de jugement sont tous `null` : aucune note n'est
créée. Le manifeste garde graine, versions, empreintes des classements et anciens
couples, empreinte du nouveau pool et implémentation. Aucun fichier RAG-010
n'est créé ou modifié.

Les traces de moteurs sont réservées aux analyses et devront être masquées dans
une future interface d'annotation à l'aveugle. Le pool final réel est
`evaluation/local/rag014/candidates-final/` ; aucune session ne lui est associée.
Tous ces artefacts restent sous le répertoire local ignoré par Git.

## Validation et limites

```bash
RAG_TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
RAG_STORAGE_TEST_DATABASE_URL=postgresql:///cahier_rag_test \
uv run --no-sync pytest
uv run --no-sync ruff check .
uv lock --check
```

Les tests unitaires fonctionnent sans PostgreSQL/GPU. L'intégration combine les
vrais moteurs PostgreSQL sur un corpus synthétique et un encodeur simulé. Elle
n'effectue aucune écriture sur les documents expérimentaux réels.

RRF promeut les documents communs mais ne garantit pas leur pertinence. Le rang
masque les écarts de scores internes à chaque moteur. La profondeur conditionne
le recouvrement et les promotions ; `k=60` est un point de départ, pas un optimum.
Les expressions obligatoires du lexical ne deviennent pas des contraintes sur
les candidats vectoriels. Aucune pondération, sélection automatique de paramètres,
recherche approximative ou phase de reranking n'est ajoutée.
