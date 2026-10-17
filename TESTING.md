# Vérifications du projet

Les tests utilisent les sources synthétiques et PostgreSQL, sans navigateur
ni téléchargement des exports nationaux. Ruff vérifie le Python du dépôt ;
les imports des migrations historiques sont conservés. Sa configuration est
dans [ruff.toml](ruff.toml), suivant la
[documentation officielle](https://docs.astral.sh/ruff/configuration/).

## Installer les outils

Après l'installation décrite dans le README :

```bash
uv sync --locked --dev
uv run --locked ruff check .
uv run --locked ruff format --check app ingest scripts tests migrations/env.py
uv run --locked python -m pytest
```

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
TEST_DATABASE_URL=postgresql:///cahier_doleances_test GDN_IMPORT_TEST_DATABASE_URL=postgresql:///cahier_doleances_test uv run --locked python -m pytest
```

`ALEMBIC_DATABASE_URL` et les variables de test sont définies uniquement pour
la commande qui suit : elles ne modifient pas la base utilisée ensuite par
le serveur. Ne pas exporter `TEST_DATABASE_URL` dans le terminal du serveur,
car l'application donne priorité à cette variable pour ses connexions.

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
