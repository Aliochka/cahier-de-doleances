# RAG-002 — Migration du backend vers uv

Compte rendu du 17 octobre 2026. Migration locale uniquement, sans commit ni
push, sans intervention sur Wallace et sans création du dossier `rag/`.

## Fichiers créés, modifiés et supprimés

Créés :

- [`pyproject.toml`](../pyproject.toml) : projet backend et groupes de dépendances.
- [`uv.lock`](../uv.lock) : versions transitives, marqueurs de plateforme et empreintes.
- Le présent compte rendu.

Modifiés :

- [`Dockerfile`](../Dockerfile) : installation verrouillée dans une étape dédiée.
- [`.dockerignore`](../.dockerignore) : exclusion des environnements, caches,
  frontend et futurs artefacts RAG du contexte backend.
- [`.gitignore`](../.gitignore) : caches uv locaux ; `.venv/` était déjà ignoré,
  y compris dans les sous-dossiers.
- [`.github/workflows/test.yml`](../.github/workflows/test.yml) : uv, installation
  stricte, commandes Python et recette Docker en CI.
- [`.github/workflows/contract.yml`](../.github/workflows/contract.yml) : uv et
  détection des modifications du manifeste/verrou backend.
- [`frontend/package.json`](../frontend/package.json) : seuls les appels Python
  d'export du contrat passent par uv ; pnpm et les dépendances frontend restent
  inchangés.
- [`scripts/check-alignment.sh`](../scripts/check-alignment.sh) : exécution avec uv.
- [`readme.md`](../readme.md), [`TESTING.md`](../TESTING.md),
  [`frontend/README.md`](../frontend/README.md),
  [`docs/ingestion.md`](ingestion.md),
  [`docs/postgresql-local-17.md`](postgresql-local-17.md),
  [`docs/nettoyage-repo.md`](nettoyage-repo.md),
  [`docs/deploiement.md`](deploiement.md) : commandes et procédures actualisées.

Supprimés : `requirements.txt` et `requirements-dev.txt`. Aucun consommateur
actif exigeant ces fichiers n'a été identifié dans la cible Docker et les
workflows maintenus. `scripts/gen_requirements.py` et
`requirements-analysis.txt`, déjà supprimés avant cette tâche, n'ont pas été
recréés. Les rapports d'audit antérieurs restent des constats historiques.

Aucun code métier, modèle SQLAlchemy, migration Alembic, fichier Compose,
Caddyfile, secret ou paramètre de production modifié.

## Organisation des dépendances

- Python **3.11**, avec `requires-python = ">=3.11,<3.12"` et `.python-version`
  inchangé.
- uv **0.13.1**, version exigée dans le projet et utilisée en CI et dans Docker.
- Projet non empaqueté (`package = false`) pour conserver l'exécution depuis
  la racine et les imports existants `app` et `ingest`.
- Les **15 déclarations de production** ont conservé leurs versions, y compris
  PyYAML et python-slugify nécessaires à l'ingestion.
- Groupe `dev` : pytest 9.1.1, httpx 0.28.1 et Ruff 0.17.0. Aucun outil de
  couverture n'était présent dans les dépendances de développement existantes.
- Aucune dépendance GPU, NLP ou de notebook ajoutée.
- Aucun workspace uv : le futur projet RAG pourra disposer de son propre
  manifeste, verrou et environnement.

Le premier verrou généré sélectionnait quatre transitives plus récentes que
l'ancien environnement. dnspython, greenlet, pluggy et websockets ont été
ramenés à leurs versions déjà installées. Sur Linux, les **46 distributions**
installées dans le nouvel environnement de développement ont ainsi les mêmes
versions que dans l'ancien `venv/`. Ce constat ne décrit pas une ancienne
image Wallace, qui n'a pas été inspectée.

## Commandes principales

Après installation de uv 0.13.1 suivant le README :

```bash
uv python install 3.11
uv sync --locked --dev
uv lock --check
uv run --locked ruff check .
uv run --locked ruff format --check app ingest scripts tests migrations/env.py
uv run --locked python -m pytest
uv run --locked uvicorn app.app:app --host 127.0.0.1 --port 8000 --reload
uv run --locked alembic current
uv run --locked python scripts/export_openapi.py --check
```

Pour les intégrations, utiliser exclusivement une base de test migrée :

```bash
TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
GDN_IMPORT_TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
uv run --locked python -m pytest
```

Pour installer uniquement la production :

```bash
uv sync --locked --no-dev
uv run --locked --no-dev uvicorn app.app:app --host 127.0.0.1 --port 8000
```

Le groupe `dev` est inclus par défaut ; conserver `--no-dev` sur `uv run` pour
ne pas le réinstaller après une synchronisation de production.

Les commandes d'ajout, de suppression, de mise à jour ciblée et d'export
facultatif d'un requirements dérivé sont documentées dans le README.

## Docker et CI

Le Dockerfile conserve la base `python:3.11-slim-bookworm`. Une étape copie uv
depuis `ghcr.io/astral-sh/uv:0.13.1`, puis exécute :

```text
uv sync --locked --no-dev --no-install-project --no-cache
```

L'environnement `/opt/venv` est copié dans l'image finale. uv reste dans
l'étape de construction. Le démarrage Gunicorn avec deux workers, le chemin
de travail, l'utilisateur non privilégié, le port et les copies de code restent
inchangés. Le `PATH` utilise l'environnement installé. Les commandes
`python -m app.deployment_check` continuent de s'utiliser sans uv dans l'image.

La CI conserve Python 3.11, PostgreSQL 17, Alembic, Ruff et pytest. Les deux
workflows Python installent uv avec une action référencée par SHA et utilisent
le verrou en mode strict. Le workflow frontend autonome reste inchangé ;
seule l'intégration Python du workflow contrat est adaptée.

La CI backend comprend désormais une construction Docker, un contrôle de
l'absence de uv et des dépendances de développement/GPU, puis un démarrage
avec système de fichiers en lecture seule, `/tmp` temporaire, capacités
retirées et contrôle HTTP de `/healthz` sur la base PostgreSQL de CI.

Références officielles consultées :
[Docker et uv](https://docs.astral.sh/uv/guides/integration/docker/),
[GitHub Actions et uv](https://docs.astral.sh/uv/guides/integration/github/).

## Résultats des validations locales

| Vérification | Résultat |
|---|---|
| Référence avant migration, ancien `venv/` Python 3.10.12 | 321 tests réussis, 7 sous-tests réussis, 3 avertissements |
| Installation propre de `.venv/` avec uv | Réussie, Python 3.11.17 |
| Vérification `uv lock --check` | Réussie |
| Versions installées comparées à l'ancien environnement | 46 sur 46 identiques |
| Ruff lint | Réussi |
| Ruff format | 72 fichiers conformes |
| Suite avec le verrou final et PostgreSQL 17.11 de test | 321 tests réussis, aucun ignoré, 7 sous-tests réussis |
| Alembic `current` et `heads` | `remove_runtime_caches (head)` |
| Alembic `upgrade head` sur la base de test | Réussi ; base déjà à jour, aucune nouvelle migration appliquée |
| Export OpenAPI en mode vérification | Réussi, snapshot inchangé |
| `pnpm contract:check` depuis `frontend/` | Réussi, schéma et types inchangés |
| CLI ingestion | Aides de `ingest.sources`, `ingest.structured_sources` et `ingest.postgres` exécutées sans import de corpus |
| Installation propre du profil production sans cache | Réussie, 39 distributions issues du verrou de production |
| Imports dans le profil production | FastAPI, SQLAlchemy, Alembic, psycopg2 et uvicorn-worker disponibles ; outils dev/GPU absents |
| Démarrage Gunicorn hors Docker, profil production | Deux workers ; `/healthz` et recherche API répondent 200 sur la base de test |
| Workflows modifiés | YAML, syntaxe Bash et script Python de recette vérifiés localement |
| Export requirements dérivé dans `/tmp` | Réussi ; aucun requirements généré dans le dépôt |
| Construction et démarrage Docker | Non exécutés : Docker absent de cet environnement |
| Exécution GitHub Actions | Non exécutée localement ; aucun push demandé |

Les trois avertissements existaient avant migration : dépréciation du client
de test Starlette/httpx et identifiants OpenAPI dupliqués pour les routes SEO.
Ils n'ont pas été corrigés dans cette tâche de dépendances.

L'ancien environnement actif se nommait `venv/`. uv signale qu'il l'ignore au
profit de `.venv/`, ce qui est attendu ; `deactivate` supprime cet avertissement.
Pour les validations, uv et le Python géré ont été installés sous `/tmp`, sans
installation globale ni modification du profil shell. Pour l'usage durable,
installer uv et Python selon le README puis refaire `uv sync --locked`.

## Limites et prochain déploiement

La migration est implémentée et les validations locales sont concluantes.
La recette Docker reste nécessaire avant de considérer le build de production
validé. Le démarrage hors Docker ne vérifie ni l'image Debian finale, ni la
copie entre étapes, ni les restrictions du conteneur.

Le verrou fixe les distributions Python et leurs empreintes ; les tags des
images Python et uv ne sont pas des digests immuables. Une reconstruction
n'est donc pas garantie identique octet pour octet. Les registres d'images et
les distributions verrouillées doivent rester accessibles au build.

Les fichiers historiques Scalingo ne sont pas une cible validée de cette
migration. Aucun requirements de compatibilité n'est maintenu pour eux.
Les notebooks et analyses NLP historiques restent hors du projet backend.

La procédure Wallace et ses précontrôles restent décrits dans
[deploiement.md](deploiement.md). Aucune recette ni mise en service n'a été
effectuée sur Wallace et aucune donnée du Grand Débat n'a été modifiée.
