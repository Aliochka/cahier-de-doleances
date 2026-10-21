# Déployer le frontend React SSR et FastAPI sur Wallace

Pour la préparation du moteur H1 CPU, consulter la procédure distincte
[SEARCH-DEPLOY-002](search-deploiement.md). Elle conserve la recherche désactivée
jusqu’à validation et ne remplace pas la procédure de sauvegarde applicative.

Cette procédure prépare un déploiement avec interruption. Elle ne démarre ni
n'arrête de service et n'applique aucune migration automatiquement au lancement.
PostgreSQL 17, son conteneur, son volume et son réseau externe restent gérés par
le projet PostgreSQL existant. Ne pas utiliser `down -v`.

## Architecture livrée

- `app` : FastAPI/Gunicorn sur le réseau PostgreSQL existant et le réseau privé.
- `frontend` : React Router SSR sous Node 24, uniquement sur le réseau privé.
- `caddy` : seul service avec des ports publiés ; il envoie les chemins API,
  authentification, marque-pages et SEO à FastAPI, le reste au frontend.
- PostgreSQL n'est ni recréé, ni publié, ni monté par ce Compose.

Les enregistrements DNS existants ne sont pas modifiés par cette procédure ;
confirmer qu'ils pointent déjà vers Wallace et que les certificats Caddy sont
renouvelables avant la bascule.

FastAPI conserve son accès sortant pour Mailjet. Le frontend SSR appelle
`http://app:8000` directement. Cette adresse HTTP est autorisée uniquement pour
le nom de service `app` et le port 8000. Le frontend a l'IP privée fixe
`172.30.80.4`, également fournie au backend par `SSR_HTTP_CLIENT_IP` dans
Compose. FastAPI autorise son HTTP uniquement pour GET/HEAD sous `/api/v1/`
avec l'en-tête Host exact `app:8000`. Le nom `app` doit figurer dans
`ALLOWED_HOSTS`. L'adresse de connexion est conservée avant le traitement des
en-têtes de proxy ; `X-Forwarded-For` ne peut pas accorder cette exception.
Les en-têtes de proxy du frontend sont ignorés, y compris celui qu'émet
l'ancienne image SSR. Seul Caddy (`172.30.80.2`) doit figurer dans
`TRUSTED_PROXY_IPS`. Une ancienne liste contenant aussi `172.30.80.4` reste
compatible : le backend ne traite pas le frontend comme un proxy.
`ENFORCE_HTTPS=true`, TrustedHost et l'exception locale `/healthz` sont conservés.
Ne pas ajouter le sous-réseau Docker entier aux proxies de confiance.

Le backend inclut le paquet Python `cahier-rag` sans extras d'embeddings, car
les routes FastAPI importent ses contrats et types d'erreur. Le contexte et
l'image Docker excluent ses modèles, index, données et base spécialisée.
La recherche hybride complète reste désactivée dans l'exemple de production
avec `HYBRID_SEARCH_ENABLED=false`. L'API documentaire et les statistiques
restent accessibles. `/recherche` affiche l'état indisponible (HTTP API 503)
tant que le service et les modèles RAG ne sont pas installés. Aucun modèle ni
base spécialisée RAG n'est attendu par ce déploiement.

## 1. Prérequis et préparation locale

Sur la machine de préparation, Node `24.21.x`, pnpm `12.11.2`, Docker et Docker
Compose v2 sont nécessaires. Le dépôt doit être propre et la version à déployer
doit être identifiée par un commit/tag conservé. Construire localement le
frontend et ses contrôles SSR :

```bash
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm build
pnpm test:build
```

La construction de l'image installe ses propres dépendances depuis le lockfile.
Le Dockerfile n'inclut aucun fichier `.env` et ne reçoit aucun secret au build.
`API_BASE_URL` est une variable runtime privée du conteneur Node, jamais une
variable `VITE_*`.

## 2. Variables privées

Sur Wallace, conserver `.env.deploy` et ses secrets existants. **Ne pas le
remplacer par `.env.deploy.example`.** Faire une copie de sauvegarde privée avant
édition, avec permissions restreintes. Ajouter/adopter les paramètres publics
de l'exemple et les paramètres suivants dans `.env.deploy` :

| Variable | Rôle |
|---|---|
| `APP_IMAGE_TAG` | Tag immuable de l'image FastAPI ; conserver le tag précédent. |
| `FRONTEND_IMAGE_TAG` | Tag immuable de l'image SSR ; conserver le tag précédent. |
| `LAN_BIND_IP` | Adresse IPv4 LAN déjà utilisée pour Caddy. |
| `ALLOWED_HOSTS` | Inclure `cahierdedoleances.fr`, `app`, `localhost` et `127.0.0.1`. |
| `TRUSTED_PROXY_IPS` | `172.30.80.2` (Caddy) après vérification du réseau privé. |
| `EXPECTED_ALEMBIC_REVISION` | Révision cible `forms_statistics_v1` pour les contrôles post-migration. |
| `MIGRATION_FROM_REVISION` | À régler à la révision constatée par le contrôle pré-migration. |
| `MIGRATION_TARGET_REVISION` | `forms_statistics_v1`. |
| `HYBRID_SEARCH_ENABLED` | `false` tant que les modèles/configurations RAG ne sont pas déployés. |

Conserver sans les afficher la clé `SECRET_KEY`, l'URL PostgreSQL existante,
les paramètres `EXPECTED_DB_*`, les clés Mailjet et l'expéditeur. Les chemins
`DATABASE_URL` et secrets Mailjet restent dans l'environnement privé utilisé
par FastAPI. Seuls `API_BASE_URL=http://app:8000`, `NODE_ENV`, `HOST` et `PORT`
sont fournis au frontend par Compose. Garder `COOKIE_SECURE=true`,
`ENFORCE_HTTPS=true`, `LOG_MAGIC_LINKS=false` en production. L'envoi d'e-mails
doit rester conforme à la configuration Mailjet existante et faire l'objet
d'un test de réception contrôlé.

Le changement de `EXPECTED_ALEMBIC_REVISION` vers la cible ne dispense pas du
contrôle pré-migration : la commande `--pre-migration` vérifie la révision source
explicitement configurée et la structure existante sans écriture.

## 3. Contrôles préalables sur Wallace

Avant d'arrêter le site, relever le commit et tags réellement actifs, la santé
des conteneurs, les réseaux et volumes. Confirmer que le réseau externe
`cahier-de-doleances_cahier-internal` existe et rejoint le conteneur PostgreSQL
existant. Vérifier le sous-réseau `172.30.80.0/24` et l'absence de conflit avec
LAN/VPN. Vérifier les ports 80/443, les règles pare-feu et DNS/IPv6.

Contrôler l'espace disque et la destination de Docker :

```bash
df -h /var /data/postgresql
docker info --format 'DockerRootDir={{.DockerRootDir}}'
docker system df
findmnt /data/postgresql
docker network inspect cahier-de-doleances_cahier-internal
docker inspect cahier-postgres --format '{{json .NetworkSettings.Ports}}'
```

Ne pas construire si l'espace libre sur le répertoire Docker ou son stockage
temporaire ne suffit pas pour deux images et leurs couches. Ne pas poursuivre si
le SSD PostgreSQL n'est pas monté, si PostgreSQL est publié vers Internet ou si
la version PostgreSQL n'est pas 17.

Après mise à jour privée de `.env.deploy`, valider Compose sans afficher sa
configuration complète (qui pourrait contenir des secrets) :

```bash
cd /srv/cahier-de-doleances-app
docker compose --env-file .env.deploy -f compose.deploy.yml config --quiet
docker compose --env-file .env.deploy -f compose.deploy.yml build app frontend
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_check --pre-migration
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_migrate
```

Les deux contrôles doivent indiquer `ready`. Ils vérifient PostgreSQL 17,
l'identité attendue de la base et du rôle, la révision exacte, la chaîne de
migrations et les tables/index requis. Ils ne modifient pas la base. **Si la
révision lue ne correspond pas à `MIGRATION_FROM_REVISION`, ne pas corriger la
valeur à l'aveugle et ne pas lancer Alembic : arrêter la procédure et faire
examiner le schéma et la chaîne réelle.**

Le contrôle de migration vérifie aussi le droit `CREATE` sur `public` et le droit
`TRIGGER` sur chacune des tables sources (`forms`, `questions`, `options`,
`answers`, `answer_options`, `contributions`, `question_stats`). Si le rôle
applicatif n'a pas ces droits, un administrateur doit examiner la propriété et
les privilèges avant toute migration ; ne pas élargir les droits par défaut.

Valider ensuite le Caddyfile avec l'image configurée, sans démarrer le service :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

## 4. Sauvegarde PostgreSQL et test de restauration

Choisir un emplacement de sauvegarde protégé, hors du volume PostgreSQL et avec
assez d'espace. Garder le chemin et l'empreinte à l'abri des journaux publics.
Arrêter temporairement les applications qui écrivent dans PostgreSQL, puis
effectuer un dump cohérent depuis le conteneur PostgreSQL existant :

```bash
umask 077
docker exec cahier-postgres pg_dump -U cahier -d cahier_doleances -Fc > /chemin-prive/cahier-pre-frontend.dump
test -s /chemin-prive/cahier-pre-frontend.dump
docker exec -i cahier-postgres pg_restore --list < /chemin-prive/cahier-pre-frontend.dump > /dev/null
sha256sum /chemin-prive/cahier-pre-frontend.dump
```

Avant la migration, restaurer également ce dump dans une base isolée temporaire
qui n'est pas la base de production. Vérifier que la restauration aboutit,
qu'elle contient les tables métier et que des comptages de référence concordent.
Une liste d'archive lisible ne remplace pas cet essai de restauration. Ne jamais
utiliser les identifiants de Wallace contre une base locale de test par erreur.

## 5. Arrêt et application contrôlée de la migration

Une fois sauvegarde et essai de restauration validés par un humain, arrêter
Caddy puis l'ancienne API/frontend. PostgreSQL reste actif :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml stop -t 30 caddy frontend app
```

Réexécuter la porte de migration juste avant l'opération. Elle utilise une
transaction et exige que la base soit toujours exactement à la source planifiée,
que cette source soit le parent direct de la cible et que la cible soit la tête
unique du dépôt. Elle n'affiche aucune URL de connexion. Puis lancer explicitement
la migration :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_migrate
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_migrate --apply
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_check
```

La première commande est un contrôle en lecture seule. La seconde est l'unique
commande de ce guide qui modifie le schéma. Elle refuse toute révision autre que
`MIGRATION_FROM_REVISION`. Elle ne lance que le passage direct prévu vers
`forms_statistics_v1` ; aucune migration n'est exécutée au démarrage des services.
La dernière vérifie que la base correspond à l'application et que les tables de
statistiques sont présentes. Si une étape échoue, ne pas relancer à répétition,
ne pas faire `stamp` et ne pas lancer un downgrade.

La migration `forms_statistics_v1` crée `statistics_source`,
`statistics_generations`, `question_statistics_snapshots`, une contrainte et
des déclencheurs sur les tables sources. Elle ne supprime pas les données
existantes. Les déclencheurs surveillent les écritures métier ; appliquer pendant
l'interruption et observer durée, verrous et journaux.

La migration crée une source de statistiques sans génération publiée. Les pages
statistiques restent indisponibles jusqu'à une première publication calculée et
validée. Le script local historique `scripts/generate_statistics.py` refuse les
bases distantes ; la commande de déploiement ci-dessous reprend le même
algorithme sans le modifier. Après le contrôle de schéma, lancer explicitement :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_statistics
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_statistics --publish
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_statistics
```

La première et la dernière commandes sont en lecture seule. `--publish` calcule
et publie une génération atomiquement dans une transaction `REPEATABLE READ`,
avec un délai maximal de 15 minutes par requête SQL. Cette opération est coûteuse sur le corpus
complet et doit être validée par un humain avant de remettre le site en ligne.
Elle exige PostgreSQL 17, `forms_statistics_v1`, les droits de lecture sur les
tables sources et les droits d'écriture nécessaires sur les tables de
statistiques. Si le calcul échoue, la transaction est annulée et les pages
restent indisponibles.

## 6. Démarrage et tests après déploiement

Mettre à jour dans le fichier privé `EXPECTED_ALEMBIC_REVISION=forms_statistics_v1`
et vérifier les paramètres de proxy, sans remplacer le reste de `.env.deploy`.
Démarrer backend, frontend puis Caddy :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml up -d --no-deps --no-build app
docker compose --env-file .env.deploy -f compose.deploy.yml up -d --no-deps --no-build frontend
docker compose --env-file .env.deploy -f compose.deploy.yml up -d --no-deps caddy
docker compose --env-file .env.deploy -f compose.deploy.yml ps
docker compose --env-file .env.deploy -f compose.deploy.yml logs --tail=100 app frontend caddy
```

Confirmer les trois états `healthy`, puis vérifier depuis un client externe :

```bash
curl -fsS https://cahierdedoleances.fr/ -o /dev/null
curl -fsSI https://cahierdedoleances.fr/assets/UN_ASSET_DU_BUILD.css
curl -fsS https://cahierdedoleances.fr/api/v1/forms -o /dev/null
curl -fsS https://www.cahierdedoleances.fr/forms/1 -o /dev/null
```

Remplacer `UN_ASSET_DU_BUILD.css` par le nom d'une ressource existant dans
l'image ; vérifier le contenu avant d'utiliser la commande. Tester manuellement
la navigation et le rendu SSR sur `/`, `/enquetes`, un formulaire, une question,
une contribution, un auteur et un tableau de bord. Tester les statistiques d'un
formulaire avec des données publiées, les routes profondes sans JavaScript, les
assets CSS/JS, les 404, la pagination et la recherche. Avec le RAG désactivé,
une requête de recherche documente explicitement l'indisponibilité (503) ; les
routes documentaires et statistiques doivent rester fonctionnelles. Tester
l'authentification, les cookies Secure/HttpOnly/SameSite et la réception Mailjet
avec un compte de recette. Confirmer les redirections HTTP→HTTPS, `www`→racine,
les certificats, et l'absence d'accès public direct aux ports 3000, 8000 et 5432.

## 7. Restauration

Conserver les anciennes images, l'ancien Compose/Caddyfile et l'environnement
privé sauvegardé. Si le frontend ou FastAPI échoue après migration, arrêter les
nouveaux services et revenir à l'ancienne image/configuration. La migration
ajoute tables et déclencheurs ; elle ne requiert pas un downgrade pour faire
fonctionner l'ancien code, mais cette compatibilité doit être validée lors de
la préparation de la version précédente.

Si la migration échoue, l'exécution transactionnelle doit être annulée par
PostgreSQL. Confirmer la révision et le schéma par les contrôles en lecture seule
avant toute nouvelle action. Si la transaction ne peut être confirmée comme
annulée ou si le schéma est incohérent, garder le site arrêté et restaurer le
dump vérifié dans une cible contrôlée. Restaurer le dump rétablit l'état d'avant
déploiement et peut perdre les écritures effectuées après sa prise : arrêter les
écritures et obtenir une décision humaine avant cette restauration.

Pour restaurer sur une instance PostgreSQL isolée, utiliser la procédure
administrative testée lors de l'essai de restauration. Ne pas restaurer directement
sur la base active sans avoir arrêté les applications et validé l'identité de la
cible. Après retour arrière, vérifier révision, santé, données, routes publiques,
recherche, authentification et e-mails avant réouverture.

## Correctif DEPLOY-002 sur une installation SSR déjà déployée

Ce correctif modifie uniquement le transport HTTP du backend. Il ne nécessite
aucune migration, restauration de données ou nouvelle publication des statistiques.

Après récupération du correctif sur Wallace :

1. Conserver l'image backend courante et noter son tag pour le retour arrière.
   Régler uniquement `APP_IMAGE_TAG` dans le fichier privé `.env.deploy` sur un
   nouveau tag, par exemple `ssr-002`. Conserver `FRONTEND_IMAGE_TAG=ssr-001`
   si c'est l'image frontend actuellement déployée.
2. Vérifier `ALLOWED_HOSTS` (dont `app`) et l'adresse fixe du frontend
   `172.30.80.4` sur le réseau privé. Compose fournit automatiquement
   `SSR_HTTP_CLIENT_IP=172.30.80.4` au backend et conserve
   `FORWARDED_ALLOW_IPS=""` pour éviter qu'Uvicorn/Gunicorn ne réécrive
   l'adresse de connexion avant le middleware applicatif. Conserver cette
   valeur vide. La liste privée `TRUSTED_PROXY_IPS` n'a pas à être élargie ;
   l'ancienne valeur incluant le frontend fonctionne aussi avec le correctif.
3. Construire puis recréer uniquement FastAPI :

   ```bash
   docker compose --env-file .env.deploy -f compose.deploy.yml build app
   docker compose --env-file .env.deploy -f compose.deploy.yml up -d --no-deps --no-build app
   docker compose --env-file .env.deploy -f compose.deploy.yml ps app
   ```

4. Attendre l'état `healthy`, puis vérifier depuis le conteneur Node, sans
   en-tête de proxy et sans suivre les redirections :

   ```bash
   docker compose --env-file .env.deploy -f compose.deploy.yml exec -T frontend node --input-type=module -e '
   const r = await fetch("http://app:8000/api/v1/forms", {redirect: "manual"});
   console.log("HTTP", r.status);
   if (r.status !== 200) process.exit(1);
   '
   curl -fsS https://cahierdedoleances.fr/enquetes -o /dev/null
   curl -fsS https://cahierdedoleances.fr/api/v1/forms -o /dev/null
   ```

5. Tester dans le navigateur les enquêtes, un formulaire et son tableau de bord
   `/forms/ID/dashboard` avec des statistiques déjà publiées. Vérifier l'absence
   de `ERR_SSL_WRONG_VERSION_NUMBER` dans les logs frontend.

Si nécessaire, remettre `APP_IMAGE_TAG` au tag backend précédent et exécuter
uniquement la commande `up -d --no-deps --no-build app` ci-dessus. Aucun retour
arrière de schéma ou de statistiques n'est associé à ce correctif. Le retour
à l'ancien backend peut rétablir le problème SSR initial.

## État non vérifié sur Wallace

Ce dépôt ne permet pas de confirmer la révision PostgreSQL réelle, l'état précis
des données, l'espace libre Docker, les conflits d'adresses réseau, les DNS,
les règles IPv6, la disponibilité des volumes Caddy, le contenu de `.env.deploy`
ni la réception Mailjet. Ces vérifications et le test réel de restauration sont
des validations humaines obligatoires. Aucune commande de cette procédure n'a
été exécutée sur Wallace pendant sa préparation.
