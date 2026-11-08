# Prérequis finalisés — multicorpus sur Gavroche

8 novembre 2026. **Préparation uniquement : aucun import, DDL documentaire, remplacement de conteneur ou changement de publication en production.** La réutilisation de la sauvegarde froide du 2 novembre est acceptée par l'opérateur ; aucune nouvelle sauvegarde physique ni nouvelle restauration n'est nécessaire maintenant.

## Garde et attestation

[backup_exception.py](../documentary/backup_exception.py), appelé par [production.py](../documentary/production.py), ajoute uniquement l'exception `gavroche-cold-20261102-v1`. Le chemin, UUID HDD, identités des deux bases, contrôle, manifeste externe, preuve de restauration isolée et dates sont épinglés aux observations du [rapport du 8 novembre](verification-sauvegarde-20261102-gavroche.md). La date exacte de fin du rsync est inconnue et reste `null` ; l'arrêt source est le 2 novembre à 12:04:28 UTC. Aucun faux `backup_manifest` n'est créé.

L'exception exige également :

- l'acceptation explicite de ce point de restauration et sa référence ;
- un contrôle de production et de sauvegarde datant de **moins de 24 h**, sans différence avec le périmètre vérifié le 8 novembre ;
- l'horizon transactionnel attendu `1155:1155:` et les bons SSD/HDD ;
- des archives de retour arrière réellement conservées et vérifiées, dans une destination HDD neuve distincte de PGDATA et de la sauvegarde froide ;
- les empreintes et tailles non nulles des trois archives, ainsi que les identifiants d'images et du modèle attendus.

Toutes les autres sauvegardes conservent la règle ordinaire des 24 h pour sauvegarde **et** restauration. Une exception inconnue, un autre cluster, une empreinte modifiée, une comparaison périmée ou des actifs manquants sont refusés. Les gardes d'URL, rôle, identité SQL, schéma et non-publication restent appliqués à chaque transaction d'import.

[nov02-backup-proof.prepared.json](../deploy/documentary/nov02-backup-proof.prepared.json) enregistre les faits observés et l'acceptation du point de restauration. **Ce fichier ne permet pas encore l'import : `rollback_assets=null`.** Il ne faut pas remplir ce champ avant la conservation effective. L'ancienne attestation d'audit reste une preuve historique ; elle n'est pas remplacée ou réécrite.

Les fichiers d'attestation sont des déclarations opérateur contrôlées par le client ; ce contrôle ne certifie pas à distance des fichiers simplement parce qu'un hash figure dans un JSON. Le contrôle RO et la vérification des archives ci-dessous sont les étapes qui produisent les faits à attester.

## Recontrôle réel du 8 novembre à 17:04:45 UTC (18:04 à Paris)

Effectué avec [recheck_multicorpus_prerequisites.py](../scripts/recheck_multicorpus_prerequisites.py), sans relancer la restauration ni parcourir à nouveau les 98 Go par checksum. Les diagnostics Docker ont uniquement des montages RO, aucun réseau et aucun port publié.

| Contrôle | Résultat |
|---|---|
| Cluster / bases | `7695026423032606758`, application `cahier_doleances` OID `16384`, recherche `cahier_search` OID `634726` |
| Migrations / extensions | `forms_statistics_v1`, `rag_0007`, pgvector `0.8.7` |
| Périmètre comparé | Identités, migrations, compteurs/recettes/manifeste GDN, statistiques, index, échantillons de documents/vecteurs, petites tables applicatives et bornes des grandes tables : identiques à la référence |
| Empreinte canonique de comparaison | `e2a11f8155a1541792273eefa69e58416834383f35d4e03407ffe9fd9167c101` |
| Écritures applicatives | Aucune différence significative détectée sur ce périmètre ; snapshot toujours `1155:1155:` |
| Sauvegarde froide | Inventaire, contrôle et manifeste externe conformes aux empreintes du test réussi |
| SSD | UUID `624405d4-3422-4b7d-8ca3-8579d8b513bb`, **334 271 528 960 octets libres** (~311 Gio) |
| HDD | UUID `52ba8e78-4375-4286-8c75-5cfef6609c8a`, **1 656 369 139 712 octets libres** (~1,51 Tio) |
| Ressources | 8 CPU, ~60,2 Gio de RAM disponibles, swap inutilisé |
| Services | Quatre images et heures de démarrage inchangées, quatre services `healthy` |
| Modèle | Vérification de tous les fichiers du snapshot BGE-M3 réussie, sans encodage |
| Configurations | Toutes les sources du manifeste de conservation sont présentes, y compris les volumes Caddy |

Les limites restent celles du rapport : pas de preuve d'égalité exhaustive de toutes les lignes/pages, checksums de pages désactivés, pas de journal historique de réussite du rsync. Le contrôle complémentaire vérifie présence/métadonnées et empreintes épinglées, en s'appuyant sur la lecture SHA-256 complète et la restauration déjà réalisées. Il n'enregistre aucune donnée source sensible.

Preuves privées : `private/search/multicorpus-prerequisites/20261108T170353Z.json`. Référence comparable, sans textes ni secrets : [gavroche-nov02-baseline.json](../deploy/documentary/gavroche-nov02-baseline.json).

## Actifs exacts à conserver lors du déploiement autorisé

La liste exploitable est [gavroche-rollback-inventory.json](../deploy/documentary/gavroche-rollback-inventory.json). Elle contient :

- `/srv/cahier-de-doleances/compose.yaml` et `.env` ;
- `/srv/cahier-de-doleances-app/.env.deploy`, `compose.deploy.yml`, `compose.search.yml`, `Caddyfile` et `deploy/postgres/` (Dockerfile, override, garde de cluster existant et SQL d'exploitation) ;
- `/srv/cahier-de-doleances-app/rag/search-reader.env` ;
- `/srv/cahier-search/private/` : publication GDN, clefs/fichiers privés et maintenance ;
- `/etc/fstab`, `/etc/systemd/system/docker.service.d/` ;
- les quatre configurations actives de `/data/postgresql/pg17/data/` : `postgresql.conf`, `postgresql.auto.conf`, `pg_hba.conf`, `pg_ident.conf`, **sans recopier PGDATA** ;
- les deux volumes Caddy, sous `/var/lib/docker/volumes/cahier-de-doleances-app_caddy-{data,config}/_data`, dont certificats et état de configuration.

| Image à archiver | Identifiant exact |
|---|---|
| Backend `cahier-de-doleances-app:search-in-question` | `sha256:e0c26f229536597004ef299d6e8406fb087916d0511eabe8bd02e5543070c7cd` |
| Frontend `cahier-de-doleances-frontend:search-in-question` | `sha256:73e31e5b321040259aae7769d5fc4eaebcd90c493ebdc85f1168d1313176a1eb` |
| PostgreSQL `cahier-postgres-pgvector:17.11-0.8.7` | `sha256:30ee450c42fda0596abaf71066c1612c79a0aaa791e655e5e00ce2c1e33ab6cc` |
| Caddy `caddy:2.11.2-alpine` | `sha256:834468128c7696cec0ceea6172f7d692daf645ae51983ca76e39da54a97c570d` |

Le modèle à conserver est `/srv/cahier-search/models/bge-m3/5617a9f61b028005a4858fdac845db406aefb181`, avec son manifeste `fe2f29e9b4699cfeb8ee4d9524c1e99df203cb4f144dbe4b463e28e65e3d1f6d`. Ses fichiers ont été hachés et vérifiés pendant le recontrôle ; la conservation privilégie ce snapshot installé, sans dépendre d'un téléchargement futur.

## Procédure future : conservation avant toute modification

**Les commandes de cette section ne sont pas exécutées dans la mission de préparation.** Elles nécessitent l'autorisation de déploiement technique. Ne pas changer le checkout distant avant d'archiver ses configurations actuelles.

Sur la machine de préparation, mettre à jour le contrôle si nécessaire (il expire après 24 h et doit être refait après tout changement connu) :

```sh
cd /home/ro/cahier-de-doleances
python3 scripts/recheck_multicorpus_prerequisites.py
```

Noter le nouveau fichier de preuve s'il diffère de celui du 8 novembre. Puis, **après autorisation**, lancer depuis cette même machine :

```sh
python3 scripts/preserve_gavroche_rollback.py --execute-preservation --via-ssh \
  --preflight private/search/multicorpus-prerequisites/20261108T170353Z.json
```

Le script s'exécute à distance en mémoire, sans installation ni changement préalable du checkout. Il refuse les mauvais hôte/disque/images, le contrôle périmé, les fichiers manquants ou le modèle altéré. Il crée uniquement `/backups/postgresql/rollback-multicorpus-<UTC>` en **0700**, archives et reçus privés en **0600**, avec créations exclusives : aucun fichier existant n'est écrasé. Il ne fait ni export complet de PostgreSQL, ni retag, ni redémarrage.

Il produit `configuration.tar`, `images.tar`, `model.tar`, `files.sha256` et `receipt.json`. Chaque archive est relue structurellement et hachée ; les trois tailles/hashes sont dans le reçu, également enregistré localement sous `private/search/multicorpus-prerequisites/rollback-<UTC>.json`. Une erreur (dont un fichier modifié pendant tar) laisse un répertoire partiel mais **aucun reçu complet** : ne pas déployer ni le nettoyer automatiquement, recommencer dans une nouvelle destination après examen.

Le modèle est validé avant l'archivage. Le script ne charge pas les images archivées pour les tester et ne fait pas de restauration des configurations actives : ces opérations remplaceraient inutilement des actifs pendant une étape de conservation. Les images sont archivées par ID ; le retour arrière les référence par ces mêmes ID, même si leurs tags ont changé.

## Compléter l'attestation après conservation réelle

Sur la machine locale, renseigner les **deux chemins de résultats réellement produits** avant d'exécuter ce bloc. Aucun accès PostgreSQL n'est effectué par cette validation :

```python
import json, os
from pathlib import Path
from documentary.production import check_backup_proof

comparison_path = Path('private/search/multicorpus-prerequisites/20261108T170353Z.json')
receipt_path = Path('private/search/multicorpus-prerequisites/rollback-REMPLACER.json')
proof = json.loads(Path('deploy/documentary/nov02-backup-proof.prepared.json').read_text())
observed = json.loads(comparison_path.read_text())
proof['recent_comparison'] = {k: observed[k] for k in proof['recent_comparison']}
proof['rollback_assets'] = json.loads(receipt_path.read_text())
check_backup_proof(proof)
with os.fdopen(os.open('private/search/production-preparation/backup-proof.json',
                      os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
    json.dump(proof, f, indent=2)
```

Si le fichier de destination existe déjà, choisir un nouveau nom et l'utiliser pour l'import, sans écraser une attestation précédente. Ne pas remplacer les vrais hashes ou inventer les reçus pour faire passer le garde.

Dans le shell root de déploiement, renseigner le chemin **exact du reçu** de cette opération :

```bash
set -euo pipefail
umask 077
export MC_ROOT=/srv/cahier-de-doleances-app
read -r -p 'Répertoire rollback-multicorpus créé : ' MC_BACKUP
[[ "$MC_BACKUP" =~ ^/backups/postgresql/rollback-multicorpus-[0-9]{8}T[0-9]{6}Z$ ]]
test -f "$MC_BACKUP/receipt.json"
(cd "$MC_BACKUP" && sha256sum -c files.sha256)
export MC_BACKUP
export MC_STAMP="${MC_BACKUP##*/rollback-multicorpus-}"
export MC_PHYSICAL_BACKUP=/backups/postgresql/wallace-original-20261102/pg17/data
```

## Suite du déploiement et retour arrière

Après validation de l'attestation et autorisation de déploiement, reprendre les étapes **B à E** du [plan principal](deploiement-multicorpus-gavroche.md) : checkout du SHA approuvé, images CPU/frontend neuves, provision documentaire contrôlé, transfert des représentations existantes, import et intégrité, puis déploiement applicatif avec le multicorpus **désactivé**, H1 conservé et `local_preview=false`. Aucun redémarrage PostgreSQL n'est requis. Les 1 224 candidats ne sont pas publiés ; les 43 autres documents restent hors publication.

Pour une régression applicative, utiliser les archives et les ID d'images ci-dessus selon le niveau 2 du plan principal ; pour un problème de multicorpus seul, désactiver sa configuration et garder H1. **Ne pas restaurer PGDATA pour un simple retour applicatif.** Une éventuelle reprise PostgreSQL reste une opération d'incident distincte, depuis une copie indépendante de la sauvegarde froide, après acceptation de son point de restauration. Aucune suppression de `documentary` ou restauration destructive n'est automatique.

## Derniers points avant autorisation

- Checkout distant confirmé : `818b5464f24cac4d8537793c15c8e2c580505f88`. Base locale de cette préparation : `fc67b17734ea2a14b546326b990955bec17fcca7`, branche `main`.
- **Le SHA final à déployer n'existe pas encore pour ces modifications non commitées.** Les versionner/revoir, puis approuver et épingler le SHA complet ; ne pas déployer automatiquement le `main` courant.
- Conservation réelle des actifs, reçu et attestation complète : **en attente de l'étape autorisée**. Le garde refuse actuellement l'attestation préparée à juste titre.
- Confirmer la fenêtre de déploiement et les intégrations externes de `main` évoquées dans le plan principal ; les contrôles du dépôt n'ont pas révélé de déploiement automatique vers Gavroche.
- Décider de la rétention et d'une copie hors serveur : le HDD ne protège pas contre la perte de toute la machine.
- L'autorisation technique de déploiement, puis l'autorisation éditoriale/publication et activation, restent distinctes. Aucune n'est déduite de l'acceptation de cette sauvegarde.

Tests exécutés : **85 réussis, 1 ignoré**, avec `tests/test_nov02_backup_exception.py`, `tests/test_documentary_production.py` et `tests/test_nov02_backup_verifier.py`. L'intégration sur un nouveau cluster local est ignorée faute d'opt-in `DOCUMENTARY_TEST_PG_BIN` ; aucune migration SQL n'a été exécutée pour cette mission. Ces tests vérifient l'exception et ses refus, les protections ordinaires et l'outil de copie précédent. Ils n'exécutent ni conservation HDD ni import de production. Ruff et le contrôle de diff passent. Aucun frontend ou moteur H1 n'est modifié.
