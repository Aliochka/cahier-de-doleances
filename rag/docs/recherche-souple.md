# Recherche lexicale RAG-009

## Isolation de la référence

Les nouvelles méthodes sont dans `search/flexible.py`, `preparation.py`,
`experiments.py` et `flexible_cli.py`. `LexicalEngine` RAG-008, sa configuration,
ses vecteurs et ses exports historiques ne sont pas modifiés. Le mode `strict`
délègue directement à son `search()` sur la requête originale.

Aucune migration, reconstruction d’index ou dépendance supplémentaire : les trois
représentations `answer`, `question`, `title` et le GIN existant sont réutilisés.
Le périmètre reste l’empreinte exacte des 20 000 unités RAG-007. Les contrôles
physiques PostgreSQL, les filtres, les partitions, les BIGINT, les contrats et
la restitution des `TextUnit` d’origine sont conservés. Aucun texte du corpus
n’est envoyé à un service externe.

## Préparation v1

Pour `partial` et `weighted`, la préparation est déterministe :

1. NFC sur la requête, avec conversion des guillemets français en guillemets doubles.
2. Séparation des mots, expressions citées et exclusions `-mot` ou `-"expression"`.
   Les tirets internes aux mots ne sont pas des négations.
3. Suppression facultative d’une liste fermée d’interrogatifs et de consignes,
   uniquement hors guillemets. La liste exacte est enregistrée dans les manifestes.
4. Normalisation française PostgreSQL : lexèmes, flexions et mots vides. Les
   termes sont dédupliqués ; aucun modèle ni dictionnaire téléchargé n’intervient.
5. Les termes non cités sont combinés en OR ; toutes les expressions citées
   sont obligatoires, avec leurs positions de lexèmes. Les exclusions s’appliquent
   ensuite. Dans une requête mixte, les mots supplémentaires servent au classement
   mais ne rendent pas une expression citée facultative.

La liste générique v1 contient notamment `quel/quelle/quels/quelles`,
`comment/pourquoi`, `retrouver`, `contributions`, `citoyens`, `réponses`,
`évoquent`, `mentionnent`, `mentionnant`, `parlent`. La comparaison de cette liste
ignore casse et accents ; les textes documentaires ne sont jamais normalisés
ou réécrits par cette préparation. Les mots de domaine sont conservés.

Un terme générique peut être utile dans une recherche précise : le citer ou
utiliser `--keep-generic`. Les guillemets protègent toujours ces mots de la liste
supplémentaire, sans désactiver les mots vides PostgreSQL. Une expression citée
entièrement composée de mots vides donne zéro résultat, car l’index ne permet
pas de la vérifier. Une requête vide, générique seule, sans lexème ou purement
négative donne une liste vide dans les nouveaux modes ; `strict` conserve le
comportement historique. Les guillemets non équilibrés sont refusés.

Les nouvelles méthodes ne reproduisent pas une grammaire booléenne complète :
les termes sont souples, les phrases citées sont toutes requises. Pour retrouver
exactement les règles OR/AND historiques, utiliser `strict`.
Les requêtes sont bornées à 1 000 caractères, 32 lexèmes positifs, huit expressions
et huit exclusions. Ces plafonds échouent explicitement, sans troncature.

## Scores

`partial` utilise la requête souple puis `ts_rank_cd(...,32)` de RAG-008.
Il peut favoriser un texte répétant un seul terme de la demande.

`weighted` combine trois composantes, avec les coefficients figés :

```text
score = 0,5 × couverture_IDF + 0,3 × couverture_termes + 0,2 × rang_fréquence_proximité
IDF(t) = ln(1 + (N - df(t) + 0,5) / (df(t) + 0,5))
couverture_IDF = somme des IDF des termes retrouvés / somme des IDF de la requête
couverture_termes = nombre de lexèmes distincts retrouvés / nombre de lexèmes positifs
rang_fréquence_proximité = ts_rank_cd(vecteur, requête préparée, 32)
```

N et les df sont calculés dans le même corpus, la même représentation, la même
partition et les mêmes filtres que la recherche. Les statistiques de développement
n’incluent donc pas les documents réservés à l’évaluation. Les termes absents du
corpus restent dans les dénominateurs. Les scores servent à ordonner une requête ;
ils ne sont ni des probabilités ni des mesures comparables entre demandes/méthodes.
Les égalités sont départagées par identifiant documentaire sous collation C.

Les expressions exactes restent des séquences de lexèmes PostgreSQL, pas des
sous-chaînes octet à octet. Les limites RAG-008 de positions et de concaténation
entre champs subsistent. Aucune réponse courte ou « Autre » n’est exclue.

## PostgreSQL et BM25

Les requêtes utilisent uniquement des valeurs liées. Les fragments SQL assemblés
sont des constantes internes ; les lexèmes sont échappés par PostgreSQL avant
construction d’une valeur tsquery liée. La candidate utilise le GIN pour les
correspondances et les df, puis calcule les couvertures sur les candidats.
Les requêtes très larges peuvent néanmoins parcourir une part importante du
petit corpus expérimental. Les délais de cinq secondes et deux secondes de
verrouillage restent actifs. Il n’y a ni cache persistant de statistiques ni
parcours des millions de réponses sources.

**BM25 n’est pas implémenté et le score pondéré n’est pas présenté comme BM25.**
Une implémentation SQL est possible avec fréquences lexicales, longueurs, df et
longueur moyenne par représentation/partition, puis saturation TF et normalisation
de longueur. Les vecteurs actuels ne constituent pas des fréquences complètes :
leurs positions sont plafonnées et les mots vides retirés. Des tables de postings
ou une extension adaptée imposeraient un travail de schéma, migration, validation
et reproductibilité supplémentaire. Sans jugements humains, son gain n’est pas
établi ; le biais de longueur observé justifie de réexaminer cette option après
annotation, plutôt que d’ajouter une approximation sous le nom de BM25.

Références : [analyse et classement PostgreSQL](https://www.postgresql.org/docs/17/textsearch-controls.html),
[limites des vecteurs](https://www.postgresql.org/docs/17/textsearch-limitations.html),
[Robertson et Zaragoza, BM25 and Beyond](https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf).

## Commandes

Depuis `rag/`, avec les paramètres RAG habituels ou un fichier explicitement choisi :

```bash
uv sync --locked
uv run --locked cahier-rag-flex --env-file .env.local search 'Quelles propositions pour réduire la fraude fiscale ?' --method weighted --representation answer
uv run --locked cahier-rag-flex --env-file .env.local search '"services publics"' --method partial
uv run --locked cahier-rag-flex --env-file .env.local search citoyens --keep-generic
uv run --locked cahier-rag-flex --env-file .env.local search TVA --method strict
uv run --locked cahier-rag-flex --env-file .env.local compare --output-directory evaluation/local/NOUVEL_ESSAI/development
```

Le CLI interactif et `compare` sont limités au **développement**. L’API Python
`FlexibleEngine.search()` conserve les filtres `questionnaire_id`, `unit_type`,
`split`, la limite configurable et les mêmes `SearchResult` que RAG-008.
Cinq expériences sont exécutées, sans produit cartésien de paramètres : stricte
réponse, souple réponse, pondérée réponse, pondérée question, pondérée titre.
La préparation est activée pour les méthodes nouvelles ; `--keep-generic` permet
un contrôle manuel explicite, sans nouvelle expérience évaluée automatiquement.

Chaque répertoire contient `results.json` compatible RAG-006 et `report.json` :
configuration, version PostgreSQL, empreintes, temps, nombre de résultats par
requête, contributions distinctes, proportions de courtes et « Autre ».
Ces statistiques décrivent le fonctionnement ; aucun calcul de qualité n’est fait.

Après choix fondé exclusivement sur le développement :

```bash
uv run --locked cahier-rag-flex freeze --experiment-directory evaluation/local/NOUVEL_ESSAI/development/weighted-answer --reason 'Justification issue du développement' --output evaluation/local/NOUVEL_ESSAI/frozen.json
uv run --locked cahier-rag-flex --env-file .env.local evaluate --frozen evaluation/local/NOUVEL_ESSAI/frozen.json --output-directory evaluation/local/NOUVEL_ESSAI/evaluation
```

Le gel est hors connexion et enregistre paramètres, version, raison, date UTC,
empreinte du rapport de développement, corpus/requêtes/index et empreintes des
cinq modules d’implémentation. L’évaluation ne propose aucun réglage : elle exige
le même code et la même configuration, puis crée un marqueur exclusif
`frozen.evaluation-claimed.json` avant son passage sur les vingt requêtes.
Un nouvel appel sur ce gel est refusé, même vers un autre répertoire. Un échec
laisse ce marqueur pour audit, sans relance silencieuse. Les sorties existantes
ne sont jamais écrasées. Pour cette tâche, un seul passage réel a été exécuté.

## Pool humain

```bash
uv run --locked python scripts/prepare_lexical_candidates.py --env-file .env.local --per-query 20 --depth 30 --random-count 2
```

Le script travaille seulement sur les vingt requêtes de développement. Il fusionne
les cinq méthodes sans doublon par paire requête/document, conserve toutes les
méthodes et leurs rangs et alterne les tranches 1–3, 4–10, 11–20, 21–30.
Deux places par requête sont réservées à des témoins pseudo-aléatoires, graine
20261019. Un témoin peut également avoir été trouvé par une méthode : les deux
provenances restent visibles. Le plafond de candidats est configurable, au
maximum cent par requête, avec une profondeur maximale de cent.

Les lignes conservent `document_id`, corpus, contribution, réponse, question,
questionnaire, empreinte, méthodes/rangs et le marqueur aléatoire. Tous les IDs
sources sont des chaînes décimales. Le texte et le contexte se retrouvent par
le stockage existant, sans les recopier dans le pool. Les champs grade, date,
évaluateur et justification restent nuls : aucun jugement n’est inventé.
`runs.json`, `pool.json` et `manifest.json` permettent de reproduire le pooling.

Tous les fichiers réels restent sous `evaluation/local/rag009/`, ignoré par Git.
Les IDs et empreintes ne sont pas une anonymisation. Voir le
[rapport RAG-009](rapport-rag-009.md) pour les résultats et limites observés.
