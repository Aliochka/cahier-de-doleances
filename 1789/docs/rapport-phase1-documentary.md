# Phase 1 documentaire — rapport de réalisation

Date : 7 novembre 2026. **Import réellement exécuté et vérifié dans une base PostgreSQL locale neuve et isolée.** Aucun déploiement, aucune publication ni phase de recherche historique n’a été exécuté.

## Architecture et fichiers

La [conception mise à jour](conception-technique-multicorpus-1789.md) distingue définitivement les corpus documentaires (`Corpus → Document → Passage`) des corpus de questionnaires, qui continueront à réutiliser le modèle métier GDN après une étude distincte. Le moteur principal commun, les adaptateurs et la RRF globale restent des objectifs des phases suivantes ; aucun modèle métier universel n’a été ajouté.

| Livrable | Fichier |
|---|---|
| Migration indépendante `doc_0001` | [Migration](../../documentary/migrations/versions/doc_0001.py), [DDL exécuté](../../documentary/migrations/versions/doc_0001.sql), [environnement Alembic](../../documentary/migrations/env.py) |
| Garde physique local | [safety.py](../../documentary/safety.py) |
| Lecture et validation des artefacts | [artifacts.py](../../documentary/artifacts.py) |
| Rejeu éditorial | [editorial.py](../../documentary/editorial.py) |
| Import atomique, idempotence et contrôle SQL | [storage.py](../../documentary/storage.py) |
| Commandes explicites | [CLI](../../documentary/__main__.py), [mode d’emploi](../../documentary/README.md) |
| Politique éditoriale versionnable | [decisions.json](../editorial/decisions.json), exception `.gitignore` limitée à ce fichier |
| Tests | [test_documentary.py](../../tests/test_documentary.py) |

Le rapport architectural antérieur existait déjà comme fichier non suivi par Git au début de cette mission ; il n’a pas été modifié ici. Aucun commit n’a été créé.

## Destination effectivement utilisée

- Nouveau cluster privé : `/tmp/documentary-phase1-45FiOt/data`.
- Socket Unix : `/tmp/documentary-phase1-45FiOt/socket`, port de socket `55487` ; **aucune écoute TCP**.
- Identifiant système attendu et vérifié : `7705356223649726476`.
- Rôle local : `documentary_admin` ; base : **`documentary_1789_test`**.
- PostgreSQL interrogé : **17.11** ; extension `vector` interrogée : **0.8.7**.

Avant chaque transaction SQL, le garde compare le nom réel de base, le répertoire physique, l’identifiant système et l’absence d’adresse TCP. Il refuse toute destination contenant les tables métier ou les schémas/version RAG. Aucun DSN applicatif, fichier `.env` ou paramètre de production n’a été utilisé pour ces opérations.

Les données du cluster restent sur disque ; le serveur de démonstration est attaché à une session locale. Si cette session est terminée, redémarrer localement sans `initdb` (uniquement après vérification que le serveur n’est plus actif) :

```sh
/usr/lib/postgresql/17/bin/postgres -D /tmp/documentary-phase1-45FiOt/data -k /tmp/documentary-phase1-45FiOt/socket -p 55487 -c listen_addresses=''
```

Laisser cette commande dans une session dédiée, puis, depuis la racine du dépôt :

```sh
.venv/bin/python -m documentary verify --url 'postgresql+psycopg2://documentary_admin@/documentary_1789_test?host=/tmp/documentary-phase1-45FiOt/socket&port=55487' --expected-data-directory /tmp/documentary-phase1-45FiOt/data --expected-system-id 7705356223649726476
```

Le même garde est requis pour `migrate`, `import` et `apply-editorial`. Il est impossible de sélectionner implicitement une autre base en omettant les arguments.

## Schéma réellement créé

Les six tables métier prévues sont présentes :

| Table | État/rôle vérifié |
|---|---|
| `documentary.corpus` | Un corpus ; pointeur actif NULL |
| `documentary.release` | Une release `reference-documents-2-7cbcaea79991`, état `verified` |
| `documentary.document` | 1 267 textes intégraux, notices, sources, ordre et projections ; 1 224 candidats et 43 non-candidats |
| `documentary.search_unit` | 11 391 unités, sans copie de leur texte ; offsets, empreintes, rattachements et permission individuelle |
| `documentary.editorial_decision` | 13 événements à empreintes précises, source externe conservée |
| `documentary.lexical_term_statistics` | Table prête pour phase 2, **zéro ligne** |

S’y ajoute uniquement la table technique **`documentary.alembic_version`**, révision `doc_0001`. Les PK, FK, unicités document/ordre et document/ordinal, contrôles d’offset/hash et index GIN/B-tree prévus ont été créés. Les GIN portent des colonnes NULL : aucune représentation lexicale n’a été calculée. Aucun HNSW nouveau n’est construit.

Les contraintes croisées de texte/positions sont contrôlées par l’import puis par le vérificateur intégral, pas par un CHECK SQL qui lirait le parent. La commande de vérification ouvre une transaction `READ ONLY` et ne change aucun statut. L’import ne change le statut en `verified` qu’à l’intérieur de sa transaction contrôlée, avant commit.

Les métadonnées originales des documents sont conservées en JSONB, y compris annotations, statuts de frontières, blocs XML, composantes et provenance. Le manifeste SQL de release conserve les **1 305 notices**, ainsi que les métadonnées des **38 notices sans texte** : elles ne deviennent pas de faux documents extraits.

## Bilan réel de l’import

| Contrôle | Résultat |
|---|---:|
| Notices conservées | **1 305** |
| Documents importés | **1 267** |
| Cahiers autonomes probables candidats | **1 224** |
| Autres documents conservés, non candidats | **43** |
| Passages techniques importés | **11 391** |
| Passages des cahiers probables | **10 750** |
| Unités individuellement exclues | **2** |
| Unités individuellement permises, tous textes | **11 389** |
| Unités permises des seuls cahiers candidats | **10 748** |
| Documents accessibles publiquement | **0** |
| Représentations lexicales/vectorielles calculées | **0** |

Le vérificateur a comparé toutes les lignes et métadonnées attendues aux artefacts. Les hash des textes complets sont vérifiés en Python ; chacune des **11 391 tranches PostgreSQL** a été comparée au texte du passage source. Aucun doublon, perte, divergence de texte, de rattachement ou de projection n’a été détecté.

Empreinte SHA-256 du manifeste source figé :

`eb9f4533e95df62a8964fbd6a71d56c0446b7769f6fa9d80fcdd8c0111e08ff2`

Empreinte canonique de la politique éditoriale :

`2b2b4c14e33ed5b7908a7e0304a980143c803c088af5dd8234690a81a8314cba`

La commande `import` a été réexécutée sur la base finale : **`imported=false`**, même contenu et mêmes décisions, aucun doublon ni réactivation. Une troisième commande `verify`, sans écriture, a confirmé le bilan.

## Décisions et publication

La révision `1789-editorial-1` comporte :

- Deux exclusions Artois : `ap1789-technical-passage-1:fffb19e46c6025e22b17d54c370c` et `ap1789-technical-passage-1:32ae8c839247d77b503fba421372` ; unités 1 et 2 non exclues.
- Un avertissement Artois sur la zone relative `[5204,8878)` ; aucun caractère source supprimé.
- Le titre de présentation validé d’Aunay-la-Côte/Avallon ; titre source conservé séparément.
- Un avertissement sur le début manquant du premier article dans Stanford.
- Huit permissions individuelles explicites pour les passages d’Aunay-la-Côte.

Aucune autre exclusion n’a été créée. Les cinq autres dossiers conservent leurs incertitudes dans les métadonnées source. Les décisions sont liées aux hash de document, à l’étendue et, le cas échéant, au hash d’unité. Leur provenance est l’autorisation utilisateur de phase 1, pas une certification historique nouvelle.

Les booléens des documents `catalogue_visible`, `readable`, `searchable` sont **tous false**, pour les 1 224 candidats comme pour les 43 autres textes. Le booléen d’unité est une permission individuelle pour les phases futures, pas un droit de publication. Aucune recherche nouvelle n’est implémentée ; l’application de ces exclusions aux deux branches fera partie des invariants de phase 2.

Release : `state=verified`, `representations_ready=false`, `statistics_ready=false`, `publication_authorized=false`, `active_release_id=NULL`. Les recettes effectives de recherche restent vides. Une tentative de passage direct à `ready` ou d’activation publique a été rejetée par les contraintes SQL dans les tests.

Le rejeu explicite permet de réintégrer puis réexclure une unité sans modifier le texte ni effacer l’historique. Ces essais ont été réalisés **uniquement avec des événements synthétiques dans le cluster temporaire de tests**, jamais dans le fichier approuvé ou dans la base finale de démonstration. Un ancien fichier, une décision modifiée ou une mauvaise empreinte provoque un refus et un rollback.

## Tests exécutés et restauration

Commande exécutée :

```sh
DOCUMENTARY_TEST_PG_BIN=/usr/lib/postgresql/17/bin .venv/bin/pytest tests/test_documentary.py tests/test_hybrid_search.py tests/test_search_packaging.py -q
```

Résultat : **60 tests réussis**, dont **21 tests documentaires** et 39 tests existants de recherche/packaging. Les tests documentaires PostgreSQL créent leur propre cluster neuf et deux bases vides ; ils migrent et importent intégralement les artefacts, vérifient l’idempotence, la reconstruction, les erreurs d’intégrité, le rejeu et les refus de destination. Les tests purement éditoriaux couvrent aussi les propriétés invalides, les empreintes, les successions explicites et les retours aux titres/avertissements précédents.

Trois avertissements des dépendances/tests existants ont été observés : dépréciation Starlette/httpx et deux identifiants OpenAPI SEO dupliqués. Aucun de ces composants n’a été modifié pour cette mission.

`ruff check documentary tests/test_documentary.py` : **conforme**. Les liens locaux des nouveaux documents sont contrôlés avant livraison.

Une sauvegarde PostgreSQL **locale et ignorée par Git** a été créée : `1789/data/private/documentary/phase1.dump` (environ 16 Mio). Elle a été restaurée avec `pg_restore --exit-on-error` dans la nouvelle base **`documentary_restore_test`** du cluster privé. Le vérificateur intégral y retrouve le même bilan, la même politique et les mêmes empreintes. La reconstruction depuis artefacts et la restauration depuis dump ont donc toutes deux été exercées.

## Limites et écarts assumés

1. **Destination locale exclusivement** : le garde refuse aussi les bases de recherche contenant GDN. C’est une restriction intentionnelle pour cette mission. Le déploiement futur du schéma dans la base partagée nécessite un garde de déploiement adapté et une autorisation distincte ; aucune concession n’a été faite aux vérifications de production.
2. **Importeur 1789 spécialisé, stockage générique** : l’importeur fixe la génération, son manifeste et les volumes attendus. Il ne prétend pas importer arbitrairement tous les corpus documentaires ; les futurs adaptateurs d’import pourront réutiliser le schéma.
3. **Pas de phase 2 anticipée** : aucune recette, statistique ou représentation calculée. Une réintégration éditoriale ne peut pas rendre la release prête par elle-même.
4. **Publication absente** : la propriété éditoriale `publication` ne peut actuellement qu’enregistrer un refus explicite ; toute autorisation positive est rejetée dans ce CLI de phase 1. Les 1 224 candidats ne sont pas publiés.
5. **Stockage local temporaire** : le cluster sous `/tmp` peut être supprimé par le système. La sauvegarde privée et les artefacts source doivent être conservés hors de `/tmp` pour une restauration durable ; le dump fourni est local, pas versionné.
6. **Retour arrière non destructeur** : aucun downgrade qui effacerait les données. Stockage inactif, reconstruction dans une autre base locale ou restauration privée sont les mécanismes retenus.

## Production et Grand Débat

Aucune connexion de maintenance vers la production n’a été ouverte. La base cible neuve ne contenait aucune table GDN ni schéma RAG. Aucun fichier sous `app/`, `frontend/`, les migrations applicatives ou `rag/` n’a été modifié ; aucune recette H1, donnée GDN, représentation vectorielle existante ou index `rag_full` n’a été changé. Les tests de compatibilité utilisent les outils de test existants, sans activation du nouveau stockage dans le moteur public.

La collection `reference-documents-2-7cbcaea79991`, son pointeur et les transcriptions Stanford ont été utilisés en lecture seule. La validation finale des empreintes est conforme. **La phase 1 est réalisée localement ; la recherche historique et la publication restent à autoriser séparément.**
