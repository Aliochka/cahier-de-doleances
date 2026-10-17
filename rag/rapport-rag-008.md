# RAG-008 — Baseline lexicale locale

## Résultat

Un moteur lexical PostgreSQL français est opérationnel sur **exactement les
20 000 unités RAG-007**. Trois variantes figées ont été indexées ; les 40 requêtes
ont été exécutées pour chacune, en séparant les partitions : **120 classements**,
exportés et reproduits automatiquement à l’identique. Aucun jugement humain ou
score de qualité n’a été créé.

Le manifeste reste `rag/evaluation/local/rag007/corpus.json`, d’empreinte
`d0173a371df7fc5d6b5d8ca393ea3f230349140b1cfb92a1ec4a2280200033cc`.
L’index contient 20 000 membres et 60 000 vecteurs, pas les 42 318 unités du cadre.
Les 40 requêtes, les partitions et les documents originaux sont inchangés.

**Limite observée importante : les vingt requêtes d’évaluation renvoient des
classements vides avec les trois variantes figées.** Les requêtes naturelles
longues sont très restrictives avec la combinaison AND de `websearch_to_tsquery`.
Les recherches courtes par mots-clés et expressions fonctionnent sur les données
réelles. Ce constat de couverture lexicale ne constitue pas une mesure de rappel
ou de pertinence. Aucun paramètre n’a été ajusté après export de l’évaluation.

## Architecture et stratégies

- `search/lexical.py` : périmètre immuable, reconstruction, validation et recherche.
- `search/evaluation.py` : exécution des requêtes par partition, classements,
  temps et candidats non jugés.
- `search/cli.py` : commande `cahier-rag-search` sans serveur HTTP.
- `schema.py` et migration Alembic `rag_0002_lexical.py` : stockage dérivé.
- Tests autonomes unitaires et PostgreSQL ; imports backend/GPU interdits.

La configuration `pg_catalog.french` est explicite. Les expressions entre
guillemets et les termes sont analysés par `websearch_to_tsquery`. Le score est
`ts_rank_cd(...,32)` ; les égalités sont départagées par ID documentaire sous
collation C. Aucun seuil de longueur ni exclusion des « Autre » n’est ajouté.
Les champs d’origine restent séparés dans `text_units`.

| Stratégie | Champs et poids |
|---|---|
| `answer` | Réponse A = 1,0 |
| `question` | Réponse A = 1,0 ; question B = 0,4 |
| `title` | Réponse A = 1,0 ; question B = 0,4 ; titre C = 0,2 |

Les variantes et paramètres sont figés dans
`evaluation/local/rag008/frozen-configuration.json`, avant les exports d’évaluation.
La configuration, sa version, le serveur PostgreSQL, le corpus, les requêtes,
les classements, la limite et la partition sont tracés dans les rapports locaux.
Le moteur est entièrement indépendant de la génération LLM.

## Schéma et sécurité

La migration RAG indépendante **rag_0002**, suivant rag_0001, crée :

| Table | Fonction |
|---|---|
| `rag.lexical_corpora` | Empreinte, taille, configuration et date de reconstruction |
| `rag.lexical_members` | Liste exacte, empreintes de contenu et partitions |
| `rag.lexical_vectors` | TSVECTOR par corpus/stratégie/document |

Un GIN sur `search_vector` complète les clés B-tree. Les clés étrangères relient
les vecteurs à leurs membres, puis aux unités originales. La reconstruction
utilise uniquement les IDs du manifeste et vérifie leurs empreintes/provenance.
Elle est transactionnelle, par lots de cent, avec verrou par corpus ; un échec
conserve l’ancien index. Les lectures vérifient version, effectifs, appartenance
et empreintes des résultats. `verify` compare tous les membres au manifeste.
Le corpus ne peut pas être remplacé implicitement par un autre fichier de même taille.

Les délais sont bornés à cinq secondes par requête cible et deux secondes
d’attente de verrou. Les contrôles physiques source/destination sont conservés.
Les recherches lisent les textes dans la base RAG ; la source n’est sollicitée
que pour les contrôles d’identité. Aucun schéma ni contenu source n’est modifié.
Les identifiants restent BIGINT/int ; le JSON documentaire les rend en chaînes.

La migration a été appliquée à `cahier_rag_test` et `cahier_rag`. Aucune migration
backend, extension, dépendance ou infrastructure supplémentaire n’est introduite.
La construction des 60 000 vecteurs a pris **3,93 secondes**. Le GIN occupe environ
**8 Mo** et le total de `lexical_vectors`, index compris, environ **50 Mo**.

## Exports et candidats

Chaque variante dispose de deux répertoires :

```text
evaluation/local/rag008/
├── answer/development/     results.json, candidates.json, report.json
├── answer/evaluation/      results.json, candidates.json, report.json
├── question/development/   results.json, candidates.json, report.json
├── question/evaluation/    results.json, candidates.json, report.json
├── title/development/      results.json, candidates.json, report.json
├── title/evaluation/       results.json, candidates.json, report.json
├── frozen-configuration.json
├── random-candidates.json
├── build.json
├── measurements.json
└── summary.json
```

`results.json` est directement compatible avec RAG-006 : objet query_id → liste
ordonnée de document_id. Chaque fichier contient exactement les vingt requêtes
de sa partition, y compris celles sans résultat. Le filtre documentaire applique
la même partition ; les 17 612 documents de développement et les 2 388 d’évaluation
ne sont jamais mélangés pendant l’exécution du jeu de requêtes.

Les candidats lexicaux ont des notes nulles : huit paires pour `answer` en
développement, neuf pour chacune des deux autres variantes. Aucun candidat
lexical n’est retourné par l’évaluation. Deux cents candidats aléatoires distincts
des classements ont également été préparés par RAG-006, cinq par requête,
en respectant les partitions. Ils peuvent servir à une annotation humaine ;
ils ne sont pas présentés comme des résultats du moteur. Aucune note n’est inventée.
Tous ces fichiers locaux sont ignorés par Git et aucun corps documentaire
n’est reproduit ici.

## Temps observés

Les latences Python incluent contrôles des bases, vérification d’état,
requête SQL et restauration des résultats. Le chargement initial du manifeste
et la validation complète avant une suite ne sont pas inclus par requête.
Mesures sur PostgreSQL local, avec cache et machine disponibles lors du test :

| Stratégie | Partition | Requêtes | Médiane | P95 | Maximum |
|---|---|---:|---:|---:|---:|
| Réponse | Développement | 20 | 13,60 ms | 17,38 ms | 22,73 ms |
| Réponse + question | Développement | 20 | 14,20 ms | 19,36 ms | 22,35 ms |
| Réponse + question + titre | Développement | 20 | 15,24 ms | 19,63 ms | 24,30 ms |
| Réponse | Évaluation | 20 | 6,21 ms | 7,76 ms | 10,41 ms |
| Réponse + question | Évaluation | 20 | 6,30 ms | 8,13 ms | 10,60 ms |
| Réponse + question + titre | Évaluation | 20 | 6,30 ms | 7,16 ms | 10,37 ms |

Les requêtes vides de résultats en évaluation peuvent être plus rapides ; ces
durées ne permettent pas de comparer la qualité des variantes. Les quantiles
locaux utilisent le rang inférieur. Il ne s’agit pas d’un benchmark de charge.

Quelques recherches manuelles limitées à la partition de développement,
cinq répétitions, dix résultats maximum, réponse seule :

| Requête | Médiane Python | Maximum |
|---|---:|---:|
| TVA | 11,21 ms | 30,29 ms |
| taxe carbone | 7,24 ms | 8,53 ms |
| "services publics" | 12,42 ms | 14,63 ms |
| école | 10,88 ms | 12,85 ms |

Ces quatre sondes ont chacune retourné dix documents au maximum demandé,
sans afficher leurs textes ni les juger. Les accents, apostrophes et expressions
sont en outre vérifiés sur des données synthétiques contrôlées.

### Justification du GIN

Après ANALYZE des seules tables lexicales RAG, comparaison de cinq exécutions
SQL avec le planificateur normal et avec parcours séquentiel forcé localement
(désactivation transactionnelle des scans index/bitmap, sans supprimer l’index) :

| Sonde | Médiane SQL avec plan normal | Médiane SQL séquentielle |
|---|---:|---:|
| carbone | 0,128 ms | 14,184 ms |
| ISF | 0,100 ms | 13,970 ms |
| "services publics" | 1,815 ms | 13,622 ms |

Les plans et buffers sont conservés dans `measurements.json`. Cette comparaison
porte sur la sélection/classement dans la table dérivée, sans les jointures et
contrôles de l’interface complète. Elle justifie le GIN pour ces sondes, pas un
gain universel ni une extrapolation aux cinq millions de réponses.

## Validations

- **233 tests réussis**, dont **45 intégrations PostgreSQL** et 188 tests unitaires.
- Recherche synthétique : pertinence lexicale attendue, accents, apostrophes,
  guillemets, réponses courtes, « Autre », filtres, limites et égalités de scores.
- Contexte et titre, BIGINT supérieurs à 2^53, provenance et texte d’origine.
- Document stocké hors manifeste exclu ; manifeste altéré ou non RAG-007 refusé.
- Reconstruction reproductible, rollback conservant l’index précédent, refus
  d’un index incomplet et de versions incompatibles.
- Exports compatibles avec les outils de métriques sur jugements synthétiques ;
  aucun jugement réel généré. La CLI protège l’évaluation par défaut.
- Correspondance exacte des 20 000 membres au manifeste réel ; trois fois
  20 000 vecteurs, références et empreintes vérifiées.
- Les 120 classements réexécutés automatiquement sont identiques ; les documents
  de l’évaluation n’ont pas été consultés pour régler les paramètres.
- Ruff, formatage, `uv lock --check`, `git diff --check` conformes.
- Les 40 requêtes et les manifestes RAG-007 conservent leurs empreintes.

## Commandes et limites

Consulter [l’interface et les commandes](recherche-lexicale.md). Depuis `rag/` :

```bash
uv sync --locked
uv run --locked cahier-rag schema-upgrade --env-file .env.local
uv run --locked cahier-rag-search --env-file .env.local rebuild
uv run --locked cahier-rag-search --env-file .env.local verify
uv run --locked cahier-rag-search --env-file .env.local search '"services publics"' --strategy answer
uv run --locked cahier-rag-search --env-file .env.local evaluate --strategy answer --split development --output-directory evaluation/local/NOUVEL_ESSAI/answer/development
```

La baseline utilise AND sur les termes significatifs des longues demandes en
langage naturel, sans retirer les formulations de consigne, reformuler ni
reconnaître les synonymes. Une future variante devra être conçue et réglée sur
le développement avant une nouvelle évaluation gelée. Les présents résultats
vides restent conservés. Un score de qualité reste impossible sans annotation.

La contextualisation peut privilégier des mots de la question ou d’un titre
sans rendre la réponse utile. Les expressions sont des séquences de lexèmes,
avec les limites de concaténation des champs et de positions PostgreSQL.
La baseline n’est pas BM25 et ne remplace pas les futurs essais sémantiques.
Le corpus reste non représentatif et les doublons peuvent réduire la diversité
des résultats ; aucune déduplication des occurrences n’est appliquée.

Aucun backend, frontend, Wallace, modèle, GPU, LLM, schéma source, dépendance
Python ou fichier de déploiement n’a été modifié. Les adaptations sont limitées
à `rag/`. Aucun commit ni push effectué.
