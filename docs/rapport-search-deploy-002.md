# SEARCH-DEPLOY-002 — Rapport d’implémentation

Date : 21 octobre 2026. **Préparation locale terminée, prête sous conditions.**
Aucune connexion à Wallace, activation publique, migration applicative, opération
sur les bases locales existantes, reconstruction d’index existants, génération
d’embeddings documentaires, commit ou push.

La recette H1 et ses paramètres de pertinence sont inchangés. Le frontend, les
pipelines expérimentaux et les verrous applicatif/RAG existants sont conservés.
Le [guide opérationnel](search-deploiement.md) distingue toutes les commandes
futures sur la machine locale et sur Wallace, ainsi que leurs critères de passage.

## A. Modifications

| Fichiers | Rôle |
|---|---|
| [Dockerfile PostgreSQL](../deploy/postgres/Dockerfile), [guard de cluster](../deploy/postgres/existing-cluster.sh), [override manuel](../deploy/postgres/compose.pgvector.override.yml) | Image pgvector épinglée, locale française, refus d’initialisation ou de changement de propriétaire, conservation des deux bind mounts |
| [Création](../deploy/postgres/create-search.sql), [droits](../deploy/postgres/grant-search-reader.sql), [contrôles](../deploy/postgres/verify-search.sql), [surveillance](../deploy/postgres/monitor-search-restore.sql) | Préparation administrative explicite ; propriétaire de maintenance distinct, lecteur limité, vérification des comptes et suivi de restauration |
| [CPU pyproject](../deploy/search-cpu/pyproject.toml), [CPU uv.lock](../deploy/search-cpu/uv.lock), [Dockerfile backend](../Dockerfile) | Verrou CPU autonome, mêmes versions applicatives, PyTorch sans CUDA, un worker Gunicorn, base Python épinglée |
| [Publication signée](../rag/src/cahier_rag/search/publication.py), [commande administrative](../app/search_admin.py) | Identité logique distincte, preuve de contenus/provenance échantillonnée, empreintes vectorielles, signature et création exclusive d’un fichier 0600 |
| [Lecteur](../rag/src/cahier_rag/search/service/reader.py), [fabrique](../rag/src/cahier_rag/search/service/__init__.py), [lifespan](../app/hybrid_runtime.py) | Vérification de l’association et des générations, refus des droits d’écriture publics, threads 1/2/4 configurables, publication CPU requise en production |
| [Compose principal](../compose.deploy.yml), [overlay CPU](../compose.search.yml), [laboratoire temporaire](../compose.search.validation.yml) | Base autonome lorsque désactivée, montages opt-in en lecture seule, validation uniquement sur la boucle locale |
| [.env d’exemple](../.env.deploy.example), [lecteur d’exemple](../deploy/search-reader.env.example), [.gitignore](../.gitignore) | Secrets séparés, recherche désactivée par défaut, exclusion des fichiers privés/archives/résultats |
| [Catalogue de restauration](../scripts/search_archive_catalog.py) | Conserve données et index ; exclut uniquement les métadonnées de l’extension préinstallée pour restaurer sous le rôle non administrateur |
| [Benchmark préparé](../scripts/benchmark_public_search.py) | Encodage/composants/API/SSR, charge 1/5/20, compte des erreurs et sondes documentaires ; aucune exécution sans `--execute` |
| [Tests de préparation](../tests/test_search_preparation.py), [PostgreSQL isolé](../tests/test_search_deploy_pg.py), [marqueur](../pytest.ini) | Régressions, signature et corpus incompatibles, contrôles CPU/Compose, essais SQL réels sur un cluster temporaire neuf |
| [Guide de recherche](search-deploiement.md), [lien de déploiement](deploiement.md) | Phases A–G, transfert, sauvegardes, conditions d’annulation HNSW, benchmarks et retour arrière |

### Décisions d’implémentation

- L’association n’ajoute aucune table et ne réécrit pas le manifeste d’origine.
  Elle est signée, externe, montée en lecture seule, et lie les deux identités
  physiques au corpus logique vérifié. Les gardes d’écriture RAG restent stricts.
- La preuve porte sur 96 ordinaux et les strates formulaire/type présentes,
  comparés aux TextUnit applicatives complètes. **Elle n’est pas exhaustive** :
  le niveau d’assurance et son approbation humaine sont enregistrés explicitement.
- La signature inclut une identité de publication nouvelle. Republier change la
  génération, exige un redémarrage et invalide les instantanés précédents.
- Un verrou CPU séparé évite les sources CUDA des extras expérimentaux sans
  modifier leurs installations. Les tests contrôlent les versions communes.
- Une instance PostgreSQL et un worker FastAPI restent les seules instances de
  production prévues. Le laboratoire est une copie temporaire de validation, sans
  Caddy ni port public, à arrêter avant activation.
- Aucun benchmark n’a été exécuté. Le test de modèle est un chargement et une
  inférence fonctionnelle uniques ; les essais H1 SQL utilisent un encodeur
  synthétique et des données nouvelles dans le cluster de test.

## B. Architecture préparée

- PostgreSQL 17.11 Trixie + pgvector 0.8.7 : digest du registre vérifié, construction
  réelle et réutilisation du cluster restant à répéter avec Docker.
- `cahier_doleances` inchangée ; nouvelle base `cahier_search` en UTF8/fr_FR.UTF-8.
- `cahier_search_owner` : maintenance/restauration, NOLOGIN, non administrateur.
- `cahier_search_reader` : lecture limitée, non propriétaire, quatre connexions,
  accès ciblé à l’identité PostgreSQL, aucun rôle écrivain hérité admis.
- Rôle applicatif existant : conservé ; l’hydratation utilise son pool READ ONLY.
- BGE-M3 exact existant, CPU/float32, un modèle par processus, monté hors image.
- Un worker, curseurs opaques et TTL existants, mêmes budgets et limites de file.
- `HYBRID_SEARCH_ENABLED=false` dans l’exemple et par défaut Compose. Aucun montage
  ni paquet PyTorch nécessaire au déploiement de base désactivé.

## C. Validations exécutées

### Backend

Commande exécutée avec les URL des bases de test existantes explicitement vides :

```bash
TEST_DATABASE_URL='' RAG_TEST_DATABASE_URL='' RAG_STORAGE_TEST_DATABASE_URL='' \
GDN_IMPORT_TEST_DATABASE_URL='' SEARCH_DEPLOY_TEST_PG_BIN=/usr/lib/postgresql/17/bin \
  /tmp/cahier-search-cpu-venv/bin/pytest tests -m 'not integration' -q
```

Résultat final : **261 réussites, 5 tests ignorés, 116 désélectionnés, 7 sous-tests
réussis**. Les tests ignorés attendent d’autres bases de test ; les tests marqués
`integration` ont été volontairement exclus pour préserver les bases existantes.
Aucun test final en échec. Avertissements existants : dépréciation httpx/TestClient
et operation IDs SEO dupliqués.

Sous-ensemble RAG directement concerné, exécuté séparément :

```bash
/tmp/cahier-search-cpu-venv/bin/pytest \
  rag/tests/unit/test_search_service.py rag/tests/unit/test_hybrid.py \
  rag/tests/unit/test_config.py -q
```

Résultat : **91 réussites**. Les comportements H1/RRF, annulation et admission
existants restent couverts.

### PostgreSQL réel isolé

Le test opt-in initialise son propre cluster PostgreSQL 17.11 dans un répertoire
temporaire neuf, sans écoute TCP, puis l’arrête à la fin. Il ne se connecte pas au
serveur local contenant les corpus de travail.

Vérifications réalisées :

- scripts de création et d’attribution des rôles, et refus de réinitialisation ;
- métadonnées, versions, collation, GIN et HNSW sur des tables synthétiques ;
- source incompatible refusée après une modification de la seule fixture neuve ;
- publication signée et lecteur public réel ;
- H1 réel lexical/HNSW/RRF avec un encodeur synthétique ;
- petit dump complet et restauration en trois sections sous le rôle propriétaire,
  extension précréée, sans droits administrateur de contournement ;
- empreintes vectorielles après restauration, incluant un zéro signé ;
- script de surveillance SQL et refus des effectifs de production par une fixture
  volontairement trop petite.

Ce test est inclus dans les 261 réussites. Il ne valide ni les volumes réels,
ni la durée/mémoire de reconstruction d’un HNSW de 36 Gio.

### CPU et désactivation

- Environnement isolé `/tmp/cahier-search-cpu-venv`, PyTorch **2.10.0+cpu** ; aucun
  paquet `nvidia-*` ni Triton dans le verrou CPU.
- Chargement du snapshot BGE-M3 existant, vérification de ses fichiers et encodage
  fonctionnel sur CPU à deux threads : **1 024 dimensions, succès**. Aucun nouveau
  modèle téléchargé ; aucun embedding documentaire recalculé ou stocké.
- Snapshot absent : échec testé avec les connexions réseau interdites.
- Environnement léger séparé, sans torch ni fichiers/montages de recherche :
  lifespan désactivé et `GET /openapi.json` via ASGI **HTTP 200**.

### Vérifications statiques

- Verrous racine et CPU : `uv lock --check` réussi ; racine/RAG inchangés.
- Ruff et formatage : réussis sur les fichiers Python concernés.
- Shell PostgreSQL : `bash -n` réussi.
- Quatre fichiers Compose : lecture YAML réussie ; liens du guide vérifiés.
- `git diff --check` réussi.

### Non exécuté

- Docker indisponible : **aucune image construite**, aucun `docker compose
  config` exécuté ; taille et comportement des images restent à vérifier.
- Aucun remplacement d’image PostgreSQL ou essai sur une copie du PGDATA de Wallace.
- Aucun dump de 78 Gio, transfert, recomptage complet ou HNSW de production reconstruit.
- Aucun benchmark 1/5/20, aucun chiffre de performances Wallace.
- Aucun nouveau test réel React SSR ↔ moteur sur Wallace. Le contrat et le
  frontend sont inchangés ; la recette SSR reste une étape future explicite.

## D. Déploiement et critères de validation

Suivre le [guide opérationnel](search-deploiement.md) dans cet ordre :

1. **A :** sauvegardes restaurables, espace, UID/montages, configurations privées et images.
2. **B :** répétition isolée de l’image PostgreSQL, sauvegarde finale, remplacement
   contrôlé, vérification de la base applicative, création de la base de recherche.
3. **C :** dump cohérent intégral, SHA-256/catalogue, transfert, restauration bornée,
   reconstruction index, comptes/contraintes/ACL.
4. **D :** comparaison des imports et contenus, publication approuvée, test du lecteur.
5. **E :** transfert du seul snapshot BGE-M3, image CPU, laboratoire sur la boucle locale.
6. **F :** encodage 1/2/4 threads, composants et charge 1/5/20 ; impact documentaire.
7. **G :** autorisation humaine, arrêt du laboratoire, activation, recette SSR et surveillance.

Ne pas passer une étape dont le contrôle a échoué. L’objectif P95 <2 s reste
indicatif ; les classements et paramètres ne sont pas modifiés pour le satisfaire.

## E. Retour arrière

- Désactivation : remettre le flag à false et recréer seulement FastAPI avec le
  Compose de base, sans les montages de recherche.
- Backend : conserver puis réutiliser son tag précédent, sans modification des bases.
- PostgreSQL : maintenir de préférence l’image pgvector si seul le moteur échoue.
  L’ancienne image sans vector.so n’assure pas le fonctionnement de la nouvelle base.
  Retour d’image seulement après revue et arrêt propre, jamais deux serveurs sur
  le même répertoire.
- Données : restauration seulement à partir d’une sauvegarde répétée, cible et
  pertes d’écritures validées humainement. Le changement d’image n’est pas une
  restauration. Ne pas supprimer automatiquement `cahier_search`, ni utiliser
  `docker compose down -v`.

## F. Interventions humaines requises

Sur Wallace, avant installation :

- confirmer le Compose PostgreSQL réel, sa clé de service et les deux montages ;
- répéter les images sur copie isolée et vérifier UID, locale et versions de collation ;
- vérifier les sauvegardes hors SSD et leur restauration ;
- mesurer l’espace, préparer le WAL/temporaire et accepter les seuils d’arrêt ;
- créer/configurer les secrets et les permissions des montages ;
- réaliser le transfert et la restauration, surveiller ou annuler HNSW si nécessaire ;
- accepter le niveau de preuve échantillonné et le compromis ANN non qualifié ;
- mener les benchmarks et la recette SSR, puis autoriser explicitement le public.

## G. État final

**Prêt sous conditions pour la préparation du transfert et les répétitions Docker.**
Les composants, scripts et procédures sont disponibles et testés localement dans
les limites décrites. Le transfert et l’installation sur l’instance partagée
restent conditionnés à la répétition réelle des images et des sauvegardes, à la
compatibilité du PGDATA et aux contrôles de ressources sur Wallace.

**Pas d’autorisation d’ouverture publique implicite.** Aucune intervention sur
Wallace ne doit commencer avant validation de ce rapport et du guide.
