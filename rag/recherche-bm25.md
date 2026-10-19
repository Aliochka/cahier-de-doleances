# Recherche BM25 locale — RAG-018

BM25-A indexe la réponse ; BM25-B indexe la réponse puis sa question, une seule
fois. Les textes et contextes d'origine restent séparés dans les `TextUnit`.
Les deux variantes ont les mêmes paramètres, fixés avant lecture des notes.
Ce module ne remplace ni ne modifie les moteurs historiques.

## Choix d'implémentation

Trois possibilités ont été examinées :

| Solution | Intérêt | Limites pour ce ticket |
|---|---|---|
| Bibliothèque Python `rank_bm25` | Formules éprouvées, API simple | Corpus/fréquences en mémoire et calcul de scores sur des tableaux couvrant tous les documents ; peu adapté tel quel à plusieurs millions d'unités |
| Tables de postings et statistiques PostgreSQL | Reste dans PostgreSQL ; SQL BM25 explicite possible | Demande de nouvelles tables, migrations et mesures de plans ; `ts_rank_cd` n'est pas BM25 et les positions/fréquences de `tsvector` ne suffisent pas à préserver les longs textes sans limites |
| Extension spécialisée, par exemple ParadeDB `pg_search` | Index inversé et BM25 spécialisés | Installation et exploitation d'une extension supplémentaire ; intérêt à réexaminer sur le corpus complet |

La solution retenue est une petite implémentation Python avec **index inversé
SQLite sur disque**, sans nouvelle dépendance ou service. SQLite ne fournit
ici ni tokenisation ni score implicite : les postings exacts et longueurs sont
stockés explicitement et la formule est exprimée dans une requête liée. Ce choix
évite le parcours Python de tous les documents à chaque requête et permet de
mesurer une baseline CPU indépendante. Il ne valide pas une architecture de
production à plusieurs millions de réponses.

La fonction `bm25()` de SQLite FTS5 a également été examinée : elle fournit bien
un score BM25, mais avec ses conventions IDF et paramètres internes. Elle n'est
pas utilisée, afin de rendre la formule et les statistiques entièrement explicites.

Sources primaires : [formulation BM25, Stanford IR](https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html),
[implémentation rank_bm25](https://github.com/dorianbrown/rank_bm25/blob/master/rank_bm25.py),
[PostgreSQL ts_debug](https://www.postgresql.org/docs/17/textsearch-debugging.html),
[SQLite FTS5 BM25](https://www.sqlite.org/fts5.html#the_bm25_function),
[ParadeDB](https://www.paradedb.com/docs/start/introduction).

## Formule et statistiques

Pour chaque terme distinct de la requête :

```text
IDF(t) = ln(1 + (N - df(t) + 0,5) / (df(t) + 0,5))
score(d,q) = Σ IDF(t) × tf(t,d) × (k1+1)
                       / (tf(t,d) + k1 × (1-b + b × dl(d)/avgdl))
k1 = 1,2 ; b = 0,75
```

Il s'agit de BM25 avec IDF positive lissée, sans feedback de pertinence ni
pondération de fréquence de requête. `tf` est le nombre exact d'occurrences,
`dl` le nombre de lexèmes après filtrage, `df` le nombre de documents contenant
le terme. Les documents vides après tokenisation restent dans N ; aucun texte
court, doublon légitime ou champ « Autre » n'est supprimé.

N, df et avgdl sont calculés **séparément pour développement et évaluation**.
Les filtres questionnaire/type sélectionnent les candidats sans recalculer les
statistiques de la partition. Une recherche ne mélange jamais les deux partitions.
Les égalités sont départagées par identifiant documentaire, ordre binaire.

BM25-B concatène réponse et question pour ses seules fréquences et longueur.
Il n'y a ni boost de question ni répétition ajoutée. La faible IDF des termes
communs réduit leur poids, sans garantir l'absence de biais contextuel. Un texte
court peut néanmoins bénéficier de sa question sans répondre réellement à la
requête : la comparaison des jugements doit précisément mesurer cet effet.

## Tokenisation française

`FrenchTokenizer` réutilise `pg_catalog.french` via `ts_debug`, en conservant
l'ordre de tous les lexèmes. Il bénéficie du parseur, des dictionnaires,
stopwords et de la racinisation Snowball français de PostgreSQL. Ce n'est pas
une lemmatisation ni une suppression générale des accents. Les règles
effectives sont celles du serveur, pas une liste Python réinventée.

Les documents ne passent pas par `to_tsvector` : les limites de positions ou
de fréquence de cette représentation ne plafonnent pas nos comptes. Les tests
contrôlent notamment 20 000 occurrences d'un même mot. Les requêtes reprennent
la préparation légère de RAG-009 : NFC, liste générique figée, au plus 32 termes,
guillemets et exclusions. Les expressions imposées sont vérifiées sur la suite
des lexèmes ; les stopwords supprimés et les frontières de champs ne sont pas
préservés comme positions de surface. Ce n'est pas une garantie d'expression
exacte caractère par caractère.

Le manifeste conserve version PostgreSQL, configuration et empreinte d'une
sonde de normalisation. Une modification personnalisée des dictionnaires peut
nécessiter une nouvelle version explicite ; cette sonde n'est pas une empreinte
exhaustive de tous les fichiers de dictionnaires du serveur.

## Stockage, lots et reprise

Chaque variante possède son fichier `.sqlite3` dans `evaluation/local/rag018/`.
Les tables dérivées contiennent documents JSON fidèles, longueurs, suites de
lexèmes, postings `(split, term, id, tf)`, df et statistiques de partition.
Les BIGINT restent des chaînes dans le JSON, puis des `int` à la restitution.
Les références ne sont pas transformées en nombres flottants.

Les lots de 50 unités sont lus dans la base RAG via `RepresentationRepository`,
avec contrôle du manifeste exact RAG-007. Les connexions PostgreSQL sont fermées
avant l'écriture locale. Documents et postings sont validés dans la même
transaction SQLite. La reprise saute les identifiants déjà validés. L'index
ne devient recherchable qu'après finalisation atomique des statistiques.

La vérification compare les membres, partitions et empreintes au manifeste,
les contenus restaurés, les comptes de termes, longueurs, df et statistiques.
Une empreinte logique ordonnée permet de comparer deux reconstructions, sans
exiger des fichiers SQLite physiquement identiques. Pour une vérification de
tokenisation depuis la source, reconstruire dans un nouveau dossier et comparer
les empreintes logiques.

Les index B-tree permettent de lire les postings des seuls termes recherchés.
La mémoire cache SQLite est bornée à 32 Mio, les temporaires de classement sont
autorisés sur disque et les requêtes sont interrompues après environ 5 secondes
par un gestionnaire de progression. La restauration charge seulement le top-k,
limité à 100. Le manifeste garde 20 000 métadonnées en mémoire, pas tous les textes.

## Commandes

Depuis `rag/`, dans l'environnement léger existant (`uv sync --locked` pour une
installation neuve ; ne pas retirer les extras d'un environnement utilisé par
l'annotation humaine). Avec `RAG_DATABASE_URL` configurée explicitement :

```bash
# Construire ou reprendre les deux index, sans migration :
uv run --locked --no-sync python -m cahier_rag.search.bm25.cli build
uv run --locked --no-sync python -m cahier_rag.search.bm25.cli verify

# Diagnostic sur le développement uniquement :
uv run --locked --no-sync python -m cahier_rag.search.bm25.cli search \
  'transports ruraux' --variant A --limit 10

# Nouveau dossier de reconstruction ou de mesure :
uv run --locked --no-sync python -m cahier_rag.search.bm25.cli \
  --directory evaluation/local/NOUVEL_INDEX build

# Comparaison : requiert le rejeu local gelé baselines100 décrit ci-dessous :
uv run --locked --no-sync python -m cahier_rag.search.bm25.cli development \
  --output evaluation/local/NOUVELLE_COMPARAISON
```

La commande `search` affiche les textes ; les rapports statistiques ne les
reproduisent pas. `--questionnaire-id` et `--unit-type` filtrent les résultats.
L'API Python expose `search(..., split=..., limit=..., questionnaire_id=...,
unit_type=...)` et retourne les `SearchResult` existants. La CLI n'exécute pas
les requêtes réservées, même si leurs unités sont présentes dans l'index commun.

## Rejeu et annotations complémentaires

Les références lexicales et vectorielles sont rejouées une fois, sans changer
leur configuration, via la CLI hybride existante et son environnement :

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.cache/embeddings-venv/bin/python -m cahier_rag.search.hybrid.cli \
  --depth 100 --limit 100 development \
  --output evaluation/local/rag018/baselines100
```

La comparaison refuse un rejeu différent de RAG-017 aux profondeurs disponibles.
Le classement hybride produit par cet outil n'entre pas dans la présente
comparaison. Les recherches BM25 sont également exécutées à 100 ; les mesures
de pertinence et le complément d'annotations concernent seulement les top 50.

```bash
.venv/bin/python -m cahier_rag.search.bm25.cli pool \
  --experiment evaluation/local/rag018/development \
  --output evaluation/local/rag018/complement/pool

HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.cache/judges-venv/bin/python -m cahier_rag.judges.campaign \
  --plan evaluation/local/rag018/complement/pool preflight

# Successivement, uniquement les 754 nouveaux couples de cette expérience :
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.cache/judges-venv/bin/python -m cahier_rag.judges.campaign \
  --plan evaluation/local/rag018/complement/pool run \
  --judge qwen3-8b --limit 754
# Même commande avec --judge qwen3-14b.

watch -n 5 'cat evaluation/local/rag018/complement/pool/*-progress.json'
```

Le complément déduplique les couples entre A et B. Un couple déjà présent dans
le plan RAG-017 n'est jamais réannoté, même si sa sortie 14B historique était
invalide. Les origines BM25 et rangs restent dans `pool.json`, hors des messages
des juges. Le cache est physiquement séparé dans `rag018/complement/cache.sqlite3`.
La recette, la grille v2 et les modèles sont strictement identiques à RAG-017.

## Comparaison de pertinence

```bash
.venv/bin/python -m cahier_rag.search.bm25.cli report \
  --experiment evaluation/local/rag018/development \
  --plan evaluation/local/rag018/complement/pool \
  --output evaluation/local/NOUVEAU_RAPPORT
```

Les anciens caches sont ouverts avec `mode=ro`. Les rapports vérifient les
plans, entrées, recettes, sorties brutes valides et empreintes des résultats.
Les références automatiques restent séparées par juge et marquées `llm`.
Les sessions humaines ne sont pas ouvertes par les outils d'expérience.

Les métriques RAG-017 sont réutilisées : précision binaire 2–3, MRR@50 et nDCG
poolée à 5/10/20/50. La référence IDCG est **l'union fixe du pool RAG-017 et du
complément BM25**, pour chaque requête et chaque juge. Elle n'est pas exhaustive
sur les 20 000 documents. Sa modification interdit de comparer directement une
nDCG RAG-018 avec la nDCG publiée avant enrichissement dans RAG-017.

Les macro-moyennes principales prennent les mêmes requêtes entièrement jugées
par les deux modèles, pour tous les moteurs. Les couvertures réelles, métriques
calculables et écarts par requête/domaine sont également exportés. Une sortie
invalide reste non jugée ; aucune réparation et aucun zéro implicite.

## Tests et limites d'échelle

```bash
uv run --locked --no-sync pytest
uv run --locked --no-sync ruff check .
uv lock --check
```

Les intégrations utilisent seulement `RAG_STORAGE_TEST_DATABASE_URL` terminant
par `_test`. Aucune migration, extension ou écriture PostgreSQL n'est requise.
À plusieurs millions d'unités, les postings, GROUP BY et tri peuvent devenir
coûteux ; il faudra mesurer, envisager des identifiants internes compacts et
des algorithmes top-k avec élagage, puis comparer un moteur spécialisé ou un
stockage PostgreSQL. La conservation locale de deux copies JSON et des suites
de lexèmes favorise l'audit, avec un coût disque explicite. Aucun débit à grande
échelle ni déploiement public n'est validé par ce ticket.
