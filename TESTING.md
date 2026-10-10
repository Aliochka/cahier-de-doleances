# Vérifications du projet

Les tests utilisent les sources synthétiques et PostgreSQL, sans navigateur
ni téléchargement des exports nationaux. Ruff vérifie le Python du dépôt ;
les imports des migrations historiques sont conservés. Sa configuration est
dans [ruff.toml](ruff.toml), suivant la
[documentation officielle](https://docs.astral.sh/ruff/configuration/).

## Installer les outils

Après l'installation décrite dans le README :

```bash
source venv/bin/activate
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check app ingest scripts tests migrations/env.py
python -m pytest
```

Sans base de test configurée, les tests PostgreSQL sont signalés comme
ignorés. Les tests des lecteurs JSON/CSV, de reprise HTTP et de transformation
des réponses s'exécutent sans connexion à PostgreSQL ni accès réseau.
Les tests `unittest` d'ingestion peuvent aussi être lancés seuls :

```bash
python -m unittest discover -s tests/ingest -v
```

## Exécuter tous les tests sur une base séparée

Créer une base de test vide avec le rôle PostgreSQL local configuré dans le
README. Appliquer les **vraies migrations** ; `Base.metadata.create_all()`
ne crée pas les index et triggers nécessaires à la recherche et aux compteurs.

```bash
createdb cahier_doleances_test
ALEMBIC_DATABASE_URL=postgresql:///cahier_doleances_test alembic upgrade head
TEST_DATABASE_URL=postgresql:///cahier_doleances_test GDN_IMPORT_TEST_DATABASE_URL=postgresql:///cahier_doleances_test python -m pytest
```

`ALEMBIC_DATABASE_URL` et les variables de test sont définies uniquement pour
la commande qui suit : elles ne modifient pas la base utilisée ensuite par
le serveur. Ne pas exporter `TEST_DATABASE_URL` dans le terminal du serveur,
car l'application donne priorité à cette variable pour ses connexions.

La suite comprend 21 cas : 11 pour l'ingestion et 10 pour l'application.
Elle vérifie les limites des fichiers JSON, la reprise des téléchargements,
les caractères nuls, les choix multiples et textes « autre », la réimportation,
les compteurs, la pagination sans perte ni doublon, les statistiques sans cache,
le rendu français et les liens de partage statiques, et les sitemaps par hôte.

Les fixtures HTTP partagent une connexion avec des savepoints et remplacent
les fabriques de sessions réellement utilisées par les routes. Même si une
route ou un test appelle `commit()`, la transaction extérieure est annulée en
fin de test. Le test d'import utilise également une transaction annulée.
Les séquences d'identifiants peuvent avancer ; aucune contribution de test
n'est conservée.

## Automatisation

La CI exécute Ruff, le contrôle de formatage, les migrations sur PostgreSQL 15
et toute la suite avec Python 3.11. Le fichier `.pre-commit-config.yaml`
fournit les hooks Ruff ; aucune installation de navigateur n'est requise.

Les anciens tests et leur infrastructure ont été audités dans
[docs/nettoyage-repo.md](docs/nettoyage-repo.md).

Les notebooks et analyses facultatives ont leurs propres dépendances dans
`requirements-analysis.txt` (Python 3.11 ou supérieur). Elles ne sont pas
nécessaires pour lancer le site, importer les données ou exécuter les tests.
