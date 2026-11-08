# Sauvegardes avant multicorpus — Gavroche

Préparé le 8 novembre 2026. **À la rédaction initiale, aucune commande de sauvegarde, de création de conteneur ou de restauration ci-dessous n'avait été exécutée sur Gavroche.** Ces opérations nécessitent l'autorisation de maintenance. Le [plan principal](deploiement-multicorpus-gavroche.md) décrit les prérequis et la bascule.

**Complément du 8 novembre :** la copie froide existante du 2 novembre a depuis été testée, sur une copie indépendante et après autorisation distincte. Le [rapport de vérification](verification-sauvegarde-20261102-gavroche.md) recommande sa réutilisation sur le périmètre contrôlé et propose une exception ciblée au protocole, **sans l'implémenter**. Aucune nouvelle sauvegarde de production n'a été créée. Ne pas lancer automatiquement la procédure ci-dessous : la décision sur l'exception, les configurations hors PGDATA et l'autorisation de déploiement restent distinctes.

## Périmètre et espace

**Décision ultérieure :** la réutilisation de la copie froide du 2 novembre est désormais autorisée. Voir les [prérequis finalisés](prerequis-deploiement-multicorpus-gavroche.md), l'exception ciblée et la nouvelle procédure de conservation des actifs. Les étapes de création d'une nouvelle sauvegarde physique ci-dessous restent une solution de secours, pas une étape à lancer pour ce déploiement. L'attestation préparée reste volontairement incomplète jusqu'à la conservation effective des configurations/images/modèle, non autorisée pendant la mission de préparation.

La sauvegarde physique complète couvre **les deux bases**, leurs données, index HNSW, statistiques, rôles et WAL nécessaires à la récupération. Elle évite une reconstruction des index à la restauration. Elle ne remplace pas la sauvegarde des configurations Docker/Caddy et du modèle situé hors de PGDATA. Une sauvegarde de schéma ou un catalogue `pg_restore --list` ne prouve pas la sauvegarde/restauration des données.

| Élément | Sauvegarde nécessaire |
|---|---|
| Application `cahier_doleances` (~13,72 Gio) | Incluse dans la sauvegarde physique ; export logique complet optionnel pour une restauration sélective |
| Recherche `cahier_search` (~76,83 Gio) | Incluse intégralement dans la même sauvegarde physique, avec les pages HNSW |
| Rôles | Inclus physiquement ; export `pg_dumpall --globals-only` privé supplémentaire |
| Déploiement | Images exactes, Compose, Caddyfile, `.env`, fichiers lecteur/publication/clefs, fstab et dépendance systemd |
| 1789 | Paquet local de 101 560 320 octets, archive documentaire complète de 76 500 332 octets, sources immuables et décisions ; à conserver sur Gavroche et hors du serveur |

Le disque `/backups/postgresql` est distinct du SSD des données : UUID `52ba8e78-4375-4286-8c75-5cfef6609c8a`, environ **1,60 Tio libres** au relevé. Réserver au minimum **300 Gio libres** pour une sauvegarde physique complète, sa copie de restauration, les images et une marge. Avec des exports logiques supplémentaires, augmenter cette réserve selon leur taille réelle. Le SSD de données dispose d'environ 311 Gio libres. Les tailles sont des observations, à recontrôler avant exécution.

Les répertoires `wallace-original-20261102` existent déjà. **Ne pas les réutiliser, les nettoyer ou les écraser.** Leur présence n'atteste pas une restauration récente. Aucun cron de sauvegarde ni timer de sauvegarde applicative n'a été identifié ; `archive_mode=off` exclut une promesse de PITR continu après la fin de cette nouvelle sauvegarde.

## 1. Vérifier les montages et créer une destination neuve

Sur Gavroche, après autorisation, dans un shell root dédié (`sudo -i`) :

```bash
set -euo pipefail
umask 077
export MC_ROOT=/srv/cahier-de-doleances-app
export MC_STAMP=$(date -u +%Y%m%dT%H%M%SZ)
export MC_BACKUP="/backups/postgresql/multicorpus-$MC_STAMP"
export MC_PG_IMAGE=sha256:30ee450c42fda0596abaf71066c1612c79a0aaa791e655e5e00ce2c1e33ab6cc
test "$(findmnt -rn -M /data/postgresql -o UUID)" = 624405d4-3422-4b7d-8ca3-8579d8b513bb
test "$(findmnt -rn -M /backups/postgresql -o UUID)" = 52ba8e78-4375-4286-8c75-5cfef6609c8a
test "$(docker inspect cahier-postgres --format '{{.Image}}')" = "$MC_PG_IMAGE"
test -f /data/postgresql/.ssd-mounted
test -f /data/postgresql/pg17/data/PG_VERSION
test "$(cat /data/postgresql/pg17/data/PG_VERSION)" = 17
df -h /data/postgresql /backups/postgresql /var/lib/docker
mkdir -m 700 "$MC_BACKUP"
mkdir -m 700 "$MC_BACKUP/physical"
MC_PG_UID=$(docker exec cahier-postgres id -u postgres)
MC_PG_GID=$(docker exec cahier-postgres id -g postgres)
chown "$MC_PG_UID:$MC_PG_GID" "$MC_BACKUP/physical"
```

L'unique `chown` vise le **nouveau répertoire vide de sauvegarde**, jamais PGDATA. Vérifier aussi les montages effectifs du conteneur avec `docker inspect --format '{{json .Mounts}}' cahier-postgres`. Ils doivent correspondre au plan principal. Ne pas continuer si le stockage, l'image ou l'identité SQL a changé.

## 2. Conserver le déploiement et les rôles

Toujours dans ce shell root, sans afficher les fichiers privés :

```bash
docker inspect --format '{{.Image}}' cahier-de-doleances-app-app-1 > "$MC_BACKUP/old-app-id"
docker inspect --format '{{.Image}}' cahier-de-doleances-app-frontend-1 > "$MC_BACKUP/old-frontend-id"
docker image tag "$(cat "$MC_BACKUP/old-app-id")" "cahier-de-doleances-app:before-mc-$MC_STAMP"
docker image tag "$(cat "$MC_BACKUP/old-frontend-id")" "cahier-de-doleances-frontend:before-mc-$MC_STAMP"
docker image save "cahier-de-doleances-app:before-mc-$MC_STAMP" \
  "cahier-de-doleances-frontend:before-mc-$MC_STAMP" \
  cahier-postgres-pgvector:17.11-0.8.7 caddy:2.11.2-alpine > "$MC_BACKUP/images.tar"
docker compose --project-name cahier-de-doleances-app \
  --project-directory "$MC_ROOT" --env-file "$MC_ROOT/.env.deploy" \
  -f "$MC_ROOT/compose.deploy.yml" -f "$MC_ROOT/compose.search.yml" \
  config --format json > "$MC_BACKUP/compose-effective.private.json"
tar -cpf "$MC_BACKUP/configuration.tar" -C / \
  etc/fstab etc/systemd/system/docker.service.d \
  srv/cahier-de-doleances/compose.yaml srv/cahier-de-doleances/.env \
  srv/cahier-de-doleances-app/.env.deploy \
  srv/cahier-de-doleances-app/compose.deploy.yml \
  srv/cahier-de-doleances-app/compose.search.yml \
  srv/cahier-de-doleances-app/Caddyfile \
  srv/cahier-de-doleances-app/deploy/postgres/compose.pgvector.override.yml \
  srv/cahier-de-doleances-app/rag/search-reader.env srv/cahier-search/private
docker exec cahier-postgres pg_dumpall -U cahier --globals-only > "$MC_BACKUP/globals.sql"
sha256sum "$MC_BACKUP/images.tar" "$MC_BACKUP/configuration.tar" "$MC_BACKUP/globals.sql" \
  "$MC_BACKUP/compose-effective.private.json" > "$MC_BACKUP/files.sha256"
```

`configuration.tar`, le JSON Compose et `globals.sql` sont **privés** : ils peuvent contenir secrets et empreintes de mots de passe. Conserver également le SHA du checkout approuvé et une copie du modèle BGE-M3 ou un dispositif de récupération du snapshot exact. Ne pas envoyer ces fichiers dans Git ni dans les logs CI.

## 3. Sauvegarde physique complète sans arrêt du serveur PostgreSQL

Il n'y a que les tablespaces `pg_default` et `pg_global` au relevé. Si de nouveaux tablespaces apparaissent, arrêter cette procédure et préparer leurs mappings explicitement. `wal_level=replica`, `full_page_writes=on`, dix WAL senders et dix slots sont disponibles ; aucune réplication active n'a été observée.

Le client suivant utilise l'image PostgreSQL déjà présente, le namespace réseau du conteneur existant et une connexion de réplication à `127.0.0.1`. Il ne démarre pas de serveur et ne monte pas PGDATA. Le mot de passe reste en mémoire et dans l'environnement du client temporaire, jamais dans ses arguments ni sa sortie. L'authentification de réplication doit encore être exercée : si pg_hba refuse, **arrêter**, sans modifier implicitement pg_hba ou les paramètres PostgreSQL.

```bash
python3 - <<'PY'
import json, os, subprocess
env = dict(x.split('=', 1) for x in json.loads(subprocess.check_output(
    ['docker','inspect','--format','{{json .Config.Env}}','cahier-postgres'], text=True)))
assert env['POSTGRES_USER'] == 'cahier'
client_env = dict(os.environ, PGPASSWORD=env['POSTGRES_PASSWORD'])
subprocess.run([
    'docker','run','--rm','--pull=never','--read-only','--tmpfs','/tmp',
    '--network','container:cahier-postgres','--user','postgres','--cpus=2',
    '--env','PGPASSWORD','--entrypoint','pg_basebackup',
    '--mount',f"type=bind,src={os.environ['MC_BACKUP']}/physical,dst=/backup",
    os.environ['MC_PG_IMAGE'],'-h','127.0.0.1','-U','cahier','-D','/backup',
    '--format=plain','--wal-method=stream','--checkpoint=spread',
    '--manifest-checksums=SHA256','--max-rate=64M','--label=before-multicorpus',
], env=client_env, check=True)
PY
date -u +%FT%TZ > "$MC_BACKUP/backup-completed-at"
docker run --rm --pull=never --network none --read-only --user postgres \
  --entrypoint pg_verifybackup \
  --mount "type=bind,src=$MC_BACKUP/physical,dst=/backup,readonly" \
  "$MC_PG_IMAGE" --exit-on-error /backup
```

Ce sont des sauvegardes physiques **complètes**, pas incrémentales. Le streaming conserve les WAL de la sauvegarde ; il ne met pas en place d'archivage permanent. Contrôler la charge disque, l'espace et les erreurs pendant cette opération. À 64 Mio/s, prévoir plusieurs dizaines de minutes pour ~100 Gio, plus le checkpoint et les vérifications. Aucun temps réel de sauvegarde n'a été mesuré ici. Références : [pg_basebackup 17](https://www.postgresql.org/docs/17/app-pgbasebackup.html), [pg_verifybackup 17](https://www.postgresql.org/docs/17/app-pgverifybackup.html).

Si des exports indépendants sont requis, commandes optionnelles après accord sur leur coût :

```bash
docker exec cahier-postgres pg_dump -U cahier -d cahier_doleances -Fc -Z 1 > "$MC_BACKUP/application.dump"
docker exec cahier-postgres pg_dump -U cahier -d cahier_search -Fc -Z 1 > "$MC_BACKUP/search.dump"
```

Ces dumps sont complets mais leur restauration logique reconstruira les index **dans la cible de restauration**. Ne pas substituer ces exports à la sauvegarde physique sans tester leur restauration. Le plan principal ne requiert aucune reconstruction HNSW de production.

## 4. Tester réellement la restauration dans une copie indépendante

Ne pas démarrer la sauvegarde elle-même et ne pas utiliser de copie par liens physiques (`cp -al`). Le nouveau conteneur n'a aucun réseau ni port publié et ne monte aucun chemin de données de production.

```bash
export MC_RESTORE="cahier-pg-restore-$MC_STAMP"
test ! -e "$MC_BACKUP/restore-data"
cp -a "$MC_BACKUP/physical" "$MC_BACKUP/restore-data"
docker run -d --pull=never --name "$MC_RESTORE" --network none \
  --user postgres --read-only --tmpfs /tmp --memory 2g --cpus 2 \
  --mount "type=bind,src=$MC_BACKUP/restore-data,dst=/var/lib/postgresql/data" \
  --entrypoint postgres "$MC_PG_IMAGE" -D /var/lib/postgresql/data \
  -c listen_addresses='' -c unix_socket_directories=/tmp
for mc_try in $(seq 1 60); do
  if docker exec "$MC_RESTORE" pg_isready -h /tmp -U cahier -d cahier_doleances; then break; fi
  sleep 1
done
docker exec "$MC_RESTORE" pg_isready -h /tmp -U cahier -d cahier_doleances
docker inspect "$MC_RESTORE" --format '{{json .Mounts}} {{json .NetworkSettings.Networks}}'
docker exec "$MC_RESTORE" psql -XAt -v ON_ERROR_STOP=1 -h /tmp -U cahier -d cahier_doleances \
  -c 'SELECT version_num FROM public.alembic_version'
docker exec "$MC_RESTORE" psql -XAt -v ON_ERROR_STOP=1 -h /tmp -U cahier -d cahier_search \
  -c "SELECT version_num FROM public.rag_alembic_version; SELECT extversion FROM pg_extension WHERE extname='vector'; SELECT documents,segments,verified,vectors_complete FROM rag_full.spaces WHERE space_id='full'; SELECT bool_and(i.indisvalid) FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('rag_full','rag_tuning');"
```

Exiger `forms_statistics_v1`, `rag_0007`, `0.8.7`, `5172356|5187190|t|t` et des index valides. Vérifier également le cluster `7695026423032606758`, les OID 16384/634726 et quelques données applicatives dans cette copie. Ces comptes de `spaces` sont des compteurs de manifeste, pas un nouveau scan des cinq millions d'unités. La vérification des fichiers complète ce contrôle ; [pg_verifybackup ne remplace pas un essai de restauration](https://www.postgresql.org/docs/17/app-pgverifybackup.html).

Une fois l'essai documenté :

```bash
docker stop "$MC_RESTORE"
docker rm "$MC_RESTORE"
```

Conserver la sauvegarde originale et la copie de validation jusqu'à la fin de la fenêtre de retour arrière. Aucun `rm -rf` de données n'est proposé ici.

## 5. Attestation permettant l'import

Copier [backup-proof.example.json](../deploy/documentary/backup-proof.example.json) vers un **nouveau fichier privé local** et renseigner les faits réellement vérifiés : opérateur, fin de sauvegarde, fin de restauration, révisions, chemins, octets et empreintes. Pour une sauvegarde physique, `sha256` désigne l'empreinte du fichier `physical/backup_manifest` vérifié par `pg_verifybackup` ; `bytes` désigne la taille de l'arborescence physique. Les entrées `application` et `search` peuvent désigner cette même sauvegarde qui couvre les deux bases.

Calculs côté Gavroche :

```bash
sha256sum "$MC_BACKUP/physical/backup_manifest" "$MC_BACKUP/globals.sql" "$MC_BACKUP/configuration.tar"
du -sb "$MC_BACKUP/physical"
stat -c '%s %n' "$MC_BACKUP/globals.sql" "$MC_BACKUP/configuration.tar"
date -u +%FT%TZ
```

Ne passer `restore_verified` à `true` qu'après tous les contrôles réussis. La sauvegarde et son contrôle doivent dater de moins de 24 heures pour l'import. Le fichier est une **attestation opérateur**, pas une preuve automatiquement produite par le client : la garde ne peut pas relire les fichiers distants protégés ni garantir la sincérité d'une attestation modifiée à la main. Les zéros, sauvegardes de schéma, dates absentes et cible incorrecte sont refusés.

Prévoir enfin une copie protégée hors de Gavroche : le second disque est distinct du SSD, mais reste dans le même serveur. La destination hors serveur et la rétention nécessitent encore une décision d'exploitation.
