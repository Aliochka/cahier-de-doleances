# Vérifications du projet

Les tests utilisent les sources synthétiques et PostgreSQL, sans navigateur
ni téléchargement des exports nationaux. Ruff vérifie le Python du dépôt ;
les imports des migrations historiques sont conservés. Sa configuration est
dans [ruff.toml](ruff.toml), suivant la
[documentation officielle](https://docs.astral.sh/ruff/configuration/).

## Installer les outils

Après l'installation décrite dans le README :

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check app ingest scripts tests migrations/env.py
uv run --locked python -m pytest
```

Le seul `.venv` racine inclut aussi les dépendances CPU de H1 (PyTorch et
Transformers) : les tests de packaging ne nécessitent pas un autre environnement.
Le RAG expérimental conserve `rag/.venv`.

Sans base de test configurée, les tests PostgreSQL sont signalés comme
ignorés. Les tests des lecteurs JSON/CSV, de reprise HTTP et de transformation
des réponses s'exécutent sans connexion à PostgreSQL ni accès réseau.
Les tests `unittest` d'ingestion peuvent aussi être lancés seuls :

```bash
uv run --locked python -m unittest discover -s tests/ingest -v
```

## Exécuter tous les tests sur une base séparée

Créer une base de test vide avec le rôle PostgreSQL local configuré dans le
README. Appliquer les **vraies migrations** ; `Base.metadata.create_all()`
ne crée pas les index et triggers nécessaires à la recherche et aux compteurs.

```bash
createdb cahier_doleances_test
ALEMBIC_DATABASE_URL=postgresql:///cahier_doleances_test uv run --locked alembic upgrade head
# Une seule fois, si .env.test n'existe pas encore :
cp -n .env.test.example .env.test
uv run --locked python -m pytest
```

Pytest lit automatiquement `.env.test` (ignoré par Git), uniquement pour
`TEST_DATABASE_URL` et `GDN_IMPORT_TEST_DATABASE_URL`. Adapter ces URL si
PostgreSQL nécessite un hôte ou des identifiants. Les variables exportées
explicitement priment sur ce fichier. Les noms des bases doivent finir par `_test`.

L'application ne lit pas `.env.test` et ignore `TEST_DATABASE_URL` pour ses
connexions : elle utilise `DATABASE_URL`. C'est pytest qui sélectionne la base
de test avant d'importer les modules applicatifs. Sans base de test configurée,
les tests concernés sont ignorés et aucun repli vers la base locale réelle
n'est effectué. `ALEMBIC_DATABASE_URL` reste réservé à la commande de migration
explicite ci-dessus ; aucune migration n'est lancée au démarrage des tests.

La suite conserve les 21 cas d'ingestion et de consultation et ajoute des
régressions de configuration, de sécurité et d'authentification.
Elle vérifie les limites des fichiers JSON, la reprise des téléchargements,
les caractères nuls, les choix multiples et textes « autre », la réimportation,
les compteurs, la pagination sans perte ni doublon, les statistiques sans cache,
le rendu français et les liens de partage statiques, les sitemaps utilisant
l'origine configurée, les cookies HTTP/HTTPS, les comptes, profils et marque-pages,
la sérialisation JSON sûre et les contrôles de schéma en lecture seule.

Les fixtures HTTP partagent une connexion avec des savepoints et remplacent
les fabriques de sessions réellement utilisées par les routes. Même si une
route ou un test appelle `commit()`, la transaction extérieure est annulée en
fin de test. Le test d'import utilise également une transaction annulée.
Les séquences d'identifiants peuvent avancer ; aucune contribution de test
n'est conservée.

## Automatisation

La CI exécute Ruff, le contrôle de formatage, les migrations sur PostgreSQL 17
et toute la suite avec Python 3.11. Le fichier `.pre-commit-config.yaml`
fournit les hooks Ruff ; aucune installation de navigateur n'est requise.

Les anciens tests et leur infrastructure ont été audités dans
[docs/nettoyage-repo.md](docs/nettoyage-repo.md).

La CI utilise uv 0.13.1 et `uv sync --locked --dev` : un verrou absent ou
incohérent fait échouer l'installation. `uv lock --check` vérifie le verrou
sans le modifier. `.venv/` contient le backend et ses outils de développement.
Les anciens notebooks et analyses NLP restent hors de cet environnement ;
aucune dépendance GPU n'est nécessaire aux tests.

La CI construit aussi l'image de production, vérifie l'absence des outils de
développement et de uv dans cette image, puis démarre le conteneur avec les
restrictions de sécurité et vérifie `/healthz` contre PostgreSQL de test.
Ces étapes nécessitent Docker ; elles ne se connectent jamais à Wallace.
