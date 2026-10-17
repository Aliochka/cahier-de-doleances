# Migrer PostgreSQL local de 14 vers 17 (Ubuntu 22.04)

État constaté avant migration : cluster `14/main`, port 5432, bases
`cahier_doleances_local` (~14 Go), `cahier_doleances_test` et `postgres`.
Extensions applicatives : `unaccent`, `pg_trgm`. Cette procédure migre tout le
cluster, rôles et bases compris. Elle nécessite un terminal avec accès sudo.

Arrêter les serveurs applicatifs locaux, les imports et les tests pendant la
migration. Garder ces processus arrêtés jusqu'à la fin des vérifications.

## 1. Installer les binaires 17

Ajouter le dépôt officiel PostgreSQL, puis installer explicitement la version 17 :

```bash
sudo apt-get update
sudo apt-get install -y postgresql-common curl ca-certificates
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
sudo apt-get update
sudo apt-get install -y postgresql-17 postgresql-client-17
pg_lsclusters
```

Le paquet 17 fournit les modules `unaccent` et `pg_trgm`. Le cluster 14 doit
rester présent. L'installation peut créer un cluster `17/main` vide sur un autre
port : ne pas le confondre avec les données existantes.

## 2. Sauvegarder

Dans le même terminal, créer une sauvegarde privée hors du dépôt :

```bash
backup_dir="$HOME/postgres-backups/avant-pg17-$(date +%Y%m%d-%H%M%S)"
install -d -m 700 "$backup_dir"
(umask 077; sudo -u postgres /usr/lib/postgresql/17/bin/pg_dumpall -p 5432 > "$backup_dir/cluster-14.sql")
```

Vérifier que la commande s'est terminée sans erreur avant de poursuivre.
Le fichier contient les données et les informations des rôles : le garder privé.

```bash
test -s "$backup_dir/cluster-14.sql"
tail -5 "$backup_dir/cluster-14.sql"
sudo tar -czf "$backup_dir/config-14.tar.gz" /etc/postgresql/14/main
sudo chmod 600 "$backup_dir/config-14.tar.gz"
```

La fin du dump doit indiquer `PostgreSQL database cluster dump complete`.

## 3. Migrer en gardant les fichiers 14 indépendants

Le nouveau cluster est nommé `cahierlocal17`, pour éviter toute collision avec
le `17/main` éventuellement créé par l'installation. Vérifier avec
`pg_lsclusters` que `17/cahierlocal17` n'existe pas déjà ; sinon, s'arrêter et
examiner ce cluster avant de relancer quoi que ce soit.

```bash
sudo pg_upgradecluster -v 17 --method=upgrade --rename=cahierlocal17 14 main
pg_lsclusters
```

Cette commande utilise `pg_upgrade` en mode copie, sans `--link`. Elle conserve
le cluster 14, arrêté et déplacé vers un autre port, et place PostgreSQL 17 sur
le port 5432. Ne supprimer aucun cluster pendant la validation. En cas d'échec,
consulter le message et `pg_lsclusters` avant de tenter un redémarrage.

Si une tentative précédente a créé `17/cahier-local17` mais échoué au démarrage
avec `AssertPathExists=/etc/postgresql/17/cahier/local17/postgresql.conf`,
le tiret du nom est interprété par systemd comme un séparateur de chemin.
Corriger le nom du cluster existant, sans relancer la migration :

```bash
sudo pg_renamecluster 17 cahier-local17 cahierlocal17
sudo systemctl daemon-reload
sudo pg_ctlcluster 17 cahierlocal17 start
```

## 4. Vérifier

```bash
psql -X -p 5432 -d cahier_doleances_local -c 'SHOW server_version;'
psql -X -p 5432 -d cahier_doleances_local -c 'SELECT extname, extversion FROM pg_extension;'
psql -X -p 5432 -d cahier_doleances_local -c 'SELECT version_num FROM alembic_version;'
psql -X -p 5432 -d postgres -c '\l'
sudo -u postgres /usr/lib/postgresql/17/bin/vacuumdb -p 5432 --all --analyze-in-stages
```

Depuis la racine du projet, lancer les tests avec la base dédiée :

```bash
TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
GDN_IMPORT_TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
venv/bin/python -m pytest -q
```

L'URL `postgresql:///cahier_doleances_local` reste identique. Relancer ensuite
l'application et contrôler la consultation et la recherche.

## Retour arrière avant reprise des écritures

Le cluster 14 conserve son état au moment de la migration. Pour revenir dessus,
arrêter les applications puis utiliser le port affiché pour `14/main` dans
`pg_lsclusters` pour arrêter le nouveau cluster et réattribuer le port 5432 :

```bash
sudo pg_ctlcluster 17 cahierlocal17 stop
sudo pg_conftool 14 main set port 5432
sudo pg_ctlcluster 14 main start
pg_lsclusters
```

Ce retour ne reprend pas les écritures qui auraient été faites dans PostgreSQL
17. Pour rendre le retour persistant après redémarrage, remettre également
`/etc/postgresql/14/main/start.conf` à `auto` et le fichier correspondant du
cluster `17/cahierlocal17` à `manual`, puis `sudo systemctl daemon-reload`.
Conserver les anciennes données et la sauvegarde jusqu'à validation complète.

Sources : [installation Ubuntu officielle](https://www.postgresql.org/download/linux/ubuntu/),
[pg_upgrade PostgreSQL 17](https://www.postgresql.org/docs/17/pgupgrade.html),
[pg_upgradecluster](https://manpages.debian.org/bookworm/postgresql-common/pg_upgradecluster.1.en.html).
