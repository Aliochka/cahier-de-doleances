# RAG-011 — Représentations documentaires et contextualisation

## Résultat

Quatre stratégies documentaires **A/B/C/D version 1**, un contrat préparé distinct
de `TextUnit`, une segmentation traçable et une CLI de génération, inspection,
récupération parentale et rejeu sont disponibles. Aucun modèle, embedding,
index ou schéma PostgreSQL supplémentaire n’a été introduit.

Les essais réels portent sur les **mêmes 512 unités de développement** pour les
quatre stratégies, puis sur une unité longue indépendante. Ils ne préparent pas
les 20 000 unités intégralement. Les unités parentes et voisines restent dans
le périmètre RAG-007, sans mélange de partitions ni modification des sources.

## 1. Architecture et contrats

Nouveaux modules sous `src/cahier_rag/representations/` :

| Fichier | Responsabilité |
|---|---|
| `contracts.py` | `PreparationConfig`, `PreparedRepresentation`, contexte, références et positions typés |
| `segmentation.py` | Découpage déterministe avec chevauchement et offsets sources |
| `prepare.py` | Transformations pures A/B/C/D, voisinage structurel et assemblage traçable |
| `repository.py` | Lots PostgreSQL READ ONLY et récupération des parents sélectionnés |
| `artifacts.py` | Sélection des cibles, JSONL, manifestes, statistiques et contrôle d’intégrité |
| `cli.py` | Génération, inspection hors ligne, rejeu et consultation des parents |

Le contrat `TextUnit`, les modèles, migrations et tables existants restent
inchangés. `PreparedRepresentation` conserve configuration, stratégie/version,
texte préparé, cible primaire, contexte distinct, partition, parent, références
sources, positions sources/sortie, indice de segment, enrichissement et empreinte.
Les BIGINT restent exacts : `int` Python, chaînes décimales JSON.

L’identité `prepared:v1:<stratégie>:<sha256>` est dérivée du périmètre, de la
configuration, de l’unité primaire et des bornes du segment. L’empreinte de
contenu porte sur tout le payload JSON canonique. Elle est distincte de
l’identité et ne dépend pas du lot, de la date ou du temps d’exécution.

Seuls `README.md` et l’ajout du point d’entrée `cahier-rag-prepare` dans
`pyproject.toml` modifient des fichiers existants. Le verrou uv et les dépendances
restent inchangés. Les modules d’annotation, de recherche et leurs paramètres
ne sont pas modifiés.

## 2. Stratégies et paramètres retenus

| Stratégie | Texte destiné à une future vectorisation |
|---|---|
| A | Réponse seule, ou segment exact de celle-ci |
| B | Question puis réponse avec libellés explicites |
| C | Texte identique à B ; les autres unités parentes sont récupérables séparément |
| D | B, puis extraits de réponses voisines pour une unité courte |

Configuration des essais : **2000 caractères de réponse par segment**, avec
**200 caractères de chevauchement** ; seuil court strictement inférieur à
**60 caractères** ; au plus **2 voisins**, chacun limité à un préfixe de
**1000 caractères**, avec sa question complète. Les titres sont conservés en
métadonnées, jamais ajoutés au texte préparé dans ces quatre stratégies.

D sélectionne les voisins les plus proches dans l’ordre structurel du
questionnaire ; en cas d’égalité, la position antérieure est prioritaire.
L’ordre et les départages utilisent positions et identifiants sources. Les
voisins appartiennent au même corpus, contribution et questionnaire.
Leurs préfixes, questions, références et positions sont explicitement tracés.
Une unité sans voisin reste non enrichie. Aucune pertinence sémantique n’est
inférée par cette règle.

Chaque unité reste une cible autonome. Les voisins ne deviennent pas de nouveaux
résultats primaires et les doublons originaux sont conservés. C ne change pas
les entrées d’embedding de B : son intérêt concerne l’accès ultérieur au parent.

## 3. Segmentation et politique de contexte

Le découpage privilégie les fins de paragraphe, puis de phrase, dans la seconde
moitié de la fenêtre ; sinon il coupe à la borne dure. Les espaces et tous les
caractères originaux sont conservés. Les intervalles `[début, fin)` sont exprimés
en points de code Unicode Python. Le chevauchement est exact et configurable.

Le budget de 2000 caractères porte sur **la réponse**, pas sur la question et
les libellés ajoutés. Il n’est donc pas une limite globale d’entrée du modèle.
La taille en tokens et la politique de débordement restent à décider.

La politique v1 est **`rag007-selected-only`**. Les 42 318 unités stockées ne sont
pas exploitées comme contexte supplémentaire : même les parents sont limités
aux 20 000 unités sélectionnées. C’est une décision conservatrice autorisée par
le ticket ; les contributions parentes peuvent être incomplètes. Un contexte
extérieur nécessiterait une nouvelle politique et des vérifications anti-fuite.

`CorpusScope` contrôle le manifeste exact RAG-007 et les règles existantes de
partition par contribution et texte complet identique. Les références sont
vérifiées contre leurs empreintes en base. Les parents sont récupérés par une
API explicite, sans charger toute une contribution dans le texte préparé.

## 4. Interface et artefacts

Depuis `rag/`, avec l’environnement déjà installé :

```bash
export RAG_DATABASE_URL='postgresql:///cahier_rag'
uv run --locked --no-sync python -m cahier_rag.representations.cli generate \
  --strategy D --limit 512 --split development --seed 20261021 \
  --batch-size 25 --output evaluation/local/rag011/mon-essai-D
uv run --locked --no-sync python -m cahier_rag.representations.cli inspect \
  evaluation/local/rag011/mon-essai-D
uv run --locked --no-sync python -m cahier_rag.representations.cli verify \
  evaluation/local/rag011/mon-essai-D --batch-size 7
```

`parent DOCUMENT_ID` récupère uniquement les références parentes sélectionnées ;
`--show-text` autorise explicitement leur affichage. `--env-file` sélectionne un
fichier de configuration local, sans recherche automatique du `.env` racine.

La sélection de cibles est déterministe par SHA-256 de `[graine, document_id]`
dans la partition demandée. La limite est obligatoire. Les sorties doivent être
dans un nouveau sous-dossier de `evaluation/local/rag011/`, ignoré par Git.

Chaque exécution crée `representations.jsonl` et un `manifest.json` de succès
écrit en dernier. Le manifeste conserve versions, paramètres, graine, filtres,
identifiants des cibles, références aux extractions RAG-007, empreintes des
sources et du code, statistiques, date et durée. Les octets du JSONL sont
reproductibles ; le manifeste d’exécution inclut volontairement une date et
une durée variables. Un répertoire incomplet n’est pas repris ni écrasé : il
faut recommencer dans un nouveau dossier.

## 5. Essais réels limités

### Lot commun de développement

Graine **20261021**, **512 cibles** :

| Questionnaire | Cibles |
|---|---:|
| 4 | 137 |
| 5 | 194 |
| 7 | 50 |
| 10 | 131 |

Le lot comprend **499 réponses ouvertes**, **13 textes « Autre »**, **188 réponses
courtes (<60 caractères)** et **1 réponse longue (>2000 caractères)**.
La plus longue réponse de ce lot mesure 2265 caractères. Il s’agit d’un sous-lot
technique du corpus expérimental ; il ne représente pas statistiquement le
Grand Débat.

Résultats des exécutions finales, lots de 25 cibles :

| Stratégie | Représentations | Unités segmentées | Unités enrichies | Longueur min./moy./max. | JSONL (Mio) | Préparation (s) |
|---|---:|---:|---:|---|---:|---:|
| A | 513 | 1 | 0 | 1 / 167,2 / 1914 | 1,102 | 0,160 |
| B | 513 | 1 | 0 | 47 / 302,2 / 2039 | 1,261 | 0,166 |
| C | 513 | 1 | 0 | 47 / 302,2 / 2039 | 1,261 | 0,162 |
| D | 513 | 1 | 184 | 107 / 515,5 / 2039 | 1,581 | 0,321 |

D enrichit **35,94 %** des cibles, soit **184 des 188 unités courtes** ; quatre
n’ont pas de voisin disponible dans le périmètre retenu. Ses textes référencent
**868 unités sélectionnées distinctes**, dont 356 contextuelles qui ne sont pas
primaires dans ce sous-lot de 512. Elles restent dans les 20 000 unités et dans
la partition développement. A/B/C référencent 512 unités dans leurs textes ;
les références parentales de C restent séparées.

Distribution des longueurs des représentations, en caractères :

| Intervalle | A | B | C | D |
|---|---:|---:|---:|---:|
| [0,60) | 188 | 3 | 3 | 0 |
| [60,200) | 204 | 186 | 186 | 45 |
| [200,500) | 87 | 271 | 271 | 241 |
| [500,1000) | 25 | 38 | 38 | 195 |
| [1000,2000) | 9 | 14 | 14 | 31 |
| [2000,4000) | 0 | 1 | 1 | 1 |

Ces nombres décrivent la longueur des textes préparés, pas leur pertinence.
Les coûts correspondent à une exécution locale, avec caches déjà utilisés,
hors chargement initial du manifeste et hors profilage mémoire. Il ne s’agit
pas d’un benchmark comparatif stabilisé.

### Réponse longue complémentaire

La plus longue réponse **de développement du périmètre RAG-007**, choisie de
manière déterministe par longueur puis identifiant, mesure **56 257 caractères**.
Elle n’appartient pas au lot de 512.

Chaque stratégie produit **34 segments**, couvrant fidèlement le texte original
avec 200 caractères de chevauchement. Les longueurs préparées vont de
1537 à 1980 caractères pour A et de 1684 à 2127 pour B/C/D.
Les artefacts occupent 143 156 octets pour A et 154 478 pour chacune des autres
stratégies. La préparation prend environ 0,011–0,012 s par stratégie sur cet essai
local. D ne regroupe pas cette réponse longue.

### Mémoire et garde-fous

Le profil `tracemalloc`, exécuté après chargement des métadonnées du périmètre,
mesure environ **0,16 Mio** de pic de préparation pour A/B/C et **0,45 Mio** pour
D sur les 512 cibles, sans accumuler les représentations. Ce n’est pas une mesure
du RSS total ni des allocations natives du pilote PostgreSQL.

Les textes sont chargés par lot avec curseur serveur, puis les transactions sont
fermées avant l’écriture locale. Les garde-fous imposent 5000 unités avec
contexte, 20 millions de caractères par lot, 256 unités par parent, 1000 segments
par source et 32 Mio par ligne JSONL. Les métadonnées du périmètre et les compteurs
par cible restent bornés à 20 000 unités. L’histogramme des longueurs utilise
un nombre fixe de classes, pas une liste de tous les segments.

## 6. Manifestes et vérifications

Sous `evaluation/local/rag011/` :

```text
final-trial-A/ … final-trial-D/       512 cibles communes, JSONL et manifeste par stratégie
final-long-A/ … final-long-D/         Essai long complémentaire, JSONL et manifeste
validation-final.json                Empreintes, rejeux, fidélité, mémoire et préservation
protected-hashes.json                Empreintes initiales des fichiers protégés
```

Des répertoires d’essais préliminaires sont conservés séparément et ne sont pas
les références finales. Aucun artefact existant n’a été écrasé. Tous les textes
réels et leurs manifestes restent locaux et ignorés par Git.

Les huit artefacts finaux ont été rejoués avec des lots de **7**, sans différence
d’octets dans les JSONL. Les réponses originales ont aussi été reconstruites à
partir des spans primaires et des chevauchements, puis comparées à leur empreinte
textuelle RAG-007 : **512 cibles fidèles par stratégie**, puis une cible longue
fidèle pour chaque stratégie. Les sorties sont identiques à celles des essais
préliminaires, malgré une optimisation du calcul des empreintes sources.

**57 fichiers protégés et 5 modules gelés RAG-009** ont conservé leurs empreintes :
requêtes, manifestes historiques, candidats, classements, code d’annotation et
verrous concernés. La session et les jugements RAG-010 **n’ont pas été ouverts,
utilisés pour régler les stratégies, ni modifiés**. Aucun environnement uv n’a
été resynchronisé pendant cette tâche.

## 7. Tests et qualité

**310 tests réussis**, dont **60 intégrations PostgreSQL** et **250 tests unitaires**.
Les nouvelles vérifications couvrent A/B/C/D, titres absents, Unicode, BIGINT,
textes très courts et très longs, segmentation, reconstruction, chevauchement,
positions, regroupements, contraintes de partition, absence de voisins extérieurs,
identifiants, empreintes, JSONL, rejeu, interruptions et limites mémoire.

Les tests PostgreSQL utilisent uniquement les bases de test dédiées. Ils
contrôlent notamment `transaction_read_only=on`, l’absence d’unités extérieures
comme contexte, les erreurs de provenance et la fermeture des connexions, y
compris lors d’un arrêt prématuré de l’itérateur.

Ruff et son contrôle de formatage passent ; **`uv lock --check` passe** sans
modification du verrou. L’avertissement Starlette déjà connu dans les tests
HTTP RAG-010 subsiste, sans échec ni nouvelle dépendance. Aucun service de
production ni GPU n’a été utilisé. Aucun commit ou push effectué.

## 8. Limites et décisions avant RAG-012

- Choisir un modèle et son tokenizer avant de définir un budget en tokens,
  une taille de segment et une politique pour les questions/contextes trop longs.
- D reste une hypothèse de contexte structurel ; les voisins peuvent détourner
  le sens de la réponse primaire. Ses préfixes ne sont pas une segmentation
  linguistique complète et ne garantissent pas la conservation d’une phrase.
- C et B ont les mêmes textes ; leur différence doit être évaluée au niveau de
  la restitution parentale, pas présentée comme une amélioration des embeddings.
- Les parents sont incomplets par choix de périmètre. L’utilisation des autres
  unités stockées, si nécessaire, devra être explicitement versionnée et contrôlée.
- Le découpage peut couper mots, abréviations ou graphèmes ; aucun tokenizer NLP
  n’est utilisé. Les déduplications partielles ou sémantiques restent hors périmètre.
- Définir l’agrégation future des scores de segments vers l’unité primaire, sans
  compter les voisins et chevauchements comme des contributions supplémentaires.
- Les artefacts JSONL n’ont pas de checkpoint persistant ; aucun manifeste de
  succès n’est produit en cas d’interruption. Recommencer dans un nouveau dossier.
- Aucun jugement humain n’a encore servi à comparer ces représentations. Les
  statistiques publiées ne démontrent aucune supériorité de pertinence.
- Le statut « développement non commencé » de `docs/plan-rag.md` reste historique
  et ne reflète plus l’implémentation ; le code et les rapports récents font foi.

Les commandes détaillées, paramètres et conventions sont dans
[representations-documentaires.md](representations-documentaires.md).
