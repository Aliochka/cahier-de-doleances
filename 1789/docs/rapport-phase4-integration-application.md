# Phase 4 — Intégration multicorpus dans l’application locale

Date : 7 novembre 2026. **Implémentation et intégration locales ; aucune publication ni aucun déploiement de production.**

## Résultat livré

L’application FastAPI/React Router fonctionne avec les véritables bases locales : données applicatives GDN dans `cahier_doleances_local`, et recherche **GDN + 1789 dans la même base `cahier_rag`**, respectivement sous `rag_full`/`rag_tuning` et `documentary`. Les deux modèles métier restent distincts. Le cluster historique sous `/tmp` ne sert plus à l’application intégrée.

Accès : **http://127.0.0.1:3000/** ; [recherche](http://127.0.0.1:3000/recherche), [Parcourir](http://127.0.0.1:3000/parcourir), [catalogue](http://127.0.0.1:3000/parcourir/1789). Le serveur est lancé localement avec l’aperçu autorisé. Pour le relancer :

```sh
pnpm --dir frontend build:offline
.venv/bin/python scripts/run_multicorpus_local.py
```

Le [guide local et déploiement](../../docs/multicorpus-local-et-deploiement.md) fournit les commandes complètes, les sauvegardes, la restauration et le retour à H1.

## Base, sauvegarde et import réellement effectués

Identités vérifiées avant écriture : cluster local `7697259424657850634`, `cahier_doleances_local` OID 16385, `cahier_rag` OID 2106636. La destination de maintenance est le socket Unix `/var/run/postgresql`, sans destination de production ni URL implicite.

La [garde locale dédiée](../../documentary/local_application.py) autorise cette seule destination, vérifie la révision `rag_0007` et exige les empreintes de la sauvegarde avant les écritures. Les mutations non documentaires sont refusées. La garde historique `documentary.safety.Destination` reste inchangée : sa protection interdisant GDN/RAG dans un cluster documentaire isolé n’a pas été affaiblie.

Une sauvegarde adaptée à cette opération additive a été créée : schéma de recherche complet, données des états/statistiques GDN, inventaire des index et identités physiques, archive documentaire source complète. Les quelque 84 Go de données GDN n’ont pas été dupliqués. Cette sauvegarde ciblée ne serait pas suffisante pour une opération destructive GDN, qui reste interdite ici.

La migration existante **`doc_0001` a été appliquée dans `cahier_rag`**. Aucune nouvelle révision ni modification de migration historique n’a été nécessaire. Les six tables et leur version Alembic indépendante sont présentes : `corpus`, `release`, `document`, `search_unit`, `editorial_decision`, `lexical_term_statistics`. Aucune migration au démarrage du lecteur public.

Le [transfert contrôlé](../../documentary/integrate_local.py) a importé les sources/décisions et recopié les représentations après vérification des identifiants et empreintes. Un réimport a été exécuté, avec le même résultat documentaire et sans changement des contrôles GDN.

| Élément | Résultat réel |
|---|---:|
| Notices conservées au manifeste | 1 305 |
| Documents | 1 267 |
| Cahiers candidats | 1 224 |
| Autres documents conservés, hors périmètre candidat | 43 |
| Notices sans texte | 38 |
| Passages techniques | 11 391 |
| Passages des cahiers candidats | 10 750 |
| Passages admissibles après exclusions Artois | 10 748 |
| Embeddings réutilisés et vérifiés | 10 748 |
| Embeddings recalculés | **0** |

Tous les textes, identifiants, positions Unicode et empreintes documentaires correspondent aux artefacts immuables de `reference-documents-2-7cbcaea79991`. Aucune extraction, correction OCR ou reconstruction de passages.

## Adaptation nécessaire : locale PostgreSQL

Le laboratoire de phase 2 utilise `C`, l’application `fr_FR.UTF-8`. Un contrôle indépendant a détecté une différence réelle de `tsvector`, notamment sur les majuscules accentuées : `pg_catalog.french` dépend aussi de la locale de la base. Copier ces dérivés puis les déclarer identiques aurait été incorrect.

Les seuls dérivés lexicaux de 1789 ont donc été reconstruits dans la cible, sans changement de formule, de texte ni d’embedding : **86 341 lexèmes**, **1 770 363 DF cumulées**, population **10 748**. Le laboratoire `C` conserve 90 943 lexèmes / 1 788 101 DF. La locale cible est enregistrée dans `release.lexical_statistics.database_locale`. Aucun recalcul des statistiques GDN. Ce changement assure la cohérence de l’analyse lexicale dans la base commune ; il ne constitue pas une campagne d’optimisation des coefficients.

Les vecteurs BGE-M3 1 024 dimensions, leur recette, révision, normalisation et empreintes binaires restent identiques. Aucun HNSW documentaire n’est créé ; celui du GDN est conservé.

## Backend, recherche et instantanés

Le [runtime applicatif multicorpus](../../app/multicorpus_runtime.py) réutilise `MultiSearch`, les deux adaptateurs et l’encodeur H1 déjà chargé. Les garde-fous vérifient aussi la compatibilité du modèle/snapshot documentaire avec l’encodeur commun. Un verrou commun empêche l’encodage simultané avec H1. Les requêtes par question continuent de suivre leur voie lexicale H1 d’origine.

Le pipeline de phase 3 est conservé : IDF commune issue des statistiques existantes, maximum par réponse/cahier avant limite, classement vectoriel global, **une seule RRF60**, D=50 et sortie 50 documents. Aucun quota et aucun ajustement automatique du classement. Un filtre 2019 ne traite pas le corpus historique.

Les instantanés ne conservent que références, empreintes, témoins, rangs et identités de publication. Le cache LRU **est partagé avec H1**, conservant la borne totale de 16 Mio et la durée de dix minutes ; aucune copie de textes intégraux dans ce cache. Les curseurs authentifiés sont liés à la requête, au corpus choisi, à la taille de page et aux permissions public/aperçu. La pagination réhydrate les sources et vérifie leur génération sans relancer encodage, lexical, vectoriel ou RRF. Les lectures sont bornées et exécutées hors event loop ; un changement de source/génération ne provoque pas un reclassement silencieux.

Budget conservé : 18 s globales, encodage 3 s, SQL des deux branches/corpus ensemble 10 s, hydratation 2 s. Les annulations et la limite d’admission restent actives. Une indisponibilité ne produit pas un mélange partiel présenté comme complet.

| Route | Comportement |
|---|---|
| `GET /api/v1/search?corpus=tous|2019|1789` | Contrat principal enrichi ; union typée réponse/document, pagination conservée |
| `GET /api/v1/search?question_id=…` | Recherche lexicale H1 existante, sans vectoriel ni RRF |
| `GET /api/v1/corpora` | Disponibilité/publication/aperçu ; ne dévoile pas les documents non autorisés |
| `GET /api/v1/documentary/1789?page=…` | Catalogue documentaire paginé, indépendant du classement |
| `GET /api/v1/documentary/1789/{release}/documents/{id}?unit=…` | Lecture versionnée, tranches Unicode calculées côté serveur, précédent/suivant |

Les [modèles documentaires](../../app/schemas/documentary.py) restent distincts de `HybridAnswer`. Les cartes GDN conservent question, réponses libres, formulaire et lien exact vers la réponse dans sa contribution. Les cartes historiques portent le véritable identifiant de corpus `cahiers-1789-ap-stanford`, le document/release, le témoin et ses offsets, les références et avertissements. Les traces techniques de classement ne sont pas ajoutées aux cartes publiques.

## Frontend et design system

La recherche conserve sa page et ses composants GDN. Un filtre natif accessible propose tous les corpus, 2019, 1789 ; un corpus non disponible est désactivé. Le choix est porté par `corpus` dans l’URL, repris dans les liens de pagination et les formulaires de relance. Changer de corpus réinitialise le curseur ; modifier la requête conserve le filtre. Rechargement et historique arrière/avant ont été testés. La mémoire de pagination du navigateur distingue aussi périmètre et visibilité.

Les cartes historiques utilisent les styles de contribution existants, avec titre, provenance 1789, lieu/ordre explicites, extrait et accès au texte intégral. La référence est consultable discrètement ; aucun passage n’est présenté comme un article historique autonome.

Nouvelles pages :

- `/parcourir` : choix entre les deux modes de consultation.
- `/parcourir/1789` : catalogue paginé dans l’ordre `edition_order`, disponible sans faire de recherche.
- `/parcourir/1789/{release}/documents/{id}` : lecteur intégral, sources, métadonnées, titre source, avertissements et navigation documentaire.

Les anciennes URL `/enquetes`, `/forms/…`, `/questions/…` et `/forms/…/contributions/…` sont conservées. L’entrée de navigation et l’appel de l’accueil mènent désormais à « Parcourir ».

Le lecteur affiche le texte inchangé avec ses retours à la ligne. Le serveur fournit les blocs avant/passage/après ; **aucun offset Python n’est appliqué à un index UTF-16 JavaScript**. Le lien contient la release et l’identifiant du passage ; une version ou un passage inconnu produit 404, sans redirection vers un autre texte. Le passage est surligné et rejoint par son ancre stable.

Aucune refonte : tokens Panda, `PageContainer`, `Alert`, `CitizenText`, `DocumentNavigation`, `ListNavigation`, contrôles et styles existants. **Special Elite** pour titres/références/navigation, **Literata** pour les textes, police système pour les formulaires. Affichage 375/1 280 pixels, focus et parcours clavier vérifiés dans Chromium.

## Publication et sécurité

L’activation applicative dépend de `MULTICORPUS_CONFIG_FILE`, absent par défaut. L’aperçu des données non publiées exige la configuration locale explicite, `ENV=dev`, la base locale précise, un transport/requérant loopback et un jeton correct sans en-têtes de proxy. Le jeton est gardé par le SSR ; une requête publique ne le reçoit pas.

Sans cet aperçu : catalogue/lecteur historiques **404**, filtre historique indisponible, et `tous` ne renvoie que les corpus publiés. Les contrôles ont aussi rejeté un ancien curseur utilisé avec un autre corpus ou sans les permissions d’aperçu.

L’accès public futur exige une release autorisée et active en état `ready`, les permissions documentaires appropriées, des unités admissibles et des statistiques cohérentes avec le périmètre public. Ces protections ne sont jamais remplacées par `candidate=true`.

**État final inchangé :** release `verified`, `publication_authorized=false`, pointeur actif NULL, zéro document publiquement autorisé. Les 43 autres documents ne sont pas candidats. Artois 3/4 restent absents de la recherche mais lisibles dans le texte intégral ; Artois 1/2 et les huit passages d’Aunay restent admissibles. Le titre validé et les avertissements sont conservés. Les autres incertitudes restent traçables en base ; aucune certification historique nouvelle n’est inventée.

Le rôle lecteur n’a pas accès au journal `editorial_decision`. Les modèles de réponse ne sérialisent ni preuves privées, ni journaux de revue, ni lignes SQL complètes. Les données, modèles, archives et secrets locaux sont exclus du contexte Docker, hormis le petit fichier de décisions approuvées nécessaire au runtime.

## Validation et limites

- **83 tests backend réussis** : phases documentaires, multicorpus, sécurité phase 4, contrat H1 et packaging ; trois avertissements existants Starlette/httpx et IDs OpenAPI SEO dupliqués.
- **189 tests frontend réussis** ; TypeScript, lint Biome, export OpenAPI et types générés vérifiés ; build frontend hors réseau réussi.
- **21 contrôles API réels**, en lecture sur l’application : les trois sélections, pages distinctes et rejouables, liens versionnés, texte/empreinte, exclusions, Aunay, accès public refusé, document hors périmètre refusé, filtre par question H1.
- Smoke Chromium réel : catalogue, lecture, ancres, navigation, filtres/URL, rechargement, historique, pagination sans doublons, clavier, polices et responsive, sans erreur JavaScript.
- Réimport local vérifié. Archive complète restaurée dans un nouveau cluster privé `fr_FR.UTF-8` : 1 267 documents et 10 748 vecteurs vérifiés.
- Retour H1 réel testé sans activation multicorpus : recette `h1-public-v2-ts-rank`, 20 réponses dans la page et sept formulaires disponibles.

Les contrôles GDN comparent état/génération, statistiques et définitions/identités physiques des index à la sauvegarde. Les écritures de cette phase sont bornées au schéma documentaire. Il n’est pas prétendu qu’une nouvelle empreinte des millions de vecteurs GDN a été recalculée : aucun de ces vecteurs ou index n’a été écrit.

Les tests ne constituent pas une nouvelle validation générale de pertinence. Les limites de classement et le comportement des noms de lieux acceptés en phase 3 restent valables. Les mesures utiles d’intégration sont données ci-dessous ; elles ne remplacent pas un test de charge de production.

<!-- measured-results -->
### Mesures utiles de l’intégration

Une observation HTTP locale par ligne, requête « Gabelle » pour les recherches, modèle déjà chargé. Ces temps ne sont ni des percentiles ni un engagement de latence de production.

| Opération | HTTP ms | Statut |
|---|---:|---:|
| Nouvelle recherche 2019 seule | 212.1 | 200 |
| Nouvelle recherche 1789 seule | 366.4 | 200 |
| Nouvelle recherche commune | 515.7 | 200 |
| Page suivante commune, sans reclassement | 37.7 | 200 |
| Retour à la première page, sans reclassement | 33.6 | 200 |
| Catalogue, première page | 11.6 | 200 |
| Lecture intégrale du premier cahier | 5.4 | 200 |

Les traces détaillées restent sous `private/search/phase4/` (ignoré par Git), avec les contrôles d’intégrité, réimport, restauration et retour H1. Le packaging CPU a conservé la recette H1 et sa signature. Le jeton d’aperçu a été recherché dans les fichiers du build navigateur : aucune occurrence.


## Déploiement, retour arrière et décisions restantes

Le Dockerfile inclut les nouveaux paquets et la politique éditoriale ; `compose.multicorpus.yml` prépare un montage opt-in de configuration sans migration/import/publication automatique. Le packaging Python CPU a été vérifié, sans charger le modèle ni se connecter à une base pour ce contrôle. Les images Docker n’ont pas été construites ni déployées dans cette mission.

Le [guide opératoire](../../docs/multicorpus-local-et-deploiement.md) distingue migration, import/restauration, validation, préparation, autorisation et activation. La maintenance livrée autorise uniquement la cible locale exacte ; une cible de déploiement réelle doit être identifiée et sa garde revue avant une exécution autorisée. Une décision de promotion éditoriale explicite reste nécessaire, notamment pour les 1 224 candidats ; les 43 autres textes restent à qualifier séparément. Une publication partielle imposera une cohérence des DF avec le sous-ensemble effectivement recherché.

Le retour arrière consiste à arrêter l’application intégrée puis la relancer sans activation multicorpus. H1 et la navigation GDN restent opérationnels ; les données documentaires peuvent rester inactives, sans DROP ni migration inverse. Les curseurs de l’ancien processus expirent normalement.

**Ce qui fonctionne ici :** application locale complète, recherche commune, catalogue et lecteur sur les deux véritables bases locales. **Ce qui n’a pas été effectué :** déploiement de production, activation publique multicorpus, décision de publication des cahiers. Ces opérations demandent votre validation explicite ultérieure.
