# Vérification de la sauvegarde PostgreSQL du 2 novembre 2026 — Gavroche

Vérification terminée le **8 novembre 2026 à 10:56:27 UTC** (11:56:27 à Paris). **Conclusion A : sauvegarde restaurable, aucune différence significative détectée sur le périmètre contrôlé. Réutiliser cette sauvegarde physique pour le retour arrière du Grand Débat, sous réserve de valider l'exception au protocole décrite ci-dessous et de conserver séparément la configuration du déploiement.** Une nouvelle copie physique complète de production n'est pas justifiée par les résultats de ce test. Aucune autorisation de déploiement ou d'import n'est déduite de ce contrôle.

## Sauvegarde identifiée et provenance

La source retenue est `/backups/postgresql/wallace-original-20261102/pg17/data`, sur le HDD UUID `52ba8e78-4375-4286-8c75-5cfef6609c8a`. Elle contient **98 318 745 851 octets**, soit **91,57 Gio**, répartis dans **1 961 fichiers réguliers**. Ce chiffre concerne le cluster retenu, pas tout le répertoire `wallace-original-20261102`.

Le répertoire parent a été créé le **2 novembre à 21:01:21 UTC** (22:01 heure de Paris). Les ctime observés sur les fichiers sont cohérents avec un transfert ce soir-là ; les mtime plus anciens sont conservés par rsync. Ce ne sont pas des journaux de fin de transfert.

L'historique shell contient les commandes suivantes, retrouvées **sans les rejouer** :

```sh
sudo rsync -aHAX --numeric-ids --info=progress2 /mnt/wallace-postgresql/ /backups/postgresql/wallace-original-20261102/
sudo rsync -aHAXnci --numeric-ids --stats /mnt/wallace-postgresql/ /backups/postgresql/wallace-original-20261102/
```

La seconde commande est une vérification à blanc avec checksum. La présence de la commande dans l'historique ne prouve ni sa réussite ni sa sortie vide : aucun compte rendu historique de ses résultats n'a été établi. `/mnt/wallace-postgresql` n'est plus un point de montage au contrôle du 8 novembre. La confirmation de l'opérateur (« PostgreSQL arrêté pendant le rsync ») est distinguée des preuves techniques ci-dessous.

Le voisin `pg17-validation` possède le même identifiant physique, mais son dernier arrêt remonte au **21 octobre à 20:13:17 UTC**. Il n'est ni sélectionné ni démarré : le nom et l'identifiant de cluster seuls ne permettent pas de choisir la bonne sauvegarde.

## Cohérence de la source froide

`pg_controldata`, exécuté avec l'image PostgreSQL de production sur un montage **en lecture seule**, donne :

| Contrôle | Résultat |
|---|---|
| Version majeure / catalogue | PostgreSQL 17 / `202406281` |
| Identifiant du cluster | `7695026423032606758`, identique à la production |
| État | `shut down` |
| Dernier checkpoint et modification du contrôle | 2 novembre 2026, **12:04:28 UTC** |
| Checkpoint / REDO | `10/C076A120` / `10/C076A120` |
| WAL du REDO | `0000000100000010000000C0`, présent |
| Fin de sauvegarde requise | `no`, bornes de sauvegarde `0/0` |
| WAL présents | 64 segments de 16 Mio |
| Tablespaces externes / liens symboliques | Aucun dans l'arborescence inspectée |
| Propriétaires des fichiers et sous-répertoires | UID/GID `999:999` |
| Permissions | PGDATA `0700` ; `PG_VERSION` et `global/pg_control` `0600` |
| Somme SHA-256 de `global/pg_control` | `f201724829977746e831b76ee128d0d76bcf606d538f96ede344a2d9b1ba02da` |
| Checksums de pages PostgreSQL | Désactivés (`0`) |

Les éléments `PG_VERSION`, `global/pg_control`, `base`, `pg_wal`, `pg_xact`, `pg_multixact` et les fichiers de configuration sont présents. Aucun `postmaster.pid`, `backup_label` actif, `standby.signal` ou `recovery.signal` n'a été trouvé. La source ne contient pas de `backup_manifest` de pg_basebackup : il s'agit d'une copie froide rsync, pas d'une sauvegarde issue de cet outil.

L'état `shut down`, les WAL et l'absence de signal de récupération sont des preuves cohérentes avec une copie à froid. Ils ne démontrent pas à eux seuls que tous les octets ont été transférés correctement ; le test de démarrage et les lectures SQL sont nécessaires. La version mineure d'origine ne se lit pas dans `PG_VERSION` ; la compatibilité avec **17.11 / pgvector 0.8.7** doit être constatée sur la copie démarrée.

## Test indépendant et éléments de preuve

Le script [verify_nov02_postgres_backup.py](../scripts/verify_nov02_postgres_backup.py) est lancé par l'opérateur depuis son terminal local ; le mot de passe sudo n'est ni enregistré ni transmis dans le rapport :

```sh
cd /home/ro/cahier-de-doleances
python3 scripts/verify_nov02_postgres_backup.py --restore-test
```

**Ne pas relancer cette commande pour consulter les résultats** : chaque exécution crée une nouvelle copie complète. Les preuves du présent essai sont dans le journal local privé `private/search/backup-20261102-validation/20261108T103330Z.jsonl`.

La destination neuve est `/backups/postgresql/restore-tests/nov02-20261108T103343Z/pgdata`, hors du SSD de production. Le parent disposait de **1 754 688 704 512 octets libres** avant la copie. Aucun lien physique n'est créé avec l'original. Les fichiers sont copiés octet par octet et leur SHA-256 source est comparé à une relecture de la destination avant le démarrage. Le manifeste est écrit dans le sous-répertoire **`evidence` du test**, jamais dans la sauvegarde originale. Les modes et dates sont conservés sur la copie, sans chown récursif.

L'image PostgreSQL réutilisée est celle déjà installée :

```text
cahier-postgres-pgvector:17.11-0.8.7
sha256:30ee450c42fda0596abaf71066c1612c79a0aaa791e655e5e00ce2c1e33ab6cc
```

Le conteneur de restauration n'a **aucun réseau (`none`), aucun port publié, aucun montage de production ni montage de l'original**. Il utilise uniquement la copie indépendante, un socket Unix dans `/tmp`, deux CPU au maximum et 2 Gio de mémoire. Son arrêt est prévu dans un bloc `finally`, y compris en cas d'échec des contrôles SQL. Le conteneur arrêté et la copie restent conservés ; aucun nettoyage des données n'est autorisé ou effectué.

La copie a commencé à **10:33:44 UTC** et sa vérification complète s'est terminée à **10:56:12 UTC**, soit environ **22 min 29 s**. Les **1 961 fichiers / 98 318 745 851 octets** ont tous été relus et leurs sommes comparées avec succès. Empreinte du manifeste externe `evidence/files.sha256.json` :

```text
b32cfdb78ec132d16a256e3c94cc97655bb7d7ef9cd8c63ecb6e777721ca9b8e
```

Les métadonnées inventoriées de la source sont restées identiques pendant la copie. Le contrôle original a également été relu après l'essai : contenu `pg_controldata` inchangé, même arrêt du 2 novembre. La vérification SHA-256 garantit ici l'identité de la copie de test avec l'original lu aujourd'hui ; elle ne constitue pas une empreinte enregistrée le 2 novembre.

Le conteneur **`cahier-restore-nov02-20261108t103343z`** a démarré à **10:56:12 UTC**. Les deux bases ont été interrogées en transactions `READ ONLY`, avec des délais SQL bornés. Résultats comparés à la production avant et après l'essai :

| Contrôle | Restauration et comparaison |
|---|---|
| Bases et identités | `cahier_doleances` OID `16384`, `cahier_search` OID `634726`, cluster `7695026423032606758` : identiques |
| PostgreSQL / extensions | PostgreSQL **17.11**, pgvector **0.8.7** ; extensions applicatives présentes |
| Migrations | `forms_statistics_v1` et `rag_0007` : identiques |
| Formulaires / questions / options | **7 / 120 / 123**, comptes exacts et empreintes intégrales des petites tables identiques ; 120 lignes de statistiques de questions identiques |
| Bornes applicatives | Derniers ID réponses **15 915 250**, contributions **1 599 306**, auteurs **1 549 787** : identiques ; ce sont des bornes, pas des nombres de lignes |
| Comptes / favoris | **1 compte, 0 favori**, empreintes des champs de contrôle et dernière connexion identiques ; aucun courriel ou secret exporté |
| Manifeste GDN `full` | **5 172 356 documents**, **5 187 190 segments**, extraction/vecteurs/vérification complets : identiques |
| Recettes / empreintes de corpus | Manifeste complet, `recipe_hash`, `chain_hash` et espace pilote identiques |
| Statistiques lexicales | Population **5 172 356**, **314 656 lexèmes**, empreinte et version identiques ; fréquences de quatre lexèmes échantillonnés identiques |
| Documents et vecteurs réels | Trois documents aux ordinaux **1, 2 586 178, 5 172 356**, puis leurs trois segments : enregistrements, identifiants, empreintes et octets vectoriels échantillonnés identiques ; dimension **1 024** |
| Index | **63 index applicatifs, 27 index de recherche** dans les schémas contrôlés : mêmes définitions et relfilenodes, tous `valid` et `ready` |
| Langue et locales | `en_US.utf8` pour l'application, `fr_FR.UTF-8` pour la recherche ; même résultat de la sonde `to_tsvector('french',…)` |

Les compteurs de `rag_full.spaces` sont ceux du **manifeste**, pas des `COUNT(*)` nouvellement calculés sur les millions de lignes. Les estimations et structures de relations inspectées sont également identiques. La comparaison automatique finale ne signale **aucune différence** dans les deux bases, ni changement des éléments contrôlés en production entre le début et la fin de l'essai.

Une **véritable recherche vectorielle** a ensuite été exécutée sur la copie : requête avec un embedding existant, trois voisins demandés. Le plan contient un `Index Scan` sur **`segments_full_hnsw`**, sans parcours exact des cinq millions de segments. Elle retourne trois résultats, dont le segment requête lui-même en premier. L'appel a pris environ **5,8 secondes** sur le HDD froid du test, conteneur limité à deux CPU ; ce n'est pas une mesure des performances de production et aucun encodage BGE-M3 n'a été effectué.

Le serveur a été **arrêté proprement à 10:56:27 UTC**, code de sortie **0**, sans OOM. Les logs montrent la disponibilité, puis le checkpoint d'arrêt et `database system is shut down`. Une tentative de connexion très précoce a reçu `FATAL: the database system is starting up` avant que le serveur soit prêt : c'est la sonde d'attente, pas une erreur de restauration. Aucune erreur de récupération ou de corruption n'a été observée.

Le conteneur PostgreSQL de production conserve son ID, son image et son heure de démarrage du **6 novembre à 19:59:25 UTC**. Il n'a pas été redémarré ni reconfiguré. La copie et le conteneur de test arrêté sont conservés sur le HDD ; aucun répertoire ancien n'a été nettoyé.

## Production actuelle : contrôles complémentaires en lecture seule

Au **8 novembre à 10:37:10 UTC**, la production a le même `next_xid = 0:1155` que le contrôle de la sauvegarde ; le snapshot courant est `1155:1155:`. Le checkpoint de production est cependant celui du **6 novembre à 20:04:25 UTC**, LSN `10/C076A3E0`, REDO `10/C076A388`. Les fichiers physiques ne sont donc pas identiques : un redémarrage et des écritures techniques ont eu lieu. L'horizon transactionnel inchangé est un indice fort contre de nouvelles écritures transactionnelles, pas une comparaison de tous les contenus des tables.

La publication GDN actuelle porte l'identifiant `f65141228f5229bc35d2619f949ea477`, daté du 22 octobre 2026 à 18:13:19 UTC. Elle référence le même cluster, `cahier_doleances` OID `16384` (`forms_statistics_v1`) et `cahier_search` OID `634726`. Son fichier `/srv/cahier-search/private/publication.json` est **extérieur à PGDATA** : sa restauration n'est pas couverte par cette copie du cluster. Empreinte actuelle : `bb117a749ded5512938d2ab701deaca6a3aa4fca8be5e08faa212fb26b79de32`.

Les deux tablespaces de production sont `pg_default` et `pg_global`, sans emplacement externe. Le schéma `documentary` reste absent. Les connexions complémentaires ont utilisé le rôle de maintenance existant, des transactions en lecture seule, un délai SQL de 5 secondes et des recherches indexées ; aucun contenu de réponse, courriel ou secret n'est publié dans les preuves.

## Limites et protocole proposé, sans modification du garde

Le garde [documentary/production.py](../documentary/production.py) demeure inchangé. Son SHA-256 de référence est `e468217665d01676bb99229a0e6f8a6217dee4cd5db485424d6dda07e13422d4`. Il rejette actuellement une copie du 2 novembre, même restaurée aujourd'hui, pour **deux raisons distinctes** : âge de la sauvegarde supérieur à 24 heures et absence de `backup_manifest` au format pg_basebackup.

Le test et la comparaison étant concluants, proposer pour validation une exception **nominative et ponctuelle** de type `cold-rsync-cluster`, liée exclusivement :

- au chemin d'origine, à l'UUID du HDD, au cluster et aux OID des deux bases ;
- aux dates distinctes de l'état sauvegardé, du transfert attesté et du test terminé ;
- au SHA-256 du contrôle et du manifeste externe de vérification des fichiers ;
- au chemin de la copie testée, à l'image exacte, aux versions et résultats SQL ;
- à une comparaison avec la production encore récente au moment du déploiement ;
- à l'opérateur et à une acceptation explicite de la perte éventuelle d'écritures postérieures au 2 novembre.

Conserver le garde des 24 heures pour les nouvelles sauvegardes ordinaires et la fraîcheur du test/de la comparaison pour cette exception. **Ne pas antidater ou rajeunir artificiellement la sauvegarde, créer un faux `backup_manifest`, ni cocher une attestation d'import acceptée par le garde actuel.** Aucune exception n'est implémentée par cette mission.

La copie physique contient les rôles PostgreSQL, mais pas les fichiers Compose/Caddy, les secrets et preuves de publication hors PGDATA, les images applicatives ni BGE-M3. Leur conservation séparée reste un préalable au futur déploiement, à autoriser distinctement selon le [protocole de sauvegarde](sauvegarde-gavroche-multicorpus.md). Le HDD est distinct du SSD mais demeure sur le même serveur : le présent test ne crée pas de copie hors site.

## Tests de l'outil

Contrôles locaux sans connexion serveur : **29 tests réussis, 1 ignoré** (le test de migration sur un nouveau PostgreSQL requiert une activation explicite). Cela comprend 7 contrôles de la copie : contenu Unicode, sommes, inodes distincts, refus des signaux de cluster actif/récupération, liens externes et destination non vide. Ruff passe. Ils complètent le véritable essai distant réussi décrit ci-dessus.

## Recommandation et décisions restantes

**Réutiliser la copie physique du 2 novembre : catégorie A sur les contrôles réalisés.** Elle permet de revenir à un cluster PostgreSQL fonctionnel contenant le Grand Débat et ses index, sans reconstruire HNSW. Aucune donnée nouvelle n'a été détectée par les contrôles bornés ; l'horizon transactionnel identique renforce cette conclusion. Il ne s'agit toutefois pas d'une preuve d'égalité exhaustive des millions de lignes ni d'une vérification de toutes les pages de tous les index. Les checksums de pages sont désactivés et aucun manifeste signé du jour du rsync n'a été retrouvé.

Avant tout futur déploiement, faire valider **l'exception décrite au garde des 24 heures**, conserver les configurations/images/preuves de publication hors PGDATA, puis refaire une comparaison récente des identités et de l'état GDN. Si de nouvelles écritures applicatives sont constatées entre-temps, réexaminer le point de restauration et le besoin d'une sauvegarde complémentaire ou complète ; ne pas réutiliser silencieusement cette conclusion.

Une attestation de **contrôle uniquement**, non utilisable comme autorisation d'import, est conservée localement dans `private/search/backup-20261102-validation/restore-attestation.json`, avec les dates, chemins, identités et résultats. Le journal détaillé reste privé et ignoré par Git. Le garde de production, les données GDN et les paramètres de publication n'ont pas été modifiés. **Aucun déploiement, import de 1789, nouvelle sauvegarde de production ou activation publique n'a été entrepris.**
