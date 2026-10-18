# RAG-014 — Recherche hybride avec fusion RRF

## Résultat

La recherche hybride est fonctionnelle sur les **20 000 unités RAG-007**.
Elle combine le lexical pondéré RAG-009, réponse seule, et BGE-M3 RAG-013,
représentation B. Aucun index, schéma, modèle, requête ou artefact historique
n'a été modifié. Les expériences portent exclusivement sur le développement.

Un pool complémentaire final de **400 couples non jugés**, absent du pool
RAG-010, est disponible localement. Aucune session d'annotation n'a été créée.

## 1. Architecture et paramètres

Le package `src/cahier_rag/search/hybrid/` comprend :

| Module | Responsabilité |
|---|---|
| `core.py` | Paramètres, RRF pure, orchestration des moteurs et traces |
| `integrity.py` | Vérification de la configuration et des empreintes gelées RAG-009 |
| `experiments.py` | Comparaison des trois configurations et exports RAG-006 |
| `pooling.py` | Sélection déterministe des candidats complémentaires |
| `cli.py` | Recherche diagnostique, développement et préparation du pool |

Les résultats restent des `SearchResult`, avec le `TextUnit` original et sa
provenance complète. Les diagnostics séparés conservent rangs, scores de chaque
moteur et contributions à la fusion. Les BIGINT restent des entiers Python et
des chaînes dans les résultats JSON.

Paramètres initiaux, fixés avant les essais : **k=60**, profondeur commune
**50 candidats**, sortie **top 10**, contributions des moteurs égales.
La profondeur est configurable entre 1 et 100, conformément au plafond
vectoriel existant ; les paramètres historiques ne sont pas modifiés.

```text
score RRF = somme de 1 / (60 + rang), avec rangs commençant à 1
```

Le calcul utilise des fractions exactes et un départage par identifiant.
Aucune comparaison ou addition des scores lexicaux et cosinus. Un doublon
interne à une liste ne compte qu'une fois, au premier rang ; deux identifiants
distincts avec le même texte restent deux occurrences citoyennes.
Une liste vide est acceptée. Les segments sont agrégés en unités par RAG-013
avant la fusion, avec sa règle du meilleur score conservée.

Les recherches sont séquentielles. BGE-M3 est chargé **une seule fois par
session**, puis utilisé pour les 20 requêtes. Chaque moteur n'est exécuté
qu'une fois par requête ; le classement hybride réutilise ces listes.

## 2. Comparaison réelle sur le développement

Les mêmes 20 requêtes, filtres (développement, tous questionnaires/types),
profondeurs et limites ont été appliqués aux trois configurations.

| Observation au top 10 | Lexical pondéré | Vectoriel BGE-M3 | Hybride RRF |
|---|---:|---:|---:|
| Requêtes avec résultats | 20/20 | 20/20 | 20/20 |
| Couples retournés | 200 | 200 | 200 |
| Contributions distinctes sur l'ensemble des requêtes | 117 | 194 | 172 |
| Contributions par requête, minimum–maximum | 7–10 | 9–10 | 9–10 |
| Réponses de moins de 60 caractères | 0 | 48 | 15 |
| Textes « Autre » | 2 | 6 | 4 |

Les réponses courtes ou « Autre » ne sont pas exclues. Les fréquences de cette
table décrivent des occurrences dans les classements, pas des opinions ni la
représentativité du Grand Débat. Une même unité peut apparaître pour plusieurs
requêtes différentes.

Les top 10 lexicaux sont **identiques aux résultats gelés RAG-009** ; les top 10
vectoriels sont **identiques à ceux de RAG-013**. Deux sessions indépendantes
ont produit les mêmes classements, listes profondes, scores et traces de fusion.
Aucun ajustement de k, de profondeur ou de modèle n'a suivi ces observations.

## 3. Latences et recouvrement

Mesures du premier passage complet sur le PC local, chargements initiaux et
vérifications globales exclus :

| Étape | Médiane | P95 |
|---|---:|---:|
| Recherche lexicale | 174,40 ms | 251,40 ms |
| Recherche vectorielle, encodage compris | 98,75 ms | 103,52 ms |
| Fusion RRF seule | 1,00 ms | 1,14 ms |
| Total, contrôles documentaires compris | 276,33 ms | 352,42 ms |

La validation des résultats est mesurée séparément dans les détails ; le total
l'inclut. Les médianes des étapes ne s'additionnent pas nécessairement.
Le second passage donne une médiane totale de **285,53 ms**, P95 **352,90 ms**,
avec des classements et scores identiques. Les deux passages sont conservés.
Il s'agit de mesures locales séquentielles, sans charge concurrente ni garantie
pour Wallace. P95 utilise le rang supérieur sur 20 observations.

À profondeur 50, cumulés sur les 20 requêtes :

- **181 couples communs** aux deux moteurs.
- **819 couples propres au lexical**, **819 propres au vectoriel**.
- **1 819 couples distincts** dans leur union.
- Intersection par requête : minimum 0, médiane 11, maximum 20.

Dans les 200 résultats hybrides au top 10 :

- **144** sont trouvés par les deux moteurs.
- **29** proviennent uniquement du lexical à cette profondeur.
- **27** proviennent uniquement du vectoriel à cette profondeur.

« Propre à un moteur » signifie absent des 50 premiers de l'autre moteur,
pas absent de l'ensemble de ses correspondances possibles.

La priorité aux candidats communs est structurelle avec ces paramètres :
`2/(60+50) > 1/(60+1)`. Ainsi, même un candidat classé 50e dans les deux listes
passe avant un candidat classé premier dans une seule. Cela explique une partie
des promotions ; **cela ne démontre aucune supériorité de pertinence**.
Aucun Precision, Recall, MRR ou nDCG n'a été calculé.

## 4. Nouveau pool d'annotation

Le pool à utiliser est :

```text
rag/evaluation/local/rag014/candidates-final/pool.json
rag/evaluation/local/rag014/candidates-final/manifest.json
```

Il contient :

| Indicateur | Valeur |
|---|---:|
| Couples requête–document | 400 |
| Requêtes / candidats par requête | 20 / 20 |
| Documents distincts | 378 |
| Contributions distinctes globales | 353 |
| Contributions distinctes par requête | 20 |
| Couples communs aux moteurs | 119 |
| Couples propres au lexical | 142 |
| Couples propres au vectoriel | 139 |
| Couples déjà proposés dans RAG-010 | 0 |
| Déficit de candidats | 0 |

La sélection utilise la graine **20261021**. Elle privilégie les nouveaux
couples, puis les contributions encore absentes et une rotation entre origines,
méthodes et tranches de classement. Elle couvre les rangs 1–10, 11–25 et 26+.
Respectivement 189, 272 et 261 candidats possèdent au moins une origine dans
ces tranches ; **ces comptes se chevauchent entre moteurs**.

Les notes, commentaires, évaluateurs et dates de jugement restent `null`.
Les méthodes/rangs/scores sont conservés dans `found_by`, pour analyse future,
et devront être masqués lors de l'annotation. Le marqueur `already_in_rag010`
compare les couples avec le fichier source non annoté RAG-009, sans lire la
session ni les jugements. Il ne prétend pas connaître l'avancement des notes.

Empreinte du pool final :

```text
5c5642b56cd37363cbef39cfe43fa2b7bcc6a4d8af9b9b0b0ce73c7d5adece0c
```

Le pool a été reconstruit avec la même graine et comparé à l'identique.
Un premier pool exploratoire est conservé sous `candidates/` ; il n'est pas
celui à utiliser. La sélection finale privilégie globalement les contributions
encore disponibles, plutôt que seulement à l'intérieur de chaque catégorie,
ce qui assure ici 20 contributions différentes pour chaque requête.
Aucun de ces pools ne possède de session d'annotation.

## 5. Commandes et artefacts

Voir [l'utilisation détaillée](recherche-hybride.md). Depuis `rag/`, variables
RAG source et destination définies explicitement :

```bash
.cache/embeddings-venv/bin/python -m cahier_rag.search.hybrid.cli \
  --depth 50 --k 60 --limit 10 search 'Comment améliorer les services publics ?'

.cache/embeddings-venv/bin/python -m cahier_rag.search.hybrid.cli \
  --depth 50 --k 60 --limit 10 development \
  --output evaluation/local/rag014/nouvel-essai

.venv/bin/python -m cahier_rag.search.hybrid.cli pool \
  --experiment evaluation/local/rag014/development-replay \
  --output evaluation/local/rag014/nouveau-pool --per-query 20 --seed 20261021
```

Le point d'entrée installé est `cahier-rag-hybrid`. La génération du pool
fonctionne dans l'environnement sans torch, sans GPU et sans connexion SQL.
Les dossiers de sortie doivent être inexistants.

Les exports compatibles RAG-006 se trouvent sous `development/` et
`development-replay/` : `lexical-rankings.json`, `vector-rankings.json`,
`hybrid-rankings.json`. Chaque fichier est un dictionnaire de requêtes vers les
identifiants ordonnés. Les listes profondes, traces, métadonnées et rapports
sont conservés à côté. Les rapports référencent les configurations gelées,
l'espace vectoriel, leurs empreintes, les paramètres et l'implémentation.
`statistics.json` décrit le pool final et les contrôles de reproduction.
Tous ces artefacts locaux sont ignorés par Git ; ils ne sont pas des jugements.

## 6. Tests et préservation

- **381 tests réussis, 3 ignorés** dans l'environnement courant sans torch.
- Les 3 tests optionnels de pooling tensoriel sont validés séparément dans
  l'environnement embeddings : **3 réussis**.
- **18 tests unitaires nouveaux** couvrent RRF, égalités, dédoublonnage,
  invariance aux échelles de scores, résultats vides, limites, filtres,
  partitions, BIGINT, corruption de manifestes, exports, sélection/reproduction
  du pool et absence d'accès aux sessions/jugements.
- **1 intégration PostgreSQL nouvelle** combine les deux vrais moteurs avec
  encodeur synthétique : recherche, provenance, filtres, égalités, reproduction
  et cas lexical vide. Aucun modèle ni texte réel n'est nécessaire à ce test.
- Ruff, `uv lock --check --offline` et `git diff --check` conformes.

Le contrôle intégral de l'index vectoriel réel retrouve son empreinte RAG-013 :

```text
6481f5b998e0e26856a8a495e657daf6616c128d3cb4734a8d1b832ed3a4a812
```

Les modifications sont limitées au nouveau package, ses tests, au point d'entrée
`rag/pyproject.toml` et à la documentation RAG. Aucune dépendance n'est ajoutée ;
le verrou reste inchangé. Aucun module historique, index ou manifeste gelé
n'est modifié. Aucun fichier de session ou jugement RAG-010 n'est consulté.
Aucune écriture sur le corpus source, aucune intervention sur Wallace,
aucun commit ni push.
L'avertissement Starlette/httpx préexistant demeure dans les tests d'annotation.

## 7. Limites et prochaine campagne

La couverture de 20/20 et le recouvrement sont descriptifs : le vectoriel peut
retourner des voisins peu pertinents pour toute requête non vide. Les candidats
communs sont favorisés par construction et peuvent partager des erreurs.
Le pool complémentaire est volontaire, pas statistiquement représentatif.
Le faible nombre de requêtes et la profondeur de 50 limitent les conclusions.
La fusion ne préserve pas comme contrainte globale les expressions imposées
par la branche lexicale : la branche vectorielle peut proposer d'autres textes.

Pour la prochaine campagne, utiliser le pool final à l'aveugle, avec exactement
les requêtes actuelles et les notes 0–3 existantes. Conserver les méthodes dans
les fichiers d'analyse, mais les masquer à l'évaluateur. Ne pas importer ce pool
dans la session RAG-010 en cours ; préparer une session complémentaire explicite.
Les jugements devront porter sur les couples requête–document : réutiliser un
document pour une autre requête ne rend pas son jugement interchangeable.
Comparer ensuite les trois classements sur les couples jugés en signalant les
zones non jugées ; aucun candidat non jugé ne doit devenir implicitement une
preuve de non-pertinence. Une éventuelle étude de k/profondeur devra rester
sur le développement. Les requêtes réservées n'ont pas été exécutées ici.
