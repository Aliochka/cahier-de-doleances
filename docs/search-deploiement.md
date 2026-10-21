# SEARCH-DEPLOY-002 — Installer H1 CPU sur Wallace

Cette procédure est préparée, **non exécutée sur Wallace**. Toute commande de
déploiement ci-dessous attend une validation humaine. La recherche publique reste
désactivée (`HYBRID_SEARCH_ENABLED=false`). Lire d’abord
[l’audit SEARCH-DEPLOY-001](audit-search-deploy-001.md).

## Architecture et invariants

- Une instance PostgreSQL **17.11**, deux bases : `cahier_doleances` inchangée et
  `cahier_search` restaurée intégralement depuis `cahier_rag`.
- pgvector **0.8.7**, schéma spécialisé `rag_0007`, UTF8, `fr_FR.UTF-8`.
- Un worker Gunicorn, un BGE-M3 CPU/float32, un cache de curseurs en mémoire.
- Recette `h1-public-v1` inchangée : lexical RAG-027 exact sans préfiltrage,
  BGE-M3 1024/cosinus, profondeur 50, ef1000/400 candidats initiaux,
  `strict_order`, 20 000 tuples, multiplicateur mémoire 1, RRF non pondérée k60.
- Aucun BM25, reranker, LLM, GPU, changement d’algorithme ou nouveau filtre.
- Aucun modèle dans l’image ; seul le snapshot existant est monté en lecture seule.
- Les index sont reconstruits par la restauration logique, les embeddings sont
  transférés. Ne pas lancer les migrations expérimentales ni recalculer de vecteurs.
- Les gardes d’écriture RAG restent stricts. L’association portable est extérieure
  au manifeste original et ne donne aucun droit SQL supplémentaire au runtime.

## Images et provenance

### PostgreSQL

Le 21 octobre 2026, l’API anonyme du registre Docker a été interrogée pour
`pgvector/pgvector:0.8.7-pg17-trixie` :

| Métadonnée | Valeur relevée |
|---|---|
| Digest de l’index multiarchitecture | `sha256:7a7e9f22015b67edb4bef5c59daeebcd7e74bfa570df6ce60ae01237c8648a84` |
| Digest du manifeste linux/amd64 | `sha256:c9f9997c9a711499b212133bc33ea05055d11dfb1e2ce243b516b1f55f0e5eb4` |
| PostgreSQL déclaré | `17.11-1.pgdg13+2` |
| `PGDATA` | `/var/lib/postgresql/data` |
| Entrypoint amont | `docker-entrypoint.sh` |
| Volume déclaré | `/var/lib/postgresql/data` |
| Taille compressée des couches amd64 | 166 348 075 octets |

Le [Dockerfile amont v0.8.7](https://github.com/pgvector/pgvector/blob/v0.8.7/Dockerfile)
utilise l’image officielle PostgreSQL, un codename Debian paramétrable et compile
pgvector avec `OPTFLAGS=""`. Le namespace amont est `pgvector/pgvector` ; le digest
fige les octets, mais cette inspection n’est pas une vérification de signature ni
une preuve de reproductibilité de la construction amont.

[Le Dockerfile préparé](../deploy/postgres/Dockerfile) utilise ce digest et impose
les versions, les chemins `vector.control`/`vector.so` et la locale française à la
construction. Son entrypoint refuse un répertoire vide, un `PG_VERSION` différent
de 17, un propriétaire différent du compte `postgres` de l’image, ou l’absence du
marqueur SSD. Il lance directement PostgreSQL via `gosu`, **sans initdb, chown,
scripts d’initialisation ou réinitialisation de mot de passe**.

Le rôle SQL existant est `cahier` (`POSTGRES_USER=cahier`), tandis que le compte
système de l’image est `postgres`, UID/GID **999:999** sur l’installation vérifiée
par l’opérateur. Le garde ne dépend pas de `POSTGRES_USER` et accepte son absence :
il ne crée ni ne modifie aucun rôle SQL. Il compare les UID/GID du répertoire,
de `PG_VERSION` et de `global/pg_control` à ceux du compte système de l’image,
et vérifie PostgreSQL 17.11 dans l’environnement et le binaire.

**Correctif SEARCH-DEPLOY-003 :** l’override fournit explicitement
`command: [postgres]`. Lorsque Compose redéfinit `entrypoint`, il ignore le `CMD`
par défaut de l’image ([documentation Docker](https://docs.docker.com/reference/compose-file/services/#entrypoint)).
Le garde choisit aussi `postgres` si aucun argument n’est fourni ; toute autre
commande explicite est refusée. Lors de la fusion, reporter les éventuelles
options PostgreSQL existantes après `postgres` dans `command` : ne pas les perdre.
La répétition doit utiliser le **même Compose fusionné** que la production,
avec seulement les montages remplacés par ceux d’une copie isolée et un réseau
isolé. Un essai via `docker run IMAGE` conserve normalement le `CMD` de l’image
et ne reproduit donc pas le défaut d’arguments de l’ancien override.

**Docker n’étant pas disponible pendant la préparation, ni la construction ni la
réutilisation d’un cluster dans cette image n’ont été testées.** Une répétition sur
une sauvegarde isolée est obligatoire avant remplacement. Un écart d’UID ne doit
pas être corrigé par un `chown -R` improvisé : conserver l’image existante et revoir
la préparation.

Cette limite concerne les validations locales de SEARCH-DEPLOY-002/003.
L’opérateur a depuis confirmé la construction de l’image et le fonctionnement
de pgvector 0.8.7 sur une copie physique ; cela ne valide pas à lui seul la
commande effective du Compose de production. Voir le
[rapport du correctif du garde](rapport-search-deploy-003.md).

### Backend CPU

Le build normal du [Dockerfile](../Dockerfile) conserve le runtime léger. Le build
`--build-arg SEARCH_RUNTIME=cpu` utilise le verrou autonome
[`deploy/search-cpu/uv.lock`](../deploy/search-cpu/uv.lock).

Les versions directes sont alignées sur le backend et `cahier-rag[embeddings]`.
Les versions transitives communes ont été conservées ; les tests en vérifient
l’alignement. Les verrous racine et RAG restent inchangés. Un verrou séparé évite
de faire entrer les sources CUDA de l’environnement expérimental dans le build CPU.
Le runtime CPU installé localement est `torch==2.10.0+cpu`, sans paquet `nvidia-*`
ni Triton. Le build vérifie `torch.version.cuda is None`.

La base Python est fixée à 3.11.17 Bookworm et au digest
`sha256:f06d01d4ba3f8ad5af45a3ec87df19c1d317d8e8961edc0fabda61811af6f7cf`,
relevé dans le registre le 21 octobre 2026. Ce changement fixe la base de l’image
et ne modifie pas les contraintes Python 3.11 du projet.

L’image finale et son poids ne sont pas mesurés ici. Après construction, relever
`docker image inspect --format '{{.Size}}' IMAGE` ; ne pas confondre la taille d’un
venv local avec celle d’une image complète.

## Configuration privée

Conserver `.env.deploy` et les paramètres Mailjet, sessions, cookies, proxy et
PostgreSQL existants. Ne pas remplacer ce fichier par l’exemple.

| Variable | Valeur / règle |
|---|---|
| `APP_IMAGE_TAG` | Nouveau tag immuable, par exemple `search-cpu-001` |
| `FRONTEND_IMAGE_TAG` | Conserver l’image frontend déployée |
| `HYBRID_SEARCH_ENABLED` | **false** jusqu’à l’autorisation publique |
| `SEARCH_RUNTIME` | `disabled` dans le Compose de base ; l’overlay force le build CPU |
| `SEARCH_DEVICE` / `SEARCH_PRECISION` | L’overlay impose `cpu` / `float32` |
| `SEARCH_CPU_THREADS` | 1, 2 ou 4 ; préparation à 2 |
| `SEARCH_CURSOR_KEY` | Secret stable d’au moins 32 octets |
| `SEARCH_PUBLICATION_KEY` | Secret de signature distinct, au moins 32 octets |
| `SEARCH_MODELS_HOST_DIR` | `/srv/cahier-search/models` |
| `SEARCH_READER_HOST_FILE` | `/srv/cahier-search/private/reader.env` |
| `SEARCH_PUBLICATION_HOST_FILE` | `/srv/cahier-search/private/publication.json` |

Créer les deux secrets avec un outil local, puis les enregistrer directement dans
le fichier privé, sans affichage ni capture de terminal. Ne jamais placer ces
valeurs dans Git, une ligne de commande, une variable publique Vite ou un journal.

Le fichier `reader.env`, modèle
[`deploy/search-reader.env.example`](../deploy/search-reader.env.example), contient :

- `RAG_SOURCE_DATABASE_URL` vers `cahier_doleances`, rôle `cahier_search_reader` ;
- `RAG_DATABASE_URL` vers `cahier_search`, même lecteur.

Les mots de passe doivent être URL-encodés. L’hydratation conserve `DATABASE_URL`
applicative et son pool READ ONLY distinct. Les noms `RAG_*` sont ceux du paquet
existant ; ils n’activent aucun parcours génératif.

Protéger les répertoires privés et fichiers en 0700/0600. Vérifier le numéro
d’utilisateur du backend construit, puis donner à ce numéro la lecture des seuls
fichiers montés ; conserver le parent privé non accessible aux autres utilisateurs.
Ne pas monter tout `.env.deploy` dans le répertoire des modèles.

`compose.deploy.yml` seul fonctionne sans aucun montage de recherche. L’overlay
opt-in [`compose.search.yml`](../compose.search.yml) exige trois chemins existants,
en lecture seule, avec `create_host_path: false`. Pour désactiver sans rendre ces
fichiers obligatoires, recréer le backend avec le Compose de base seul. L’overlay
ne crée aucun service supplémentaire et n’active pas la recherche par défaut.

## Association portable du corpus

### Garantie fournie

[`app.search_admin`](../app/search_admin.py) ne possède aucune écriture SQL. Il :

1. vérifie les noms explicites des bases et leur distinction physique ;
2. contrôle PostgreSQL, pgvector, révision, état du corpus et index ;
3. compare l’empreinte logique à celle relevée sur la source avant transfert ;
4. sélectionne 96 ordinaux répartis sur le corpus, extrémités comprises, plus une
   unité par couple formulaire/type présent ;
5. reconstruit les TextUnit depuis les réponses applicatives cibles ;
6. compare identifiants, texte, question, formulaire et provenance complète ;
7. vérifie les empreintes binaires originales du premier segment de chaque unité
   échantillonnée, sans inférence ;
8. écrit exclusivement un nouveau fichier signé HMAC-SHA256, en 0600.

La preuve est **échantillonnée, pas exhaustive**. Des comptes identiques ne suffisent
pas, mais un échantillon ne prouve pas l’identité de toutes les lignes. L’opérateur
doit vérifier l’origine des imports et accepter explicitement cette limite avec
`--approve-sampled-equivalence`. Si la correspondance historique des imports n’est
pas établie, arrêter et prévoir une comparaison exhaustive hors de cette mission.

L’attestation conserve l’identité source originale et l’empreinte du manifeste,
identifie les deux installations réelles et porte une nouvelle identité de
publication. Le lecteur vérifie signature, corpus, provenance et installations.
Le modèle, les vecteurs et le manifeste PostgreSQL original ne sont pas réécrits.
Les gardes de maintenance ne consomment pas cette attestation.

Une publication modifiée ou remplacée change la génération ; le service refuse
de continuer sans redémarrage et les anciens instantanés sont invalidés. Ne pas
écraser un fichier existant : produire un nouveau nom, faire valider, mettre à jour
le chemin privé et recréer le backend. La clé de signature doit être conservée
hors Git et sauvegardée avec les configurations privées.

Une future migration applicative non déjà approuvée sera refusée : examiner sa
compatibilité, ajouter les tests nécessaires puis republier explicitement. La seule
compatibilité additive préexistante reste `remove_runtime_caches` →
`forms_statistics_v1`, à installation identique.

## Phase A — Préparation locale et contrôles Wallace

### Machine locale

1. Conserver la version du dépôt et les images précédentes.
2. Vérifier les dépendances CPU et les tests sans toucher aux environnements RAG :

   ```bash
   UV_PROJECT_ENVIRONMENT="$PWD/.cache/search-cpu-venv" uv sync --project deploy/search-cpu --locked
   .cache/search-cpu-venv/bin/python -m pytest tests/test_search_preparation.py -q
   .cache/search-cpu-venv/bin/python -m app.search_admin model-check --models rag/models --threads 2
   ```

   Le `model-check` est un test fonctionnel unique, sans SQL ni écriture de vecteurs.
   Il vérifie le snapshot, charge le modèle existant et encode une requête synthétique.
3. Relever l’identité logique, avec les fichiers privés locaux existants :

   ```bash
   .cache/search-cpu-venv/bin/python -m app.search_admin inspect \
     --reader-env rag/search-reader.env \
     --source-name cahier_doleances_local --search-name cahier_rag --check-reader
   ```

   Conserver l’empreinte `logical_id` avec le dossier de transfert, sans secrets.
4. Construire l’image CPU sans activer de service :

   ```bash
   docker build --build-arg SEARCH_RUNTIME=cpu -t cahier-de-doleances-app:search-cpu-001 .
   docker build -f deploy/postgres/Dockerfile -t cahier-postgres:17.11-vector0.8.7-001 .
   ```

   Si ces images sont construites localement, les exporter avec `docker image save`
   dans un nouveau fichier privé, contrôler son SHA-256, le transférer puis utiliser
   `docker image load` sur Wallace avant l’interruption. Autre possibilité : lancer
   ces mêmes constructions sur Wallace, après récupération du code approuvé.
   Ne pas supposer que les tags privés préparés existent dans un registre public.

### Wallace — contrôles humains avant toute interruption

Relever les éléments suivants, sans publier les environnements des conteneurs :

```bash
findmnt -T /data/postgresql/pg17/data
df -h /data/postgresql /srv/docker
free -h
docker info --format '{{.DockerRootDir}}'
docker inspect --format '{{json .Mounts}}' cahier-postgres
docker exec cahier-postgres cat /var/lib/postgresql/data/PG_VERSION
docker exec cahier-postgres stat -c '%u:%g %a' /var/lib/postgresql/data
```

Confirmer les deux montages exacts :

| Hôte | Conteneur |
|---|---|
| `/data/postgresql/pg17/data` | `/var/lib/postgresql/data` |
| `/data/postgresql/.ssd-mounted` | `/run/ssd-mounted` |

Relever aussi le Compose PostgreSQL réel, sa clé de service, ses réseaux, ses
commandes PostgreSQL, sa politique de redémarrage et ses mécanismes de sauvegarde.
Ils ne sont pas présents dans le dépôt applicatif. Ne pas remplacer cette définition
par un `docker run` improvisé. Le modèle d’override suppose une clé `postgres` ;
adapter cette clé au service réel après revue.
Vérifier qu’aucun port PostgreSQL n’est publié sur `0.0.0.0` ou `::` : conserver
le réseau privé, et au plus un accès administratif explicitement lié à la boucle
locale. L’override n’ajoute aucun port.

Budget indicatif : 78 Gio de données restaurées, taille d’archive à mesurer,
80–160 Gio de WAL/temporaire à provisionner sans garantie de plafond, réserve de
50 Gio. Surveiller les slots de réplication et la rétention du WAL. Ne pas déposer
archive ou couches Docker dans `/var`.

**Critère de passage :** sauvegardes vérifiées, image répétée sur copie isolée,
montages/UID compatibles et capacité disque suffisante constatée.

## Phase B — PostgreSQL avec pgvector

Toutes les commandes de cette phase sont futures. Travailler dans une fenêtre
d’interruption validée et empêcher les écritures pendant la sauvegarde finale.

1. Sauvegarder la configuration privée et conserver l’image PostgreSQL actuelle
   sous un tag de retour arrière. Protéger tout `docker inspect` complet : ses
   résultats peuvent contenir des secrets, ne pas les afficher.
2. Arrêter FastAPI avant la sauvegarde finale ; arrêter le laboratoire s’il existe.
   Le frontend/Caddy peuvent être arrêtés pour rendre l’interruption explicite :

   ```bash
   docker compose --env-file .env.deploy -f compose.deploy.yml stop frontend app
   ```

3. Avec le rôle administrateur existant (remplacer `postgres` si nécessaire),
   produire une archive applicative protégée, stockée sur un volume assez grand :

   ```bash
   set -euo pipefail
   set -o noclobber
   umask 077
   sudo install -d -m 700 -o "$(id -u)" -g "$(id -g)" /data/search-transfer
   docker exec cahier-postgres pg_dump -U postgres -Fc -d cahier_doleances \
     > /data/search-transfer/application-before-search.dump
   pg_restore --list /data/search-transfer/application-before-search.dump \
     > /data/search-transfer/application-before-search.toc
   sha256sum /data/search-transfer/application-before-search.dump \
     > /data/search-transfer/application-before-search.dump.sha256
   ```

   Exiger une répétition de restauration dans un cluster isolé et comparer révision,
   données représentatives, comptes et statistiques publiées. La présence d’un
   fichier ou un `pg_restore --list` réussi ne prouve pas la restaurabilité.
4. Prévoir aussi une sauvegarde physique cohérente du cluster pour un retour arrière
   de l’instance : `pg_basebackup` avec WAL si le dispositif existant le permet, ou
   copie/snapshot intégral uniquement après arrêt propre. Ne jamais copier à chaud
   le répertoire de données avec `cp`/`rsync`. Tester cette restauration isolément.
5. Arrêter proprement PostgreSQL via son gestionnaire existant. Fusionner son Compose
   avec [l’override préparé](../deploy/postgres/compose.pgvector.override.yml), après
   avoir réglé `SEARCH_POSTGRES_IMAGE` sur le nouveau tag construit :

   ```bash
   docker compose --env-file /CHEMIN/ENV_POSTGRES_PRIVE \
     -f /CHEMIN/COMPOSE_POSTGRES_EXISTANT \
     -f /srv/cahier-de-doleances-app/deploy/postgres/compose.pgvector.override.yml config --quiet
   ```

   Examiner séparément les montages et options effectifs. Les placeholders sont
   bloquants : les remplacer par les chemins réellement relevés, sans modifier les
   identifiants, le volume ou la politique de sauvegarde existants.
6. Recréer **seulement le service PostgreSQL existant** avec cette combinaison de
   fichiers et `up -d --no-deps --no-build postgres` (clé à confirmer).
7. Vérifier la version, les données applicatives et les binaires d’extension :

   ```bash
   docker exec cahier-postgres psql -X -U postgres -d cahier_doleances -c \
     "SELECT version_num FROM alembic_version;"
   docker exec cahier-postgres psql -X -U postgres -d postgres -c \
     "SELECT version FROM pg_available_extension_versions WHERE name='vector' AND version='0.8.7';"
   ```

   La version applicative attendue est `forms_statistics_v1`. Aucune migration
   applicative ni publication de statistiques n’est nécessaire.
   Comparer aussi, avant et après remplacement, `datcollversion` et
   `pg_database_collation_actual_version(oid)` dans `pg_database`. Un écart de locale
   ou de version de collation bloque la reprise : ne pas réindexer l’application
   ou marquer ses collations à jour automatiquement.
8. Redémarrer le backend documentaire précédent, recherche désactivée, et vérifier
   le site. Puis créer la nouvelle base et ses rôles :

   ```bash
   docker compose --env-file .env.deploy -f compose.deploy.yml up -d --no-deps --no-build app frontend
   docker exec -i cahier-postgres psql -X -U postgres -d postgres \
     -v ON_ERROR_STOP=1 < deploy/postgres/create-search.sql
   docker exec -it cahier-postgres psql -X -U postgres -d postgres \
     -c '\password cahier_search_reader'
   ```

   Le script refuse des bases/rôles de recherche préexistants. En cas d’échec partiel,
   inspecter et reprendre sous contrôle ; il ne supprime rien pour « réparer ».

## Phase C — Archive, transfert et restauration

### Machine locale

La source reste immutable pendant la capture et les contrôles :

```bash
set -euo pipefail
set -o noclobber
umask 077
mkdir -p search-transfer
```

Créer l’archive suivante (aucun fichier d’archive ne doit être déjà présent) :

```bash
pg_dump --format=custom --no-owner --no-acl --dbname=cahier_rag \
  > search-transfer/cahier-search.dump
pg_restore --list search-transfer/cahier-search.dump > search-transfer/cahier-search.toc
.cache/search-cpu-venv/bin/python scripts/search_archive_catalog.py \
  --archive search-transfer/cahier-search.dump --output search-transfer/cahier-search.restore.toc
(cd search-transfer && sha256sum cahier-search.dump > cahier-search.dump.sha256)
```

Examiner le catalogue : extension vector, tous les schémas `rag`, `rag_full`,
`rag_tuning`, partitions full/pilote, `public.rag_alembic_version`, HNSW, GIN,
contraintes et données. Un dump complet conserve les objets auxiliaires. Ne pas
utiliser `--create` à la restauration : le nom cible est différent.

Le catalogue filtré conserve toutes les données et les index ; seules la création
et le commentaire de l’extension vector sont retirés, car l’extension est précréée
par l’administrateur. Cela évite un échec de propriété d’extension sous le rôle de
maintenance. Examiner le diff des deux catalogues : aucun autre objet ne doit manquer.

Transférer les quatre fichiers (archive, deux catalogues et somme SHA-256) via le canal SSH habituel, **uniquement après
validation**, puis vérifier le SHA-256 sur Wallace. Ne pas transférer tout `rag/`
ou le répertoire de modèles : il contient aussi les expériences exclues.

Exemple avec le compte et l’hôte existants (à confirmer avant utilisation) :

```bash
scp search-transfer/cahier-search.dump search-transfer/cahier-search.toc \
  search-transfer/cahier-search.restore.toc search-transfer/cahier-search.dump.sha256 \
  wallace@Wallace:/data/search-transfer/
```

Sur Wallace :

```bash
(cd /data/search-transfer && sha256sum --check cahier-search.dump.sha256)
```

Exiger une vérification réussie avant toute restauration.

### Wallace

1. Placer l’archive sous `/data/search-transfer`. Vérifier son SHA-256 et son catalogue
   avec un client PostgreSQL 17. Vérifier à nouveau l’espace, la RAM et les sauvegardes.
   Recréer localement sur Wallace la liste filtrée avec le script ci-dessus et la
   comparer à la liste transférée (nouveau nom de sortie, ne pas écraser le fichier
   reçu) ; la copier ensuite dans le conteneur :

   ```bash
   docker cp /data/search-transfer/cahier-search.restore.toc cahier-postgres:/tmp/cahier-search.restore.toc
   ```
2. Restaurer sous le rôle propriétaire de maintenance, avec des réglages **de session**,
   sans changer les paramètres globaux ni utiliser ceux de la migration locale :

   ```bash
   docker exec -i \
     -e PGOPTIONS='-c maintenance_work_mem=4GB -c max_parallel_maintenance_workers=0 -c statement_timeout=0 -c lock_timeout=2s -c application_name=search-restore' \
     cahier-postgres pg_restore -U postgres --role=cahier_search_owner \
       --no-owner --no-acl --exit-on-error --use-list=/tmp/cahier-search.restore.toc --section=pre-data --dbname=cahier_search \
       < /data/search-transfer/cahier-search.dump
   docker exec -i \
     -e PGOPTIONS='-c maintenance_work_mem=4GB -c max_parallel_maintenance_workers=0 -c statement_timeout=0 -c lock_timeout=2s -c application_name=search-restore' \
     cahier-postgres pg_restore -U postgres --role=cahier_search_owner \
       --no-owner --no-acl --exit-on-error --use-list=/tmp/cahier-search.restore.toc --section=data --dbname=cahier_search \
       < /data/search-transfer/cahier-search.dump
   docker exec -i \
     -e PGOPTIONS='-c maintenance_work_mem=4GB -c max_parallel_maintenance_workers=0 -c statement_timeout=0 -c lock_timeout=2s -c application_name=search-restore' \
     cahier-postgres pg_restore -U postgres --role=cahier_search_owner \
       --no-owner --no-acl --exit-on-error --use-list=/tmp/cahier-search.restore.toc --section=post-data --dbname=cahier_search \
       < /data/search-transfer/cahier-search.dump
   ```

   Les trois étapes sont séquentielles, sans `-j`. Le graphe de 36 Gio ne tiendra pas
   dans les 4 Gio choisis : la construction peut être longue et faire beaucoup d’I/O.
   Ce budget est un point de départ à valider, pas un temps de construction garanti.
   L’extension est précréée par l’administrateur et exclue de la liste de restauration.
   Ne pas ignorer une erreur ni donner des droits administrateur généraux au rôle
   de maintenance pour contourner un problème de catalogue.
3. Surveiller dans un autre terminal :

   ```bash
   docker exec -i cahier-postgres psql -X -U postgres -d cahier_search \
     < deploy/postgres/monitor-search-restore.sql
   df -h /data/postgresql
   free -h
   vmstat 1
   docker stats cahier-postgres
   ```

   Si disponibles, compléter par `iostat -xz 1` et `pidstat -r -u -d 1`. Examiner
   l’occupation réelle de `pg_wal` et la rétention, pas seulement la position LSN.
   Le choix de zéro worker de maintenance évite la construction HNSW parallèle
   en mémoire partagée ; ne pas augmenter le parallélisme sans vérifier `/dev/shm`.
4. Conditions d’arrêt proposées : espace libre <50 Gio, `MemAvailable` <4 Gio
   durablement, swap entrant/sortant soutenu, OOM, blocage des sauvegardes ou forte
   dégradation documentaire. Les seuils doivent être acceptés avant l’opération.
   Identifier le PID via `application_name='search-restore'`, puis utiliser
   `pg_cancel_backend(PID_VERIFIE)` en administrateur. Attendre l’annulation et
   inspecter les objets partiellement restaurés. Ne pas tuer PostgreSQL, supprimer
   du WAL, relancer tout le dump ou effacer une base automatiquement.
5. Contrôler les effectifs réels et la structure, puis attribuer les droits :

   ```bash
   docker exec -i cahier-postgres psql -X -U postgres -d cahier_search \
     < deploy/postgres/verify-search.sql
   docker exec -i cahier-postgres psql -X -U postgres -d postgres \
     < deploy/postgres/grant-search-reader.sql
   ```

   Le contrôle lit toutes les lignes pour les comptes : prévoir son coût, ne pas
   le mettre dans un healthcheck. Les effectifs attendus sont 5 172 356 documents
   et 5 187 190 segments. Le script d’ACL refuse de réparer des droits hérités
   dangereux sur la source : il conserve les permissions applicatives et demande
   une revue séparée. Aucun droit d’écriture ni appartenance au rôle propriétaire
   n’est accordé au lecteur. Il n’existe pas de privilège séparé de lecture d’index.

## Phase D — Publication de l’association

Construire ou charger l’image CPU sur Wallace. Préparer un fichier privé
`maintenance.env`, même format que `reader.env`, avec accès SELECT aux données
applicatives nécessaires à la comparaison et accès à la copie de recherche.
Ne pas utiliser ce fichier comme configuration du service public. L’opération
reste SQL READ ONLY même si ses identifiants ont davantage de droits.

Le répertoire de sortie doit être accessible en écriture au UID du conteneur,
sans autoriser le runtime public à y écrire. Conserver son accès via un montage
administratif ponctuel uniquement :

```bash
docker run --rm --network cahier-de-doleances_cahier-internal \
  --env-file .env.deploy --read-only --tmpfs /tmp:rw,size=64m \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --mount type=bind,src=/srv/cahier-search/private/maintenance.env,dst=/run/maintenance.env,readonly \
  --mount type=bind,src=/srv/cahier-search/private,dst=/publication-out \
  cahier-de-doleances-app:search-cpu-001 python -m app.search_admin publish \
  --reader-env /run/maintenance.env \
  --expected-logical-id EMPREINTE_RELEVEE_SUR_LA_SOURCE \
  --approve-sampled-equivalence --output /publication-out/publication.json
```

Remplacer l’empreinte et le tag par les valeurs validées. Ne pas utiliser un simple
compte de contributions pour accepter une équivalence. Examiner le nombre de
samples et le niveau d’assurance indiqué dans le résultat. Conserver l’attestation
avec la preuve de transfert et la configuration privée.

Tester ensuite avec le **vrai lecteur**, sans chargement du modèle :

```bash
docker run --rm --network cahier-de-doleances_cahier-internal \
  --env-file .env.deploy --read-only --tmpfs /tmp:rw,size=64m \
  --mount type=bind,src=/srv/cahier-search/private/reader.env,dst=/run/reader.env,readonly \
  cahier-de-doleances-app:search-cpu-001 python -m app.search_admin inspect \
  --reader-env /run/reader.env --check-reader
```

Le service vérifiera aussi la signature et les identités de l’attestation à son
démarrage puis avant les nouveaux classements. Une copie de ce fichier vers une
autre installation sans nouvelle publication est refusée.

## Phase E — Modèle et laboratoire non public

### Machine locale

Transférer exclusivement le snapshot existant
`rag/models/bge-m3/5617a9f61b028005a4858fdac845db406aefb181/`, avec son manifeste et
tous les fichiers qu’il déclare. Cible :
`/srv/cahier-search/models/bge-m3/5617a9f61b028005a4858fdac845db406aefb181/`.
Préserver la lecture par l’utilisateur du conteneur ; aucun téléchargement ne sera
effectué au démarrage. Le code vérifie les SHA-256 des fichiers du snapshot.

Après création de ce nouveau répertoire cible par l’opérateur, transfert futur :

```bash
rsync -a --exclude=.cache --exclude=.git \
  rag/models/bge-m3/5617a9f61b028005a4858fdac845db406aefb181/ \
  wallace@Wallace:/srv/cahier-search/models/bge-m3/5617a9f61b028005a4858fdac845db406aefb181/
```

Aucun `--delete`, autre modèle ou dossier expérimental n’est nécessaire.

### Wallace

Construire sans activer le backend public, puis vérifier le modèle :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml -f compose.search.yml config --quiet
docker compose --env-file .env.deploy -f compose.deploy.yml -f compose.search.yml build app
docker run --rm --read-only --tmpfs /tmp:rw,size=64m \
  --mount type=bind,src=/srv/cahier-search/models,dst=/models,readonly \
  cahier-de-doleances-app:search-cpu-001 python -m app.search_admin model-check --models /models --threads 2
```

Le [Compose de validation](../compose.search.validation.yml) crée seulement une
instance backend **temporaire**, publiée sur `127.0.0.1:8015`, sans Caddy ni réseau
`proxy-private`. Elle utilise les mêmes bases et rôles en lecture seule. Le HTTP
local y est autorisé uniquement pour la recette ; la politique HTTPS du site n’est
pas modifiée. Ne pas faire tourner deux laboratoires/modèles en parallèle.

```bash
docker compose --env-file .env.deploy -f compose.search.validation.yml config --quiet
docker compose --env-file .env.deploy -f compose.search.validation.yml up -d --no-build
curl -fsS http://127.0.0.1:8015/healthz
curl -fsS --get --data-urlencode 'q=Transports publics' http://127.0.0.1:8015/api/v1/search -o /dev/null
```

`/healthz` n’est pas une readiness du modèle. La recherche peut répondre 503 pendant
le chargement ; attendre une réponse 200 avant la recette. Vérifier page suivante,
retour à la première et expiration 410, ainsi que les routes documentaires pendant
chargement/erreur. Ne pas tester une panne par modification des bases existantes.

## Phase F — Benchmarks futurs, non exécutés pendant la préparation

Le script [`benchmark_public_search.py`](../scripts/benchmark_public_search.py)
refuse de fonctionner sans `--execute`, refuse d’écraser un résultat et ne publie
ni requêtes ni textes citoyens dans ses sorties. Les IDs de requêtes et le SHA-256
du jeu sont conservés. La recette H1 n’est jamais modifiée.

Suivre les mesures de CPU, mémoire, swap, I/O et PostgreSQL du protocole de l’audit.
Les pics RSS produits par le script concernent seulement son processus, pas
PostgreSQL ni le modèle d’une API distante. Ne pas additionner les RSS des processus
PostgreSQL comme s’ils représentaient des pages physiques distinctes.

Pour l’encodage, lancer un processus neuf par réglage 1/2/4 threads. Monter le jeu
de requêtes dans le conteneur ; aucun autre modèle ne doit être actif :

```bash
docker run --rm --read-only --tmpfs /tmp:rw,size=64m \
  --mount type=bind,src=/srv/cahier-search/models,dst=/models,readonly \
  --mount type=bind,src=/srv/cahier-de-doleances-app/rag/evaluation/performance-rag027.json,dst=/queries.json,readonly \
  --mount type=bind,src=/srv/cahier-search/benchmark-results,dst=/results \
  cahier-de-doleances-app:search-cpu-001 python scripts/benchmark_public_search.py \
  --execute --mode encoding --models /models --threads 2 --cache-state model-cold \
  --queries /queries.json --output /results/encoding-2threads.json
```

Répéter avec `--threads 1` et `--threads 4`, sorties différentes. Pour les composants,
utiliser `--mode components` dans une exécution ponctuelle avec l’environnement
CPU et les trois montages de recherche (mêmes options que le laboratoire), en ayant
**arrêté le laboratoire API**. Le résultat sépare validation, encodage, lexical,
HNSW et RRF. Cette séparation instrumente la recette réelle, sans substituer des
vecteurs ni des paramètres d’approximation.

Pour l’API, installer le venv CPU avec le groupe dev sur la machine pilote, puis :

```bash
.cache/search-cpu-venv/bin/python scripts/benchmark_public_search.py \
  --execute --mode http --base-url http://127.0.0.1:8015 \
  --users 1 --repeats 10 --cache-state warm --output benchmark-results/http-1.json
```

Répéter à 5 puis 20 utilisateurs, avec sorties distinctes. Choisir un formulaire
aux statistiques déjà publiées via `--statistics-path /api/v1/forms/ID/stats`.
Le script mesure aussi ces routes documentaires en parallèle. Relever un état de
référence sans recherches pour comparer l’impact. Les P50/P95 de succès sont
toujours accompagnés du taux d’erreur et du débit réussi ; les 503/504 ne sont pas
écartés du compte rendu. Respecter le contrat de 512 caractères/32 lexèmes.

Pour le SSR, après validation et accès contrôlé, utiliser `--mode http --path
/recherche --base-url https://cahierdedoleances.fr --allow-remote` avec les mêmes
niveaux de charge. Ajouter une recette de pagination à curseurs et de navigation
sans JavaScript. Ne pas présenter un test API comme une validation SSR.

Le label `--cache-state` est une déclaration d’expérience : le script ne vide aucun
cache. Distinguer modèle froid, buffers PostgreSQL froids/OS chaud et vrai froid.
Ne pas exécuter `drop_caches` ni redémarrer l’instance partagée pour fabriquer une
mesure à froid sur le site ; utiliser une cible isolée ou une maintenance approuvée.

Le P95 <2 s reste indicatif. Examiner surtout disponibilité du site, erreurs,
limites de file, mémoire et stabilité des résultats. Ne pas changer les poids,
profondeurs ou algorithmes pour améliorer le résultat de cette campagne.

## Phase G — Activation publique après décision humaine

1. Arrêter le laboratoire :

   ```bash
   docker compose --env-file .env.deploy -f compose.search.validation.yml stop
   docker compose --env-file .env.deploy -f compose.search.validation.yml rm -f
   ```

2. Faire approuver résultats, preuve échantillonnée, compromis ANN et limites de
   concurrence. Conserver les artefacts et les images précédentes.
3. Régler explicitement `HYBRID_SEARCH_ENABLED=true` dans le fichier privé, puis :

   ```bash
   docker compose --env-file .env.deploy -f compose.deploy.yml -f compose.search.yml \
     up -d --no-deps --no-build app
   ```

4. Vérifier un seul worker, `/healthz`, `/api/v1/search`, `/recherche`, pagination,
   liens originaux et SSR sans JavaScript. Vérifier aussi enquêtes, statistiques,
   comptes et e-mails. Ne pas reconstruire le frontend pour cette activation.
5. Surveiller 503/504, délais, mémoire, swap, I/O et autres routes. Les mesures locales
   ne certifient ni la latence Wallace ni le rappel du HNSW reconstruit.

## Retour arrière

### Désactivation rapide de la recherche

Remettre `HYBRID_SEARCH_ENABLED=false`, puis recréer seulement le backend avec le
Compose de base, sans les montages de recherche :

```bash
docker compose --env-file .env.deploy -f compose.deploy.yml up -d --no-deps --no-build app
```

Le changement d’environnement suffit à recréer le conteneur. Contrôler le flag
sans afficher tous ses secrets, puis vérifier les routes documentaires et la
réponse explicite 503 de la recherche. Les bases et embeddings sont conservés.

### Backend précédent

Remettre le tag `APP_IMAGE_TAG` précédent et le Compose de base sauvegardé si
nécessaire, recherche désactivée, puis exécuter la même commande de recréation.
Conserver le volume PostgreSQL, la base `cahier_search`, les secrets et les archives.

### Image PostgreSQL précédente

Privilégier le maintien de l’image pgvector si seule la recherche échoue. Revenir
à `postgres:17` sans pgvector peut rendre la base spécialisée inutilisable :
les objets restaurés référencent `vector.so`. Aucun retour d’image ne doit être
présenté comme une restauration de données.

Un retour à l’ancienne image n’est permis qu’après revue de la compatibilité du
cluster, arrêt propre et répétition isolée. Ne pas démarrer simultanément deux
instances sur le même `PGDATA`. Si une restauration physique ou applicative est
nécessaire, arrêter les écritures, vérifier la cible, mesurer les écritures perdues
depuis la sauvegarde et obtenir une décision humaine. Conserver d’abord l’état
défaillant pour diagnostic ; ne pas restaurer un dump dans la base active par défaut.

**Ne jamais utiliser `docker compose down -v`, supprimer des embeddings, supprimer
la base spécialisée automatiquement ou réinitialiser le répertoire de données.**

## Contrôles nécessitant l’opérateur Wallace

- Répétition de restauration et conservation des sauvegardes hors SSD.
- Revue du Compose PostgreSQL réel, des UID, du marqueur SSD et des montages.
- Construction réelle des deux images et répétition sur cluster isolé.
- Validation des ACL, mots de passe, fichiers privés et permissions des montages.
- Approbation de la correspondance des imports et de la preuve échantillonnée.
- Surveillance et éventuelle annulation de la reconstruction HNSW.
- Benchmarks réels et acceptation du compromis de qualité/performances.
- Autorisation explicite de l’activation publique.

État préparé : **prêt sous conditions**, sans action sur Wallace. Les résultats
réellement exécutés sont consignés dans le rapport d’implémentation, séparément
des commandes futures de ce guide.
