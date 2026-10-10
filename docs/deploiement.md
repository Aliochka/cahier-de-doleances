# Déployer FastAPI sur Wallace, avec PostgreSQL existant

Ce guide prépare une installation sur **http://192.168.1.56:8000**. Les commandes
sont destinées à être exécutées manuellement par l'administrateur de Wallace.
La préparation du dépôt n'exécute aucune commande sur ce serveur.

## Architecture et invariants

- `/srv/cahier-de-doleances` : projet PostgreSQL existant, conservé intégralement.
- `/srv/cahier-de-doleances-app` : dépôt et projet Compose FastAPI indépendant.
- Conteneur PostgreSQL : `cahier-postgres`, PostgreSQL 17, rôle `cahier`, base
  `cahier_doleances`, révision `remove_runtime_caches`.
- Réseau partagé existant : `cahier-de-doleances_cahier-internal`.
- FastAPI seul publie `192.168.1.56:8000`. Aucun volume PostgreSQL n'est défini
  ni monté dans son Compose. Un second réseau bridge fournit les connexions
  sortantes nécessaires à Mailjet, même si le réseau PostgreSQL est `internal`.

Utiliser **toujours** `-f compose.deploy.yml --env-file .env.deploy` pour les
commandes applicatives. `docker-compose.yml` est réservé au développement
avec une autre base. Aucun démarrage ne lance Alembic automatiquement, y compris
dans le Compose de développement : son schéma neuf doit être préparé manuellement.

Ne jamais supprimer/recréer les volumes PostgreSQL, utiliser `down -v`, restaurer
une base par-dessus celle-ci, lancer un import, ou appliquer `upgrade`, `downgrade`
ou `stamp` dans cette procédure. Une divergence de schéma arrête le déploiement ;
elle nécessite une analyse et une validation séparées.

La consultation des contributions est en lecture seule. Les comptes, profils et
marque-pages conservent leurs écritures normales dans `users`, `authors` et
`bookmarks`. Le précontrôle et le healthcheck utilisent des transactions en lecture
seule ; cela ne rend pas toutes les connexions applicatives read-only.

## Prérequis et inspection du PostgreSQL existant

Git, Docker et Docker Compose v2 sont nécessaires. Vérifier les versions :

```bash
git --version
docker --version
docker compose version
```

Vérifier que l'adresse `192.168.1.56` appartient à Wallace et que le port 8000
est libre. Vérifier la RAM, l'espace disque et la disponibilité de la sauvegarde
indépendante. Garder suffisamment d'espace pour l'image et la sauvegarde existante.

Avant tout démarrage, lire le Compose actuellement installé dans
`/srv/cahier-de-doleances`, sans l'écraser. Examiner les noms de projet, les ports,
les volumes/montages et les réseaux. Ne partager aucun mot de passe ou fichier
d'environnement. Ces commandes complémentaires ne montrent pas les secrets :

```bash
docker inspect cahier-postgres --format '{{.Config.Image}}'
docker inspect cahier-postgres --format '{{json .Mounts}}'
docker inspect cahier-postgres --format '{{json .NetworkSettings.Networks}}'
docker inspect cahier-postgres --format '{{json .NetworkSettings.Ports}}'
docker network inspect cahier-de-doleances_cahier-internal
docker port cahier-postgres
```

Le conteneur doit déjà être membre du réseau indiqué. Si le réseau est absent,
ou si le conteneur n'en fait pas partie, **arrêter ici** : ne pas créer un réseau
de substitution ou recréer PostgreSQL. Le précontrôle ci-dessous vérifiera
effectivement la résolution DNS de `cahier-postgres` depuis le réseau applicatif.

Si 5432 est publié, vérifier ses adresses d'écoute et son accessibilité réelle.
FastAPI ne nécessite aucune publication du port PostgreSQL. Vérifier aussi les
redirections de la box et les règles IPv6 : ni 5432 ni 8000 ne doivent être ouverts
sur Internet pour cette phase. Une publication Docker mérite un contrôle propre,
elle ne doit pas être supposée bloquée par les seules règles habituelles du pare-feu.

## A — Récupérer le dépôt

Les changements de déploiement doivent d'abord être commités et poussés sur GitHub
depuis le poste de développement. Choisir et noter le commit validé. Depuis un
compte ayant les droits sur `/srv`, cloner dans le **nouveau** répertoire :

```bash
git clone https://github.com/Aliochka/cahier-de-doleances.git /srv/cahier-de-doleances-app
cd /srv/cahier-de-doleances-app
git checkout --detach <COMMIT_VALIDE>
test -f compose.deploy.yml
git rev-parse HEAD
```

Remplacer `<COMMIT_VALIDE>` par le SHA contenant ces fichiers. Si le répertoire
applicatif existe déjà, suivre la section mises à jour ; ne pas recloner ni écraser
des fichiers locaux. Ne pas déplacer le répertoire PostgreSQL.

## Variables d'environnement

Pour une première installation uniquement :

```bash
umask 077
cp .env.deploy.example .env.deploy
chmod 600 .env.deploy
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Python est utilisé ici seulement pour générer une clé ; `openssl rand -hex 48`
est une alternative. Éditer `.env.deploy` dans un éditeur privé et renseigner :

| Variable | Valeur ou rôle |
|---|---|
| `APP_IMAGE_TAG` | Tag unique de cette version, par exemple `lan-001`. Ne pas réutiliser un tag déjà déployé. |
| `LAN_BIND_IP` | `192.168.1.56` |
| `ENV` | `prod` : validations de déploiement, sans forcer HTTPS lorsque désactivé explicitement. |
| `BASE_URL` | `http://192.168.1.56:8000` |
| `ALLOWED_HOSTS` | `192.168.1.56,127.0.0.1,localhost`, sans ports et sans joker global. |
| `HEALTHCHECK_HOST` | `192.168.1.56`, doit être autorisé. |
| `COOKIE_SECURE` | `false`, opt-in explicite pour les tests HTTP privés. `HttpOnly` et `SameSite=Lax` restent actifs. |
| `ENFORCE_HTTPS` | `false` pour cette phase. |
| `TRUSTED_PROXY_IPS` | Vide : aucun proxy actuellement. |
| `SECRET_KEY` | Clé aléatoire générée ci-dessus, au moins 32 caractères. Conserver cette clé lors des mises à jour. |
| `DATABASE_URL` | `postgresql+psycopg2://cahier:MOT_DE_PASSE_ENCODE@cahier-postgres:5432/cahier_doleances` |
| `EXPECTED_DB_*`, `EXPECTED_PG_MAJOR`, `EXPECTED_ALEMBIC_REVISION` | Conserver les valeurs confirmées du fichier exemple. |
| `MAILJET_API_KEY`, `MAILJET_SECRET_KEY` | Identifiants nécessaires pour envoyer les liens de connexion. |
| `FROM_EMAIL` | Adresse d'expéditeur validée dans Mailjet ; ne pas configurer le domaine ici. |
| `LOG_MAGIC_LINKS` | `false`, obligatoire en déploiement. |

Utiliser le mot de passe **existant**, sans modifier le rôle PostgreSQL. Encoder
les caractères spéciaux du mot de passe pour une URL (`@` → `%40`, `#` → `%23`,
`%` → `%25`, `/` → `%2F`, etc.). Conserver les guillemets simples autour de
`DATABASE_URL` dans le fichier pour éviter l'interpolation Compose des `$`.
Ne pas placer de secret dans la ligne de commande ou l'historique du terminal.

Ne définir ni `TEST_DATABASE_URL`, ni `ALEMBIC_DATABASE_URL`, ni
`SCALINGO_POSTGRESQL_URL` dans `.env.deploy`. Le conteneur n'embarque pas `.env`.
Les variables de test sont refusées par la configuration de production et le
précontrôle. `.env.deploy` est ignoré par Git et exclu du contexte Docker.

Sans Mailjet, le site démarre et les comptes existants restent présents, mais la
demande de lien de connexion échoue explicitement. Aucun lien de connexion n'est
journalisé en production. Ne pas réactiver leur journalisation pour contourner
une configuration Mailjet absente. En HTTP, les sessions circulent sans chiffrement :
réserver cette phase au réseau privé de confiance.

## B — Valider le Compose et construire l'image

Toutes les commandes suivantes s'exécutent dans `/srv/cahier-de-doleances-app`.
`config --quiet` valide sans afficher les secrets résolus :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml config --quiet
docker compose --env-file .env.deploy -f compose.deploy.yml build app
```

La construction ne se connecte pas à PostgreSQL. L'image contient l'application,
les templates, les fichiers statiques et les migrations pour consultation de
leur état. Elle n'embarque ni données, ni secrets, ni outils d'ingestion.
Elle démarre Gunicorn avec deux workers Uvicorn, sans reload ni migrations.

## C — Vérifier DNS et connexion, en lecture seule

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_check --connection-only
```

Le rapport doit afficher `status: ok`, le nom `cahier-postgres`, ses adresses
résolues, `database: cahier_doleances`, `user: cahier`, une version PostgreSQL
17 et `transaction_read_only: on`. Le processus termine avec le code 1 en cas
de divergence ou d'échec. Ne pas poursuivre dans ce cas.

Cette commande lance uniquement un conteneur FastAPI temporaire sur les réseaux
définis. Elle ne démarre, n'arrête et ne recrée aucun conteneur PostgreSQL.
Le mode read-only et les délais SQL sont imposés dès l'établissement de connexion.

## D — Vérifier Alembic et les objets PostgreSQL

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_check
```

Le contrôle compare les heads du dépôt et `alembic_version` à
`remove_runtime_caches`. Il vérifie les tables et colonnes utilisées par le site,
les extensions `unaccent` et `pg_trgm`, la recherche française sans accents et
la présence/validité des index critiques et les privilèges nécessaires aux comptes,
profils et marque-pages, y compris leurs séquences. Aucun objet manquant n'est créé.

Pour confirmer le nombre de contributions, une fois et séparément du healthcheck :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_check --count-contributions
```

Le résultat attendu est **1 589 285**. Le comptage est limité à 30 secondes ; un
dépassement de délai est un échec à analyser, sans relancer en boucle. Les autres
requêtes du précontrôle sont limitées à 5 secondes.

Pour consulter les commandes Alembic elles-mêmes :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app alembic heads
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps -e PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=5000' app alembic current
```

`heads` lit les fichiers ; `current` consulte la base sous protection read-only.
Ne pas utiliser `upgrade`, `downgrade` ou `stamp`, même si les versions diffèrent.
L'utilisateur applicatif doit posséder les droits de consultation et les droits
d'écriture/séquences nécessaires aux comptes et marque-pages ; toute modification
de privilèges doit être étudiée séparément, sans changer le schéma automatiquement.

## E — Démarrer uniquement FastAPI

Après réussite des contrôles :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml up -d --no-deps --no-build app
docker compose --env-file .env.deploy -f compose.deploy.yml ps
```

Attendre que le conteneur soit `healthy`. Le healthcheck vérifie `SELECT 1` toutes
les 30 secondes et ne parcourt pas les contributions. Un statut `unhealthy`
n'entraîne pas automatiquement un redémarrage Docker : consulter les logs.
La politique `unless-stopped` redémarre un processus qui se termine.

Le conteneur fonctionne sans privilèges, sans capacités Linux supplémentaires,
avec un système de fichiers en lecture seule et `/tmp` en mémoire.

## F — Tester depuis le LAN

Depuis Wallace puis depuis un autre ordinateur du LAN :

```bash
curl --fail http://192.168.1.56:8000/healthz
curl --fail -o /dev/null http://192.168.1.56:8000/
curl --fail -o /dev/null 'http://192.168.1.56:8000/search/answers?q=culture'
curl --fail -o /dev/null http://192.168.1.56:8000/static/css/reset.css
curl --fail -o /dev/null http://192.168.1.56:8000/static/js/scroll-header.js
```

Le healthcheck renvoie `{"status":"ok"}` et les pages/fichiers renvoient 200.
Ouvrir ensuite **http://192.168.1.56:8000** dans un navigateur. Aucun renvoi vers
HTTPS ou vers le domaine public ne doit intervenir. Un Host non autorisé doit
être refusé avec 400.

## G — Recette fonctionnelle

| Fonction | Vérification manuelle |
|---|---|
| Navigation | Accueil, liens, retour arrière et pagination. |
| Recherche | Questions et réponses, mots avec/sans accents, absence de doublons au chargement suivant. |
| Contributions | Ouvrir une réponse textuelle et une réponse à choix multiples ; vérifier qu'elle reste une réponse avec plusieurs sélections. |
| Auteurs | Ouvrir une page auteur depuis une contribution et consulter ses réponses. |
| Questionnaires | Ouvrir un formulaire et ses questions. |
| Statistiques | Ouvrir les tableaux de bord et graphiques ; vérifier nombres et sélections multiples. |
| HTMX | Charger les pages suivantes/filtres ; vérifier les fragments dans l'onglet Réseau du navigateur. |
| Statiques | Styles, image de partage et JavaScript chargés sans 404. |
| Authentification | Demander un lien à une adresse de test, recevoir le courriel, vérifier son origine `http://192.168.1.56:8000`, l'ouvrir depuis le LAN. |
| Cookies | `session_token` avec `HttpOnly`, `SameSite=Lax`, sans `Secure` uniquement pour cette phase HTTP. |
| Profils | Compléter/modifier le profil du compte de test, recharger et vérifier la persistance. |
| Marque-pages | Ajouter, consulter et retirer un marque-page ; tester après reconnexion. |
| Déconnexion | Se déconnecter et vérifier que les pages privées exigent une connexion. |

La recette d'authentification crée/modifie normalement un compte et ses
marque-pages. Elle n'importe ni ne remplace les contributions existantes.
HTMX, Chart.js et les polices sont chargés depuis des CDN : les navigateurs doivent
avoir accès à Internet. Mailjet nécessite une connexion sortante depuis FastAPI.
Ne jamais exécuter pytest ou les tests d'ingestion contre la base de Wallace.

## Logs et diagnostic

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml logs --tail=100 app
docker compose --env-file .env.deploy -f compose.deploy.yml logs -f app
docker compose --env-file .env.deploy -f compose.deploy.yml ps
```

`Ctrl+C` arrête le suivi des logs, pas le service. Docker limite les journaux à
trois fichiers de 10 Mo. Les chemins de connexion `/auth/verify/...` sont masqués
dans les logs d'accès. Les logs peuvent contenir des adresses de comptes : conserver
un accès administrateur restreint. Ne pas partager `docker compose config` sans
`--quiet`, ni un `docker inspect` complet incluant l'environnement.

Une erreur DNS se vérifie en relançant le contrôle de connexion ; une erreur de
schéma avec le contrôle complet. Une connexion qui refuse les identifiants ne se
résout pas en restaurant une nouvelle base. Une erreur Mailjet nécessite des clés
valides et un expéditeur autorisé.

## Mises à jour

1. Noter le commit et `APP_IMAGE_TAG` actuellement déployés. Garder l'ancienne
   image locale et une copie privée de `.env.deploy` si sa configuration doit changer.
2. Vérifier que les changements sont compatibles avec `remove_runtime_caches`.
   Une migration nouvelle implique une procédure séparée, pas ce déploiement.
3. Récupérer le nouveau commit validé :

```bash
cd /srv/cahier-de-doleances-app
git status --short
git rev-parse HEAD
git fetch origin
git checkout --detach <NOUVEAU_COMMIT_VALIDE>
```

4. Changer `APP_IMAGE_TAG` dans `.env.deploy` (par exemple `lan-002`), en conservant
   `SECRET_KEY`, les identifiants et les valeurs de contrôle. Ne pas écraser ce fichier
   avec l'exemple. Valider, construire et contrôler :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml config --quiet
docker compose --env-file .env.deploy -f compose.deploy.yml build app
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_check
```

5. Après réussite seulement :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml up -d --no-deps --no-build app
docker compose --env-file .env.deploy -f compose.deploy.yml ps
curl --fail http://192.168.1.56:8000/healthz
```

Effectuer la recette principale. Une courte interruption est possible pendant
le remplacement du conteneur FastAPI. Ne pas supprimer les anciennes images avant
validation et ne pas utiliser de commande générale de nettoyage des volumes.

## Retour arrière

Revenir au commit et au tag d'image notés avant la mise à jour. Restaurer la
configuration privée précédente si nécessaire, tout en conservant la clé JWT :

```bash
cd /srv/cahier-de-doleances-app
git checkout --detach <ANCIEN_COMMIT_VALIDE>
```

Rétablir l'ancien `APP_IMAGE_TAG` dans `.env.deploy`, puis :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml config --quiet
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps --pull never app python -m app.deployment_check
docker compose --env-file .env.deploy -f compose.deploy.yml up -d --no-deps --no-build --pull never app
curl --fail http://192.168.1.56:8000/healthz
```

Ne pas reconstruire sous l'ancien tag : réutiliser l'image déjà validée. Ce retour
arrière ne touche ni PostgreSQL, ni ses volumes, ni ses données. Il ne supprime pas
les profils ou marque-pages créés pendant la mise à jour et n'exécute aucune
migration inverse. Vérifier qu'aucune écriture métier incompatible n'a été ajoutée
par la nouvelle version avant de revenir en arrière.

## Évolution HTTPS ultérieure, hors de cette phase

Après installation séparée et validation de Caddy : utiliser une `BASE_URL` HTTPS,
mettre `COOKIE_SECURE=true`, activer `ENFORCE_HTTPS` et adapter `ALLOWED_HOSTS`.
Configurer seulement les adresses du proxy dans `TRUSTED_PROXY_IPS`, jamais `*`,
et adapter aussi le healthcheck pour éviter une redirection vers un HTTPS interne
non servi. Restreindre alors l'accès direct au port 8000 ou supprimer sa publication.
Le réseau applicatif distinct permet cette évolution sans déplacer PostgreSQL.

Avant une exposition publique, revoir aussi les limites de trafic/authentification
et le fonctionnement existant des liens magiques, qui restent réutilisables pendant
leur durée de validité. Le remplacement de la bibliothèque JWT conserve le format
HS256 et ne modifie ni les comptes ni le schéma ; un changement de `SECRET_KEY`
invalide cependant toutes les sessions et tous les liens déjà émis.

Aucun domaine, reverse proxy, service RAG ou accès Internet entrant n'est configuré
par ce guide.
