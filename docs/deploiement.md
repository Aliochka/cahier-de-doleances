# Déployer temporairement https://cahierdedoleances.fr sur Wallace

Toutes les opérations de ce guide sont **manuelles, après validation du dépôt**.
Aucune commande n'a été exécutée sur Wallace pendant la préparation.
L'installation LAN est déjà fonctionnelle : ne pas réinstaller PostgreSQL.

## Architecture et invariants

- PostgreSQL 17 reste dans `/srv/cahier-de-doleances`, sur le SSD monté à
  `/data/postgresql`, avec son réseau `cahier-de-doleances_cahier-internal`.
- Le dépôt applicatif reste dans `/srv/cahier-de-doleances-app`, projet Compose
  `cahier-de-doleances-app`. Ne pas changer ce nom entre les commandes.
- `compose.deploy.yml` est la cible HTTPS : seul Caddy publie les ports TCP
  `192.168.1.56:80` et `192.168.1.56:443`. FastAPI ne publie aucun port.
- `compose.deploy.lan.yml`, ajouté **après** ce fichier, conserve temporairement
  `192.168.1.56:8000` et les paramètres HTTP LAN. Il sert aussi au retour arrière.
- Caddy et FastAPI partagent un réseau privé `internal`, `172.30.80.0/24`.
  Caddy y possède l'adresse fixe `172.30.80.2`, seule adresse de proxy autorisée.
  Vérifier l'absence de conflit avec les réseaux Docker, LAN et VPN avant démarrage.
  En cas de conflit, adapter ensemble le sous-réseau, l'adresse Caddy et
  `TRUSTED_PROXY_IPS` ; ne pas autoriser un sous-réseau entier pour contourner cela.
- Caddy n'est pas membre du réseau PostgreSQL. FastAPI conserve un réseau sortant
  pour Mailjet ; Caddy a son propre réseau sortant pour DNS et ACME.
- Les volumes `cahier-de-doleances-app_caddy-data` et
  `cahier-de-doleances-app_caddy-config` conservent certificats, clés et état.
  Les préserver lors des mises à jour et arrêts, avec un accès administrateur privé.

Ne jamais utiliser `down -v`, supprimer les volumes PostgreSQL ou Caddy, lancer
un import, ni exécuter Alembic `upgrade`, `downgrade` ou `stamp` dans cette procédure.
Aucun démarrage n'exécute de migration. Les précontrôles sont en lecture seule.
Les comptes, profils et marque-pages gardent leurs écritures métier normales.
Ne jamais lancer pytest contre la base de Wallace.

## Configuration Caddy et FastAPI

Le [Caddyfile](../Caddyfile) transmet les requêtes de `cahierdedoleances.fr`
à `app:8000` et conserve le Host public. `www.cahierdedoleances.fr` redirige
vers `https://cahierdedoleances.fr` avec le code **308**, en conservant le chemin
et les paramètres de requête grâce à `{uri}`. Ce sous-domaine ne transmet aucune
requête à FastAPI et ne nécessite aucun changement de `ALLOWED_HOSTS` ou `BASE_URL`.
Voir la [documentation redir](https://caddyserver.com/docs/caddyfile/directives/redir).
Caddy obtient et renouvelle automatiquement les certificats pour **les deux domaines**
et redirige HTTP vers HTTPS pour chacun. Aucun plugin DNS
OVH, aucun identifiant OVH et aucun service supplémentaire ne sont nécessaires.
Voir la [documentation HTTPS automatique](https://caddyserver.com/docs/automatic-https).

Caddy ignore les valeurs `X-Forwarded-*` fournies par les visiteurs et produit
les en-têtes de proxy ; `Forwarded` est retiré. Ne pas ajouter `trusted_proxies`
à Caddy pour cette architecture sans proxy en amont. Voir la
[documentation reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
Gunicorn/Uvicorn ont `FORWARDED_ALLOW_IPS` vide : seule la couche FastAPI traite
ces en-têtes, avant la redirection HTTPS, depuis `172.30.80.2` exclusivement.
Cela évite la double interprétation, l'usurpation directe et les boucles HTTPS.

Le healthcheck FastAPI passe en HTTP uniquement depuis le loopback du conteneur
sur `/healthz`, avec un Host autorisé. Toute autre route garde la protection HTTPS.
Le healthcheck Caddy utilise un listener `127.0.0.1:8080` **non publié**, qui teste
le proxy vers le vrai `/healthz` avec le protocole HTTPS annoncé. Ces contrôles
vérifient `SELECT 1`, pas le million de contributions. Ils ne vérifient pas le
certificat public : la recette Internet reste obligatoire.

Les deux services ont `restart: unless-stopped` et des logs Docker limités à
3 fichiers de 10 Mo. `unhealthy` seul ne provoque pas un redémarrage Docker.
HSTS dure seulement 300 secondes, sans sous-domaines ni preload, pour permettre
le retrait temporaire. Les réponses comprennent aussi `nosniff` et une politique
Referrer. Aucune CSP nouvelle n'est imposée aux scripts, graphiques et CDN existants.

## Variables de production et secrets

Conserver la clé `SECRET_KEY`, le mot de passe PostgreSQL et les paramètres
`EXPECTED_*` de l'installation actuelle. **Ne pas écraser `.env.deploy` avec
l'exemple**. Avant modification :

```bash
cd /srv/cahier-de-doleances-app
umask 077
cp .env.deploy .env.deploy.lan-backup
chmod 600 .env.deploy .env.deploy.lan-backup
```

`.env.deploy.lan-backup` est ignoré par Git et exclu du contexte Docker.
Dans un éditeur privé, adapter `.env.deploy` selon [.env.deploy.example](../.env.deploy.example) :

| Variable | Valeur publique |
|---|---|
| `APP_IMAGE_TAG` | Nouveau tag unique, par exemple `https-001` ; conserver l'ancienne image. |
| `LAN_BIND_IP` | `192.168.1.56` |
| `ENV` | `prod` |
| `BASE_URL` | `https://cahierdedoleances.fr` |
| `ALLOWED_HOSTS` | `cahierdedoleances.fr,127.0.0.1,localhost` |
| `HEALTHCHECK_HOST` | `localhost` |
| `COOKIE_SECURE` | `true` |
| `ENFORCE_HTTPS` | `true` |
| `TRUSTED_PROXY_IPS` | `172.30.80.2`, jamais `*` ou une plage ouverte |
| `LOGIN_EMAIL_ENABLED` | `false` tant que Mailjet est indisponible |
| `LOG_MAGIC_LINKS` | `false`, obligatoire en production |
| `SECRET_KEY` | Conserver la clé existante d'au moins 32 caractères. |
| `DATABASE_URL` | URL existante vers `cahier-postgres:5432/cahier_doleances`, rôle `cahier`. |
| `EXPECTED_DB_HOST/NAME/USER` | `cahier-postgres` / `cahier_doleances` / `cahier` |
| `EXPECTED_PG_MAJOR` | `17` |
| `EXPECTED_ALEMBIC_REVISION` | `remove_runtime_caches` |
| `MAILJET_API_KEY`, `MAILJET_SECRET_KEY` | Clés privées, conservées ou renseignées quand disponibles. |
| `FROM_EMAIL`, `FROM_NAME` | Expéditeur validé Mailjet, nom du site. |

Conserver les guillemets simples de `DATABASE_URL` et encoder les caractères
spéciaux du mot de passe dans l'URL. Ne pas définir `TEST_DATABASE_URL`,
`ALEMBIC_DATABASE_URL` ou `SCALINGO_POSTGRESQL_URL`. Ne pas placer de secrets dans
Git, les commandes, captures ou tickets. `docker compose config --quiet` valide
sans les afficher ; un `config` normal ou `inspect` complet peut les révéler.
Caddy reçoit seulement sa configuration, pas les secrets applicatifs.

## Authentification pendant l'indisponibilité de Mailjet

Sans courriel, un nouveau visiteur ne peut pas obtenir son lien magique ; une
session expirée ne peut pas être renouvelée. Les comptes, profils et marque-pages
existants restent présents. Les cookies LAN liés à l'adresse IP ne se transfèrent
pas au domaine public, même avec la même clé JWT.

`LOGIN_EMAIL_ENABLED=false` masque les deux formulaires d'envoi et affiche un
message d'indisponibilité dans les modales de connexion et de marque-pages.
L'API `/auth/send-link` renvoie 503 sans générer de token ni contacter Mailjet.
Les sessions existantes, la vérification de liens déjà émis, les profils,
marque-pages et la déconnexion restent actifs. La consultation, la recherche
et les statistiques restent accessibles sans compte. Le réglage vaut `true`
par défaut hors de cet exemple : ce changement est explicite et réversible.
Ne pas contourner Mailjet en affichant des tokens ou en désactivant l'authentification.

Après réparation de Mailjet, tester avec un compte de recette : réception réelle,
lien commençant par l'origine HTTPS publique, connexion, profil, marque-page,
déconnexion. Pour cette recette puis l'ouverture, mettre `LOGIN_EMAIL_ENABLED=true`
et recréer `app`. En mode de transition LAN, les liens utilisent encore l'origine
LAN : la recette d'authentification publique doit attendre la bascule finale.
Les liens magiques restent réutilisables pendant leur validité, comme auparavant.

## 1 — Préparer la version sur Wallace, sans interrompre le LAN

Noter l'ancien commit et tag d'image, garder l'image locale et la sauvegarde privée.
Après publication manuelle du commit validé depuis le poste de développement :

```bash
cd /srv/cahier-de-doleances-app
git status --short
git rev-parse HEAD
git fetch origin
git checkout --detach <COMMIT_VALIDE>
docker network ls
docker network inspect cahier-de-doleances_cahier-internal
docker inspect cahier-postgres --format '{{json .NetworkSettings.Ports}}'
docker port cahier-postgres
findmnt /data/postgresql
ss -lnt
```

Confirmer le réseau existant, le montage SSD, l'absence de publication PostgreSQL
et la disponibilité de 80/443. Si PostgreSQL est publié, suspendre l'ouverture
publique et faire examiner sa configuration séparément : ce dépôt ne la modifie pas.
Vérifier également les règles Docker, pare-feu, VPN et IPv6 : ne pas supposer
qu'une règle UFW seule filtre toutes les publications Docker.

Après adaptation de `.env.deploy` :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml -f compose.deploy.lan.yml config --quiet
docker compose --env-file .env.deploy -f compose.deploy.yml build app
docker compose --env-file .env.deploy -f compose.deploy.yml pull caddy
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_check
```

Le précontrôle doit indiquer `status: ok`, PostgreSQL 17 et la révision attendue.
Il ne crée aucun objet et ne lance aucune migration. En cas d'échec, arrêter ici.
Le contrôle de quantité optionnel est `python -m app.deployment_check --count-contributions`
avec la même commande `run` : résultat attendu 1 589 285, sans boucle de recomptage.

Démarrer d'abord FastAPI avec l'override LAN, puis Caddy :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml -f compose.deploy.lan.yml up -d --no-deps --no-build app
docker compose --env-file .env.deploy -f compose.deploy.yml -f compose.deploy.lan.yml up -d --no-deps caddy
docker compose --env-file .env.deploy -f compose.deploy.yml -f compose.deploy.lan.yml ps
curl --fail http://192.168.1.56:8000/healthz
curl --fail -o /dev/null 'http://192.168.1.56:8000/search/answers?q=culture'
```

Une courte interruption pendant le remplacement de FastAPI est possible.
Le port 8000 reste lié uniquement à l'adresse LAN ; ne jamais le rediriger sur la box.
La transition conserve HTTP et les cookies LAN non sécurisés ; ne pas y tester des
comptes sensibles. Elle sert à valider Caddy avant d'activer HTTPS côté FastAPI.

## 2 — DNS OVHcloud et Freebox, opérations manuelles

Sauvegarder les valeurs DNS et les règles de ports actuelles pour pouvoir revenir
à leur état antérieur. Dans la zone DNS OVHcloud de `cahierdedoleances.fr`, modifier
l'enregistrement **A du domaine racine** vers `88.163.85.242`. Un TTL de 300 secondes
facilite cette phase ; attendre l'expiration de l'ancien TTL. Retirer les A
concurrents ou redirections web OVH qui ciblent un ancien hébergement. Ne pas
modifier NS, MX, SPF, DKIM ou les entrées des autres services. Ajouter ou remplacer
l'entrée **CNAME `www` vers `cahierdedoleances.fr.`**, sans A/AAAA concurrent sur
`www` ; elle doit résoudre vers la même IPv4. Vérifier les CAA éventuels pour les
deux noms, qui doivent autoriser l'autorité utilisée par Caddy.
Voir le [guide DNS OVHcloud](https://docs.ovhcloud.com/en/guides/web-cloud/domains/faq-domain-dns).

Pour cette installation **IPv4 uniquement**, contrôler le domaine racine et `www`
et retirer tout AAAA qui annoncerait un autre serveur ou une IPv6 non validée. Un AAAA erroné peut
faire échouer clients et validation ACME. Ne pas remplacer par l'IPv6 de la box.
Ne publier un AAAA à l'avenir qu'après validation de l'adresse stable de Wallace,
des écouteurs Docker IPv6, du pare-feu et de tests externes `curl -6`.
L'IPv6 Free est activé automatiquement : l'absence de AAAA ne protège pas une
adresse connue. Vérifier qu'aucun service Wallace, notamment 5432/8000, n'est
accessible par son IPv6 globale ; vérifier le pare-feu IPv6 Freebox et Wallace.
Voir [Free IPv6](https://assistance.free.fr/articles/356) et
[OVHcloud AAAA](https://docs.ovhcloud.com/fr/guides/web-cloud/domains/dns-zone-aaaa-record-creation).

Dans Freebox OS, Paramètres de la Freebox, mode avancé, Gestion des ports,
créer seulement ces redirections (intitulés à vérifier sur la version installée) :

| Protocole | Port WAN début/fin | Destination | Port LAN |
|---|---|---|---|
| TCP | 80 / 80 | 192.168.1.56 | 80 |
| TCP | 443 / 443 | 192.168.1.56 | 443 |

Fixer le bail DHCP de Wallace à cette adresse. Selon les informations fournies,
80 et 443 appartiennent à la plage partagée 0–16383 : pas de demande full-stack
nécessaire. Confirmer ces informations dans Freebox OS. Pas de DMZ, pas d'ouverture
5432/8000, pas d'UDP 443 (HTTP/3 désactivé ici). Vérifier que l'accès distant
Freebox n'occupe pas ces ports et qu'aucune autre règle ne les utilise.

## 3 — Certificat et recette depuis Internet

Caddy tentera automatiquement l'émission pour les deux domaines une fois leurs
DNS et les ports accessibles. `www` nécessite un certificat valide avant de pouvoir
servir sa redirection HTTPS.
Les challenges HTTP-01/TLS-ALPN-01 passent par TCP 80/443 ; autoriser DNS et HTTPS
sortants pour Caddy. Ne pas supprimer les volumes pour relancer une émission,
ne pas redémarrer en boucle après un échec : inspecter DNS, AAAA, CAA, ports et logs.
Les renouvellements requièrent aussi que le serveur et l'accès public restent
fonctionnels. Après une longue extinction, un certificat expiré nécessitera
une nouvelle émission au redémarrage. L'heure système doit être correcte.

Depuis une connexion extérieure (mobile sans Wi-Fi ou autre machine distante) :

```bash
dig +short A cahierdedoleances.fr
dig +short AAAA cahierdedoleances.fr
dig +short CNAME www.cahierdedoleances.fr
dig +short A www.cahierdedoleances.fr
dig +short AAAA www.cahierdedoleances.fr
curl -4 -I 'http://www.cahierdedoleances.fr/search/answers?q=culture&page=2'
curl -4 -I 'https://www.cahierdedoleances.fr/search/answers?q=culture&page=2'
curl -4 --fail --max-redirs 3 -L -o /dev/null 'http://www.cahierdedoleances.fr/search/answers?q=culture&page=2'
curl -4 -I http://cahierdedoleances.fr/
curl -4 --fail --max-redirs 3 -L -o /dev/null https://cahierdedoleances.fr/
curl -4 --fail https://cahierdedoleances.fr/healthz
curl -4 --fail -o /dev/null 'https://cahierdedoleances.fr/search/answers?q=culture'
curl -4 -I https://cahierdedoleances.fr/static/css/reset.css
curl -4 -I -H 'X-Forwarded-Proto: http' https://cahierdedoleances.fr/static/css/reset.css
curl -4 -I -H 'X-Forwarded-Proto: https' http://cahierdedoleances.fr/
openssl s_client -connect cahierdedoleances.fr:443 -servername cahierdedoleances.fr -verify_return_error </dev/null
openssl s_client -connect www.cahierdedoleances.fr:443 -servername www.cahierdedoleances.fr -verify_return_error </dev/null
```

Les deux noms doivent résoudre vers `88.163.85.242`, sans adresse IPv6 annoncée
(`dig` peut afficher la cible CNAME pour `www`). HTTPS sur `www` doit renvoyer 308
avec `Location: https://cahierdedoleances.fr/search/answers?q=culture&page=2`.
HTTP sur `www` redirige d'abord en 308 vers son HTTPS, puis vers le domaine racine ;
le chemin et les paramètres doivent rester identiques aux deux étapes.
HTTP sur le domaine racine doit rediriger vers son HTTPS,
même avec un faux en-tête. HTTPS doit réussir avec certificat valide, sans `-k`,
sans boucle et avec les en-têtes attendus. Inspecter aussi le certificat dans le
navigateur (domaine, chaîne, expiration). Le test du faux en-tête HTTPS doit être
répété après la bascule finale. Le healthcheck Docker ne suffit pas pour la recette TLS.
Pour vérifier le mode courriel indisponible (attendu : HTTP 503, sans envoi) :

```bash
curl -4 -i https://cahierdedoleances.fr/auth/send-link -H 'Content-Type: application/json' --data '{"email":"recette@example.org"}'
```

Tester que TCP 8000 et 5432 sont inaccessibles depuis Internet (avec un outil de
scan depuis l'extérieur) ; si Wallace a une IPv6 globale, tester aussi cette adresse
pour tous les ports concernés, même sans AAAA. En IPv4 seul, `curl -6` sur le domaine
ne doit pas atteindre un autre hébergement. Un test LAN ne prouve pas l'accès Internet.

## 4 — Bascule finale : HTTPS FastAPI et suppression de 8000

Après réussite de la recette Caddy, utiliser **uniquement** le Compose de base.
Cela applique les valeurs HTTPS de `.env.deploy` et retire la publication 8000 :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml config --quiet
docker compose --env-file .env.deploy -f compose.deploy.yml up -d --no-deps --no-build app
docker compose --env-file .env.deploy -f compose.deploy.yml ps
docker compose --env-file .env.deploy -f compose.deploy.yml port app 8000
docker compose --env-file .env.deploy -f compose.deploy.yml logs --tail=100 caddy app
```

`port app 8000` doit indiquer qu'aucun port n'est publié (peut terminer non-zéro).
Depuis une autre machine LAN, `http://192.168.1.56:8000` doit devenir inaccessible.
Refaire **tous** les tests Internet ci-dessus, notamment faux `X-Forwarded-Proto`,
redirections, `/healthz` et recherche. Attendre les deux services `healthy`.
Ne plus utiliser l'override LAN pour les mises à jour publiques.

Recette navigateur après bascule :

| Fonction | Vérification |
|---|---|
| Navigation | Accueil, contributions, auteurs, formulaires, questions, pagination. |
| Recherche | Questions/réponses, mots avec et sans accents, filtres et fragments HTMX sans doublons. |
| Contributions | Texte libre et choix multiples avec toutes les sélections. |
| Statistiques | Tableaux, graphiques, nombres et choix multiples. |
| Statiques | CSS, JS, images, CDN ; aucune URL interne, aucun contenu mixte HTTP. |
| Connexion indisponible | Les deux modales annoncent l'indisponibilité, sans formulaire d'envoi ; consultation possible. |
| API indisponible | `/auth/send-link` renvoie 503 si le réglage est désactivé. |
| Après réparation Mailjet | Réception du lien HTTPS, connexion, profil, ajout/retrait de marque-page, persistance et déconnexion. |
| Cookies après connexion | `session_token` avec `Secure`, `HttpOnly`, `SameSite=Lax` ; mêmes attributs à la suppression. |

Les essais de compte effectuent des écritures métier normales ; utiliser seulement
un compte de recette autorisé. Aucun test automatique ne doit cibler les données
Wallace. Si le domaine n'est pas accessible depuis le LAN à cause du NAT loopback,
utiliser un DNS LAN ou temporairement `curl --resolve cahierdedoleances.fr:443:192.168.1.56`
avec l'URL HTTPS publique ; ne pas désactiver la vérification TLS.

## Logs, mises à jour et retour arrière

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml logs --tail=100 caddy app
docker compose --env-file .env.deploy -f compose.deploy.yml logs -f caddy app
docker compose --env-file .env.deploy -f compose.deploy.yml ps
```

`Ctrl+C` quitte le suivi. Caddy journalise ses opérations et erreurs, sans log
d'accès ajouté : les chemins de liens magiques contiennent des tokens.
Les logs d'accès FastAPI masquent `/auth/verify/...`. Les erreurs peuvent encore
contenir des informations personnelles ou des requêtes : accès administrateur,
pas de partage brut des logs, pas de mode debug en production.

Pour une mise à jour : noter commit/tag, conserver l'ancienne image et la clé JWT,
récupérer le commit validé, changer le tag, refaire `config --quiet`, `build app`,
précontrôle puis `up -d --no-deps --no-build app` avec le Compose de base seulement.
Pour une mise à jour Caddy, valider le Caddyfile puis recréer Caddy en gardant ses
volumes et le nom du projet. Une interruption courte est possible.

**Retour immédiat au LAN**, sans changer de version : retirer d'abord les deux
redirections Freebox et toute ouverture IPv6 éventuelle, puis :

```bash
cd /srv/cahier-de-doleances-app
docker compose --env-file .env.deploy -f compose.deploy.yml stop caddy
docker compose --env-file .env.deploy -f compose.deploy.yml -f compose.deploy.lan.yml config --quiet
docker compose --env-file .env.deploy -f compose.deploy.yml -f compose.deploy.lan.yml up -d --no-deps --no-build app
curl --fail http://192.168.1.56:8000/healthz
```

Le même binaire et les comptes sont conservés ; seul l'accès devient HTTP LAN.
La désactivation de courriel reste celle de `.env.deploy`. Pour revenir également
à l'ancienne version : après arrêt Caddy, restaurer l'ancien commit, le fichier
privé `.env.deploy.lan-backup` vers `.env.deploy` et l'ancien tag, puis utiliser
le Compose de cet ancien commit : `config --quiet`, précontrôle `run --rm --no-deps
--pull never app python -m app.deployment_check`, puis `up -d --no-deps --no-build
--pull never app`. Ne pas reconstruire sous l'ancien tag et ne pas appliquer de
migration inverse. Garder les volumes Caddy pour une prochaine tentative.

## Arrêt temporaire, redémarrage et retrait de l'exposition

Pour retirer l'accès public : supprimer manuellement les redirections TCP 80/443
Freebox et les éventuelles autorisations IPv6, arrêter Caddy, restaurer ou retirer
l'enregistrement A public et le CNAME `www` selon la sauvegarde DNS
(la propagation n'est pas immédiate).
Conserver les entrées des autres services. Vérifier depuis Internet l'inaccessibilité.
Le DNS seul n'arrête pas l'accès à une IP connue. Attendre au plus 300 secondes
pour l'expiration du HSTS déjà mémorisé ; ce domaine reste destiné à HTTPS.

Avant extinction de Wallace :

```bash
cd /srv/cahier-de-doleances-app
docker compose --env-file .env.deploy -f compose.deploy.yml stop -t 30 caddy app
cd /srv/cahier-de-doleances
docker compose stop -t 60
sudo shutdown -h now
```

La commande PostgreSQL suppose le même Compose et les mêmes options que lors du
démarrage existant : s'il utilise d'autres fichiers/options, reprendre **sa commande
habituelle**, sans modifier sa configuration. Vérifier qu'il est bien arrêté avant
extinction. Ne pas débrancher le SSD et ne pas démonter un volume utilisé.

Au redémarrage, vérifier d'abord `findmnt /data/postgresql`, puis relancer
PostgreSQL avec sa commande existante dans `/srv/cahier-de-doleances`.
Un montage manquant impose l'arrêt de la procédure. Ensuite :

```bash
cd /srv/cahier-de-doleances-app
docker compose --env-file .env.deploy -f compose.deploy.yml run --rm --no-deps app python -m app.deployment_check
docker compose --env-file .env.deploy -f compose.deploy.yml up -d --no-deps --no-build app caddy
docker compose --env-file .env.deploy -f compose.deploy.yml ps
```

Ces commandes réutilisent les volumes/certificats. Si l'accès doit rester LAN,
utiliser l'override LAN et démarrer seulement `app`, sans Caddy et sans redirections.
Pour réexposer le domaine, refaire les contrôles DNS/ports et toute la recette
Internet. Les conteneurs explicitement arrêtés avec `stop` ne redémarrent pas
simplement par la politique `unless-stopped` : utiliser `up -d`.
