# RAG-011 — Représentations documentaires expérimentales

Le package `cahier_rag.representations` prépare des textes et leur provenance.
Il ne calcule aucun embedding et ne définit aucun nouveau document source.
`TextUnit` RAG-004 reste inchangé, tout comme le schéma PostgreSQL.

## Stratégies v1

| Stratégie | Texte préparé | Contexte et restitution |
|---|---|---|
| A | Réponse seule, ou son segment exact | Question, titre et questionnaire conservés en métadonnées |
| B | `Question :\n…\n\nRéponse :\n…` | Champs originaux séparés, provenance vers la réponse |
| C | Exactement le même texte que B | Références parentes et récupération des autres unités sélectionnées à la demande |
| D | B, enrichi pour les réponses de moins de 60 caractères | Jusqu’à deux extraits voisins de la même contribution, avec leur question et leurs références |

Les titres restent des métadonnées pour les quatre stratégies ; ils ne sont pas
ajoutés au texte préparé. B et C produiront les mêmes entrées d’embedding : C
prépare surtout une restitution plus large après recherche. Aucun gain de
classement propre à C ne peut être déduit de ce travail.

Chaque réponse reste une **cible primaire distincte**, y compris avec D. Il n’y
a ni fusion d’identités, ni déduplication, ni document autonome pour les voisins.
Les futurs résultats devront être ramenés aux identifiants `TextUnit` primaires ;
plusieurs segments ou contextes partagés ne constituent pas plusieurs opinions.

### Paramètres de `PreparationConfig`

| Paramètre | Défaut | Effet |
|---|---:|---|
| `strategy` | obligatoire | `Strategy.A`, `.B`, `.C`, `.D` |
| `segment_chars` | 2000 | Budget du segment de **réponse**, en caractères Python |
| `overlap_chars` | 200 | Chevauchement exact entre segments ; de 0 à la moitié du budget |
| `short_chars` | 60 | D enrichit uniquement si `len(text) < short_chars` |
| `max_neighbors` | 2 | De 0 à 8 voisins, hors unité primaire |
| `neighbor_chars` | 1000 | Préfixe maximal du texte de chaque voisin |

Toutes les valeurs, y compris celles inactives pour une stratégie, participent
à l’empreinte de configuration. Les versions de stratégie, segmentation et
contrat préparé sont **1**. La configuration enregistre également la politique
de contexte, l’unité des positions, l’ordre des voisins et l’exclusion des titres.

### Règles D

L’ordre structurel est défini par : présence/valeur de position de question,
identifiant de question, position de réponse, identifiant de réponse, indice
textuel puis identifiant documentaire. Une position de question absente est
placée après celles qui sont renseignées.

Les voisins sont choisis par distance dans cet ordre, puis par position en cas
d’égalité. Ils peuvent être des réponses ouvertes ou des textes « Autre ». Ils
appartiennent au **même corpus, à la même contribution et au même questionnaire**.
Les libellés du contexte sont explicites :

```text
Contexte — autre réponse de la même contribution :
Question :
…
Réponse (extrait) :
…
```

Un voisin long utilise son préfixe `[0:neighbor_chars]`, sans modification du
texte original stocké. La coupure et ses positions sont tracées. Une réponse
sans voisin reste une représentation B et porte `enriched=false`.
Le voisinage est une **heuristique structurelle**, sans estimation de pertinence
sémantique. Il peut apporter du bruit ; aucune annotation humaine ne l’a réglé.

## Périmètre et partitions

La CLI exige le manifeste exact des **20 000 unités RAG-007**, validé par
`CorpusScope`, avec son empreinte et ses contraintes anti-fuite par contribution
et texte identique. Le moteur ne parcourt pas implicitement les 42 318 unités.

La politique v1, volontairement conservatrice, est **`rag007-selected-only`** :
les parents et voisins sont eux aussi limités à ces 20 000 unités, même lorsque
le traitement porte sur un sous-ensemble de 512 cibles. Aucune unité des 22 318
restantes n’est utilisée, pas même comme contexte externe. Une contribution
parente peut donc être incomplète. L’ouverture au cadre stocké plus large devra
faire l’objet d’une nouvelle politique versionnée et de contrôles anti-fuite
spécifiques ; elle n’est pas nécessaire à cette première expérience.

Les unités d’une contribution ont toutes la même partition. Un traitement
`--split all` conserve la partition propre de chaque représentation et ne mélange
jamais les voisins des deux ensembles. Par défaut, la sélection et les essais
utilisent **uniquement le développement**. Les doublons proches, les préfixes
communs et les recouvrements partiels ne sont pas dédupliqués ; les garanties
RAG-007 portent sur les contributions et les textes complets identiques.

## Segmentation v1

Les positions sont des intervalles **[début, fin)** dans `TextUnit.text`, en
points de code Unicode Python : ni octets, ni tokens, ni graphèmes affichés.
Les caractères combinés et emoji ne sont jamais normalisés. Une coupure de
secours peut séparer un mot ou une séquence de graphèmes.

Les textes d’au plus `segment_chars` restent entiers. Pour les autres :

1. Choisir une borne dure à `début + segment_chars`.
2. Chercher une fin de paragraphe `\n\n` dans la seconde moitié de cette fenêtre.
3. Sinon, chercher une ponctuation `.`, `!`, `?` suivie d’espaces ou de retours à
   la ligne dans cette même zone ; ce n’est pas une analyse linguistique complète.
4. Sinon, utiliser la borne dure.
5. Repartir à `fin - overlap_chars`, en garantissant une progression stricte.

Aucun espace n’est supprimé, aucune casse ni accent n’est modifié. Les fragments
primaires et leurs chevauchements permettent de reconstruire exactement le
texte source. La question est répétée pour chaque segment en B/C/D.

**Le budget porte sur la réponse, pas sur tout le texte préparé.** La question,
les libellés et les voisins peuvent dépasser 2000 caractères en sortie. Il faudra
une politique de budget en tokens adaptée au modèle avant la vectorisation ;
les valeurs actuelles ne constituent pas un choix définitif.

## Contrats préparés

`PreparedRepresentation`, dataclass immuable distincte de `TextUnit`, contient :

- Identifiant `prepared:v1:<stratégie>:<sha256>` ; son identité dépend de la
  version, de l’empreinte de configuration, du périmètre RAG-007, de l’unité
  primaire et des bornes du segment. Elle ne dépend pas de l’ordre de traitement,
  d’un UUID aléatoire, du texte comme identité principale ou de la taille du lot.
- Stratégie/version, empreinte de configuration, périmètre et partition.
- `embedding_text`, texte préparé ; aucun modèle n’est appelé.
- `primary` et `sources` : références vers les unités utilisées, leurs empreintes,
  corpus, contribution, réponse, question et questionnaire.
- `context` : question, questionnaire, titre éventuel, positions et type
  documentaire, distincts du texte destiné à l’embedding.
- `parent` : corpus, contribution, politique et identifiants des unités parentes
  sélectionnées. Ces références n’ajoutent pas leurs textes au segment C.
- `segment` : indice et intervalle dans la réponse primaire.
- `spans` : pour chaque extrait de réponse ou de question, document source,
  champ (`text` ou `question_text`), positions sources et positions dans la sortie,
  rôle primaire ou voisin. Les libellés ajoutés sont hors des spans sources.
- `enriched` et `content_hash`.

Les BIGINT restent des `int` en Python et des chaînes décimales dans le JSON.
Les références externes complètes restent disponibles dans les `TextUnit`
originaux, retrouvables par leurs identifiants et empreintes.

L’empreinte de contenu porte sur toute la représentation sérialisée, hors
`content_hash`, avec JSON canonique Unicode et clés triées. Identité et contenu
restent distincts : un changement de contenu à positions identiques conserve
l’identité, mais change l’empreinte. Un changement de configuration ou de bornes
produit une autre identité. Les versions et le contexte source sont tracés.

## Interface Python et traitement

```python
from cahier_rag.config import load_settings
from cahier_rag.db import create_rag_engine
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.search.lexical import CorpusScope
from cahier_rag.representations.artifacts import select_targets
from cahier_rag.representations.contracts import PreparationConfig, Strategy
from cahier_rag.representations.repository import RepresentationRepository

scope = CorpusScope(load_sample("evaluation/local/rag007/corpus.json"))
engine = create_rag_engine(load_settings())
try:
    repository = RepresentationRepository(engine, scope)
    ids = select_targets(scope, limit=512, split="development", seed=20261021)
    for prepared in repository.iter_prepared(ids, PreparationConfig(Strategy.D), batch_size=25):
        consume(prepared)  # votre traitement ; ne pas accumuler tout le corpus
    parent_units = repository.parent(ids[0])  # uniquement le périmètre sélectionné
finally:
    engine.dispose()
```

`prepare_unit()` est la transformation pure, utilisable sur des données
synthétiques. Pour les données réelles, utiliser le dépôt validé : c’est lui qui
contrôle l’appartenance au corpus, les empreintes et les partitions.

Les lectures SQL utilisent exclusivement la connexion RAG, en **READ ONLY**,
avec requêtes liées à la clé primaire, paramètres liés, délais de 5 s/2 s et
résultats parcourus en flux. Une requête charge un lot et ses contextes nécessaires,
pas une requête par réponse. Les connexions sont fermées **avant** chaque `yield`
de représentation, donc avant l’écriture locale ou un traitement lent extérieur.
Aucune connexion à la source ni migration n’est nécessaire.

Garde-fous : lots de 1 à 100 cibles, au plus 5000 unités avec contexte et 20 millions
de caractères chargés par lot, 256 unités parentes, 1000 segments par unité,
32 Mio par ligne JSONL. Les dépassements échouent explicitement : réduire le lot
ou revoir la configuration, sans troncature silencieuse. Un enregistrement très
volumineux doit toutefois être reçu avant son contrôle. Les métadonnées des
20 000 unités restent en mémoire ; les textes dépendent du lot et du contexte.
L’histogramme a des classes fixes ; les identifiants/compteurs sont bornés par
le périmètre de 20 000 cibles, pas par le nombre de segments.

## Commandes et indépendance de l’annotation

Depuis `rag/`, avec l’environnement existant :

```bash
export RAG_DATABASE_URL='postgresql:///cahier_rag'
uv run --locked --no-sync python -m cahier_rag.representations.cli generate \
  --strategy D --limit 512 --split development --seed 20261021 \
  --batch-size 25 --segment-chars 2000 --overlap-chars 200 \
  --short-chars 60 --max-neighbors 2 --neighbor-chars 1000 \
  --output evaluation/local/rag011/mon-essai-D

uv run --locked --no-sync python -m cahier_rag.representations.cli inspect \
  evaluation/local/rag011/mon-essai-D

uv run --locked --no-sync python -m cahier_rag.representations.cli verify \
  evaluation/local/rag011/mon-essai-D --batch-size 7

uv run --locked --no-sync python -m cahier_rag.representations.cli parent \
  'IDENTIFIANT_TEXTUNIT'
```

`--env-file .env` sélectionne explicitement une configuration locale ; il doit
précéder la sous-commande. Aucun `.env` n’est chargé automatiquement.
`parent --show-text` affiche le contexte intégral à la demande ; par défaut,
seuls références, empreintes et longueurs sont affichées. `inspect` est hors
ligne et ne reproduit aucun texte personnel. `verify` relit la base RAG en lecture
seule, re-prépare les unités et compare les empreintes du JSONL et des représentations.
Il refuse un code de préparation différent de celui enregistré.

Le point d’entrée `cahier-rag-prepare` est également déclaré ; il sera disponible
après la prochaine installation/synchronisation du projet. Les commandes
`--no-sync python -m …` fonctionnent avec le package éditable déjà installé et
**n’altèrent pas l’environnement de l’annotation en cours**. Aucun `uv sync` n’a
été nécessaire pour RAG-011. Ne pas synchroniser en retirant l’option `annotation`
pendant que l’interface RAG-010 utilise ce même environnement.

## Artefacts et reproductibilité

La CLI n’accepte qu’un **nouveau sous-dossier de `evaluation/local/rag011/`**,
ignoré par Git. Elle n’écrase aucun fichier existant.

- `representations.jsonl` : une représentation par ligne, avec contenu et provenance.
- `manifest.json` : écrit en dernier, seulement après succès et synchronisation
  du JSONL. Versions, corpus, extractions de RAG-007, paramètres, graine,
  partition, cibles, empreintes des sources, des données et du code, garde-fous,
  date, durée et statistiques descriptives.

La sélection bornée est le tri SHA-256 `[graine, document_id]` dans la partition
choisie, suivi de la limite. La même graine sélectionne les mêmes unités pour les
quatre stratégies. Les versions du corpus proviennent du manifeste source.

Les octets du JSONL et l’empreinte ordonnée des identifiants/contenus sont
reproductibles. La date et la durée rendent le manifeste d’exécution variable ;
son empreinte vérifie son intégrité, pas une identité octet à octet entre deux
exécutions. `inspect` vérifie le manifeste, les références et les données en flux.
Un répertoire interrompu sans manifeste est incomplet ; choisir un nouveau
répertoire pour recommencer. Il n’y a pas de reprise au milieu d’un JSONL dans
cette tâche, contrairement aux extractions PostgreSQL RAG-005.

Les longueurs sont des longueurs de **représentations**, incluant contexte et
libellés. Les médiane/P95 publiées dans les manifestes sont des **bornes de
classes d’histogramme**, pas des quantiles exacts. Les champs `by_questionnaire`,
`by_split`, `by_unit_type` comptent les représentations, segments compris ; la
sélection de cibles et ses identifiants sont enregistrés séparément.

Aucun fichier de jugements, aucune session RAG-010, aucune requête de recherche
ou classement n’est utilisé pour préparer les représentations.

## Tests et suite

```bash
uv run --locked --no-sync pytest
uv run --locked --no-sync ruff check .
uv run --locked --no-sync ruff format --check .
uv lock --check
```

Les intégrations utilisent uniquement les bases `_test` configurées selon le
README. Les tests de préparation unitaires n’ont besoin ni de PostgreSQL, ni de
FastAPI, ni d’un modèle. Voir [le rapport RAG-011](rapport-rag-011.md) pour les
essais réels, leurs limites et les choix à reporter avant RAG-012.
