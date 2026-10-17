# Compte rendu RAG-006 — 17 octobre 2026

## Résultat et périmètre

Le protocole local d’échantillonnage et d’évaluation est disponible sans moteur,
modèle ni nouvelle dépendance. Il réutilise les unités et extractions RAG-005.
Le [protocole technique](evaluation.md) décrit les formats, commandes, garanties
et limites. Les [40 requêtes initiales](evaluation/queries.json) sont versionnables.
Aucun jugement réel n’a été produit et aucun score de performance réel n’est annoncé.

Divergences documentaires constatées : l’en-tête historique de
`docs/plan-rag.md` indique encore « développement non commencé », alors que le
code et les rapports RAG-003 à RAG-005 attestent les composants déjà réalisés.
Le lecteur et le stockage sont la référence opérationnelle. RAG-005 fournit des
extractions limitées, pas un échantillonnage probabiliste global : cette tâche
ne présente donc pas son tirage comme uniforme sur tout le corpus.

## Méthodes et architecture

- `evaluation/sampling.py` : sélection pseudo-aléatoire par SHA256(graine, ID),
  sélection stratifiée par quotas minimaux, statistiques, manifestes et groupes
  anti-fuite. Cadre explicite d’extractions terminées, limité à 100 000 unités.
- `evaluation/files.py` : fichiers JSON bornés, requêtes, jugements humains,
  validation des références, versions et partitions, préparation de candidats.
- `evaluation/metrics.py` : Precision@k, Recall@k, reciprocal rank/MRR et nDCG@k,
  agrégations avec dénominateurs explicites et mesures indéfinies conservées.
- `evaluation/cli.py` : point d’entrée indépendant `cahier-rag-eval`.
- `evaluation/queries.json` : requêtes manuelles sans texte du corpus.

Les documents restent dans PostgreSQL ; les fichiers d’échantillon contiennent
leurs IDs, empreintes de contenu et de texte, provenance minimale, strates et
partitions. Les manifestes référencent les extractions avec leurs paramètres,
filtres et versions, une version déclarée du corpus, les graines, la méthode,
la date UTC et les empreintes du cadre et de la sélection. Aucun schéma ou
migration supplémentaire n’est créé.

Le cadre est parcouru par lots et seuls les résumés sont conservés. Le plafond
est explicite et provoque une erreur, sans sélection silencieuse des premières
lignes. Aucun tri aléatoire SQL, extraction source complète, OFFSET ou collection
complète de corps documentaires n’est utilisé.

La stratification couvre questionnaires 4/5/7/10, réponses courtes, longues,
textes « Autre », textes identiques de contributions distinctes et contributions
à réponses multiples. Les réponses courtes sont aussi des **candidats** à un
besoin de contexte : seule une revue humaine peut établir ce besoin.
Les quotas impossibles sont signalés ; par défaut la CLI refuse la sortie.

Les composantes connexes contribution/texte exact du cadre entier sont placées
dans une seule partition. La graine de partition est indépendante du tirage.
Réutiliser le même cadre et cette graine pour les deux méthodes : les sélections
peuvent se recouvrir sans changer la partition des documents communs. Des cadres
différents ne doivent pas être mélangés. Aucun original n’est supprimé.

## Requêtes et jugements

Les 40 requêtes couvrent dix exemples dans chacun des quatre domaines :
fiscalité, démocratie, services publics et écologie.

| Catégorie | Total | Développement | Évaluation |
|---|---:|---:|---:|
| Thématique | 8 | 4 | 4 |
| Propositions concrètes | 8 | 4 | 4 |
| Expression précise | 8 | 4 | 4 |
| Vocabulaire différent | 8 | 4 | 4 |
| Contexte de question | 4 | 2 | 2 |
| Ambiguë ou difficile | 4 | 2 | 2 |
| **Total** | **40** | **20** | **20** |

Les familles de formulations apparentées ne traversent pas les partitions.
Le jeu reste à relire humainement avant gel et réglage des futurs moteurs.

Les jugements JSON comportent query_id, document_id, grade entier 0–3,
justification facultative, judged_at avec fuseau, version et evaluator.
Un candidat a une note nulle ; ce n’est pas un jugement zéro. Les versions
mélangées et notes concurrentes sont refusées pour le calcul : l’adjudication
reste humaine. Les fichiers peuvent être réimportés et écrits sous une nouvelle
version ; les sorties n’écrasent pas un fichier existant.

## Mesures

La pertinence binaire commence à la note 2. Precision utilise k au dénominateur,
même pour un classement plus court. MRR utilise le premier pertinent de la liste
fournie entière. nDCG utilise les gains `2^note - 1` et la décote `log2(rang+1)`.
Sans jugement, les mesures valent `null`. Un non-jugé n’est jamais converti en
non-pertinent. Le rapport indique couverture et nombre de requêtes définies.

Recall et nDCG ne sont publiés que si les jugements sont déclarés complets ;
la CLI vérifie alors que tous les documents de la partition sont jugés pour
chaque requête. Cette exhaustivité est locale à l’échantillon, pas au corpus.
Les moyennes sont disponibles par catégorie, partition et globalement. Comparer
les mêmes requêtes définies ; utiliser la partition d’évaluation pour la mesure
finale et conserver le développement pour les réglages.

## Validation locale limitée

Huit contributions ont été choisies volontairement : les deux dernières de
chacun des quatre questionnaires détaillés, via l’index existant
`(form_id, submitted_at, id)`. Huit extractions plafonnées chacune à vingt
unités et cent lignes sources ont constitué un cadre de **62 unités**.
Les requêtes étaient soumises à un délai PostgreSQL de cinq secondes.
C’est un cadre de commodité, sans prétention statistique.

Deux sélections de **40 unités**, graine 20261017 et graine de partition 1729,
ont été enregistrées sous `evaluation/local/`, ignoré par Git :

| Indicateur | Aléatoire dans ce cadre | Stratifié |
|---|---:|---:|
| Questionnaire 4 | 7 | 7 |
| Questionnaire 5 | 23 | 22 |
| Questionnaire 7 | 3 | 5 |
| Questionnaire 10 | 7 | 6 |
| Réponses courtes / candidats contexte | 4 | 5 |
| Réponses longues | 1 | 1 |
| Textes « Autre » | 0 | 1 |
| Développement | 23 | 26 |
| Évaluation | 17 | 14 |

Le stratifié présente des déficits explicites : quatre longues, quatre « Autre »
et cinq occurrences de doublons par rapport aux quotas du petit essai. Le cadre
ne contient pas de doublons textuels entre contributions. Cette sélection est
un diagnostic avec déficits acceptés explicitement, pas un jeu final validé.
Deux cents candidats non jugés ont été préparés, cinq par requête, sans note.
Aucun corps documentaire ni donnée personnelle n’est affiché dans ce rapport.

Le jeu réel de 10 000–20 000 unités n’a pas été constitué lors de cette
vérification volontairement limitée. Le mécanisme est testé sur une sélection
de 10 000 unités parmi 12 000 unités synthétiques. La constitution d’un cadre
réel suffisamment diversifié et sa revue humaine restent nécessaires avant
les comparaisons de moteurs. Aucun parcours massif n’a été lancé.

## Vérifications

- **195 tests réussis**, dont **33 intégrations PostgreSQL** et 162 tests unitaires.
- Cas couverts : déterminisme, quotas/déficits, BIGINT, doublons, regroupements
  transitifs, partitions, import/export, notes invalides, mesures connues,
  jugements incomplets et commandes hors connexion.
- Test d’itérateur plafonné et sélection synthétique de 10 000 unités.
- Isolation : imports du nouveau module avec réseau, backend et GPU interdits.
- Ruff, conformité du formatage, `uv lock --check` et `git diff --check` conformes.
- Distribution source et wheel construits ; commandes locales exécutées.
- `.gitignore` vérifié : requêtes versionnables ; fichiers locaux et JSONL ignorés.
- Le manifeste et le verrou racine du backend sont inchangés. Le verrou RAG ne
  change pas : aucune dépendance n’a été ajoutée, seul un point d’entrée est déclaré.
- Les données synthétiques du stockage de test sont nettoyées après la suite.

## Commandes et suite

Consulter [les commandes détaillées](evaluation.md#commandes) pour `sample`,
`describe`, `candidates` et `score`. Installation depuis `rag/` : `uv sync --locked`.
Les commandes d’évaluation hors échantillonnage ne nécessitent aucune connexion.

Les limites principales sont le biais de constitution du cadre, le caractère
heuristique du besoin de contexte, les groupes parfois très grands dus aux
textes répétés, l’absence de détection de paraphrases et le coût humain des
jugements exhaustifs. Les métriques documentaires ne mesurent pas la fréquence
des opinions ou la représentativité statistique du corpus.

Les seules écritures réelles sont dans la base RAG et les fichiers locaux
ignorés ; la source reste en lecture seule. Aucun backend, frontend, Wallace,
modèle, moteur, schéma source, infrastructure, commit ou push n’a été modifié
ou introduit. Les modules sont prêts pour recevoir les classements de futurs
moteurs, après constitution et annotation du jeu retenu.
