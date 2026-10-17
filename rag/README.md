# Socle autonome du RAG — RAG-003

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
- Aucun PostgreSQL, Docker, GPU ou accès réseau requis pour les tests et les
  diagnostics une fois les dépendances installées.

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
python-dotenv 1.2.4, aux mêmes versions que le backend. Elles permettent les
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
| `RAG_DATABASE_URL` | Future base expérimentale distincte | Lors d'une opération RAG |

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
Privilégier des destinations explicites et vérifier les rôles avant tout futur
traitement. Une base logique distincte n'isole pas les ressources physiques
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

Pour le futur stockage expérimental, utiliser le moteur RAG et ses transactions
explicites (`engine.begin()`), puis `engine.dispose()`. Aucun schéma, requête
documentaire ou traitement d'écriture n'est fourni pour le moment.

La protection source devra aussi reposer sur un **rôle PostgreSQL limité à la
lecture**, sans droits de création ni d'écriture sur les tables du corpus.
Ce rôle n'est ni créé ni vérifié ici. Les options de transaction ne remplacent
pas les privilèges du serveur. Cette tâche ne vérifie aucune connexion réelle.

## Tests et qualité

Depuis `rag/` :

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m pytest
```

Les tests utilisent une configuration synthétique et bloquent sockets,
résolution DNS et psycopg2. Ils vérifient les URL, les priorités de configuration,
les erreurs sans secrets, les moteurs paresseux, les transactions sources,
la fermeture sur erreur et les imports depuis un processus extérieur au dépôt.
Aucun serveur, modèle ou base de données n'est nécessaire.
La CI RAG est un workflow autonome sans service PostgreSQL, Docker ou GPU.

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
│   ├── __main__.py           Diagnostic CLI sans connexion
│   ├── config.py             Chargement et validation explicites
│   └── db.py                 Moteurs et transaction source READ ONLY
└── tests/
    ├── conftest.py            Environnement isolé et réseau interdit
    └── unit/                 Configuration, CLI, connexions et isolation
```

Le moteur de recherche n'existe pas encore. Aucun modèle d'embedding n'est
installé, aucun LLM n'est intégré, aucune base RAG n'a été créée par cette
tâche et aucune indexation du corpus n'a été effectuée. Il n'y a ni lecteur
documentaire, ni contrat documentaire définitif, ni table, migration, extension
vectorielle, serveur HTTP, échantillon ou jeu d'évaluation.

RAG-004 précisera le contrat documentaire et le lecteur PostgreSQL source.
Les modules `contracts`, `sources`, `indexing`, `search`, `reranking`,
`generation` et `evaluation` seront introduits seulement lorsqu'ils auront un
contenu utile. La recherche devra rester indépendante de la génération LLM.

L'audit RAG-001 est historique : sa recommandation pip/venv a été remplacée
par la décision uv de RAG-002. Les paramètres, contrats et migrations futurs
ne doivent pas importer `app.db`, `app.config` ou `app.models`.

Références : [cadrage](../docs/plan-rag.md), [audit](../docs/audit-rag.md),
[migration uv](../docs/migration-uv.md),
[transactions PostgreSQL SQLAlchemy](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#setting-read-only-deferrable),
[construction de packages uv](https://docs.astral.sh/uv/concepts/build-backend/).
