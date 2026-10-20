# RAG-027 — Optimisation et validation du corpus complet

État au 20 octobre 2026 : **lexical accéléré sans changement observé de classement ;
parcours personnel complet validé ; ANN et filtres conservent des limites importantes**.
Aucun embedding documentaire recalculé, aucun index existant reconstruit, aucune
intervention sur Wallace. Les générations et jugements historiques sont conservés.

## 1. Référence et méthode

Corpus RAG-026 : **5 172 356 unités, 5 187 190 segments**, BGE-M3 dense 1024,
représentation B et cosinus inchangés. H1 conserve RRF `k=60`, profondeur 50.
La référence reste `FullSearch` ; le nouveau profil est explicitement `rag027`.

Jeu versionné : `evaluation/performance-rag027.json`, **32 questions** : 20 de
développement et 12 exploratoires couvrant formulations naturelles, termes fréquents,
expressions rares, apostrophes et réponses monosyllabiques. Aucune requête réservée
exécutée. Les filtres `historical_split` testent des **documents**, pas le jeu réservé
de questions.

Mesures lexicales : trois passages par requête/configuration. Le passage initial
de référence inclut parfois un EXPLAIN supplémentaire : il est exclu des agrégats
chauds. Aucun vidage de caches système ; **pas de véritable mesure à froid**.
Les P95 ci-dessous sont empiriques sur des exécutions répétées et corrélées, sans
charge concurrente représentative. Les essais navigateur et diagnostics filtrés
sont séparés des tableaux de référence ; les premières observations peuvent subir
des effets de cache et d'autres travaux locaux.

Artefacts locaux : `evaluation/local/rag027/`. Les textes consultés restent dans
ce répertoire ignoré par Git. Le rapport général fournit des références, pas leurs
textes citoyens.

## 2. Diagnostic lexical vérifié

Les plans `baseline/plan-*.json` révèlent deux coûts dominants :

- Les fréquences documentaires sont recalculées par terme à chaque recherche,
  avec des Bitmap Index/Heap Scans utilisant effectivement GIN.
- Le score corrélé exécute un agrégat et un parcours de la petite table des termes
  **pour chaque document candidat**. Sur `fiscalite-01` : 2 853 649 candidats et
  autant d'exécutions de l'agrégat, sept termes. Une grande union de termes conduit
  raisonnablement PostgreSQL à préférer un parcours séquentiel pour les candidats.

Le tri top-N n'est pas le problème principal. Les statistiques automatiques des
tables étaient présentes ; aucun ANALYZE ni réglage global PostgreSQL n'a été
imposé. Les temps inclusifs d'un plan ne doivent pas être additionnés entre parents
et enfants.

Correction équivalente : matérialiser les DF exactes des `tsvector` immuables et
remplacer le sous-plan corrélé par des expressions CASE explicites. Même formule,
mêmes poids, même normalisation française, même ordre des termes et même départage.
Avec filtre, les statistiques sont calculées sur la population filtrée pour
préserver la formule. Aucun préfiltrage approximatif dans le profil retenu.

La migration RAG **`rag_0007`** ajoute uniquement `rag_tuning.statistics` et
`rag_tuning.term_statistics` : **314 656 lexèmes, environ 36,1 Mo** supplémentaires,
index B-tree compris. Construction idempotente, transactionnelle et gardée par
identité réelle des bases ; refus de manifeste incompatible. Aucun nouvel index
sur les tables documentaires ou vectorielles historiques.

| Variante | Médiane chaude | P95 empirique | Échecs chauds |
|---|---:|---:|---:|
| RAG-026 historique | 9,02 s | 26,70 s | 2/64 |
| Expressions + DF exactes | **1,87 s** | **5,15 s** | **0/64** |
| Préfiltrage expérimental 1 000 | 1,66 s | 4,40 s | 0/64 |

Les **93 comparaisons abouties** avec la référence retrouvent exactement les IDs,
l'ordre et les scores. La trente-deuxième question dépassait 30 s dans les trois
passages historiques ; son équivalence réelle n'a donc pas été mesurée. La nouvelle
recette la traite en environ 7,9 s. L'équivalence algébrique est également testée
sur corpus synthétique et filtres.

Le préfiltrage modifie les classements sur **10 des 31 questions comparables** :
gain trop limité pour le retenir. Il reste explicitement diagnostique.

EXPLAIN optimisé : `fiscalite-01`, 26,79 → 4,51 s ; question naturelle
`explore027-08`, 20,98 → 3,59 s. Les sous-plans par document disparaissent ; le
classement peut être parallélisé avec deux workers. Une expression rare passe
à 4,4 ms dans ce diagnostic chaud. Ces observations isolées ne sont pas des SLA.

Limite structurelle restante : pour une union très fréquente, plusieurs millions
de candidats doivent encore être évalués exactement. PostgreSQL n'est pas démontré
inadapté ; une latence systématiquement inférieure à 100 ms n'est pas acquise avec
cette formule. Une réduction des candidats changerait la recherche et demanderait
une expérience de pertinence distincte, pas un simple réglage technique.

## 3. ANN : résultats et limites

Index conservé : HNSW `m=16`, `ef_construction=64`, pgvector 0.8.7. Huit profils
figés avant mesure, trois répétitions sur 32 questions, exact top 100 conservé.
Les traces contiennent IDs de segments/unités, positions et distances.

| Profil | ef | Candidats | Médiane / P95 | Recouvrement ID top 10 / top 50 |
|---|---:|---:|---:|---:|
| Référence | 400 | 400 | 18,4 / 47,4 ms | 82,5 % / 82,6 % |
| ef800 | 800 | 400 | 21,4 / 36,1 ms | 85,3 % / 85,8 % |
| **ef1000** | **1000** | **400** | **23,5 / 59,4 ms** | **91,9 % / 91,8 %** |
| wide400 | 400 | 800 | 39,3 / 72,4 ms | 82,5 % / 82,6 % |
| wide800 | 800 | 800 | 27,1 / 60,2 ms | 85,3 % / 85,8 % |
| deep1600 | 1000 | 1600 | 92,5 / 113,6 ms | 91,9 % / 91,8 % |
| deep3200 | 1000 | 3200 | 173,8 / 224,5 ms | 91,9 % / 91,8 % |
| off1000 | 1000 | 400 | 25,5 / 64,0 ms | 91,9 % / 91,8 % |

`strict_order` et plafond 20 000 tuples, multiplicateur mémoire 1 par défaut.
Les profils deep utilisent 100 000 tuples et multiplicateurs 2/4 ; off désactive
le parcours itératif. Aucun bénéfice de couverture observé au-delà d'ef1000 dans
ces essais. Cela ne prouve pas une équivalence générale entre ces paramètres.

**Aucun profil ne satisfait les seuils figés dans `selection-policy.json`**, y compris
la variante tenant compte du contexte et des distances. Le manifeste de sélection
conserve donc **`qualified: false`**, sans affaiblir les seuils après observation.
`ef1000` est retenu uniquement comme compromis interactif mesuré, avec exact toujours
accessible ; ce n'est pas une validation de rappel suffisant dans tous les cas.

Les doublons n'expliquent pas tous les écarts : avec ef1000, recouvrement contextualisé
top 10 moyen 92,5 %, contre 91,9 % pour les IDs. La question exploratoire « non »
a un recouvrement textuel de 100 % mais **contextuel de 0 %** : mêmes réponses très
courtes, autres questions et provenances ; regret de distance moyen d'environ 0,090.
Ce cas ne doit pas être déclaré inoffensif. Fraude fiscale, patrimoine et expression
rare présentent aussi des omissions réelles de candidats, pas seulement des ex æquo.

Le regroupement reste au niveau de l'unité, avec meilleur segment et départage stable.
Les 32 reprises ANN à profondeur 50 reproduisent exactement le préfixe des classements
à 100 enregistrés. Les segments multiples, distances et départages sont traçables ;
une stabilité d'exécution n'est pas une preuve de fidélité à l'exact.

## 4. Filtres : obstacle confirmé

Sept diagnostics réels couvrent questionnaires 4/5/7/10, type « Autre » et deux
partitions documentaires. Aucun document retourné ne sort du filtre.

Cependant, HNSW peut épuiser son budget après postfiltrage : **5 résultats au lieu
de 50** sur un questionnaire, et **10 au lieu de 50** sur une partition documentaire.
Augmenter uniquement la limite demandée n'est donc pas une garantie de complétude.

L'API `tuning.retrieval.search_vector` adopte un parcours **exact avec filtres**,
distinct du diagnostic ANN bas niveau. Le tri `distance + 0.0` empêche un parcours
HNSW de se substituer à l'exact et laisse les index relationnels disponibles.
Résultats mesurés : partitions documentaires en 0,70 et 0,55 s ; questionnaire 7
en 27,29 s, avec IDs/scores identiques à l'exact historique. Questionnaires 4/5/10
et type « Autre » expirent encore à 30 s. L'historique expirait dans six des sept
cas. Une expiration reste une erreur explicite, sans classement réparé ni partiel
présenté comme exhaustif.

**Les filtres larges ne sont donc pas déclarés optimisés.** Il faudra étudier un
accès filtré aux vecteurs plus adapté avant une interface de recherche filtrée
intensive. Aucun partitionnement ou index coûteux supplémentaire créé ici.

## 5. H1 et inspection ciblée

Fusion mesurée sur listes précalculées : environ **0,23 ms**. Les estimations
séquentielles suivantes additionnent les mesures des composants ; elles n'incluent
ni chargement du modèle ni encodage de la question et ne constituent pas un nouveau
benchmark complet :

| Recherche | Médiane estimée | Requêtes disponibles |
|---|---:|---:|
| H1 historique | 9,03 s | 31 |
| H1 lexical équivalent + ef1000 | **1,89 s** | 32 |
| Lexical équivalent + vectoriel exact | 7,47 s | 32 |

Un complément réellement exécuté, séquentiel, à profondeur 50, utilise les vecteurs
de requêtes déjà encodés (encodage mesuré séparément). Une seule observation par
cas/configuration, donc **aucun P95 déduit de ces trois cas** :

| Requête | H1 historique | H1 optimisé | Lexical optimisé + exact |
|---|---:|---:|---:|
| fiscalite-03 | 11,80 s | 2,06 s | 8,39 s |
| democratie-01 | 5,53 s | 1,21 s | 7,43 s |
| expression rare explore027-05 | 0,63 s | 0,031 s | 5,69 s |

Les détails sont dans `hybrid-live.json`. Pic RSS de ce **seul client SQL Python** :
67,35 Mo ; ce chiffre n'inclut ni les backends PostgreSQL ni les modèles GPU.

Le recouvrement des hybrides avec H1 exact passe de 90,0 % à 95,3 % au top 10,
et de 91,6 % à 96,3 % au top 50, moyennes sur les ensembles disponibles ci-dessus.
Ce sont des correspondances de classements, **pas des scores de pertinence**.
Les JSON donnent résultats par requête, recouvrement lexical/vectoriel, contributions
distinctes, répétitions, réponses courtes et « Autre ». Les ensembles parfois peu
communs aux moteurs rendent utile leur complémentarité, sans prouver la supériorité
sémantique de la fusion.

Lecture assistée ciblée des premières positions sur trois questions, sources dans
`qualitative-retrieval-sources.json` :

- Fraude : le lexical place un très long texte multithématique
  (`open_answer:5267543:0`) ; vectoriel/hybride placent une proposition courte ciblée
  (`open_answer:3814110:0`). La longueur ou le nombre de mots correspondants ne
  suffit pas à conclure à une meilleure réponse.
- Représentation politique : une réponse courte retrouve directement l'intention
  (`open_answer:2187143:0`), tandis que le lexical remonte une longue contribution
  (`open_answer:3408895:0`). Les deux restent consultables avec leur question.
- Obstacles à la réduction énergétique : le premier résultat vectoriel/hybride
  (`open_answer:6179754:0`) énonce un objectif de réduction, sans identifier un
  obstacle dans son texte et sa question d'origine. **Confusion d'intention encore
  possible**, même avec proximité thématique.

Préfixe complet des références : `text-unit:v1:gdn-2019:`. Aucune nouvelle campagne
LLM ni réutilisation automatique des anciens jugements sur ces nouveaux documents.
Cette lecture n'est pas une évaluation humaine indépendante ni exhaustive.

## 6. Parcours personnel réellement testé

Chromium local, question libre nouvelle sur l'accueil humain dans les petites
communes. Corpus complet → H1 optimisé → Qwen3-Reranker-4B → S2/P1 →
Qwen3-14B **generation-fr-v6-personal inchangée** : **succès**, six blocs valides,
20 sources affichées, six références utilisées, liens ouvrant les passages,
BIGINT sérialisés en chaînes et correspondances vérifiées. Aucun extrait incomplet
dans cette réponse ; leur signalement est couvert par les tests existants, pas
par ce cas réel. Aucune erreur JavaScript.

| Étape | Temps mesuré |
|---|---:|
| Chargement BGE-M3 | 4,92 s |
| Encodage question | 0,081 s |
| Lexical | 6,05 s |
| Vectoriel ANN | 0,066 s |
| Fusion | 0,0005 s |
| Reranking total | 46,82 s |
| dont chargement / appels de scoring | 4,52 / 31,70 s |
| Assemblage | 0,25 s |
| Génération, chargement et validation compris | 41,25 s |
| dont chargement / génération GPU | 16,82 / 10,31 s |
| **Parcours total** | **99,70 s** |

La différence entre totaux et sous-mesures inclut notamment tokenisation,
vérifications des modèles, préparation et validation ; les postes inclusifs ne
s'additionnent pas tous. Pic VRAM allouée rapporté par l'étape générative :
**14,02 Go décimaux**. Aucun pic RAM fiable de bout en bout collecté pour ce ticket ;
ne pas reprendre le RSS de l'indexation RAG-026 comme mesure de cette interface.

Le même parcours avec le lexical historique avait échoué sur son délai SQL,
avant génération. Le navigateur a aussi vérifié le retour explicite à RAG-007,
sans produire de nouveaux artefacts dans l'expérience historique.

Correction technique nécessaire : le cache personnel refusait auparavant tout
répertoire sans composant `rag025`. Son namespace devient explicite, testé et isolé ;
les nouvelles requêtes du corpus complet sont écrites sous RAG-027. Aucun changement
de prompt, modèle, réglage d'inférence ou algorithme de reranking.

Lecture des six attributions générées : les propositions principales sont soutenues,
mais deux résumés omettent des conditions utiles (`S02`, `S06`) ; les deux limites
rédigées restent des raisonnements génériques non explicitement attribués.
Détails et sources exactes dans `qualitative-e2e.json`. **Validation des citations
ne signifie pas fidélité sémantique complète**. Le générateur n'est pas modifié ici.

## 7. Intégrité, tests et exploitation

État du manifeste, nombres de lignes et définitions des index d'origine contrôlés.
**2 331 fichiers historiques surveillés : aucun changement**. Pas de nouvelle
vérification intégrale octet par octet des 5,18 millions de vecteurs : aucun vecteur
n'a été écrit dans ce ticket. Les tables principales occupent toujours environ
11,15 Go (documents) et 70,55 Go (segments et index), plus les statistiques lexicales.

**596 tests réussis, 3 ignorés** (torch optionnel absent de `.venv`), avec
intégrations sur bases de test isolées ; Ruff et
`uv lock --check` exécutés. Les résultats finaux sont conservés dans
`tests-final.log`. Les tests couvrent équivalence, filtres, BIGINT, cache, reprise,
paramètres ANN, distinction texte/contexte, RRF et identité du corpus sélectionné.
Les tests GPU facultatifs sans torch dans `.venv` sont signalés comme ignorés ;
le parcours réel GPU est vérifié séparément dans l'environnement lourd existant.

Code ajouté : `tuning/{lexical,statistics,vector,retrieval,experiments,selection,report,cli}.py`,
migration `rag_0007`, jeu de requêtes et tests. Adaptations limitées de l'interface
personnelle : sélection du profil, chronométrage, cache isolé, erreur avec phase et
type sans secret. Aucune dépendance ajoutée ; `uv.lock` inchangé.

Commandes de lancement, exact, retour historique, reprise et rapports :
[optimisation-recherche.md](optimisation-recherche.md). Artefacts principaux :
`baseline/manifest.json`, `lexical.json`, `vector.json`, `comparison.json`,
`selection.json`, plans EXPLAIN, `filters.json`, `filtered-exact.json`,
`browser-optimized.json`, `e2e-optimized.json`, `integrity.json`.

## 8. Configuration recommandée et suite

Pour l'exploration locale : lexical équivalent + ef1000/400 candidats, RRF 60,
profondeur 50, **ANN explicitement approximatif**. Pour contrôler des voisins ou
une question sensible aux changements de contexte : vectoriel exact. Aucun profil
ANN n'est homologué selon tous les seuils préfixés ; conserver cette réserve.

Priorités restantes : filtres vectoriels larges, rappel ANN sur requêtes très
courtes, intentions « obstacles » vs « propositions », puis coût du reranking et
du chargement successif des modèles. Les limites génériques de génération et les
conditions perdues relèvent d'un travail documentaire ultérieur.

Pour Wallace, aucune architecture définitive : recherche SQL et RRF sont CPU ;
les embeddings peuvent être préparés hors ligne sur le PC. Les usages GPU mesurés
concernent encodage, reranking et génération ; aucun coût CPU serveur n'est déduit
du PC. Prévoir les quelque 82 Go de tables/index, espace temporaire et maintenance,
puis mesurer sur son matériel réel. Les données peuvent être exportées logiquement ;
les index doivent être restaurés/reconstruits selon la compatibilité PostgreSQL et
pgvector, sans supposer qu'une copie brute des fichiers d'index est transférable.
Les latences séquentielles mesurées ne valident aucune capacité concurrente.
Aucun accès à Wallace, déploiement, commit ou push effectué.
