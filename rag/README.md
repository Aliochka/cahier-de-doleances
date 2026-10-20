# RAG local — Corpus, recherche lexicale et évaluation

Ce sous-projet prépare le futur moteur de recherche et RAG documentaire du
Cahier de doléances. Il appartient au monorepo, mais possède son propre projet
Python installable, son verrou uv, son environnement et ses tests.

Il fonctionne exclusivement sur le PC local. Il n'importe aucun module de
`app/` et n'utilise ni la configuration ni les connexions du backend. Wallace
et le site public restent indépendants de sa disponibilité. Le dossier `rag/`
est déjà exclu du contexte Docker du backend ; aucun Dockerfile ou Compose
n'est modifié par cette tâche.

## Prérequis et installation

- uv **0.13.1**, comme le backend (installation décrite dans le README racine).
- Python **3.11**. uv peut l'installer si nécessaire.
- Aucun PostgreSQL, Docker, GPU ou accès réseau requis pour les tests unitaires
  et les diagnostics une fois les dépendances installées. La lecture du corpus
  et les tests d'intégration nécessitent un PostgreSQL explicitement configuré.

Depuis la racine du dépôt :

```bash
cd rag
uv python install 3.11
uv sync --locked --dev
uv lock --check
uv run --locked python -m cahier_rag --version
```

Cette commande installe `cahier_rag` en mode éditable dans **`rag/.venv/`**.
Ne pas utiliser `uv sync --active` ni définir `UV_PROJECT_ENVIRONMENT` vers
l'environnement du backend. Si un ancien environnement est activé, le quitter
avec `deactivate`. Aucun workspace uv ne relie les deux projets ; le manifeste
et le verrou racine ne sont pas utilisés par `uv sync` exécuté dans `rag/`.

Les dépendances d'exécution sont SQLAlchemy 2.0.43, psycopg2-binary 2.9.10 et
python-dotenv 1.2.4 et Alembic 1.16.5, aux mêmes versions que le backend. Elles permettent les
fabriques PostgreSQL et la lecture facultative d'un fichier explicitement
choisi. La configuration utilise des dataclasses de la bibliothèque standard.
pytest 9.1.1 et Ruff 0.17.0 sont dans le groupe `dev` indépendant.
`uv_build` 0.13.1 sert uniquement à construire le package Python.

Pour un environnement sans les outils de développement :

```bash
uv sync --locked --no-dev
uv run --locked --no-dev python -m cahier_rag --version
```

## Configuration explicite

| Variable | Destination | Obligation |
|---|---|---|
| `RAG_SOURCE_DATABASE_URL` | Corpus original, accès en lecture seule | Lors d'une opération source |
| `RAG_DATABASE_URL` | Base expérimentale distincte | Lors d'une opération RAG |

Les noms `cahier_doleances` et `cahier_rag` dans `.env.example` sont des
exemples configurables, pas des bases créées. La documentation locale existante
utilise aussi `cahier_doleances_local` : adapter l'URL à l'installation réelle.

Les paramètres peuvent venir de l'environnement, ou d'un fichier local choisi
par `--env-file`. **Aucun `.env` n'est recherché ni chargé automatiquement**,
à la racine du monorepo ou dans `rag/`. Les variables `DATABASE_URL`,
`TEST_DATABASE_URL`, `ALEMBIC_DATABASE_URL` et Scalingo sont ignorées. Le fichier
ne modifie pas `os.environ`, et son interpolation `${VARIABLE}` est désactivée.
Les variables RAG de l'environnement priment sur celles du fichier, y compris
une valeur vide (alors considérée comme manquante).

Le modèle fourni ne contient aucun secret et peut être vérifié directement :

```bash
uv run --locked python -m cahier_rag check-config --env-file .env.example
```

Pour une configuration locale, copier soi-même `.env.example` vers `.env.local`,
adapter les destinations et les rôles, puis sélectionner ce fichier :

```bash
uv run --locked python -m cahier_rag check-config --env-file .env.local
uv run --locked python -m cahier_rag check-config --env-file .env.local --connection source
uv run --locked cahier-rag check-config --env-file .env.local --connection rag
```

Sans `--env-file`, seules les variables RAG de l'environnement sont consultées.
`check-config` demande les deux destinations par défaut ; `--connection` permet
de valider un seul rôle. Le diagnostic n'ouvre jamais de connexion, même avec
une configuration complète. Une erreur donne le code de sortie **2**, sans
URL, mot de passe ou traceback. Ne pas journaliser les URL retournées par les
méthodes `require_*_url()` ; le `repr` de `Settings` les masque intégralement.

Les URL acceptées sont `postgres://`, `postgresql://` et
`postgresql+psycopg2://`, normalisées vers psycopg2. Une base explicite et un
port valide sont requis (5432 par défaut). Les sockets Unix sont possibles,
par exemple `postgresql:///corpus?host=/var/run/postgresql`.
Les paramètres autorisés sont `host`, `port`, `sslmode`, `sslrootcert`,
`sslcert`, `sslkey`, `application_name` et `connect_timeout`. Les DSN via
`service`, les connexions multihôtes, les paramètres répétés et les options
libpq arbitraires sont refusés pour éviter les destinations ambiguës.

La validation refuse une source et une cible désignant la même base, même
avec des rôles ou mots de passe différents. Elle rapproche les ports implicites,
les noms d'hôtes en casse différente et les adresses locales courantes.
Elle ne fait aucune résolution DNS : deux alias d'hôte différents, un tunnel
ou des chemins de sockets équivalents peuvent masquer un même serveur.
Les migrations et le stockage vérifient aussi l’identité réelle des bases
(identifiant système du cluster et OID), avant toute écriture ; les alias ne
contournent donc pas cette protection. Voir [les garanties du stockage](stockage.md). Une base logique distincte n'isole pas les ressources physiques
d'une instance PostgreSQL partagée.

## Primitives PostgreSQL

`config.load_settings()` valide les paramètres sans moteur ni connexion.
`db.create_source_engine(settings)` et `db.create_rag_engine(settings)` créent
des moteurs SQLAlchemy paresseux à la demande. Aucun moteur n'est global.
Les délais de connexion et d'attente du pool sont bornés à cinq secondes ;
`connect_timeout` dans l'URL ne peut pas augmenter le délai de connexion.

Pour les futures opérations sources, `db.source_connection(engine)` ouvre une
transaction avec `postgresql_readonly=True` **avant** son démarrage, et ferme
la transaction et la connexion à la sortie, y compris en cas d'erreur.
Le moteur source configure également cette option par défaut. L'appelant reste
responsable de libérer le pool avec `engine.dispose()`.

Le stockage expérimental utilise `RagStore` et `DatabaseGuard` : transactions
RAG explicites, contrôle des destinations et fermeture des connexions sources
avant toute écriture. Les moteurs sont libérés explicitement.

La protection source devra aussi reposer sur un **rôle PostgreSQL limité à la
lecture**, sans droits de création ni d'écriture sur les tables du corpus.
Ce rôle n'est ni créé ni vérifié ici. Les options de transaction ne remplacent
pas les privilèges du serveur. Les intégrations vérifient le mode READ ONLY
sur une base de test ; elles ne provisionnent ni ne valident un rôle de production.

## Contrat et lecteur source — RAG-004

`contracts.TextUnit` représente une unité textuelle extraite, avec son texte,
la question, le questionnaire et le titre conservés séparément. Ce n'est pas
un futur segment d'embedding. Les IDs restent des `int` en Python et deviennent
des chaînes décimales dans `to_dict()` et `to_json()`.

Les types `open_answer` et `other_text` distinguent les réponses ouvertes et
les éléments de `value_json.other_text`. Les libellés sélectionnés ne sont
jamais utilisés comme texte libre. Le lecteur ne normalise ni ne segmente
les textes et conserve les occurrences répétées.

Depuis `rag/`, après configuration explicite des variables RAG :

```python
from cahier_rag.config import load_settings
from cahier_rag.db import create_source_engine
from cahier_rag.sources.gdn import GdnReader

engine = create_source_engine(load_settings(env_file=".env.local"))
try:
    reader = GdnReader(engine, corpus_id="gdn-2019", batch_size=100)
    for batch in reader.iter_batches(limit=10):
        for document in batch.documents:
            # Aucun texte n'est affiché ; le futur stockage recevra les objets.
            print(document.document_id, document.content_hash)
        resume = batch.next_cursor
finally:
    engine.dispose()
```

`GdnReader` accepte aussi les filtres `questionnaire_id`, `contribution_id`
et `unit_type=UnitType.OPEN_ANSWER` ou `UnitType.OTHER_TEXT`.
`iter_documents(after=cursor, limit=10)` permet une lecture document par
document. Chaque lot ferme ses résultats, sa transaction READ ONLY et sa
connexion **avant** de remettre les objets au consommateur. Un arrêt anticipé
ne laisse donc pas de connexion ouverte.

`batch_size` borne les lignes `answers` lues par requête, et non les unités
émises : un tableau `other_text` peut fournir plusieurs unités. Les lots vides
font avancer le curseur. `Cursor.after_document(document)` permet aussi de
reprendre au milieu d'une réponse ; `to_dict()` et `Cursor.from_dict()`
conservent son identifiant BIGINT exactement. Réutiliser un curseur avec le
même corpus, les mêmes filtres et la même version d'extraction.

`get_contribution(id)` restitue les métadonnées d'une contribution, y compris
un titre sans réponse ouverte, sans créer de document autonome pour ce titre.

Voir [le contrat et les règles d'extraction](extraction.md) pour les champs,
l'identité, les empreintes, les anomalies JSON, la reprise et les limites.
Le [compte rendu RAG-004](rapport-rag-004.md) détaille les validations effectuées.

## Stockage documentaire — RAG-005

Le schéma indépendant `rag` conserve les unités, manifestes, associations et
checkpoints. Les migrations ne créent aucune base ni aucun rôle. Les deux bases
doivent exister et la source doit être accessible pour les contrôles d’identité.

Depuis `rag/`, après configuration locale :

```bash
uv run --locked cahier-rag schema-upgrade --env-file .env.local
uv run --locked cahier-rag extract --env-file .env.local --limit 20 --questionnaire-id 7 --batch-size 10 --max-source-rows 1000 --max-batches 1
uv run --locked cahier-rag status UUID_DU_MANIFESTE --env-file .env.local
uv run --locked cahier-rag resume UUID_DU_MANIFESTE --env-file .env.local
```

La CLI affiche l’UUID avant de commencer et des métadonnées de progression,
sans texte documentaire. La limite est obligatoire et plafonnée à 10 000 unités.
Les paramètres et versions sont immuables lors d’une reprise. Une limite séparée
borne les lignes sources retournées, y compris lorsque les lots n’émettent aucun
document. Un arrêt volontaire conserve le statut `running`, reprenable.

Voir [le stockage et ses limites](stockage.md) et le
[compte rendu RAG-005](rapport-rag-005.md).

## Échantillons et évaluation — RAG-006

Le module `evaluation` sélectionne des jeux aléatoires et stratifiés sur un cadre
explicite d’extractions terminées, avec manifestes et partitions par contribution
et texte identique. Le tirage aléatoire porte sur ce cadre ; il ne constitue pas
un tirage uniforme sur tout le corpus. La cible expérimentale est de 10 000 à
20 000 unités ; les essais locaux peuvent être plus petits.

Le fichier [de requêtes](evaluation/queries.json) contient 40 requêtes françaises,
réparties entre développement et évaluation. Les annotations restent humaines.
Les métriques Precision@k, Recall@k, MRR et nDCG@k distinguent les non-jugés des
notes zéro et publient leur couverture. Aucun score réel n’est disponible avant
annotation. Les fichiers locaux restent sous `evaluation/local/`, ignoré par Git.

```bash
uv run --locked cahier-rag-eval --help
uv run --locked cahier-rag-eval describe --sample evaluation/local/random.json
```

Voir le [protocole, les formats et les commandes](evaluation.md) et le
[compte rendu RAG-006](rapport-rag-006.md). Aucun modèle, index ou moteur de
recherche n’est ajouté.

## Corpus expérimental réel — RAG-007

Un cadre de 42 318 unités a permis de constituer **20 000 unités distinctes**,
stockées dans PostgreSQL local et identifiées par
`evaluation/local/rag007/corpus.json`. Le tirage aléatoire contient 10 000 unités,
le stratifié 13 103 ; leur recouvrement de 3 103 unités donne l’union finale.
Tous les quotas sont atteints ; les partitions par contribution et texte exact
sont conservées sans rééquilibrage artificiel.

Le [rapport RAG-007](rapport-rag-007.md) contient les statistiques et limites.
La [procédure de constitution](corpus-experimental.md) documente le plan réparti,
les commandes et la reprise. Les manifestes locaux sont ignorés par Git ; ils
ne sont pas intégrés à l’image publique. Cette étape n’installe aucun modèle.

## Recherche lexicale — RAG-008

Le moteur `cahier_rag.search.lexical` interroge exclusivement les 20 000 membres
du manifeste RAG-007. Il propose trois variantes : réponse seule (`answer`), avec
question (`question`), puis avec question et titre (`title`). PostgreSQL français,
`tsvector`, GIN et `ts_rank_cd` assurent la recherche, sans modèle ni LLM.

```bash
uv run --locked cahier-rag schema-upgrade --env-file .env.local
uv run --locked cahier-rag-search --env-file .env.local rebuild
uv run --locked cahier-rag-search --env-file .env.local search '"services publics"' --strategy answer
```

La CLI recherche en développement par défaut ; `--split all` choisit tout le
corpus explicitement. Les exports des 40 requêtes sont séparés par partition,
avec candidats non jugés et latences. Aucun score de qualité n’est disponible.
Voir [l’interface et les commandes](recherche-lexicale.md) et le
[rapport d’exécution](rapport-rag-008.md).

## Recherche lexicale souple — RAG-009

`FlexibleEngine` ajoute les correspondances partielles et un classement combinant
couverture, rareté des termes et fréquence/proximité. RAG-008 et ses exports restent
inchangés. Les mêmes vecteurs et le GIN sont réutilisés, sans migration.

```bash
uv run --locked cahier-rag-flex --env-file .env.local search 'Quelles propositions pour réduire la fraude fiscale ?'
uv run --locked cahier-rag-flex --env-file .env.local search '"services publics"' --method partial
```

Le CLI est limité au développement ; l’évaluation passe par un manifeste gelé et
un marqueur empêchant une relance accidentelle. Un pool de 400 paires de développement
reste à annoter humainement. Voir [les règles et commandes](recherche-souple.md) et
[le compte rendu RAG-009](rapport-rag-009.md). Aucun score de pertinence n’est calculé.

## Tests et qualité

Depuis `rag/` :

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m pytest tests/unit
```

Les tests unitaires utilisent une configuration synthétique et bloquent sockets,
résolution DNS et psycopg2. Ils vérifient les URL, les priorités de configuration,
les erreurs sans secrets, les moteurs paresseux, les transactions sources,
la fermeture sur erreur et les imports depuis un processus extérieur au dépôt.
Aucun serveur, modèle ou base de données n'est nécessaire.
La CI RAG est un workflow autonome sans service PostgreSQL, Docker ou GPU.

Pour toute la suite, `uv run --locked python -m pytest` ignore les intégrations
si `RAG_TEST_DATABASE_URL` est absent. Pour les exécuter sur une base dédiée,
**déjà migrée** avec les migrations du backend :

```bash
RAG_TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
RAG_STORAGE_TEST_DATABASE_URL=postgresql:///cahier_rag_test \
uv run --locked python -m pytest
```

La base doit porter un nom terminé par `_test` et être à la révision
`remove_runtime_caches`. Aucun repli sur les URL du backend. Les fixtures
insèrent puis retirent leurs seules données synthétiques ; aucune migration
ni création de table source n'est effectuée. Les tests de stockage appliquent
les migrations RAG sur la seconde base dédiée, également suffixée `_test`.
Les bases elles-mêmes ne sont jamais créées automatiquement. Ne jamais utiliser le corpus réel pour
ces tests d'écriture. Les tests utilisent les index, compteurs et contraintes
existants, sans `Base.metadata.create_all()`.

## Premiers fichiers et suite du projet

```text
rag/
├── .env.example              Variables d'exemple sans secret
├── .gitignore                Configuration locale et futurs artefacts
├── .python-version           Python 3.11
├── pyproject.toml            Package installable, dépendances, pytest et Ruff
├── uv.lock                   Verrou propre au RAG
├── src/cahier_rag/
│   ├── __init__.py           Package sans effets de bord
│   ├── __main__.py           Diagnostics et commandes locales
│   ├── config.py             Chargement et validation explicites
│   ├── db.py                 Moteurs et transaction source READ ONLY
│   ├── contracts.py          Unités, identité, empreintes et JSON
│   ├── sources/gdn.py        Adaptateur PostgreSQL et curseurs
│   ├── safety.py             Contrôle des identités réelles des bases
│   ├── schema.py             Tables SQLAlchemy Core du stockage
│   ├── extraction.py         Paramètres et versions d’extraction
│   ├── storage.py            Persistance atomique et restitution
│   ├── pipeline.py           Lecture, écriture et reprise
│   ├── evaluation/           Échantillons, jugements, métriques et CLI
│   ├── search/               Baseline lexicale et exports de classements
│   ├── migrate.py            Initialisation Alembic sécurisée
│   └── migrations/           Environnement et révisions autonomes
└── tests/
    ├── conftest.py            Environnement isolé
    ├── unit/                 Tests sans réseau, y compris contrat et lecteur
    └── integration/          PostgreSQL de test explicitement sélectionné
```

Les moteurs lexical, vectoriel et hybride locaux existent ; les embeddings
et les deux juges LLM utilisent des environnements optionnels séparés.
Le projet ne crée pas les bases : le schéma RAG est appliqué explicitement
à une base préexistante. Aucun reranker ni génération de réponses RAG n'est
implémenté. La recherche reste indépendante des LLM et de l'annotation.

L'audit RAG-001 est historique : sa recommandation pip/venv a été remplacée
par la décision uv de RAG-002. Les paramètres, contrats et migrations futurs
ne doivent pas importer `app.db`, `app.config` ou `app.models`.

Références : [cadrage](../docs/plan-rag.md), [audit](../docs/audit-rag.md),
[migration uv](../docs/migration-uv.md),
[transactions PostgreSQL SQLAlchemy](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#setting-read-only-deferrable),
[construction de packages uv](https://docs.astral.sh/uv/concepts/build-backend/).

## RAG-010 — Annotation humaine locale

Installer l'option web, indépendante des dépendances du moteur (mêmes versions
FastAPI/Uvicorn que le backend, sans importer `app`) :

```bash
cd rag
uv sync --locked --extra annotation --dev
export RAG_DATABASE_URL='postgresql:///cahier_rag'
uv run --locked --extra annotation cahier-rag-annotate --evaluator ro
```

Ouvrir **http://127.0.0.1:8765**. Un fichier explicitement choisi est aussi
possible : `--env-file .env`. Aucun `.env` n'est chargé automatiquement.
Le serveur écoute exclusivement sur `127.0.0.1`, sans proxy, sans journal
HTTP et sans connexion à la base source. `--port` permet de changer le port,
mais pas l'adresse d'écoute. Arrêter avec Ctrl+C.

Les 400 candidats sont validés contre le manifeste RAG-009, les requêtes et le
corpus RAG-007. Les sources restent inchangées. Les requêtes sont regroupées
par identifiant ; les documents sont ordonnés par SHA-256 de
`[graine, query_id, document_id]`, graine **20261020** par défaut (`--seed`).
Cette permutation déterministe est indépendante des méthodes et rangs.
Un changement de graine, d'évaluateur ou de données refuse la reprise.

L'écran présente une seule réponse intégrale, sa question, son questionnaire
et son titre. Les textes longs défilent dans une zone dédiée ; aucune troncature.
La contribution parente s'affiche à la demande : **uniquement ses unités déjà
présentes dans la base RAG**, potentiellement incomplètes, avec un plafond de
500 unités. Aucun accès complémentaire au corpus source. Aucun moteur, score,
rang ou statut de contrôle aléatoire n'est transmis à la page.

- Noter avec **0, 1, 2, 3** ou les boutons : sauvegarde, puis document suivant.
- Revenir avec **Précédent** ou les flèches gauche/droite ; sélectionner une
  requête dans la liste pour changer de groupe.
- Les raccourcis sont désactivés dans les champs de saisie.
- Une note existante se modifie en revenant au document puis en notant à nouveau.
- Le commentaire est sauvegardé après 700 ms d'inactivité, et avant chaque
  navigation. Sur un document déjà jugé, il modifie aussi la justification du
  jugement. Sur un document non jugé, il reste un brouillon, jamais une note.
- Le message **Enregistré sur disque** suit uniquement une sauvegarde réussie.
  En cas d'erreur, rester sur la page et réessayer ; la navigation est suspendue.
  La fermeture avec une saisie en cours provoque l'avertissement du navigateur.
  Une fermeture forcée peut perdre les caractères saisis depuis la dernière
  sauvegarde confirmée ; aucun navigateur ne garantit leur conservation.

### Persistance et export

`rag/evaluation/local/rag010/session.json` conserve ensemble jugements,
brouillons, curseur exact, graine, versions, empreintes et révision. Il est
**ignoré par Git**, créé en mode 0600, remplacé atomiquement après écriture et
`fsync`, puis synchronisation du dossier. L'ancien état mémoire est conservé
si une sauvegarde échoue. Un verrou de processus interdit deux serveurs CLI
simultanés ; une révision interdit les écritures d'un onglet obsolète. Une
seule session et un seul évaluateur sont pris en charge. Reprendre avec la
même commande : le curseur et les brouillons sont restaurés.

Le lien **Exporter les jugements JSON** télécharge une liste compatible avec
RAG-006, contenant seulement les couples effectivement notés :

```json
[{"query_id":"exemple","document_id":"text-unit:v1:corpus:open_answer:123:0","grade":2,"justification":null,"evaluator":"ro","judged_at":"2026-10-18T10:00:00+02:00","version":"rag010-v1"}]
```

Cet exemple est synthétique. Les identifiants documentaires restent des chaînes
et les identifiants BIGINT des documents sont sérialisés en chaînes décimales.
Un couple ne possède qu'un jugement courant ; la modification remplace sa
note et sa date. Aucun historique détaillé des modifications n'est conservé.
Sauvegarder le téléchargement dans `evaluation/local/rag010/judgments.json`,
puis utiliser ce fichier avec `cahier-rag-eval score --help` (options
`--judgments`, `--results`, `--sample`, `--queries`, `--output`, `--k`).
Par exemple, avec un classement de développement RAG-009 :

```bash
uv run --locked cahier-rag-eval score \
  --sample evaluation/local/rag007/corpus.json \
  --queries evaluation/queries.json \
  --judgments evaluation/local/rag010/judgments.json \
  --results evaluation/local/rag009/development/weighted-answer/results.json \
  --output evaluation/local/rag010/metrics.json --k 10
```

Les brouillons et documents non jugés sont exclus, distincts de la note zéro.
L'export relit l'état sauvegardé en mémoire, sans lancer d'évaluation automatique.
Ne pas placer les annotations ou des textes réels dans un dossier versionné.

### Contrôles

```bash
uv run --locked --extra annotation pytest
uv run --locked --extra annotation ruff check .
uv lock --check
```

Les tests HTTP utilisent des données synthétiques et `httpx` (groupe `dev`).
Sans l'option `annotation`, ces tests sont ignorés ; le moteur reste utilisable
sans FastAPI. Les intégrations PostgreSQL restent conditionnées aux bases de
test dédiées décrites plus haut. Les contrôles du pool réel sont en lecture
seule et ne créent aucun jugement dans la session réelle.

Les protections locales combinent client loopback, hôte exact, origine,
Fetch Metadata, jeton anti-CSRF, CSP, interdiction d'intégration dans une frame
et absence de cache. Les textes sont injectés via `textContent`, jamais comme
HTML. Il ne s'agit pas d'une application multiutilisateur : les processus de
la même machine et les extensions du navigateur restent dans le périmètre de
confiance. Voir aussi la [documentation FastAPI sur les middlewares](https://fastapi.tiangolo.com/advanced/middleware/).

## RAG-011 — Préparations documentaires sans modèle

Quatre stratégies versionnées sont disponibles : **A** réponse seule, **B**
question + réponse, **C** même texte que B avec récupération du parent, **D**
enrichissement expérimental des réponses courtes par leurs voisins. La segmentation
conserve des positions et chevauchements en caractères dans le texte original.
Les textes et contrats sources ne changent pas.

La politique de contexte est limitée aux **20 000 unités RAG-007**, parents et
voisins compris, dans la même contribution et partition. Les autres unités
stockées ne sont pas utilisées. Aucun modèle ou schéma supplémentaire n’est créé.

Depuis `rag/`, pour conserver l’environnement de l’annotation en cours :

```bash
export RAG_DATABASE_URL='postgresql:///cahier_rag'
uv run --locked --no-sync python -m cahier_rag.representations.cli generate \
  --strategy D --limit 512 --batch-size 25 \
  --output evaluation/local/rag011/mon-essai-D
uv run --locked --no-sync python -m cahier_rag.representations.cli inspect \
  evaluation/local/rag011/mon-essai-D
uv run --locked --no-sync python -m cahier_rag.representations.cli verify \
  evaluation/local/rag011/mon-essai-D --batch-size 7
```

Une limite explicite et un nouveau dossier sont obligatoires. Les sorties JSONL
contenant les textes restent locales et ignorées par Git. Aucun jugement ni
fichier de session RAG-010 n’est lu ou modifié. Le point d’entrée
`cahier-rag-prepare` sera disponible à la prochaine synchronisation du projet ;
les commandes ci-dessus fonctionnent déjà sans synchronisation.

Voir les [règles et contrats détaillés](representations-documentaires.md) et le
[rapport des essais réels RAG-011](rapport-rag-011.md). Les budgets actuels portent
sur la réponse en caractères ; ils devront être adaptés au tokenizer du futur
modèle avant toute vectorisation.

## RAG-012 — Modèles d’embedding locaux optionnels

Le moteur interchangeable propose **multilingual E5-small**, **BGE-M3 dense** et
**Qwen3-Embedding-0.6B**, avec révisions fixées. Les modèles sont chargés
explicitement ; l’inférence est hors ligne. Les fenêtres sont vérifiées avec les
tokenizers réels, préfixes inclus, avec refus des entrées trop longues.

Pour préserver l’annotation, installer les dépendances GPU dans un environnement
**distinct** ; ne pas resynchroniser `rag/.venv/` :

```bash
cd rag
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv \
  uv sync --locked --extra embeddings --dev
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli list
```

Les téléchargements explicites des poids, la préparation du plan commun et les
commandes de benchmark sont détaillés dans [embeddings-locaux.md](embeddings-locaux.md).
Les dépendances du backend public restent inchangées. Les fichiers de modèle,
les matrices et les manifestes de mesure restent locaux et ignorés par Git.
Aucun index vectoriel n’est créé et les 20 000 documents ne sont pas encodés.

Les mesures réelles des trois modèles sur **RTX 5090 et CPU** sont présentées
dans [le rapport RAG-012](rapport-rag-012.md). Elles décrivent fonctionnement,
ressources et coût, sans établir de classement de pertinence sur le Grand Débat.

### Recherche vectorielle locale — RAG-013

BGE-M3 dense et la représentation B peuvent être préparés, encodés avec reprise,
puis recherchés exactement via pgvector, sur le seul corpus RAG-007. Voir
[les commandes, garanties et migrations](recherche-vectorielle.md). Les dépendances
ML restent dans l'environnement optionnel ; l'annotation ne change pas.
Le [compte rendu RAG-013](rapport-rag-013.md) décrit l'index réel de 20 000 unités,
les mesures finales et les validations exécutées.

### Recherche hybride — RAG-014

La [fusion RRF locale](recherche-hybride.md) combine le lexical pondéré RAG-009
et BGE-M3 RAG-013, avec diagnostics par moteur et un pool complémentaire non jugé.
Elle conserve les index et la session d'annotation existants. Voir le
[compte rendu des expériences](rapport-rag-014.md).

## RAG-015 — Campagnes indépendantes et suivi des jugements

La campagne RAG-010 conserve ses fichiers et sa commande historique. Une seconde
campagne peut être créée puis ouverte explicitement, sans mélanger les sessions :

```bash
# Depuis rag/, environnement d'annotation existant :
.venv/bin/python -m cahier_rag.annotation.campaign_cli list
.venv/bin/python -m cahier_rag.annotation.campaign_cli create --campaign rag014 --evaluator ro
export RAG_DATABASE_URL=postgresql:///cahier_rag
.venv/bin/python -m cahier_rag.annotation.campaign_cli open --campaign rag014
```

La commande de création ne lance aucun serveur. Pour reprendre la première
campagne, utiliser `open --campaign rag010`, ou la commande RAG-010 habituelle.
Les [commandes de consolidation, rapports et règles méthodologiques](campagnes-annotation.md)
préservent les sessions sources et distinguent non-jugés, conflits et notes zéro.
Voir le [premier bilan réel RAG-015](rapport-rag-015.md).

## Deux juges LLM locaux — RAG-016

L'annotation automatique dispose d'un environnement optionnel séparé, de deux
checkpoints Qwen3 officiels (8B et 14B), de prompts figés et d'un cache reprenable.
Elle ne modifie aucune annotation humaine. L'inférence reste hors ligne et
les campagnes de 800 couples nécessitent une activation explicite après examen
de la calibration. Voir [la procédure et les limites](juges-locaux.md) et
[le bilan réel des deux juges](rapport-rag-016.md).

## Évaluation automatique approfondie — RAG-017

Le protocole `relevance-fr-v2` évalue l'adéquation à l'intention sans récompenser
la longueur. Le pool de 2 500 couples conserve les top 50 gelés, avec un
enrichissement déterministe aux rangs suivants. Les deux juges locaux restent
indépendants, sans fusion avec les notes humaines. Les commandes de préparation,
précontrôle, annotation reprenable et rapports sont dans
[la procédure v2](evaluation-llm-v2.md). Le
[bilan réel RAG-017](rapport-rag-017.md) présente les métriques et limites :
4 997 jugements valides sur 5 000, avec trois sorties 14B invalides conservées
comme telles, sans assimilation à une note zéro.

## Baseline BM25 — RAG-018

Deux index inversés CPU sur disque comparent réponse seule et réponse + question,
avec une formule BM25 explicite et des statistiques séparées par partition.
Les moteurs historiques restent inchangés. Voir les
[commandes et choix techniques](recherche-bm25.md) et le
[rapport comparatif réel](rapport-rag-018.md), incluant les annotations
complémentaires indépendantes et les limites des jugements LLM.

## Comparaison des hybrides — RAG-019

L'extension RRF multi-source compare H1 à H5, avec poids et profondeur figés,
sans modifier les moteurs historiques. Les classements sources sont mutualisés,
les traces conservent chaque contribution et un rejeu CPU fonctionne sans modèle.
Voir [la procédure](recherche-multi-hybride.md) et
[le bilan comparatif](rapport-rag-019.md). Aucun nouveau jugement n'était
nécessaire : les 2 673 couples cibles sont déjà référencés dans RAG-017/018.

### RAG-020 — Reranking local

Deux rerankers optionnels reclassent les top 50 gelés H1/H5/V, sur le développement uniquement. Installation, préparation, reprise, mesures CPU/GPU et conventions de comparaison : [reranking-local.md](reranking-local.md). Les poids et caches restent locaux ; les moteurs et l'annotation humaine restent indépendants.

### RAG-021 — Construction du contexte documentaire

L'assembleur `cahier_rag.context` prépare des sources citées depuis les classements RAG-020, avec sélection S1/S2/S3, modes parentaux P0/P1/P2, extraits exacts et budgets vérifiés par tokenizer réel. Aucune génération ni inférence de modèle. Voir [contexte-documentaire.md](contexte-documentaire.md) pour les contrats, citations, commandes et limites, puis [rapport-rag-021.md](rapport-rag-021.md) pour les essais.

### RAG-022 — Première génération sourcée

Qwen3-14B local réutilise les contextes gelés H1+R2/S2/P1/8192 via une présentation compacte, avec références résolues, citations littérales contrôlées et cache indépendant. Voir [generation-locale.md](generation-locale.md) pour le pilote, la campagne, l'audit et les limites : validité structurelle ne signifie pas fidélité sémantique.

### RAG-023 — Décodage contraint

L'expérience `generation.constrained` utilise LM Format Enforcer avec le modèle, le prompt v2 et les entrées gelées RAG-022. Le validateur original reste obligatoire. Voir [decodage-contraint.md](decodage-contraint.md) pour les schémas versionnés, limites, commandes et reprises ; [rapport-rag-023.md](rapport-rag-023.md) pour la comparaison structurelle et les coûts, sans conclusion de fidélité sémantique.

### RAG-024 — Audit ciblé de fidélité

Le [rapport d’audit](rapport-rag-024.md) compare les dix-sept réponses communes v2/v3 et prépare les priorités RAG-025. Les observations détaillées restent locales sous `evaluation/local/rag024/`. Lecture assistée par Codex, sans inférence ni validation humaine indépendante ; aucun générateur modifié.

### RAG-025 — RAG personnel local

L’interface de questions libres combine H1, le reranker Qwen3-4B et Qwen3-14B sur les 20 000 unités. Voir [personnel.md](personnel.md) pour démarrer et arrêter le service local, et [rapport-rag-025.md](rapport-rag-025.md) pour les corrections, les essais et les limites de fidélité.

## Corpus complet local

RAG-026 : [résultats, performances et limites](rapport-rag-026.md),
[commandes et reprise](corpus-complet.md). Le corpus expérimental reste le défaut
de l’interface personnelle ; le corpus complet se sélectionne explicitement.
