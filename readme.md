> Interface web : React dans `frontend/`. FastAPI fournit les routes JSON
> `/api/v1`, l’authentification, les opérations de marque-pages, la santé et le SEO.
> Le backend ne sert plus de pages HTML ni de fichiers `/static`.
> Le proxy de production doit envoyer les pages vers le serveur React ; les
> configurations de déploiement FastAPI seules ne servent que le backend.

# Cahier de doléances

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()

> **Vision** : *Un pas de plus vers la révolution.*

## Déploiement sur une base PostgreSQL existante

Pour Wallace (`http://192.168.1.56:8000`), suivre le
[guide de déploiement](docs/deploiement.md). Il utilise `compose.deploy.yml`,
avec FastAPI uniquement, et préserve le PostgreSQL 17 existant. Les instructions
d'installation depuis zéro ci-dessous concernent une **base locale neuve** et
ne doivent pas être appliquées à la base restaurée du serveur.

---

## 🚀 Objectif du projet

Cahier de doléances est un site/service permettant d’explorer, rechercher et analyser les contributions citoyennes du **Grand Débat National**.  
L’idée : donner un accès simple et puissant à cette matière brute, pour nourrir les réflexions et ouvrir la voie à de nouvelles perspectives collectives.

Gros merci a chat gpt qui a codé l'ultra majorité de ce que vous voyez !




---

## 🗺️ Roadmap v0

- [x] Mise en place du backend (FastAPI + SQLite pour démarrage local)  
- [x] Ingestion massive des contributions (CSV compressés)  
- [x] Indexation plein texte (FTS5) pour recherche rapide  
- [x] Front-end minimaliste mobile-first
  - [x] ui
  - [ ] page accueil
    - [x] back
    - [ ] ux
    - [ ] ui
    - [ ] contenu
  - [x] page question
    - [x] back
    - [x] ux
    - [x] ui
  - [x] page auteur
    - [x] back
    - [x] ux
    - [x] ui
  - [x] recherche par question
    - [x] back
    - [x] ux
    - [x] ui
    - [x] optimisation
  - [x] recherche par réponses
    - [x] back
    - [x] ux
    - [x] ui
    - [x] optimisation
- [x] migration postgresql
- [x] MEP !

## V0+

- [x] page formulaire
- [ ] bugs
  - [x]  page answer contenu responsive
- [x] SEO technique
- [x] perf page question
- [x] rework page question
- [x] check bdd (questions sans réponses ?)

 
## v1
- [ ] optimisations SEO
- [ ] ux/ui 
  - [x] refaire le _card answer
  - [ ] navigation
  - [ ] pagination (loader)
- [ ] page thème
- [ ] mentions légales
- [ ] footer
- [ ] menu joli
- [ ] quelques tests bien pensés
- [ ] logo
- [ ] accueil

## v2
- [ ] secret secret




---

## 🛠️ Guide pour les développeurs

### Scripts utiles

#### Vérification de l'alignement modèles/BDD

Pour s'assurer que les modèles SQLAlchemy sont alignés avec la structure PostgreSQL :

```bash
# Via script shell (charge automatiquement DATABASE_URL depuis .env)
./scripts/check-alignment.sh

# Ou directement via Python
uv run --locked python scripts/check_model_alignment.py
```

Ce script compare automatiquement :
- Les tables présentes
- Les colonnes et leurs types
- Les contraintes de clés étrangères
- Ignore les tables et colonnes générées automatiquement (Alembic, triggers FTS)
- Charge la configuration depuis le fichier .env

Pour migrer une installation locale existante de PostgreSQL 14 vers 17, suivre
[la procédure de migration](docs/postgresql-local-17.md).

### 1. Installation depuis zéro (Ubuntu / Debian)

Le site utilise **FastAPI, SQLAlchemy et PostgreSQL**. La procédure ci-dessous
lance une instance locale avec une base sans contributions citoyennes.
Python 3.11 est la référence, fixée par `.python-version` et `pyproject.toml`.
PostgreSQL 17 est utilisé pour les tests et sur Wallace.

#### Installer les outils système

Dans votre terminal, installer Git, PostgreSQL et ses extensions :

```bash
sudo apt-get update
sudo apt-get install -y git postgresql postgresql-contrib curl
sudo systemctl start postgresql
pg_isready
```

`pg_isready` doit indiquer que PostgreSQL accepte les connexions.
Les commandes `sudo` peuvent demander votre mot de passe système.

#### Récupérer le projet

```bash
git clone https://github.com/Aliochka/cahier-de-doleances.git
cd cahier-de-doleances
```

Si vous avez déjà téléchargé le projet, ouvrez simplement un terminal dans
son dossier. Toutes les commandes suivantes s'exécutent depuis cette racine.

#### Créer le rôle et la base PostgreSQL

Créer un rôle PostgreSQL portant le nom de votre utilisateur Linux,
puis une base dédiée dont ce rôle sera propriétaire :

```bash
sudo -u postgres createuser --createdb "$(id -un)"
createdb cahier_doleances_local
psql cahier_doleances_local -c 'SELECT current_database(), current_user;'
```

Ces créations ne se font qu'une fois. Si le rôle ou la base existe déjà,
passer la commande correspondante et vérifier la connexion avec `psql`.
Pour cette procédure, utiliser une base neuve : les migrations ne vident
pas une base existante.

La connexion utilise le socket Unix local et l'authentification `peer` de
PostgreSQL : le nom du rôle correspond à celui de votre session Linux.
Aucun mot de passe PostgreSQL ni port TCP exposé n'est nécessaire.

#### Installer les dépendances Python

Installer [uv](https://docs.astral.sh/uv/getting-started/installation/),
version **0.13.1**, utilisée aussi en CI et dans Docker :

```bash
curl -LsSf https://astral.sh/uv/0.13.1/install.sh | sh
```

Ouvrir ensuite un nouveau terminal si nécessaire pour disposer de `uv` dans
le `PATH`, puis, à la racine du dépôt :

```bash
uv python install 3.11
uv sync --locked
```

`pyproject.toml` déclare les dépendances ; `uv.lock` verrouille également les
dépendances transitives. `uv sync --locked` installe le backend et le groupe
`dev` (pytest, httpx, Ruff) dans `.venv/`. Pour les seules dépendances de
production : `uv sync --locked --no-dev`. Utiliser ensuite
`uv run --locked --no-dev …` pour conserver ce profil ; `uv run --locked …`
inclut le groupe de développement par défaut.

Il n'est pas nécessaire d'activer l'environnement. Si l'ancien `venv/` est
actif, le quitter avec `deactivate` ; uv utilise désormais `.venv/`.
Le backend reste exécuté depuis la racine, sans installation du code comme
package. Aucun workspace uv n'est déclaré : le futur `rag/` aura son propre
`pyproject.toml`, verrou et environnement, sans dépendance au backend.
Le frontend conserve pnpm.

Les scripts de maintenance s'exécutent depuis la racine avec
`uv run --locked python scripts/nom_du_script.py`. Cela place aussi Alembic
dans le `PATH` des sous-processus. Les scripts d'analyse NLP historiques ne
sont pas couverts par les dépendances du backend ; ne pas y ajouter leurs
modèles ou bibliothèques GPU.

Pour faire évoluer les dépendances :

```bash
uv add 'nom-du-paquet==VERSION'
uv add --dev 'outil==VERSION'
uv remove nom-du-paquet
uv lock --check
```

Pour mettre à jour une dépendance directement fixée, utiliser
`uv add 'nom-du-paquet==NOUVELLE_VERSION'` (ou `--dev`). Pour une dépendance
transitive compatible avec les contraintes : `uv lock --upgrade-package nom`.
Examiner le diff de `pyproject.toml` et `uv.lock`, puis relancer les contrôles.
Les anciens fichiers requirements ne sont plus maintenus. Si un outil externe
en exige un, exporter le verrou avec
`uv export --locked --no-dev --format requirements-txt --output-file /tmp/cahier-requirements.txt`.

#### Configurer l'environnement local

Lors de la première installation :

```bash
cp .env.example .env
```

Si `.env` existe déjà, modifier son contenu sans l'écraser. Les valeurs
nécessaires au lancement local sont :

```dotenv
DATABASE_URL=postgresql:///cahier_doleances_local
ENV=dev
BASE_URL=http://127.0.0.1:8000
COOKIE_SECURE=false
ENFORCE_HTTPS=false
```

L'application et Alembic chargent `.env` automatiquement. `ENV=dev` permet
de servir le site localement en HTTP. `.env` est ignoré par Git. Générer une
clé persistante avec `uv run --locked python -c 'import secrets; print(secrets.token_urlsafe(48))'`
et la renseigner dans `SECRET_KEY`. Sans clé en développement, une clé temporaire
est générée et les sessions expirent au redémarrage. En déploiement, une clé
aléatoire d'au moins 32 caractères est obligatoire.

#### Créer le schéma, sans importer de données

```bash
uv run --locked alembic upgrade head
uv run --locked alembic current
```

La révision attendue est `remove_runtime_caches (head)`. Les migrations rétablissent
la recherche, créent le suivi des imports, maintiennent les compteurs par
lot et retirent les anciennes tables de cache. Il faut les appliquer avant
de démarrer le site.

Les migrations créent les tables, extensions (`unaccent`, `pg_trgm`), index,
déclencheurs et compteurs techniques. Elles n'importent aucun fichier de
contributions.

#### Démarrer le serveur

```bash
uv run --locked uvicorn app.app:app --host 127.0.0.1 --port 8000 --reload
```

Ouvrir **http://127.0.0.1:8000**. Garder ce terminal ouvert ; `Ctrl+C`
arrête le serveur. L'option `--reload` recharge le code modifié pendant
le développement.

### 2. Vérifier le lancement avec une base vide

Dans un second terminal ouvert à la racine du projet :

```bash
uv sync --locked
uv run --locked alembic current
psql cahier_doleances_local -c '
SELECT
  (SELECT count(*) FROM forms) AS forms,
  (SELECT count(*) FROM questions) AS questions,
  (SELECT count(*) FROM authors) AS authors,
  (SELECT count(*) FROM contributions) AS contributions,
  (SELECT count(*) FROM answers) AS answers,
  (SELECT count(*) FROM users) AS users;
'
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8000/api/v1/search/answers?q=culture'
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8000/api/v1/search/catalog?q=culture'
```

Sur une installation neuve, les six compteurs doivent être à **0** et les
trois requêtes HTTP doivent renvoyer **200**. Les pages de recherche sont
accessibles mais leurs résultats restent vides jusqu'à l'import.

Les routes incomplètes `/mentions` et `/topics` ont été retirées. Les pages
de détail correspondant à des données absentes renvoient 404. Sans configuration
Mailjet, les e-mails sont journalisés et ne sont pas envoyés ; cela ne bloque pas le lancement.

### 3. Relancer le projet après l'installation

Depuis la racine du dépôt :

```bash
uv sync --locked
pg_isready
uv run --locked alembic current
uv run --locked uvicorn app.app:app --host 127.0.0.1 --port 8000 --reload
```

Si PostgreSQL est arrêté, lancer `sudo systemctl start postgresql`.
Il n'est pas nécessaire de recréer le rôle, la base, le fichier `.env`
ou l'environnement virtuel à chaque lancement.
Une divergence de révision doit être examinée avant toute migration ; le
démarrage n'applique aucune migration automatiquement.

### Dépannage du lancement local

- **`sudo` demande un mot de passe** : exécuter la commande dans votre
  terminal et saisir le mot de passe de votre session Linux.
- **`role … does not exist`** : créer le rôle portant le nom retourné par
  `id -un`, comme indiqué plus haut.
- **`Peer authentication failed`** : exécuter l'application avec le même
  utilisateur Linux que celui du rôle PostgreSQL, et conserver l'URL par
  socket Unix indiquée dans `.env`.
- **`database … does not exist`** : exécuter `createdb cahier_doleances_local`.
- **`No database URL found`** : vérifier que `.env` se trouve à la racine,
  contient `DATABASE_URL` et que le serveur est lancé depuis cette racine.
- **Une autre base est utilisée** : les variables déjà exportées dans le
  terminal priment sur `.env`. `TEST_DATABASE_URL` prime aussi sur
  `DATABASE_URL` pour l'application ; `ALEMBIC_DATABASE_URL` peut remplacer
  l'URL des migrations. Retirer ces substitutions pour le lancement local.
- **Erreur de colonne de recherche absente** : exécuter
  `uv run --locked alembic upgrade head`, puis vérifier `uv run --locked alembic current`.
- **`Address already in use`** : arrêter le serveur déjà lancé avec `Ctrl+C`,
  ou choisir un autre port, par exemple `--port 8001`.

### 4. Importer les données complètes

La [procédure d'ingestion](docs/ingestion.md) détaille le téléchargement,
le contrôle des sources, le pilote et l'import complet PostgreSQL. Après
l'installation ci-dessus, pour récupérer les sept exports complets :

```bash
uv sync --locked
uv run --locked alembic upgrade head
uv run --locked python -m ingest.sources fetch --full
uv run --locked python -m ingest.structured_sources fetch
uv run --locked python -m ingest.structured_sources profile
uv run --locked python -m ingest.structured_sources samples --rows 1000
uv run --locked python -m ingest.postgres --samples
uv run --locked python -m ingest.postgres
uv run --locked python -m ingest.verify
```

Les JSON officiels distinguent les choix sélectionnés du texte « autre ».
Une question à choix multiples reste **une seule question**, avec **une
réponse par contribution** et plusieurs liens vers ses options. Les CSV
servent à contrôler les identifiants et la complétude des JSON.

L'import complet complète les données du pilote par upserts, sans doublons.
Si l'import est interrompu, relancer `uv run --locked python -m ingest.postgres` : il reprend
au dernier lot validé. Les résultats sont consignés dans le
[rapport de vérification](docs/ingestion-resultats.md).

L’ancien importeur `ingest/gdn_ingest.py` et `scripts/import_from_csv.sh`
ne correspondent pas à cette procédure. Ne pas les combiner avec elle.

### 5. Linter et tests

```bash
uv sync --locked --dev
uv run --locked ruff check .
uv run --locked ruff format --check app ingest scripts tests migrations/env.py
uv run --locked python -m pytest
```

Le [guide des tests](TESTING.md) explique comment exécuter toute la suite sur
une base PostgreSQL de test séparée. Sans cette base, les tests d’intégration
sont signalés comme ignorés. Le [mini audit](docs/nettoyage-repo.md) détaille
les suppressions et les tests conservés.

L’interface est en français. Les images de partage utilisent le fichier
statique existant ; aucun navigateur Playwright ni cache applicatif n’est
nécessaire. Les anciens notebooks et analyses NLP ne font pas partie de
l'environnement backend. Leurs dépendances lourdes ne sont pas installées ;
le futur projet RAG les gérera indépendamment selon ses besoins.

### Mise en prod

1. Vérifier le montage du SSD
```
findmnt /data/postgresql
ls -l /data/postgresql/.ssd-mounted
```

2. Démarrer PostgreSQL
```
cd /srv/cahier-de-doleances
sudo docker compose up -d
```

3. Démarrer FastAPI
```
cd /srv/cahier-de-doleances-app

sudo docker compose \
  --env-file .env.deploy \
  -f compose.deploy.yml \
  up -d
```


4. Vérifier les conteneurs
```
sudo docker ps
```


5. Consulter les logs de l'application
```
sudo docker compose \
  --env-file .env.deploy \
  -f compose.deploy.yml \
  logs -f
```

#### Arrêt propre du serveur
1. Arrêter l'application :

```
cd /srv/cahier-de-doleances-app

sudo docker compose \
  --env-file .env.deploy \
  -f compose.deploy.yml \
  down
```

2. Arrêter PostgreSQL :
```
cd /srv/cahier-de-doleances
sudo docker compose down
```

3. Éteindre le serveur :
```
sudo shutdown -h now
```


---

## 📜 Licence

Ce projet est distribué sous licence **MIT**.  
Voir le fichier [LICENSE](./LICENSE) pour plus de détails.

---

## ✊ Un pas de plus vers la révolution
