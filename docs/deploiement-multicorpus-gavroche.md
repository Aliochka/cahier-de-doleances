# Préparer le multicorpus en production — Gavroche

État du **8 novembre 2026**. Diagnostic réel effectué en lecture seule. **Aucune migration, aucun import, aucune sauvegarde lourde, aucun build/restart de production et aucune publication n'ont été exécutés.** Les commandes d'exploitation ci-dessous sont futures et requièrent l'autorisation correspondante.

Ce document remplace les hypothèses « Wallace » pour cette opération. Les anciens guides restent des références historiques. La préparation repose sur le code local `79dfefe7d21b9035318c043bb194b5a770513ed7`, plus les fichiers de cette mission à revoir et versionner avant déploiement.

## 1. Environnement réellement observé

Accès : `ssh gavroche@192.168.1.185`, machine **Gavroche**, Linux amd64. Le compte nécessite sudo pour Docker ; aucun changement de groupe, de droits du socket ou de sudoers n'a été effectué. Les mots de passe ont été saisis par l'opérateur dans son terminal, pas transmis à l'agent.

| Élément | État vérifié |
|---|---|
| Checkout applicatif | `/srv/cahier-de-doleances-app`, branche `main`, commit `818b5464f24cac4d8537793c15c8e2c580505f88` |
| Projet applicatif Docker | `cahier-de-doleances-app` ; `compose.deploy.yml` puis `compose.search.yml` ; `.env.deploy` privé, root:root 0600 |
| Projet PostgreSQL indépendant | `cahier-de-doleances` ; `/srv/cahier-de-doleances/compose.yaml` puis `/srv/cahier-de-doleances-app/deploy/postgres/compose.pgvector.override.yml` |
| PostgreSQL | Conteneur `cahier-postgres`, 17.11, pgvector 0.8.7 ; port 5432 non publié |
| Application | `cahier_doleances`, OID **16384**, `forms_statistics_v1`, ~13,72 Gio, locale `en_US.utf8` |
| Recherche | **`cahier_search`**, OID **634726**, `rag_0007`, ~76,83 Gio, locale **`fr_FR.UTF-8`**, fournisseur libc |
| Identité du cluster | **`7695026423032606758`**, pour les deux bases |
| GDN indexé | Compteurs de manifeste : **5 172 356 documents / 5 187 190 segments**, verified/extraction_complete/vectors_complete vrais |
| Schéma historique | `documentary` **absent** de production |
| Sources PostgreSQL persistantes | `/data/postgresql/pg17/data` → `/var/lib/postgresql/data`, RW ; `.ssd-mounted` → `/run/ssd-mounted`, RO |
| SSD PostgreSQL | UUID `624405d4-3422-4b7d-8ca3-8579d8b513bb`, ~311 Gio libres |
| Sauvegardes | `/backups/postgresql`, disque distinct UUID `52ba8e78-4375-4286-8c75-5cfef6609c8a`, ~1,60 Tio libres |
| Docker | Racine `/var/lib/docker`, filesystem `/`, ~182 Gio libres ; Compose **5.7.0** |
| Ressources | **8 CPU**, ~62,56 Gio RAM, ~60,4 Gio disponibles ; ~11,5 Gio swap inutilisés au relevé |
| État des services | App, frontend, Caddy et PostgreSQL `healthy`, démarrés le 6 novembre ; `restart: unless-stopped` |

Images actives, sans label OCI de commit permettant de certifier leur correspondance au checkout :

| Service | Tag réel | Identité image observée |
|---|---|---|
| Backend | `cahier-de-doleances-app:search-in-question` | `sha256:e0c26f229536597004ef299d6e8406fb087916d0511eabe8bd02e5543070c7cd` |
| Frontend | `cahier-de-doleances-frontend:search-in-question` | `sha256:73e31e5b321040259aae7769d5fc4eaebcd90c493ebdc85f1168d1313176a1eb` |
| PostgreSQL | `cahier-postgres-pgvector:17.11-0.8.7` | `sha256:30ee450c42fda0596abaf71066c1612c79a0aaa791e655e5e00ce2c1e33ab6cc` |
| Caddy | `caddy:2.11.2-alpine` | `sha256:834468128c7696cec0ceea6172f7d692daf645ae51983ca76e39da54a97c570d` |

### Recherche, modèle et réseaux

- H1 est activé : `HYBRID_SEARCH_ENABLED=true`, CPU, float32, **2 threads**, recette **`h1-public-v2-ts-rank`**. Un worker Gunicorn reste prévu ; les budgets et la file existants ne sont pas augmentés.
- Modèle monté RO : `/srv/cahier-search/models` → `/models`. Snapshot BGE-M3 `5617a9f61b028005a4858fdac845db406aefb181`, empreinte de manifeste **`fe2f29e9b4699cfeb8ee4d9524c1e99df203cb4f144dbe4b463e28e65e3d1f6d`**, identique à la recette des représentations 1789. Le modèle existe sur disque ; ses fichiers n'ont pas été transférés ou recalculés ici.
- Lecteur RO : `/srv/cahier-de-doleances-app/rag/search-reader.env` → `/run/search/reader.env`. Rôle **`cahier_search_reader`**, quatre connexions, sans appartenance à un rôle écrivain. Source : `cahier_doleances` ; cible : `cahier_search`, hôte Docker `cahier-postgres:5432`.
- Publication GDN existante : `/srv/cahier-search/private/publication.json`, identifiant `f65141228f5229bc35d2619f949ea477`, association physique conforme aux bases relevées. Clefs de curseur/publication présentes. **Ne pas les régénérer ni réécrire cette publication.**
- Maintenance : `cahier_search_maintenance`, LOGIN, deux connexions, non administrateur, sans droit CREATE ni appartenance à un rôle ; propriétaire RAG : `cahier_search_owner`, NOLOGIN. Le superutilisateur existant `cahier` sert uniquement aux commandes administratives explicites.
- Backend : IP privée proxy `172.30.80.3`, réseau PostgreSQL `172.18.0.3`. Frontend : `172.30.80.4`, `API_BASE_URL=http://app:8000`. Caddy : `172.30.80.2`, seul exposé en TCP 80/443 sur `192.168.1.185`. PostgreSQL : `172.18.0.2` sur `cahier-de-doleances_cahier-internal`.
- `ENV=prod`, HTTPS imposé, seul Caddy proxy de confiance. Les chemins `/api/*` restent servis par FastAPI ; les pages `/parcourir/*` par le SSR. Volumes Caddy nommés `cahier-de-doleances-app_caddy-data` et `..._caddy-config`, sous `/var/lib/docker/volumes/`, à conserver.

Observations de consommation, pas des limites : backend ~800 Mio, frontend ~309 Mio, PostgreSQL ~345 Mio, Caddy ~67 Mio à l'instant du relevé. Les conteneurs actifs n'ont pas de limite CPU/RAM déclarée. Ne pas en déduire le pic d'une recherche, d'un build ou d'une sauvegarde.

### Démarrage et risque de volume vide

Le Dockerfile/override PostgreSQL réellement actif utilise `existing-cluster.sh`, `command: [postgres]`, des bind mounts avec `create_host_path:false`, le marqueur SSD et les contrôles de PG_VERSION/propriété. Le garde n'exécute ni initdb ni chown. Le service Docker a **`RequiresMountsFor=/data/postgresql`**, avec `Requires` et `After` sur `data-postgresql.mount`, malgré le `nofail` de fstab.

**Le Compose PostgreSQL de base seul est insuffisant** : il indique `postgres:17`. L'override actif est indispensable. Cette opération ne demande aucun remplacement ou redémarrage de PostgreSQL : **ne lancer aucune commande `up` dans son projet**, ne pas utiliser `down -v`, `volume prune` ni `initdb`. Recontrôler mountpoint, UUID, PGDATA, identité SQL et image avant toute maintenance. Un marqueur seul ne prouve pas le bon disque ; une copie physique peut aussi conserver l'identifiant du cluster.

### Merge dans main

Les workflows versionnés lancent contrôles backend, RAG, contrat et frontend sur `main`. Ils construisent des images de test, mais ne publient pas d'image ni ne contiennent de commande SSH de déploiement vers Gavroche. Aucun conteneur Watchtower, cron de déploiement root/utilisateur, timer de déploiement ou hook Git actif n'a été observé. Le checkout distant est encore antérieur au code local.

Cela ne certifie pas l'absence d'une intégration externe GitHub/Netlify non visible dans le dépôt. **Confirmer côté administration GitHub/Netlify l'absence de webhook de déploiement avant le merge.** Aucun accès à cette administration n'a été utilisé. Un fichier privé `.env.deploy.avant-gavroche` est actuellement non suivi sur le serveur : ne jamais faire de `git add -A` ; l'exclusion `.env.deploy.avant-*` est ajoutée localement dans cette préparation.

## 2. Préparation livrée et limites

| Fichier | Rôle |
|---|---|
| `scripts/inspect_multicorpus_production.py` | Relevé distant RO, sortie nettoyée ; authentification sudo dans le terminal de l'opérateur ; aucun fichier installé sur le serveur |
| `documentary/production.py` | Cible Gavroche épinglée ; inspection par défaut RO ; import uniquement avec option explicite et attestation fraîche ; rôle documentaire dédié ; garde SQL et refus de publication |
| `deploy/documentary/provision-gavroche.sql` | Préprovisionnement idempotent du seul propriétaire/schéma documentaire, après vérification physique ; non exécuté en production |
| `deploy/documentary/multicorpus-gavroche.disabled.json` | Configuration correcte pour Gavroche, **enabled=false, local_preview=false** |
| `deploy/documentary/backup-proof.example.json` | Modèle d'attestation volontairement invalide/non vérifié |
| `deploy/documentary/publication-authorization.example.json` | Modèle d'autorisation volontairement **approved=false** |
| `deploy/documentary/activate-1789.sql` | Promotion initiale séparée, transactionnelle, journalisée et limitée aux 1 224 candidats ; non exécutée en production |

Les gardes locaux d'origine restent stricts. Le nouveau client de maintenance n'accepte que `cahier_search_maintenance@127.0.0.1:55495/cahier_search` via le tunnel SSH explicite, puis vérifie le cluster/OID/révision/vector à chaque transaction. Ses écritures s'exécutent sous **`cahier_documentary_owner`**, sans droit GDN, après preuve opérateur de sauvegarde complète/restauration de moins de 24 heures. Il interdit toute mutation SQL hors documentary et refuse, avant commit, une release prête/publiée, un pointeur actif ou des permissions documentaires publiques. L'import ne peut donc pas servir à publier.

`documentary.storage.migrate` évite de recréer un schéma déjà préprovisionné : son propriétaire n'a pas besoin de CREATE sur la base. La chaîne reste `documentary.alembic_version=doc_0001`, indépendante de `public.rag_alembic_version=rag_0007` et de la chaîne applicative. Le SQL `doc_0001` existant n'est pas modifié ; son empreinte est épinglée dans la garde. Aucun Alembic n'est appelé au démarrage des serveurs.

Les commandes actuelles de phase 1/2 refusent volontairement les releases publiques et les événements de publication supplémentaires. **Après promotion, leur réimport doit s'arrêter**, pas retirer la publication ou ignorer les nouveaux événements. L'autorisation de publication versionnée est une entrée distincte ; les projections de contenu d'origine conservent leur hash. Les prochaines évolutions éditoriales après publication devront intégrer explicitement ce second flux ; ne pas relancer l'ancien import sur une release active.

## 3. Données historiques prêtes au transfert

Paquet préparé localement, ignoré par Git :

```text
private/search/production-preparation/transfer-1789.tar
101560320 octets
SHA256 1d4b991d51171921ce2efa121ac1a6bb69c87060c3d6a03dcf020c3b02c1f804
```

Il contient 15 fichiers : archive documentaire complète, collection immuable et son manifeste, pointeur `current.json`, décisions versionnées et manifeste externe de transfert. Aucun journal privé de revue n'est inclus. L'archive seule fait 76 500 332 octets, SHA256 **`a9196d21f3abe5c8198cf4f13c05826e6ab21f37ec109b09571523c36c3e3275`**. Elle contient **1 267 documents, 11 391 passages, 10 748 vecteurs**, les 38 notices sans texte dans le manifeste, les 43 autres documents non candidats et zéro publication. Les 10 748 vecteurs ne sont ni recalculés ni contextualisés à nouveau.

Hashes de référence : source `eb9f4533e95df62a8964fbd6a71d56c0446b7769f6fa9d80fcdd8c0111e08ff2`, décisions `2b2b4c14e33ed5b7908a7e0304a980143c803c088af5dd8234690a81a8314cba`.

Mesure locale du schéma documentaire complet : **378 183 680 octets (~360,7 Mio)**, index et TOAST inclus. Réserver au moins 2 Gio supplémentaires sur le stockage PostgreSQL pour l'import, ses dérivés et une marge WAL ; cela ne comprend ni les images ni les sauvegardes complètes. La taille exacte après import en production sera contrôlée, pas déduite de la taille compressée du paquet.

Production et export local utilisent tous deux `fr_FR.UTF-8`, PostgreSQL 17.11 et `pg_catalog.french`. Le défaut global de production est `pg_catalog.english` : il ne faut pas le modifier, les requêtes documentaires nomment explicitement `french`. La sonde « École privilèges jurandes agriculture » donne `'agricultur':4 'jurand':3 'privileg':2 'écol':1` dans la cible. Les statistiques transférées comptent **86 341 termes**, N=10 748, somme des DF=1 770 363.

L'import conserve initialement les dérivés lexicaux transférés et recalcule indépendamment leurs valeurs attendues sur la destination pour vérifier leur compatibilité. À la moindre divergence, il échoue sans publication. Après examen, `--rebuild-lexical` reconstruit **uniquement les tsvector/DF documentaires**. Les statistiques GDN ne sont jamais recalculées. Aucun HNSW documentaire n'est créé.

## 4. Conditions de passage avant toute écriture

1. Autoriser une fenêtre de maintenance et la charge de sauvegarde/build ; désigner l'opérateur et le commit approuvé **après** intégration de ces fichiers.
2. Effectuer et restaurer les sauvegardes du [protocole dédié](sauvegarde-gavroche-multicorpus.md). Les anciennes copies ne suffisent pas. Décider de la copie hors serveur et de la rétention.
3. Conserver les images exactes et configurations précédentes ; ne pas écraser `.env.deploy` par un exemple. Vérifier les UUID et la dépendance Docker après tout redémarrage.
4. Répéter les builds Docker CPU/frontend et les contrôles d'image. **Docker n'est pas disponible sur la machine de préparation ; aucun nouveau build Docker n'a été exécuté ici**, et construire sur Gavroche serait déjà une modification hors autorisation actuelle.
5. Vérifier l'authentification de réplication, l'espace de sauvegarde et l'état des connexions. Ne pas augmenter le budget de recherche.
6. Le déploiement technique n'autorise aucune publication. L'exemple d'autorisation reste false.

## 5. Déploiement technique futur — sans publication

### A. Sauvegardes et conservation

Commencer par le protocole de sauvegarde. Les variables `MC_STAMP`, `MC_BACKUP`, `MC_ROOT` du shell root de ce protocole restent nécessaires. **Aucune étape suivante si une sauvegarde, restauration ou vérification échoue.** L'attestation doit être remplie sur les faits réels, pas activée pour débloquer l'import.

### B. Code et images

Depuis le compte gavroche, choisir le SHA complet approuvé (pas un `main` mouvant), vérifier les modifications suivies et récupérer ce commit. Ne pas nettoyer les fichiers privés non suivis. Dans le shell root d'exploitation, après récupération du code :

Récupération préalable, dans un autre terminal connecté comme gavroche :

```bash
set -euo pipefail
cd /srv/cahier-de-doleances-app
read -r -p 'SHA complet approuvé après merge : ' MC_APPROVED_REVISION
[[ "$MC_APPROVED_REVISION" =~ ^[0-9a-f]{40}$ ]]
git diff --quiet
git diff --cached --quiet
git fetch origin main
git merge-base --is-ancestor "$MC_APPROVED_REVISION" origin/main
git checkout --detach "$MC_APPROVED_REVISION"
test -f documentary/production.py
```

Puis reprendre le shell root qui conserve les variables de sauvegarde :

```bash
cd /srv/cahier-de-doleances-app
MC_REVISION=$(git -c safe.directory="$MC_ROOT" rev-parse HEAD)
test -z "$(git -c safe.directory="$MC_ROOT" status --porcelain --untracked-files=no)"
# Comparer MC_REVISION au SHA approuvé avant de continuer.
export MC_TAG="mc-${MC_REVISION:0:12}"
docker build --pull=false --build-arg SEARCH_RUNTIME=cpu \
  --label "org.opencontainers.image.revision=$MC_REVISION" \
  -t "cahier-de-doleances-app:$MC_TAG" .
docker build --pull=false -f frontend/Dockerfile \
  --label "org.opencontainers.image.revision=$MC_REVISION" \
  -t "cahier-de-doleances-frontend:$MC_TAG" frontend
docker run --rm --pull=never --network none --read-only --tmpfs /tmp \
  "cahier-de-doleances-app:$MC_TAG" python -m app.search_packaging
```

Vérifier les imports `documentary` et `multicorpus` dans l'image CPU. Les poids BGE restent montés en RO, pas intégrés au build. Conserver une image/tag neuf sans remplacer `search-in-question` ; enregistrer les nouveaux ID avec les anciens. Aucun rebuild de PostgreSQL n'est requis.

### C. Préprovisionnement documentaire

Seulement après sauvegardes et autorisation du déploiement technique :

```bash
docker exec -i cahier-postgres psql -X -v ON_ERROR_STOP=1 -U cahier -d cahier_search \
  < "$MC_ROOT/deploy/documentary/provision-gavroche.sql"
```

Le nouveau rôle NOLOGIN ne possède que documentary ; le rôle maintenance en devient membre. Aucun droit GDN ou rôle lecteur public n'est élargi. Les grants SELECT du lecteur sur les tables documentaires sont appliqués par le transfert ; le journal `editorial_decision` lui est explicitement interdit.

### D. Transfert durable et import contrôlé

Créer, sur Gavroche après autorisation, une destination neuve privée appartenant à gavroche : `/srv/cahier-search/transfers/1789-1d4b991d51171921`. Depuis la machine locale :

```bash
scp -o ControlPath=/tmp/cahier-gavroche-audit.sock \
  private/search/production-preparation/transfer-1789.tar \
  private/search/production-preparation/transfer-1789.sha256 \
  gavroche@192.168.1.185:/srv/cahier-search/transfers/1789-1d4b991d51171921/
```

Sur Gavroche, vérifier depuis ce répertoire `sha256sum -c transfer-1789.sha256`, puis extraire dans un **nouveau sous-répertoire** en conservant la protection 0700. Ne pas extraire sur le checkout ni sur PGDATA. Conserver une seconde copie protégée hors serveur. Le paquet n'est pas un répertoire temporaire et ne contient aucune configuration du laboratoire à monter en production.

L'import se pilote depuis la machine de préparation, avec ses binaires PG17/pgvector et les artefacts immuables. Un tunnel neuf peut être ouvert après authentification :

```bash
ssh -M -S /tmp/cahier-gavroche-audit.sock -o ControlPersist=30m -fN gavroche@192.168.1.185
ssh -S /tmp/cahier-gavroche-audit.sock -O forward \
  -L 127.0.0.1:55495:172.18.0.2:5432 gavroche@192.168.1.185
```

Vérifier préalablement que `172.18.0.2` est toujours l'IP du conteneur PostgreSQL inventorié. Créer un **nouveau fichier local privé** contenant uniquement `DOCUMENTARY_PRODUCTION_URL` :

```python
import io, os, subprocess
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

raw = subprocess.run([
    'ssh','-S','/tmp/cahier-gavroche-audit.sock','-o','BatchMode=yes',
    'gavroche@192.168.1.185','cat /srv/cahier-search/private/maintenance.env',
], capture_output=True, text=True, check=True).stdout
values = dotenv_values(stream=io.StringIO(raw), interpolate=False)
url = make_url(values['RAG_DATABASE_URL']).set(
    drivername='postgresql+psycopg2', host='127.0.0.1', port=55495)
with os.fdopen(os.open('private/search/production-preparation/production.env',
                      os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), 'w') as f:
    f.write('DOCUMENTARY_PRODUCTION_URL=' + url.render_as_string(hide_password=False) + '\n')
```

Ne pas afficher cette URL et ne pas utiliser la configuration du lecteur public comme écrivain. La base source du laboratoire n'est jamais raccordée au backend de production : l'archive est restaurée dans un **nouveau cluster local privé** uniquement pendant le transfert, puis supprimée.

```bash
.venv/bin/python -m documentary.production inspect \
  --maintenance-env private/search/production-preparation/production.env

# APRÈS AUTORISATION ET PREUVE DE SAUVEGARDE/RESTAURATION RENSEIGNÉE :
.venv/bin/python -m documentary.production import --execute-import \
  --maintenance-env private/search/production-preparation/production.env \
  --backup-proof private/search/production-preparation/backup-proof.json \
  --source-archive private/search/phase4/documentary-local.dump \
  > private/search/production-preparation/import-production.json
```

Pour reconstruire depuis le paquet seul, utiliser son `documentary.dump` et replacer les artefacts de référence aux chemins attendus du checkout de préparation, avec leurs empreintes vérifiées, sans écraser une collection différente. Les dépendances PG17/pgvector/locales doivent être disponibles sur cette machine, pas installées implicitement sur le serveur. Sans `--source-archive`, la seule source alternative est le `cahier_rag` local déjà identifié ; aucune source implicite n'est choisie.

L'import applique `doc_0001`, rejoue les décisions, copie les représentations par identifiants/empreintes, vérifie textes/offsets/vecteurs/statistiques, ANALYZE uniquement documentary et compare l'état/statistiques/identités des index GDN avant/après. Réexécuter la même commande avant publication doit être idempotent. En cas de divergence linguistique, examiner l'erreur puis répéter avec `--rebuild-lexical` ; aucun embedding n'est recalculé. Un échec peut laisser une préparation documentaire partielle, toujours non publiée : diagnostiquer/rejouer, jamais supprimer GDN.

### E. Nouvelle application avec multicorpus désactivé

Dans le shell root Gavroche :

```bash
MC_APP_UID=$(docker exec cahier-de-doleances-app-app-1 id -u)
MC_APP_GID=$(docker exec cahier-de-doleances-app-app-1 id -g)
install -m 600 -o "$MC_APP_UID" -g "$MC_APP_GID" \
  "$MC_ROOT/deploy/documentary/multicorpus-gavroche.disabled.json" \
  /srv/cahier-search/private/multicorpus.json
cat > /srv/cahier-search/private/multicorpus-images.yml <<EOF
services:
  app:
    image: cahier-de-doleances-app:$MC_TAG
  frontend:
    image: cahier-de-doleances-frontend:$MC_TAG
EOF
mc() {
  MULTICORPUS_CONFIG_HOST_FILE=/srv/cahier-search/private/multicorpus.json \
  docker compose --project-name cahier-de-doleances-app --project-directory "$MC_ROOT" \
    --env-file "$MC_ROOT/.env.deploy" \
    -f "$MC_ROOT/compose.deploy.yml" -f "$MC_ROOT/compose.search.yml" \
    -f "$MC_ROOT/compose.multicorpus.yml" \
    -f /srv/cahier-search/private/multicorpus-images.yml "$@"
}
mc config --quiet
mc run --rm --no-deps app python -m app.deployment_check
mc up -d --no-deps --no-build --pull never app frontend
```

Conserver `HYBRID_SEARCH_ENABLED=true` et toutes les valeurs H1 existantes. Ne définir **aucun** `DOCUMENTARY_LOCAL_PREVIEW`/`DOCUMENTARY_PREVIEW_TOKEN`. L'image et l'overlay savent fonctionner avec `enabled=false` : H1 sert la recherche, la recherche par question reste lexicale, les cahiers restent en 404 et le filtre 1789 indisponible. Ne pas tester en activant des permissions documentaires pour contourner cela.

**Point d'arrêt technique :** release `verified`, flags représentations/statistiques vrais, `publication_authorized=false`, `active_release_id=NULL`, zéro document lisible/catalogué/recherchable publiquement, deux unités Artois exclues, 43 non candidats hors publication. Valider H1 et l'application avant de demander l'autorisation B.

## 6. Publication ultérieure — autorisation distincte obligatoire

Cette étape n'est **pas autorisée** par la mission. Préparer une autorisation versionnée à partir de `publication-authorization.example.json`, sans modifier le fichier de décisions de contenu d'origine ni la collection. La faire approuver explicitement avec date, décideur, périmètre, manifeste/release et exclusion des 43 autres documents. `approved=false` reste la valeur livrée.

Conserver la décision approuvée dans un nouveau fichier `deploy/documentary/publication-authorization-<ID>.json` du checkout de préparation et la versionner explicitement (`git add -f` sur **ce fichier seul**, après revue ; les JSON sont ignorés globalement). Après accord, copier ce fichier vers `/srv/cahier-search/private/publication-authorization.json`, en refusant de remplacer une autorisation déjà conservée. Son SHA256 exact sera enregistré dans les 1 224 événements ; ni ce fichier ni son approbation ne sont créés par cette mission.

Le script `activate-1789.sql` :

1. Vérifie la cible physique, la release vérifiée, les empreintes, les représentations et N=10 748.
2. Vérifie les deux identifiants Artois exclus, les 1 224 candidats, l'absence de publication antérieure et les documents toujours privés.
3. Enregistre **1 224 décisions de publication dérivées de l'autorisation versionnée**, liées aux IDs/empreintes/étendues, sans prétendre certifier historiquement les cahiers.
4. Rend uniquement les candidats lisibles/catalogués/recherchables ; passe la release à ready/autorisation vraie puis active son pointeur dans la même transaction. Il ne change pas les unités exclues, avertissements, titres, vecteurs ou DF.

Une seconde exécution n'ignore pas silencieusement un journal existant : elle refuse la promotion déjà enregistrée. Vérifier l'état avant toute relance. Les permissions d'origine et le fichier d'autorisation permettent une décision ultérieure de retrait ; aucun outil d'import technique n'accorde ou n'annule implicitement cette autorisation.

Commande de publication **future**, sur Gavroche root, à partir d'un fichier d'autorisation réellement approuvé et conservé dans le déploiement :

```python
import hashlib, json, subprocess
from pathlib import Path

approval = Path('/srv/cahier-search/private/publication-authorization.json')
raw = approval.read_bytes()
a = json.loads(raw)
assert a['format'] == 'cahier-publication-authorization-v1'
assert a['approved'] is True and a['candidate_documents'] == 1224
assert a['other_documents_authorized'] is False
assert a['corpus_id'] == 'cahiers-1789-ap-stanford'
assert a['release_id'] == 'reference-documents-2-7cbcaea79991'
assert a['source_manifest_hash'] == 'eb9f4533e95df62a8964fbd6a71d56c0446b7769f6fa9d80fcdd8c0111e08ff2'
assert a['editorial_hash'] == '2b2b4c14e33ed5b7908a7e0304a980143c803c088af5dd8234690a81a8314cba'
args = ['docker','exec','-i','cahier-postgres','psql','-X','-v','ON_ERROR_STOP=1',
        '-U','cahier','-d','cahier_search','-v','authorize_publication=true']
for k, value in dict(approval_id=a['approval_id'],
                    approval_sha256=hashlib.sha256(raw).hexdigest(),
                    decided_by=a['decided_by'], approved_at=a['approved_at']).items():
    args += ['-v', f'{k}={value}']
with open('/srv/cahier-de-doleances-app/deploy/documentary/activate-1789.sql') as script:
    subprocess.run(args, stdin=script, check=True)
```

Après contrôles SQL, modifier **seulement** `enabled` à true dans `/srv/cahier-search/private/multicorpus.json`. Garder `local_preview=false`, identité et hashes corrects. Recréer explicitement le backend :

```bash
mc up -d --no-deps --no-build --pull never --force-recreate app
```

Une modification du contenu d'un bind mount fichier ne garantit pas sa prise en compte après remplacement atomique : la recréation explicite recharge bien la configuration. Le frontend SSR n'a pas besoin d'un nouveau build pour découvrir les corpus publiés. Attendre le chargement du modèle et les sondes de recherche, pas seulement `/healthz`.

## 7. Protocole de réception court

Après **installation technique** :

- Conteneurs sains, accueil et `/healthz` en 200 ; vérifier les IDs d'images et les logs sans copier d'URL/secret.
- H1 `/api/v1/search?q=...`, formulaire, question, contribution et ancre, recherche par question, première/page suivante et rechargement. Les instantanés du processus précédent peuvent expirer normalement.
- `/api/v1/corpora` : 2019 disponible, 1789 non publié ; catalogue et lecteur historiques publics en **404**, y compris avec un faux en-tête de preview et un curseur d'aperçu local. Le filtre 1789 ne doit pas révéler de document.
- Contrôle SQL : 1 267/11 391/10 748, deux exclusions, Aunay et avertissements, aucun flag public, révisions doc_0001/rag_0007 intactes. Compte lecteur sans accès au journal éditorial ni écriture.

Après **publication et activation autorisées** :

- 2019 seul, 1789 seul et tous ; filtre conservé dans URL/rechargement/historique ; pagination sans doublon, une seule RRF, aucun quota.
- Catalogue indépendant, Agen en lecture, précédent/suivant, lien depuis extrait vers passage versionné et surlignage Unicode ; présentation mobile et polices.
- Artois : texte intégral et avertissement, unités 3/4 absentes des candidats/extraits. Aunay : titre de présentation validé, titre source et avertissement de lacune. Aucune mention « Aperçu local » en public.
- Exactement 1 224 documents publiés et 1 224 événements, 43 non candidats privés ; 10 748 unités admissibles ; aucun journal privé sérialisé. Comparer état/statistiques/index GDN avant/après.

Observations H1 actuelles : `/healthz` 200 ; première sonde de recherche en erreur HTTP non détaillée après 10,16 s, puis `transports publics` **200 en 4,24 s** et `vélomobile` **200 en 1,65 s**, recette attendue. Ce ne sont pas des percentiles ni une validation de charge. Les contrôles à froid, la mémoire en pic, quelques requêtes concurrentes et le comportement après redémarrage applicatif restent à mesurer lors de la réception autorisée. Aucune optimisation ni augmentation de budget n'est proposée.

Surveiller `docker stats --no-stream`, `df`, connexions PostgreSQL, erreurs 503/504, temps d'encodage/SQL/hydratation et OOM. Un redémarrage serveur complet ne se fait pas pour ce déploiement : si une répétition de boot est souhaitée, prévoir une fenêtre séparée, avec sauvegardes, console de secours et contrôle des montages avant le démarrage Docker. Il n'a pas été testé ici.

## 8. Retour arrière

### Niveau 1 : H1 dans la nouvelle image

Dans la fonction `mc` définie plus haut, ajouter un override privé :

```bash
cat > /srv/cahier-search/private/h1-only.yml <<'EOF'
services:
  app:
    environment:
      MULTICORPUS_CONFIG_FILE: ""
EOF
mc -f /srv/cahier-search/private/h1-only.yml up -d --no-deps --no-build --pull never --force-recreate app
```

H1 reste activé. Les routes historiques deviennent indisponibles sans intégration documentaire. Aucun DROP ni restauration ; garder les tables et décisions. Une autorisation éditoriale déjà accordée n'est pas effacée silencieusement par ce retour technique.

### Niveau 2 : images et configuration précédentes

Reprendre le répertoire `MC_BACKUP` exact de cette opération, pas un répertoire « latest ». Dans le shell root :

```bash
mkdir -m 700 "$MC_BACKUP/rollback-files"
tar -xf "$MC_BACKUP/configuration.tar" -C "$MC_BACKUP/rollback-files"
MC_OLD_ROOT="$MC_BACKUP/rollback-files/srv/cahier-de-doleances-app"
cat > "$MC_BACKUP/rollback-images.yml" <<EOF
services:
  app:
    image: cahier-de-doleances-app:before-mc-$MC_STAMP
  frontend:
    image: cahier-de-doleances-frontend:before-mc-$MC_STAMP
EOF
docker compose --project-name cahier-de-doleances-app --project-directory "$MC_ROOT" \
  --env-file "$MC_OLD_ROOT/.env.deploy" \
  -f "$MC_OLD_ROOT/compose.deploy.yml" -f "$MC_OLD_ROOT/compose.search.yml" \
  -f "$MC_BACKUP/rollback-images.yml" up -d --no-deps --no-build --pull never app frontend
```

Les poids, fichiers lecteur/publication GDN, réseau et Caddy restent aux mêmes chemins. Si les images ont disparu, vérifier les checksums puis `docker image load -i "$MC_BACKUP/images.tar"`. Ne pas relancer le projet PostgreSQL, toucher les données ni retirer le schéma documentaire pour revenir à H1.

Une restauration PostgreSQL n'est nécessaire qu'en cas de corruption réelle, perte de stockage ou modification indue des données, pas pour une régression frontend/moteur. Restaurer d'abord la sauvegarde dans une copie isolée et établir le périmètre de reprise : une restauration du cluster complet ferait perdre les écritures applicatives postérieures au point de sauvegarde. Cette bascule de données exige une décision d'incident séparée ; aucun remplacement automatique de PGDATA n'est préparé.

## 9. Validations de préparation et décisions restantes

- **685 tests backend réussis**, six tests d'intégration ignorés faute d'opt-in dédié, trois avertissements existants ; sept sous-tests réussis. Les tests documentaires utilisent uniquement de nouveaux clusters privés.
- **23 tests de garde/procédure** inclus : refus de mauvaises cibles et preuves, séparation des privilèges, migration sous propriétaire sans CREATE sur la base, transfert/réimport et reconstruction lexicale, promotion avec autorisation refusée/acceptée sur copie, protection des 43 autres documents et des exclusions. Vecteurs synthétiques dans ces tests, aucun calcul BGE.
- Archive réelle restaurée/vérifiée localement avec ses **10 748 vecteurs réels** ; callback de source vérifiée essayé sans écriture cible. Paquet et manifestes contrôlés.
- Garde Gavroche essayée réellement **en lecture seule** ; aucune commande `import`, `provision` ou `activate` de production exécutée. Ruff/format et contrôles de diff réussis.
- Contrôle final de production : schéma `documentary` et rôle `cahier_documentary_owner` toujours absents ; état GDN, statistiques lexicales et définitions/identités physiques des index identiques au relevé initial. Ce contrôle de métadonnées n'est pas un nouveau hachage des millions d'embeddings : aucune écriture sur eux n'a été effectuée.
- Builds Docker, sauvegarde physique de Gavroche, authentification de réplication, restauration du cluster de production, nouvelle image en réseau réel et test de boot **non exécutés** : prérequis d'exploitation à réaliser après accord.

Les relevés nettoyés et preuves locales sont dans `private/search/production-preparation/`, ignoré par Git. Aucun fichier contenant un mot de passe, journal historique privé ou dump n'est ajouté au dépôt.

Décisions humaines : commit/images à déployer, fenêtre/charge de sauvegarde, opérateur et rétention/copie hors serveur ; confirmation des intégrations externes sur main ; acceptation de la réception technique ; puis **autorisation explicite des 1 224 candidats et activation du multicorpus**, séparément. Les 43 autres documents nécessiteront une qualification distincte. Rien dans cette préparation ne les certifie ni ne les publie.
