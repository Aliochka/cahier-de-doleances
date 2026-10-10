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
  - [ ] l'url partial qui pop http://127.0.0.1:8000/search/answers?partial=1&q=politique
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
python scripts/check_model_alignment.py
```

Ce script compare automatiquement :
- Les tables présentes
- Les colonnes et leurs types
- Les contraintes de clés étrangères
- Ignore les tables et colonnes générées automatiquement (Alembic, triggers FTS)
- Charge la configuration depuis le fichier .env

### 1. Installation depuis zéro (Ubuntu / Debian)

Le site utilise **FastAPI, SQLAlchemy et PostgreSQL**. La procédure ci-dessous
lance une instance locale avec une base sans contributions citoyennes.
Elle a été vérifiée avec Python 3.10 et PostgreSQL 14 ; le fichier
`.python-version` du dépôt indique Python 3.11.

#### Installer les outils système

Dans votre terminal, installer Git, Python avec le support des environnements
virtuels, PostgreSQL et ses extensions :

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip postgresql postgresql-contrib curl
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

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

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
clé persistante avec `python -c 'import secrets; print(secrets.token_urlsafe(48))'`
et la renseigner dans `SECRET_KEY`. Sans clé en développement, une clé temporaire
est générée et les sessions expirent au redémarrage. En déploiement, une clé
aléatoire d'au moins 32 caractères est obligatoire.

#### Créer le schéma, sans importer de données

```bash
alembic upgrade head
alembic current
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
uvicorn app.app:app --host 127.0.0.1 --port 8000 --reload
```

Ouvrir **http://127.0.0.1:8000**. Garder ce terminal ouvert ; `Ctrl+C`
arrête le serveur. L'option `--reload` recharge le code modifié pendant
le développement.

### 2. Vérifier le lancement avec une base vide

Dans un second terminal ouvert à la racine du projet :

```bash
source venv/bin/activate
alembic current
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
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8000/search/answers?q=culture'
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8000/search/questions?q=culture'
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
source venv/bin/activate
pg_isready
alembic current
uvicorn app.app:app --host 127.0.0.1 --port 8000 --reload
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
- **Erreur de colonne de recherche absente** : activer `venv`, exécuter
  `alembic upgrade head`, puis vérifier `alembic current`.
- **`Address already in use`** : arrêter le serveur déjà lancé avec `Ctrl+C`,
  ou choisir un autre port, par exemple `--port 8001`.

### 4. Importer les données complètes

La [procédure d'ingestion](docs/ingestion.md) détaille le téléchargement,
le contrôle des sources, le pilote et l'import complet PostgreSQL. Après
l'installation ci-dessus, pour récupérer les sept exports complets :

```bash
source venv/bin/activate
python -m pip install -r requirements.txt
alembic upgrade head
python -m ingest.sources fetch --full
python -m ingest.structured_sources fetch
python -m ingest.structured_sources profile
python -m ingest.structured_sources samples --rows 1000
python -m ingest.postgres --samples
python -m ingest.postgres
python -m ingest.verify
```

Les JSON officiels distinguent les choix sélectionnés du texte « autre ».
Une question à choix multiples reste **une seule question**, avec **une
réponse par contribution** et plusieurs liens vers ses options. Les CSV
servent à contrôler les identifiants et la complétude des JSON.

L'import complet complète les données du pilote par upserts, sans doublons.
Si l'import est interrompu, relancer `python -m ingest.postgres` : il reprend
au dernier lot validé. Les résultats sont consignés dans le
[rapport de vérification](docs/ingestion-resultats.md).

L’ancien importeur `ingest/gdn_ingest.py` et `scripts/import_from_csv.sh`
ne correspondent pas à cette procédure. Ne pas les combiner avec elle.

### 5. Linter et tests

```bash
source venv/bin/activate
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check app ingest scripts tests migrations/env.py
python -m pytest
```

Le [guide des tests](TESTING.md) explique comment exécuter toute la suite sur
une base PostgreSQL de test séparée. Sans cette base, les tests d’intégration
sont signalés comme ignorés. Le [mini audit](docs/nettoyage-repo.md) détaille
les suppressions et les tests conservés.

L’interface est en français. Les images de partage utilisent le fichier
statique existant ; aucun navigateur Playwright ni cache applicatif n’est
nécessaire. Les dépendances facultatives des analyses et notebooks sont dans
`requirements-analysis.txt`, à installer avec Python 3.11 ou supérieur.

---

## 📜 Licence

Ce projet est distribué sous licence **MIT**.  
Voir le fichier [LICENSE](./LICENSE) pour plus de détails.

---

## ✊ Un pas de plus vers la révolution
