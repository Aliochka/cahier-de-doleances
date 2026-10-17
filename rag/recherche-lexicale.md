# Baseline lexicale locale — RAG-008

## Périmètre et architecture

Le moteur se trouve dans `cahier_rag.search.lexical`. Il utilise SQLAlchemy Core,
PostgreSQL 17 et les connexions/contrôles d’identité RAG-005. Il n’importe ni
backend, ni FastAPI, ni module LLM. Aucun moteur ou connexion n’est créé à l’import.

`CorpusScope` charge un instantané immuable du manifeste RAG-007. Par défaut,
il exige **20 000 unités** et l’empreinte exacte
`d0173a371df7fc5d6b5d8ca393ea3f230349140b1cfb92a1ec4a2280200033cc`.
Le fichier est d’abord validé par `load_sample`. Un autre manifeste, même de
20 000 unités, est refusé par la CLI. Les tests peuvent explicitement fournir
une autre empreinte et une taille synthétique. Cette possibilité Python n’est
pas un mécanisme implicite de remplacement du corpus expérimental.

Les tables ajoutées dans le schéma `rag` par Alembic `rag_0002` sont :

| Table | Responsabilité |
|---|---|
| `lexical_corpora` | Empreinte du corpus, compte, configuration et version PostgreSQL |
| `lexical_members` | IDs, empreintes de contenu et partitions exactes du manifeste |
| `lexical_vectors` | Un `tsvector` par membre et par stratégie |

Les membres référencent `text_units`. Les vecteurs référencent les membres par
une clé étrangère composite et sont uniques par corpus/stratégie/document.
Les 20 000 unités produisent 60 000 vecteurs : ce ne sont pas 60 000 documents.
La jointure de recherche passe toujours par ce périmètre et ne recherche jamais
implicitement dans les 42 318 unités du cadre. Les tables documentaires ne sont
pas modifiées et les champs texte/question/titre restent séparés.

L’index `ix_rag_lexical_vector_gin` porte sur `search_vector`. Les clés primaires
B-tree servent au périmètre et à la stratégie. Le GIN commun aux trois stratégies
peut retourner des candidats d’autres variantes, filtrés ensuite par la requête.
Les mesures locales ont confirmé son intérêt ; voir le rapport d’exécution.

## Analyse, stratégies et scores

La configuration est explicitement **`pg_catalog.french`**, sans dépendre du
paramètre global du serveur. Les requêtes utilisent `websearch_to_tsquery` :
termes non cités combinés par AND, expressions entre guillemets doubles,
`OR` et exclusion par `-`. Les opérateurs sont ceux de PostgreSQL et ne sont
pas traduits en français. Aucun SQL utilisateur n’est interpolé.

Trois stratégies seulement sont proposées, construites ensemble :

| Valeur CLI/Python | Champs dérivés indexés | Poids |
|---|---|---|
| `answer` | Réponse seule | A = 1,0 |
| `question` | Réponse puis question | A = 1,0 ; B = 0,4 |
| `title` | Réponse puis question puis titre éventuel | A = 1,0 ; B = 0,4 ; C = 0,2 |

Le classement est `ts_rank_cd(vector, query, 32)`, avec les poids PostgreSQL
standards D/C/B/A = 0,1/0,2/0,4/1,0. La normalisation 32 transforme le score en
`score/(score+1)`. Ce nombre classe des correspondances lexicales ; ce n’est
ni une probabilité ni un jugement humain de pertinence. Les égalités sont
résolues par ID documentaire croissant sous collation **C**, indépendamment
de la locale du serveur. Aucun seuil de longueur n’est appliqué.

La configuration française traite lexèmes, flexions, apostrophes et mots vides.
Une réponse courte telle que « TVA » est indexée et recherchable ; un texte
composé uniquement de mots vides peut avoir un vecteur vide. Les « Autre » sont
indexés comme les autres unités, sans réintroduire les libellés des choix.
Les expressions portent sur des séquences de lexèmes, pas sur des octets exacts.
La concaténation des vecteurs peut permettre une expression à la frontière de
deux champs dans les variantes contextualisées ; cette limite doit être prise
en compte lors des jugements. Les positions et tailles maximales des `tsvector`
restent celles de PostgreSQL ; aucun découpage des longs documents n’est ajouté.

## Reconstruction et garanties

`rebuild` effectue une reconstruction atomique : verrou transactionnel par
empreinte, suppression de l’ancien index dérivé, vérification des unités et
empreintes, insertion des membres et des trois vecteurs par lots de cent.
Une unité manquante ou altérée annule l’ensemble, en conservant l’ancien index.
Le texte source n’est jamais réécrit. Les requêtes cibles sont bornées à cinq
secondes et l’attente de verrou à deux secondes.

Les lectures vérifient version, configuration et nombre de membres/vecteurs.
Un verrou partagé sur le manifeste d’index stabilise ces contrôles pendant la
recherche. `validate()` compare en plus tous les membres, empreintes et partitions
au manifeste fourni. Chaque résultat est restauré en `TextUnit` et ses empreintes
sont vérifiées. Les IDs restent des `int` Python et des chaînes décimales dans
les exports documentaires JSON. Seul le score utilise un flottant.

Une configuration ou version PostgreSQL différente exige une reconstruction
explicite. Le corpus et les règles sont figés pour ces expériences ; changer les
poids ou le parseur impose de versionner la configuration, reconstruire et
produire un nouveau répertoire de classements. Conserver PostgreSQL et ses
dictionnaires identiques pour reproduire les scores. Les fichiers de dictionnaire
modifiés manuellement sous une même version serveur ne sont pas détectés.

Les contrôles RAG-005 exigent aussi que la source soit accessible pour vérifier
l’identité des bases, même si les recherches n’en lisent aucun texte. Un rôle
source réellement limité à la lecture reste nécessaire. La base RAG est locale ;
aucun déploiement public n’est modifié.

## Interface Python

```python
from cahier_rag.__main__ import open_store
from cahier_rag.config import load_settings
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.search.lexical import CorpusScope, LexicalEngine, Strategy

scope = CorpusScope(load_sample("evaluation/local/rag007/corpus.json"))
with open_store(load_settings(env_file=".env.local")) as store:
    engine = LexicalEngine(store.guard, scope)
    results = engine.search(
        '"services publics"',
        strategy=Strategy.ANSWER,
        questionnaire_id=4,
        split="development",
        limit=10,
    )
    # result.document contient le TextUnit original, contexte et provenance compris.
    # result.to_dict() sérialise les BIGINT en chaînes ; éviter de journaliser les corps.
```

Filtres disponibles : `questionnaire_id`, `unit_type`, `split`.
La limite est comprise entre 1 et 1 000 résultats ; la requête entre 1 et
1 000 caractères non blancs. Dans l’API, `split=None` recherche les 20 000 membres.
Dans la CLI, le défaut est **development** pour éviter de consulter l’évaluation
pendant les réglages ; `--split all` choisit explicitement tout le corpus.

## Commandes locales

Depuis `rag/` :

```bash
uv sync --locked
uv run --locked cahier-rag schema-upgrade --env-file .env.local
uv run --locked cahier-rag-search --env-file .env.local rebuild
uv run --locked cahier-rag-search --env-file .env.local verify
uv run --locked cahier-rag-search --env-file .env.local search '"services publics"' --strategy answer --questionnaire-id 4 --limit 10
uv run --locked cahier-rag-search --env-file .env.local search TVA --unit-type open_answer --split development
```

Les options globales `--env-file` et `--sample` précèdent le sous-ordre.
Le manifeste par défaut est `evaluation/local/rag007/corpus.json`.
Les paramètres RAG d’environnement peuvent remplacer le fichier explicite.
La CLI affiche seulement IDs et scores par défaut ; `--show-text` expose les
objets complets et peut afficher des données personnelles. Les rapports de
cette tâche n’en contiennent aucune.

## Exécution des requêtes et annotations

```bash
uv run --locked cahier-rag-search --env-file .env.local evaluate --strategy answer --split development --output-directory evaluation/local/NOUVEL_ESSAI/answer/development
# Après gel de la configuration, sans adaptation sur les résultats d’évaluation :
uv run --locked cahier-rag-search --env-file .env.local evaluate --strategy answer --split evaluation --output-directory evaluation/local/NOUVEL_ESSAI/answer/evaluation
```

Répéter pour `question` et `title`. Chaque répertoire reçoit :

- `results.json` : objet query_id → liste ordonnée d’IDs, directement compatible
  avec `cahier-rag-eval score` et les métriques RAG-006.
- `candidates.json` : paires requête/document retournées, note `null`, sans faux
  jugement humain. Les doublons entre fichiers de variantes restent à dédupliquer
  par paire avant adjudication commune.
- `report.json` : configuration, version PostgreSQL, empreintes, partition,
  limite, temps par requête et avertissement d’absence de mesure de qualité.

Les fichiers existants ne sont pas écrasés. La partition de chaque requête
restreint celle des documents, sans modifier les 40 requêtes. Le défaut est
le développement. Les mesures finales doivent utiliser l’évaluation gelée.
Les latences comprennent contrôles d’identité, vérification d’état et restauration
des résultats ; elles ne sont pas des temps SQL seuls.

Les exports de l’opération RAG-008 sont dans `evaluation/local/rag008/`, ignoré
par Git. Le fichier `random-candidates.json` contient aussi cinq candidats
aléatoires par requête, préparés avec RAG-006, indépendamment des classements.
Ils permettent de commencer une annotation lorsque le moteur ne retourne rien ;
ils ne sont jamais injectés dans les résultats lexicaux.

## Limites et références

Les longues requêtes naturelles combinées en AND sont très restrictives. Cette
baseline ne reformule pas les demandes, ne traduit pas les synonymes et n’utilise
ni BM25, embeddings, reranker, LLM ou recherche hybride. Un résultat vide ne permet
pas de conclure que le corpus ne contient pas de réponse pertinente. Les variantes
contextualisées peuvent retrouver la question plutôt qu’une réponse utile : des
jugements humains sont indispensables avant toute comparaison de qualité.

Voir [le rapport RAG-008](rapport-rag-008.md), le
[protocole d’évaluation](evaluation.md), ainsi que les documentations PostgreSQL
sur [l’analyse, les requêtes et le classement](https://www.postgresql.org/docs/17/textsearch-controls.html)
et sur [les index plein texte](https://www.postgresql.org/docs/17/textsearch-indexes.html).
