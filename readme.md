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

Pour Wallace (`https://cahierdedoleances.fr`), suivre le
[guide de déploiement](docs/deploiement.md). Il utilise `compose.deploy.yml`,
avec le frontend React SSR, FastAPI et Caddy, et préserve le PostgreSQL 17 existant.
Les commandes courantes figurent dans [Mise en prod](#mise-en-prod). Les instructions
d'installation depuis zéro ci-dessous concernent une **base locale neuve** et
ne doivent pas être appliquées à la base restaurée du serveur.

---

## 🚀 Objectif du projet

Cahier de doléances est un site/service permettant d’explorer, rechercher et analyser les contributions citoyennes du **Grand Débat National**.  
L’idée : donner un accès simple et puissant à cette matière brute, pour nourrir les réflexions et ouvrir la voie à de nouvelles perspectives collectives.

Gros merci a chat gpt qui a codé l'ultra majorité de ce que vous voyez !




---

## 🗺️ Roadmap v0

 
### v1
- [ ] SEO
- [ ] accueil




---

## 🛠️ Guide pour les développeurs

### Lancer le backend et le frontend en local

**La recherche hybride a besoin de PyTorch et Transformers.** Ils sont déjà
installés par défaut dans **`.venv` à la racine**, avec le verrou `uv.lock`
en version CPU. Un seul `uv sync --locked` prépare le backend, H1 et les tests.
Le RAG expérimental conserve son environnement indépendant **`rag/.venv`**.
PostgreSQL doit être démarré et `.env` doit désigner la **base applicative locale**
via `DATABASE_URL`, avec `ENV=dev`, `COOKIE_SECURE=false` et `ENFORCE_HTTPS=false`.

**Terminal 1 — backend avec recherche hybride CPU**, depuis la racine :

```bash
uv sync --locked
uv run --locked uvicorn app.app:app \
  --host 127.0.0.1 --port 8000
```

Cela installe les dépendances CPU, sans télécharger de modèle. H1 nécessite
aussi le snapshot BGE-M3 **déjà présent**, la base de recherche **déjà indexée**,
les connexions en lecture seule dans le fichier privé `rag/search-reader.env`
et une `SEARCH_CURSOR_KEY` d’au moins 32 octets dans `search-api.env` ou
l’environnement. La base source de ce lecteur doit correspondre à `DATABASE_URL`.
Conserver les fichiers privés existants ; ne pas y mettre les URL des bases de
test. L’initialisation peut prendre un moment ; `/healthz` seul ne valide pas H1.
Éviter `--reload` avec le modèle chargé pour ne pas le recharger à chaque édition.

Pour développer **sans recherche hybride**, utiliser à la place :

```bash
uv sync --locked
HYBRID_SEARCH_ENABLED=false \
  uv run --locked uvicorn app.app:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — frontend**, depuis la racine : Node24 et pnpm sont requis.

```bash
cd frontend
nvm use
corepack enable
pnpm install --frozen-lockfile
API_BASE_URL=http://127.0.0.1:8000 pnpm dev
```

`nvm use` suppose nvm installé et la version de `.nvmrc` déjà disponible
(`nvm install` au premier lancement). Ouvrir **http://127.0.0.1:5173** pour
le site ; l’API est sur **http://127.0.0.1:8000/docs**. `Ctrl+C` dans chaque
terminal arrête le service correspondant.

Pour lancer les tests dans le même environnement racine, PyTorch compris :

```bash
uv run --locked python -m pytest
```

Les tests PostgreSQL nécessitent toujours `.env.test` et les bases de test
préparées : voir [TESTING.md](TESTING.md). PyTorch seul ne supprime pas ces skips.

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
`dev` (pytest, httpx, Ruff) dans `.venv/`. Pour les dépendances de
production avec recherche CPU : `uv sync --locked --no-dev`. Utiliser ensuite
`uv run --locked --no-dev …` pour conserver ce profil ; `uv run --locked …`
inclut les groupes `dev` et `search` par défaut. Le groupe `search` fournit
PyTorch CPU et Transformers. `--no-dev` conserve la recherche ;
`--no-default-groups` produit le profil léger sans recherche ni outils de test.

Il n'est pas nécessaire d'activer l'environnement. Si l'ancien `venv/` est
actif, le quitter avec `deactivate` ; uv utilise désormais `.venv/`.
Le backend reste exécuté depuis la racine, sans installation du code comme
package. Aucun workspace uv n'est déclaré : `rag/` conserve son propre
`pyproject.toml`, verrou et environnement pour le RAG/GPU. Le backend importe
son paquet Python par chemin éditable sans utiliser ses extras GPU.
Le frontend conserve pnpm.

Les anciens `.cache/search-cpu-venv` et `.cache/search-api-venv` ne sont plus
utilisés par ces commandes. Ils ne sont pas supprimés automatiquement.
Si `UV_PROJECT_ENVIRONMENT` est exporté dans votre terminal, le retirer avec
`unset UV_PROJECT_ENVIRONMENT` pour retrouver le `.venv` racine par défaut.

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

La révision historique attendue par l'installation précédente est
`remove_runtime_caches`. La tête actuelle du dépôt est `forms_statistics_v1` ;
pour déployer le frontend, consulter [la procédure de déploiement](docs/deploiement.md)
et vérifier la révision réelle avant d'appliquer la migration. Les migrations rétablissent
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

Ce terminal sert l’API sur **http://127.0.0.1:8000/docs**. Pour l’interface,
lancer aussi le frontend comme indiqué plus haut. Garder ce terminal ouvert ; `Ctrl+C`
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
  terminal priment sur `.env`. L'application utilise `DATABASE_URL` ;
  `TEST_DATABASE_URL` et `.env.test` sont réservés à pytest.
  `ALEMBIC_DATABASE_URL` peut remplacer l'URL des migrations.
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
une base PostgreSQL de test séparée. Copier une fois `.env.test.example` vers
`.env.test` et y configurer les URL permet ensuite de lancer simplement pytest.
Sans cette base, les tests d’intégration
sont signalés comme ignorés. Le [mini audit](docs/nettoyage-repo.md) détaille
les suppressions et les tests conservés.

L’interface est en français. Les images de partage utilisent le fichier
statique existant ; aucun navigateur Playwright ni cache applicatif n’est
nécessaire. Les anciens notebooks et analyses NLP ne font pas partie de
l'environnement backend. Leurs dépendances lourdes ne sont pas installées ;
le futur projet RAG les gérera indépendamment selon ses besoins.

### Mise en prod

Ces commandes s’exécutent **sur Wallace**, pour redémarrer l’installation
existante. Utiliser le projet **`cahier-de-doleances-app`** et les deux fichiers
**`compose.deploy.yml` et `compose.search.yml`**. Les tags des images et le flag
`HYBRID_SEARCH_ENABLED` restent ceux de la configuration privée approuvée dans
`.env.deploy` ; ces commandes ne les remplacent pas. Ne pas écraser ce fichier.

#### Démarrer le site actuel

1. Vérifier le SSD avant tout démarrage de PostgreSQL :

   ```bash
   findmnt --mountpoint /data/postgresql
   ls -l /data/postgresql/.ssd-mounted
   sudo test -f /data/postgresql/pg17/data/PG_VERSION
   ```

   Arrêter la procédure si le SSD n’est pas monté ou si un fichier manque.
   Ne pas créer de marqueur ou de répertoire pour contourner ce contrôle.

2. Redémarrer le **conteneur PostgreSQL existant**, avec son image et ses montages
   déjà validés, puis vérifier qu’il accepte les connexions :

   ```bash
   sudo docker start cahier-postgres
   sudo docker exec cahier-postgres pg_isready -U cahier -d cahier_doleances
   ```

   Attendre que `pg_isready` indique `accepting connections` avant de continuer.
   Si `cahier-postgres` n’existe plus, utiliser la définition PostgreSQL réellement
   installée et son override pgvector approuvé ; ne pas recréer le conteneur
   depuis un ancien Compose. Les deux montages à conserver sont
   `/data/postgresql/pg17/data:/var/lib/postgresql/data` et
   `/data/postgresql/.ssd-mounted:/run/ssd-mounted` (marqueur en lecture seule).

3. Démarrer FastAPI, le frontend SSR et Caddy, avec les images déjà construites :

   ```bash
   cd /srv/cahier-de-doleances-app
   sudo docker compose \
     --project-name cahier-de-doleances-app \
     --env-file .env.deploy \
     -f compose.deploy.yml \
     -f compose.search.yml \
     up -d --no-build
   ```

   L’overlay fournit les trois montages de recherche en lecture seule. Les chemins
   et fichiers privés requis doivent déjà exister. `--no-build` utilise les images
   préparées ; le démarrage conserve le flag d’activation configuré.

4. Vérifier l’état, le site et le trajet HTTP interne SSR → FastAPI :

   ```bash
   sudo docker compose --project-name cahier-de-doleances-app \
     --env-file .env.deploy -f compose.deploy.yml -f compose.search.yml ps
   curl --fail --max-time 15 -I https://cahierdedoleances.fr/
   sudo docker compose --project-name cahier-de-doleances-app \
     --env-file .env.deploy -f compose.deploy.yml -f compose.search.yml \
     exec -T frontend node -e \
     'fetch("http://app:8000/api/v1/forms", {redirect:"manual"}).then(r=>{console.log(r.status);process.exit(r.status===200?0:1)}).catch(()=>process.exit(1))'
   ```

   Attendre les healthchecks ; le test interne doit afficher **200**, sans
   redirection vers `https://app:8000`. Vérifier aussi `/enquetes` et les pages
   statistiques dans le navigateur.

5. Consulter les logs (quitter le suivi avec `Ctrl+C`) :

   ```bash
   sudo docker compose --project-name cahier-de-doleances-app \
     --env-file .env.deploy -f compose.deploy.yml -f compose.search.yml \
     logs --tail 100 -f app frontend caddy
   ```

#### Construire et préparer une nouvelle version P6

La préparation P6 doit construire **le code actuel avec le verrou CPU** :

```bash
cd /srv/cahier-de-doleances-app
# Choisir un nouveau tag ; ne pas remplacer ssr-002.
sudo docker build -f Dockerfile --build-arg SEARCH_RUNTIME=cpu \
  -t cahier-de-doleances-app:search-cpu-p6-candidat .
sudo docker run --rm --network none --read-only --tmpfs /tmp \
  cahier-de-doleances-app:search-cpu-p6-candidat python -m app.search_packaging
```

Cette construction n’installe aucun service et n’active pas la recherche.
Pour la prévalidation avec les trois montages, les recherches réelles,
l’installation et le rollback vers l’**ID exact de `ssr-002`**, suivre la
[procédure P6](docs/rag027-p6-deploiement-ts-rank.md).
Le [diagnostic du timeout](docs/p6-diagnostic-timeout.md) reste à résoudre avant
l’activation publique. Ne pas dériver l’image de `ssr-002` ni réutiliser
`search-cpu-001` comme preuve de compatibilité du backend actuel.

##### Mise en prod d'un nouvelle version


1. Créer un commit de version avec tous les changements — ils ne sont pas encore enregistrés dans Git.
2. Récupérer ce commit sur Wallace, dans /srv/cahier-de-doleances-app.
3. Sauvegarder les anciens tags d’images, puis donner de nouveaux tags à APP_IMAGE_TAG et FRONTEND_IMAGE_TAG dans .env.deploy. Conserver les autres paramètres, notamment ceux de la recherche.
4. Construire puis remplacer les deux services :

cd /srv/cahier-de-doleances-app

sudo docker compose --project-name cahier-de-doleances-app \
  --env-file .env.deploy \
  -f compose.deploy.yml -f compose.search.yml \
  build app frontend

sudo docker compose --project-name cahier-de-doleances-app \
  --env-file .env.deploy \
  -f compose.deploy.yml -f compose.search.yml \
  up -d --no-build --wait app frontend

5. Vérifier le site : accueil, enquêtes, recherche, dates françaises et navigation entre contributions. Une courte interruption est possible pendant le remplacement du backend.







#### Arrêt propre du serveur

1. Arrêter Caddy, le frontend et FastAPI avant PostgreSQL :

   ```bash
   cd /srv/cahier-de-doleances-app
   sudo docker compose --project-name cahier-de-doleances-app \
     --env-file .env.deploy -f compose.deploy.yml -f compose.search.yml \
     stop --timeout 120 caddy frontend app
   ```

2. Si le laboratoire de recherche tourne, l’arrêter aussi. Dans Bash, ce bloc
   n’agit que si son conteneur est démarré :

   ```bash
   p6_lab=$(sudo docker ps -q \
     --filter label=com.docker.compose.project=cahier-search-validation \
     --filter label=com.docker.compose.service=validation)
   if [ -n "$p6_lab" ]; then
     sudo docker stop --timeout 120 "$p6_lab"
   fi
   ```

   Vérifier qu’aucun autre import, diagnostic ou client PostgreSQL n’est en cours.

3. Arrêter PostgreSQL et vérifier qu’il est bien arrêté :

   ```bash
   sudo docker stop --timeout 120 cahier-postgres
   sudo docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' cahier-postgres
   sudo docker logs --tail 20 cahier-postgres
   ```

   Attendu : état `exited`, code `0` et message d’arrêt PostgreSQL propre
   (`database system is shut down`). Si le code est `137` ou si l’arrêt est
   anormal, examiner les logs avant de poursuivre ; ne pas considérer l’arrêt
   forcé comme validé.

4. Éteindre Wallace :

   ```bash
   sudo shutdown -h now
   ```

Utiliser `stop` pour conserver conteneurs et réseaux. Ne jamais utiliser
`docker compose down -v` ni supprimer des volumes/répertoires PostgreSQL.
Après rallumage, reprendre les vérifications SSD et santé ci-dessus ; les
politiques de redémarrage Docker peuvent avoir déjà relancé certains services.


---

## 📜 Licence

Ce projet est distribué sous licence **MIT**.  
Voir le fichier [LICENSE](./LICENSE) pour plus de détails.

---

## ✊ Un pas de plus vers la révolution
