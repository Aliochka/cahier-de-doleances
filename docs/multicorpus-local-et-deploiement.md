# Multicorpus — application locale et préparation du déploiement

Le relevé réel de **Gavroche du 8 novembre 2026** et les procédures de sauvegarde, transfert, déploiement désactivé, publication séparée et retour arrière sont désormais dans [le plan de production multicorpus](deploiement-multicorpus-gavroche.md). Les commandes locales ci-dessous restent des outils de développement ; ne pas les transposer directement à la production.

La phase 4 est intégrée à FastAPI et React Router. **Aucun déploiement ni aucune publication historique n’est effectué.** L’activation reste explicite ; sans configuration multicorpus, H1 continue de servir la recherche principale et la recherche par question.

## Ouvrir l’application locale

Depuis la racine, après le build frontend :

```sh
pnpm --dir frontend build:offline
.venv/bin/python scripts/run_multicorpus_local.py
```

- Application : **http://127.0.0.1:3000/**
- Recherche : **http://127.0.0.1:3000/recherche**
- Parcourir : **http://127.0.0.1:3000/parcourir**
- Catalogue : **http://127.0.0.1:3000/parcourir/1789**
- API : `http://127.0.0.1:8000`

Le script lance les deux processus sur 127.0.0.1 et les arrête avec Ctrl-C. `backend` ou `frontend` en argument lance une seule partie. Le premier chargement du modèle prend quelques secondes ; la recherche peut répondre 503 pendant cette initialisation, comme H1 auparavant. La consultation documentaire ne dépend pas du chargement du modèle.

Le fichier **local et ignoré par Git** `private/search/phase4/runtime.json` existe sur cette machine, mode 0600. Il contient l’activation, le jeton d’aperçu, l’identité physique attendue de `cahier_rag`, les empreintes source et éditoriale. Le lanceur passe le jeton uniquement au processus SSR et au backend par configuration privée : jamais dans l’URL, les arguments de processus, les fichiers frontend compilés ou les données du navigateur.

Pour recréer cette configuration après restauration **sur la machine locale déjà identifiée**, utiliser les valeurs vérifiées du rapport et un nouveau jeton aléatoire :

```python
import json, os, secrets
from documentary.local_application import LOCAL_IDENTITY
from documentary.artifacts import MANIFEST_SHA256

value = {
    "enabled": True,
    "local_preview": True,
    "expected_target": LOCAL_IDENTITY,
    "preview_token": secrets.token_urlsafe(48),
    "source_manifest_hash": MANIFEST_SHA256,
    "editorial_hash": "2b2b4c14e33ed5b7908a7e0304a980143c803c088af5dd8234690a81a8314cba",
}
with os.fdopen(os.open("private/search/phase4/runtime.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
    json.dump(value, f, indent=2)
```

Ne pas transposer ces identités à un autre cluster sans les vérifier. Les ports 8000/3000 doivent être libres. Les configurations applicative et lecteur GDN existantes restent utilisées ; elles désignent les véritables bases locales.

## Stockage et maintenance locale autorisée

Application GDN : `cahier_doleances_local`, cluster `7697259424657850634`, OID 16385. Recherche commune : **`cahier_rag`, même cluster, OID 2106636**, avec `rag_full`, `rag_tuning` et désormais `documentary`. Aucun accès de l’application intégrée au cluster documentaire temporaire de laboratoire.

La classe `documentary.safety.Destination` conserve ses refus initiaux. La nouvelle `LocalApplicationDestination` est une exception séparée : socket `/var/run/postgresql`, nom exact, identité physique exacte et révision RAG `rag_0007`. Les écritures nécessitent un manifeste de sauvegarde vérifié ; une garde SQL limite les mutations à `documentary`, avec les seuls GRANT/REVOKE documentaires prévus. Elle refuse une destination distante ou de production.

La sauvegarde ciblée initiale est dans `private/search/phase4/backup/` : schéma de recherche complet, données des états/statistiques GDN, inventaire des index avec leurs identités physiques, et archive documentaire source complète. Elle représente environ 75 Mio, et **ne prétend pas être une sauvegarde des 84 Go de données GDN**. Le choix repose sur une migration additive dont les écritures sont limitées au nouveau schéma ; aucune réécriture GDN n’est autorisée. Si une future opération peut toucher GDN, cette sauvegarde ne suffit pas : une sauvegarde complète adaptée à cette opération sera nécessaire.

Les commandes utilisées pour une première intégration, avec le laboratoire source encore présent, sont :

```sh
.venv/bin/python -m documentary.integrate_local backup \
  --source-url 'postgresql+psycopg2://documentary_admin@/documentary_1789_test?host=/tmp/documentary-phase1-45FiOt/socket&port=55487' \
  --source-data-directory /tmp/documentary-phase1-45FiOt/data \
  --source-system-id 7705356223649726476 \
  --backup-directory private/search/phase4/backup

.venv/bin/python -m documentary.integrate_local import \
  --source-url 'postgresql+psycopg2://documentary_admin@/documentary_1789_test?host=/tmp/documentary-phase1-45FiOt/socket&port=55487' \
  --source-data-directory /tmp/documentary-phase1-45FiOt/data \
  --source-system-id 7705356223649726476 \
  --backup-manifest private/search/phase4/backup/manifest.json
```

La première commande refuse de remplacer un répertoire existant : choisir un nouveau nom pour une nouvelle sauvegarde. L’import applique `doc_0001` via la chaîne Alembic documentaire indépendante, importe les sources et décisions, recopie les vecteurs avec correspondance des identifiants/empreintes, reconstruit seulement le lexical documentaire dans la locale cible et vérifie le résultat. Il ne calcule aucun embedding. Un réimport a été exécuté et contrôlé.

Le rôle `cahier_search_reader` reçoit seulement USAGE du schéma et SELECT des tables de consultation/recherche et de sa version Alembic. Il ne peut pas lire `documentary.editorial_decision` ; les justifications et preuves internes ne sont pas des données de présentation. Aucun droit sur `rag_full`, ses données ou ses index n’est ajouté/modifié.

## Archive durable et restauration

L’archive complète préparée est **`private/search/phase4/documentary-local.dump`** (environ 73 Mio). Elle contient documents, passages, métadonnées, représentations, recettes, décisions et version Alembic. Les textes de référence restent aussi dans `1789/data/documents/reference-documents-2-7cbcaea79991`, immuables et ignorés par Git ; conserver/sauvegarder ces artefacts avec l’archive et la politique éditoriale versionnée.

```sh
.venv/bin/python -m documentary.restore_check private/search/phase4/documentary-local.dump
```

Cette commande restaure dans un **nouveau** cluster privé, sans TCP, puis contrôle intégralement les textes/slices/vecteurs/statistiques avant de supprimer le cluster de test. Le test a été exécuté avec succès. Elle ne touche pas à `cahier_rag`.

Après disparition du laboratoire initial, la même archive peut alimenter l’import contrôlé local, avec une sauvegarde appropriée déjà vérifiée :

```sh
.venv/bin/python -m documentary.restore_check private/search/phase4/documentary-local.dump \
  --install-local --backup-manifest private/search/phase4/backup/manifest.json
```

Ce mode est préparé : la restauration est d’abord vérifiée dans le cluster temporaire, puis la même fonction de transfert contrôlé est utilisée vers la seule destination locale autorisée. La restauration seule et le transfert/réimport ont été testés séparément ; cette combinaison CLI n’a pas servi à réinstaller une troisième fois la base de travail. Si l’état GDN a changé depuis la sauvegarde, le contrôle refuse l’ancien manifeste : produire une sauvegarde correspondant au nouvel état avant toute écriture.

**Locale :** le laboratoire initial utilise `C`, l’application `fr_FR.UTF-8`. La configuration `pg_catalog.french` ne supprime pas cette différence : le traitement des majuscules accentuées peut varier. La phase 4 a donc reconstruit les seuls `tsvector` et DF documentaires dans la cible : 86 341 lexèmes, population 10 748. Les 10 748 embeddings restent identiques. La locale est enregistrée dans `release.lexical_statistics.database_locale`. Après une restauration dans une autre locale/version linguistique, vérifier et éventuellement reconstruire ce lexical avant de déclarer la recherche prête. Ne pas modifier les statistiques GDN.

Les dumps ne restaurent pas les statistiques du planificateur : exécuter ANALYZE sur les seules tables documentaires après import/restauration. Le transfert contrôlé le fait déjà. Aucun HNSW documentaire n’est nécessaire ni créé.

## Contrôles de publication

Sans `MULTICORPUS_CONFIG_FILE`, l’application conserve H1. Avec une configuration active, elle propose la voie multicorpus ; cela **n’autorise pas** un corpus historique.

Pour un accès public, la politique exige simultanément :

1. Une identité de base et des empreintes source/éditoriale conformes à la configuration revue.
2. Une release active, `state=ready`, `publication_authorized=true`.
3. Des permissions documentaires appropriées (`readable`, `catalogue_visible` pour le catalogue, `searchable` pour la recherche).
4. Des unités individuellement admissibles et, pour la recherche, des représentations/DF cohérentes avec le périmètre réellement public.

Aucun de ces changements éditoriaux n’a été appliqué. La release reste `verified`, non autorisée, sans pointeur actif, et les permissions publiques des documents restent false. Les 43 autres documents sont exclus du périmètre candidat initial.

L’aperçu local constitue un chemin distinct : environnement backend `dev`, base locale exacte, transport local, requête loopback sans en-tête de proxy et jeton SSR correct. Le navigateur ne possède pas ce jeton. Le SSR ne l’utilise que pour une requête entrante locale explicitement configurée ; les accès aux documents sans cette autorisation répondent 404. Un curseur d’aperçu ne fonctionne pas en accès public ni avec un autre filtre de corpus.

Aucune route ne renvoie les journaux de revue ou les preuves internes des décisions. Les réponses sont sérialisées avec des modèles explicites, pas avec les lignes SQL complètes.

## Préparer un futur déploiement, sans l’exécuter

Les sources `documentary`, `multicorpus` et la politique approuvée sont ajoutées au Dockerfile. `.dockerignore` exclut les données 1789, les journaux et tout `private/` ; seul `1789/editorial/decisions.json` est admis. Le modèle BGE-M3 reste monté selon le profil CPU existant.

L’overlay **`compose.multicorpus.yml`** est préparé, opt-in, pour monter en lecture seule une configuration revue. Il n’importe rien, n’exécute aucune migration et n’active aucune publication. Ne jamais monter le profil local contenant `local_preview=true` en production : il est refusé avec `ENV=prod`.

Séquence à effectuer dans un environnement de validation puis, **après autorisation distincte**, sur la véritable cible :

1. Identifier physiquement source et recherche, vérifier révisions/extensions, droits, espace et sauvegardes de l’environnement cible.
2. Revoir/adapter explicitement la garde de maintenance à cette cible : le profil local livré refuse volontairement une production inconnue.
3. Créer le seul schéma documentaire et sa version indépendante ; importer les artefacts/décisions et restaurer les représentations contrôlées. Garder publication et activation désactivées.
4. Vérifier empreintes/offsets, exclusions, DF/locale, modèle/révision/snapshot BGE, absence de changements GDN ; ANALYZE documentaire uniquement. Vérifier les droits de lecture et l’interdiction du journal éditorial.
5. Construire et tester les images/contrats sur cette cible isolée avec la configuration revue et sans aperçu non publié accessible extérieurement.
6. Faire prendre la décision éditoriale explicite sur les 1 224 candidats. Une publication partielle demande des statistiques de recherche cohérentes avec ce sous-ensemble ; le moteur refuse une incohérence de population.
7. Enregistrer/rejouer une décision de promotion traçable dans une mission autorisée, puis seulement activer le pointeur public et la recherche commune. Les 43 autres documents nécessitent leur propre qualification.

Le profil de maintenance production et la commande de promotion éditoriale ne sont pas autorisés/exécutés dans cette mission. Les barrières de lecture sont préparées ; aucune procédure proposée ne consiste à rendre tous les documents publics pour contourner la politique. Les images Docker n’ont pas été construites ni déployées ici ; le contrôle Python de packaging CPU, les contrats et le build frontend hors réseau ont été exécutés.

## Retour à H1

Arrêter les processus locaux, puis lancer le backend sans activation multicorpus et le frontend sans jeton/aperçu :

```sh
# Dans un terminal ne définissant pas MULTICORPUS_CONFIG_FILE :
.venv/bin/python -m uvicorn app.app:app --host 127.0.0.1 --port 8000 --no-access-log
# Autre terminal, sans DOCUMENTARY_LOCAL_PREVIEW ni DOCUMENTARY_PREVIEW_TOKEN :
API_BASE_URL=http://127.0.0.1:8000 HOST=127.0.0.1 PORT=3000 pnpm --dir frontend start
```

Si ces variables existent dans le shell, les retirer explicitement avant de lancer ces commandes. Le retour arrière a été testé réellement : recette `h1-public-v2-ts-rank`, réponses GDN, sept formulaires et historique indisponible publiquement. Aucun DROP, restauration de millions de réponses ou reconstruction d’index n’est nécessaire ; conserver le schéma documentaire inactif. Un redémarrage invalide les anciens curseurs, qui doivent être relancés.

## Validation locale

```sh
DOCUMENTARY_TEST_PG_BIN=/usr/lib/postgresql/17/bin .venv/bin/pytest \
  tests/test_documentary.py tests/test_documentary_search.py tests/test_multicorpus.py \
  tests/test_phase4_documentary.py tests/test_hybrid_search.py tests/test_search_packaging.py -q
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend lint
.venv/bin/python scripts/export_openapi.py --check
pnpm --dir frontend contract:types:check
.venv/bin/python scripts/smoke_multicorpus_application.py
node frontend/tests/smoke-multicorpus-local.mjs
```

Lancer les deux derniers contrôles après la disponibilité effective du modèle et du serveur frontend. Les tests automatisés d’écriture utilisent uniquement de nouveaux clusters privés. Les smokes de l’application réelle sont en lecture et ne publient rien. Le [rapport de phase 4](../1789/docs/rapport-phase4-integration-application.md) donne les résultats et limites mesurés.
