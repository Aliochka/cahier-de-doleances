# Audit architectural — multicorpus et cahiers de 1789

Date : 3 novembre 2026. Périmètre : dépôt et collection locale indiquée dans la demande. Mission d’audit uniquement.

## Synthèse de la recommandation

Conserver les tables applicatives, les textes indexés et le HNSW du Grand Débat. Ajouter dans **la même base PostgreSQL de recherche** un stockage documentaire générique pour les nouveaux corpus, avec passages, positions et métadonnées propres. Pour 1789, commencer par une recherche vectorielle exacte sur les passages admissibles. Réunir les candidats des stockages dans **deux classements globaux, lexical et vectoriel, au niveau du document présenté**, puis appliquer une seule fusion RRF.

Cette proposition combine E (stockages distincts, fédération interne) et B (exact pour les petits périmètres), sans multiplier les bases, les services, les modèles ni les interfaces de recherche. Elle répond mieux aux contraintes réellement présentes qu’une insertion immédiate de 1789 dans `rag_full.documents`. Un HNSW pour les nouveaux corpus restera une évolution locale, conditionnée aux mesures.

La recommandation est un choix architectural provisoire à valider en environnement isolé. Les performances et la pertinence multicorpus n’ont pas été mesurées pendant cet audit.

## 1. Portée et niveau de preuve

**Vérifié** : lecture du code, des migrations, de la configuration de déploiement non secrète, de la table des matières du dump et des fichiers de la collection de référence. Un contrôle local, en mémoire, a parcouru les 11 391 passages : aucune divergence entre le texte du passage, sa tranche dans `full_text`, ses positions absolues/relatives et son SHA-256 ; 1 267 identifiants documentaires distincts. Ce contrôle ne certifie ni l’attribution historique ni les frontières documentaires.

**Non vérifié** : état courant des serveurs, index effectivement déployés, cardinalités SQL actuelles, RAM disponible, latences, paramètres PostgreSQL en production. Aucune connexion à une base, aucun import, aucune migration, aucun calcul d’embeddings ni benchmark de recherche n’ont été exécutés. Le chiffre d’environ 5,17 millions d’unités est celui fourni dans la demande ; il ne faut pas le confondre avec un nombre vérifié de vecteurs ou de réponses distinctes.

Les mentions « vérifié » ci-dessous signifient « présent dans les sources examinées », sauf précision. Les schémas issus des migrations décrivent le schéma attendu, pas une inspection du catalogue SQL déployé.

## 2. Diagnostic de l’existant

### 2.1 Deux bases et plusieurs couches documentaires

Le moteur public n’interroge pas simplement la table applicative `answers` avec un embedding ajouté. Il sépare une base source applicative et une base de recherche dédiée. `ReadGuard.transaction()` refuse une destination contenant les tables applicatives et impose des identités distinctes. `SearchBackend.verify_source()` vérifie aussi que l’hydratation publique correspond à la source indexée.

Références : [reader.py](../rag/src/cahier_rag/search/service/reader.py), classes `ReadGuard`, `SearchReader`, `ReadStore` ; [hybrid_runtime.py](../app/hybrid_runtime.py), `build_backend()`, `verify_source()`.

Dans la base applicative, [models.py](../app/models.py:44) décrit :

| Entité | Relations et contenu |
|---|---|
| `forms` | Questionnaire ; nom, version, source ; questions et contributions |
| `questions` | FK `form_id`, code, libellé, position, type, options JSON |
| `contributions` | FK formulaire et auteur ; titre, date, provenance, lot et JSON source |
| `answers` | FK contribution et question ; position, texte, valeur JSON |
| `options`, `answer_options` | Choix d’une question et choix associés à une réponse |
| Tables auxiliaires | Auteurs, thèmes et associations, statistiques, utilisateurs, marque-pages |

Une contribution contient plusieurs réponses. La réponse possède son propre identifiant : **le résultat 2019 doit rester la réponse, pas la contribution**. Le lecteur vérifie que le formulaire de la question et celui de la contribution concordent ; les deux FK ne suffisent pas seules à exprimer cet invariant.

### 2.2 Ce qui est réellement indexé en 2019

[gdn.py](../rag/src/cahier_rag/sources/gdn.py:56), `row_to_documents()`, produit :

- Une unité `open_answer` pour le texte non blanc d’une réponse à une question de type `text`.
- Zéro à plusieurs unités `other_text` provenant de la liste `value_json.other_text` des questions à choix simple ou multiple.
- Pas une unité pour chaque choix fermé ni pour chaque contribution complète.

Le contrat [TextUnit](../rag/src/cahier_rag/contracts.py) contient déjà `corpus_id`. Son `document_id` est un identifiant d’**unité textuelle**, construit avec corpus, type, `answer_id` et `unit_index`. Il ne désigne pas encore le document présenté au sens de la demande. Son empreinte couvre texte, contexte et provenance.

Une unité peut produire plusieurs segments vectoriels. [pipeline.py](../rag/src/cahier_rag/fullcorpus/pipeline.py), `prepare_unit()` et `prepare_metadata()`, ajoute **le contexte de la question** au texte encodé. L’intégration 1789 ne doit pas reprendre ce préfixe : sa recette doit encoder uniquement le passage source. Il faut enregistrer cette différence de recette sans recalculer les vecteurs 2019.

### 2.3 Stockage de recherche et index

La migration [rag_0004_fullcorpus.py](../rag/src/cahier_rag/migrations/versions/rag_0004_fullcorpus.py:13) définit :

| Structure | Rôle et contraintes |
|---|---|
| `rag_full.spaces` | Manifestes, compteurs, curseurs, empreintes et états de vérification ; espaces limités à `pilot100k` et `full` |
| `rag_full.documents` | Une unité `TextUnit` ; JSONB `record` contenant notamment le texte ; `tsvector search_vector` ; références 2019 obligatoires |
| `rag_full.segments` | Un vecteur par segment ; `vector(1024)`, positions, nombre de tokens, empreintes et représentation ; FK vers l’unité |
| `rag_tuning.statistics`, `term_statistics` | Nombre d’unités et fréquences documentaires des lexèmes ; liées à l’empreinte de la génération |

`documents` et `segments` sont **déjà partitionnées par LIST sur `space_id`**, avec partitions pilote et complète. Il ne s’agit pas d’un partitionnement par corpus. L’espace `full` a un manifeste explicitement `gdn-2019`.

Index attendus : PK et unicité des identifiants/ordinaux ; GIN lexical sur `search_vector` ; B-tree `(space_id, questionnaire_id, unit_type)` et `(space_id, contribution_id)` ; HNSW cosinus sur `segments_full`, `m=16`, `ef_construction=64`. Voir [rag_0005](../rag/src/cahier_rag/migrations/versions/rag_0005_fullcorpus_ann.py), [rag_0006](../rag/src/cahier_rag/migrations/versions/rag_0006_fullcorpus_ann_full.py). [index-question-search.sql](../deploy/postgres/index-question-search.sql) prévoit en supplément un index d’expression sur `record.question_id`, sans changement des embeddings.

La base applicative conserve d’autres mécanismes lexicaux : GIN de questionnaires/questions, trigrammes et configuration `fr_unaccent`, index de jointure/navigation. Leur histoire n’est pas identique à celle de H1 : [migration search infra](../migrations/versions/f839a0433a71_search_infra_extensions_fts_tsvector_.py), [configuration fr_unaccent](../migrations/versions/f9a8ff4a78dd_fix_question_search_tsv_fr_unaccent.py). H1 indexe le texte avec `pg_catalog.french` ; ne pas présumer que les traitements d’accents de la base applicative s’y appliquent.

### 2.4 Versions vérifiables

[deploy/postgres/Dockerfile](../deploy/postgres/Dockerfile) fixe une image PostgreSQL **17.11** avec pgvector **0.8.7**, par digest, avec assertions de construction. [cahier-search.toc](../search-transfer/cahier-search.toc:1) atteste un dump issu de PostgreSQL 17.11 le 21 octobre 2026, mais sa table des matières n’atteste pas à elle seule la version de l’extension. Le [rapport de déploiement](rapport-search-deploy-003.md) distingue déjà les vérifications dans le dépôt des déclarations opérateur. Conclusion : versions cibles documentées, versions actuellement exécutées à confirmer.

### 2.5 Parcours exact d’une recherche publique

[HybridSearch.retrieve()](../rag/src/cahier_rag/search/service/core.py:240) utilise la recette `h1-public-v2-ts-rank` :

1. Validation/NFC, requête de 512 caractères au maximum, puis encodage BGE-M3 persistant.
2. Branche lexicale H1, profondeur 50. Couverture IDF pondérée à 0,5, couverture des termes à 0,3, composante `ts_rank(...,32)` à 0,2. Les statistiques de lexèmes sont figées et vérifiées ; pas de préfiltrage lexical approximatif dans cette recette.
3. Branche vectorielle : `ef_search=1000`, 400 segments candidats initiaux, parcours `strict_order`, plafond de parcours 20 000 et multiplicateur mémoire 1. Sélection du meilleur segment par unité, puis au plus 50 unités. La boucle peut augmenter le nombre de candidats jusqu’à 50 000, sans transformer le HNSW en recherche exacte.
4. RRF non pondérée, `sum(1/(60+rang))`, rangs commençant à 1, départage par identifiant. Fusion sur les identifiants d’unités ; sortie limitée à 50 unités.
5. `group_hits()` regroupe ensuite par `answer_id`, dans l’ordre de la première unité rencontrée. Ce regroupement ne somme pas les scores des unités d’une réponse.
6. Hydratation à partir des réponses applicatives, avec contrôle des empreintes ; extrait limité à 1 000 caractères par carte. Le segment vectoriel gagnant existe dans `Hit`, mais n’est pas utilisé par la carte publique actuelle pour positionner cet extrait.

Références : [core.py](../rag/src/cahier_rag/search/service/core.py:27), [TunedSearch](../rag/src/cahier_rag/tuning/lexical.py), [WEIGHTS](../rag/src/cahier_rag/search/flexible.py), [ann_search()](../rag/src/cahier_rag/tuning/vector.py:54), [fuse()](../rag/src/cahier_rag/search/hybrid/core.py), [group_hits()](../app/services/search_snapshots.py:59), [public_card()](../app/services/search_hydration.py:22).

Les expressions entre guillemets et exclusions sont traitées dans la **branche lexicale** par [preparation.py](../rag/src/cahier_rag/search/preparation.py). Elles ne constituent pas aujourd’hui des contraintes communes aux deux branches : une correspondance vectorielle peut entrer dans la fusion sans les satisfaire. Les futurs critères documentaires obligatoires doivent, eux, définir l’ensemble admissible des deux branches.

Le mode public avec `question_id` est **lexical uniquement**, sans embeddings ni RRF : `retrieve_question()`. Le helper vectoriel possède séparément une recherche exacte pour les périmètres de question d’au plus 5 000 unités ; cette voie n’est pas le comportement public de la recherche par question. Son seuil ne doit pas être réutilisé sans mesure pour 1789 : le coût dépend des vecteurs, pas seulement des unités.

### 2.6 Pagination, services et publication

[calculate()](../app/routers/api_hybrid_search.py:104) fige les cartes après regroupement et hydratation. [SnapshotCache](../app/services/search_snapshots.py:89) conserve des références compactes, pendant 600 secondes, avec curseurs HMAC, taille de page et génération vérifiées. Pages de 20 éléments au maximum. La fenêtre est une sélection bornée, **pas un total exhaustif** ; 50 unités peuvent donner moins de 50 réponses distinctes. Les pages suivantes ne relancent pas la recherche. Une source disparue peut réduire une page sans reclassement.

Le modèle reste chargé ; [SearchWorker](../rag/src/cahier_rag/search/service/worker.py) utilise un seul thread de calcul et admet au plus trois travaux en attente/exécution. Le budget HTTP est de 18 secondes et couvre aussi hydratation et annulation. Préserver ces bornes ; une fédération séquentielle ajoute du temps à ce même budget.

[SearchReader.validate()](../rag/src/cahier_rag/search/service/reader.py) impose corpus GDN, recette, révision `rag_0007`, statistiques et index précis. [publication.py](../rag/src/cahier_rag/search/publication.py) et [search_packaging.py](../app/search_packaging.py) encadrent la publication et le transfert. Ajouter un corpus exige d’étendre ces validations explicitement, sans neutraliser les contrôles de la génération 2019.

### 2.7 Import et migrations

Deux chaînes Alembic : migrations applicatives à la racine et migrations de recherche sous `rag/`, avec `rag_alembic_version` distinct. [deployment_migrate.py](../app/deployment_migrate.py) borne la migration applicative à une révision attendue. [ingest/postgres.py](../ingest/postgres.py), `stage_record()`, `process_batch()`, `import_source()`, et [gdn_ingest.py](../ingest/gdn_ingest.py) sont liés aux questionnaires/mappings 2019.

La chaîne RAG procède par extraction, checkpoints transactionnels, encodage, vérification et indexation : [FullStore](../rag/src/cahier_rag/fullcorpus/store.py), [pipeline.py](../rag/src/cahier_rag/fullcorpus/pipeline.py), [run.py](../rag/src/cahier_rag/fullcorpus/run.py). Réutiliser les principes de reprise et d’intégrité ; ne pas lancer cette chaîne pour importer 1789. Attention : certaines méthodes nommées `verify`, dont `FullStore.verify()`, écrivent un état de validation ; elles ne sont pas des outils d’audit strictement en lecture seule.

## 3. Compatibilité avec le modèle documentaire

### 3.1 Correspondance conceptuelle

| Niveau | Grand Débat 2019 | Cahiers 1789 |
|---|---|---|
| Corpus | `gdn-2019` | `cahiers-1789-ap-stanford` dans les fichiers |
| Document affiché | Réponse `answer_id` | Cahier `id` |
| Unité de recherche | `TextUnit`, ouverte ou précision « autre » | Passage technique `id` |
| Représentation vectorielle | Un ou plusieurs segments contextualisés par la question | Un vecteur du passage seul, selon recette publiée |

Le modèle conceptuel comporte donc éventuellement une représentation vectorielle sous l’unité. Il n’impose pas trois nouvelles tables pour 2019. L’appellation SQL historique `documents` reste compatible via un adaptateur, sans renommer ni réécrire les millions de lignes.

**Incompatibilités directes** : les colonnes 2019 `NOT NULL`, le `CHECK` sur les types d’unités, les dataclasses et restaurateurs `TextUnit`, les espaces autorisés, les manifestes, le regroupement numérique `answer_id` et les schémas publics. Éviter les faux questionnaires, fausses questions et faux `answer_id` historiques. `space_id` désigne une génération/espace expérimental ; ne pas le transformer implicitement en `corpus_id`.

### 3.2 Contenu local 1789 vérifié

Le pointeur [current.json](../1789/data/documents/current.json) vise bien `reference-documents-2-7cbcaea79991`. Ses fichiers `documents`, `passages`, `metadata` et `inventory` sont présents localement.

- 1 305 notices ; 1 267 documents avec texte ; 38 notices sans texte.
- 1 224 cahiers probables avec texte, 10 750 passages.
- 43 autres textes : **19 documents associés, 6 procès-verbaux, 16 listes, 2 extraits**, soit les 641 autres passages selon le bilan.
- Passages de 55 à 800 tokens, médiane 598 ; recouvrements volontaires.

Sources : [summary.json](../1789/data/documents/reference-documents-2-7cbcaea79991/summary.json), [manifest.json](../1789/data/documents/reference-documents-2-7cbcaea79991/manifest.json) et comptage direct des documents. Le manifeste déclare expressément l’absence d’embeddings.

Les documents conservent `id`, `extent_id`, `text_sha256`, texte intégral, volume, provenance Stanford/Persée, positions absolues, blocs XML, annotations et statut des frontières. Les passages conservent `document_id`, `document_extent_id`, positions relatives et absolues, `ordinal`, liens précédent/suivant, empreintes, pages et références XML. Le statut est `mechanical_excerpt_not_historical_article` ; `historical_article_claim=false`. Ne pas les présenter comme des revendications individualisées.

Les offsets sont des intervalles **[début, fin) en points de code Unicode**, dans le texte XML décodé, sans normalisation des espaces. Ne pas les appliquer directement à une chaîne JavaScript indexée en UTF-16. Le serveur peut produire les fragments et ancres ; toute mise en forme doit conserver une correspondance vers le texte canonique. Les liens `local_context_url` pointent vers l’outil local de revue, pas vers des routes publiques déjà disponibles.

### 3.3 Métadonnées et admissibilité éditoriale

`metadata.jsonl.gz` contient titre, `historical_orders`, origine littérale, contexte territorial, champs lexicaux et métadonnées originales : citation, pages, URLs, `catalogue_order`, `local_order`, type documentaire et données d’attribution. Les ordres sont déduits des titres lorsqu’ils sont explicites ; les lieux ne sont pas géocodés. La date d’édition n’est pas la date historique. Référence : [prepare_documents.py](../1789/extraction/prepare_documents.py:43), `metadata()`.

Il n’existe pas dans ces champs un verdict général de publiabilité. Le bilan signale 251 documents aux frontières suspectes ou non résolues ; une certification de frontières ne certifie pas la nature revendicative du contenu. Les documents peuvent aussi contenir des notes éditoriales identifiées dans `annotations`/`xml_blocks`.

**Recommandation** : conserver les 43 textes dans la collection, mais les exclure initialement de la recherche publique et du catalogue publié tant qu’une décision explicite n’existe pas. Revue document par document à partir du texte, de sa place dans l’édition, du titre, des types Persée et des annotations. Enregistrer séparément : nature (`revendicatif`, `mixte`, `éditorial/documentaire`, `indéterminé`), éligibilité au catalogue, à la consultation et à la recherche, justification, responsable et version. Un procès-verbal peut contenir des revendications ; une liste n’est pas automatiquement éditoriale. Aucun type seul ne tranche.

La même politique doit préciser le traitement des cahiers probables aux frontières suspectes et des notes éditoriales incluses dans leurs passages. Ne pas modifier silencieusement les textes ou offsets pour retirer une note : une variante de texte indexable exigerait une recette et une correspondance de positions explicites.

## 4. Comparaison des stratégies vectorielles

### 4.1 Filtrage réel et disproportion des corpus

Avec HNSW, un prédicat SQL placé avant `LIMIT` est nécessaire mais n’est pas synonyme de préfiltrage du graphe : pgvector parcourt l’index puis PostgreSQL élimine les lignes non admissibles. Un B-tree sur le corpus peut servir à sélectionner un petit ensemble pour une recherche exacte ; il ne crée pas une intersection ordonnée « B-tree ∩ HNSW » garantissant le meilleur voisin filtré. La jointure actuelle avec `documents` ne change pas ce principe. Voir la [documentation pgvector 0.8.7, Filtering](https://github.com/pgvector/pgvector/blob/v0.8.7/README.md#filtering).

Les parcours itératifs peuvent prolonger l’exploration, mais restent bornés par mémoire, nombre approximatif de tuples visités et budget SQL. `strict_order` ordonne les résultats émis sans certifier un rappel exact. Dans le code 0.8.7, des candidats plus proches que la dernière distance émise sont écartés en mode strict ; atteindre les bornes limite la poursuite de l’exploration. Augmenter le `LIMIT` ne lève pas ces contraintes. Référence primaire : [hnswscan.c](https://github.com/pgvector/pgvector/blob/v0.8.7/src/hnswscan.c), `hnswgettuple()`, `ResumeScanItems()`.

**Illustration, pas prédiction** : 11 391 / (5 170 000 + 11 391) ≈ 0,22 %. À distribution indépendante, 1 000 éléments examinés représenteraient seulement environ 2,2 passages historiques ; obtenir 50 correspondances demanderait un ordre de grandeur de 23 000 éléments. `ef_search` n’est pas un nombre de résultats ni un nombre exact de visites. Les corpus occupent des voisinages sémantiques non uniformes, et le nombre réel de segments 2019 reste à relever. Ces chiffres illustrent pourquoi on ne peut pas garantir le filtrage 1789 avec les seuls réglages actuels.

Un corpus minoritaire peut aussi être pertinent globalement : il ne faut ni lui réserver des places ni le rendre introuvable par insuffisance du rappel. Le déséquilibre des tailles est une contrainte de génération des candidats, pas une justification de quotas.

### 4.2 Tableau de décision

| Option | Avantages | Limites et coûts dans ce projet | Avis |
|---|---|---|---|
| **A — HNSW commun + B-tree corpus** | Stockage logique uniforme ; un parcours global ; insertions possibles sans reconstruire nécessairement le graphe | Filtrage minoritaire fragile ; contraintes et contrats GDN à assouplir ; index corpus sur les millions de lignes si nécessaire ; publication/statistiques à faire évoluer | Ne pas retenir seule |
| **B — Commun global, exact petit périmètre** | Bons voisins filtrés pour petits ensembles ; plan adaptatif simple ; HNSW global conservé | Même coût de généralisation du stockage si réalisé dans `rag_full` ; seuil à mesurer en vecteurs/IO ; historique global encore soumis au rappel ANN | Bonne stratégie de routage, indépendamment du stockage |
| **C — HNSW partiels/spécialisés** | Recherche isolée efficace pour corpus importants ; pas de déplacement obligatoire des anciens vecteurs | Index supplémentaire, espace et maintenance ; global commun + spécialisés dupliquent des graphes ; un index partiel ne peut pas dépendre d’une jointure vers le corpus ; prédicat disponible dans la table vectorielle requis | Option ultérieure, inutile a priori pour 11 000 vecteurs |
| **D — Partitionnement par corpus** | Élagage des partitions ; stratégies exact/HNSW locales ; retrait et ajout de corpus structurés | Partitionnement existant par espace à respecter ; conversion de `full` non triviale, clés/FK à étudier ; pas de graphe global unique ; recherche globale visite les partitions et fusionne | Cible possible pour futurs stockages, pas migration initiale du GDN |
| **E — Stockages distincts et recherche fédérée** | Préserve tables, HNSW et empreintes GDN ; contrats propres ; exact historique ; retrait facile | Adaptateur, fusion globale et statistiques comparables nécessaires ; risques de rangs locaux trompeurs ; coût global additionnel par stockage | **Recommandée dans la même base et le même service** |

Les index partiels exigent que le planificateur puisse déduire leur prédicat ; tester les requêtes préparées, notamment les plans génériques et les filtres multi-valeurs. Voir [PostgreSQL 17 — Partial Indexes](https://www.postgresql.org/docs/17/indexes-partial.html). Le partitionnement donne des index locaux et un élagage dépendant des prédicats, pas un HNSW commun magique ; voir [PostgreSQL 17 — Table Partitioning](https://www.postgresql.org/docs/17/ddl-partitioning.html).

Une autre possibilité serait un stockage vectoriel générique commun aux nouveaux corpus, avec un HNSW spécialisé GDN conservé : c’est précisément l’évolution proposée de E, plutôt qu’une table/un service par futur corpus. Changer vers IVFFlat, une base vectorielle externe, une quantification ou un nouveau modèle n’est pas justifié par le volume historique actuel.

### 4.3 Coût de l’exact historique

11 391 × 1 024 = environ **11,66 millions de coordonnées** par balayage complet. Le contenu vectoriel brut float32 représente environ **44,5 Mio**, hors lignes, TOAST, index, cache et textes. Ce volume rend l’exact crédible ; il ne démontre aucune latence particulière. Mesurer CPU, accès TOAST, lectures à froid, cache, tri et contention. Un filtre documentaire réduit encore le nombre de distances si les passages admissibles sont sélectionnés en amont.

Le plan exact doit matérialiser/sélectionner le périmètre relationnel puis calculer toutes ses distances, sans utiliser par accident le HNSW global. Ne pas désactiver globalement les index relationnels : on souhaite les utiliser pour sélectionner les documents et leurs passages. Le helper `exact-question` existant fournit un précédent de plan, pas une API générique immédiatement réutilisable.

## 5. Architecture recommandée et classement

### 5.1 Stockage additif et identités

Proposer, sans DDL à ce stade :

- Un registre léger des corpus, initialement configurable et versionné ; une table n’est nécessaire que si sa gestion dynamique le justifie.
- Une table générique des documents des **nouveaux** corpus : identité, corpus, texte intégral/version, titre, ordre documentaire, provenance, état de publication et métadonnées JSONB.
- Une table générique des unités/passages : identité stable existante, FK document, ordinal, offsets, empreintes, recette, texte indexable ou tranche référencée, vecteur et index lexical. Index relationnels par corpus/document/ordre ; petit index lexical documentaire pour les métadonnées.

Ces structures vivraient dans un schéma dédié de la base de recherche. Le texte intégral importé est une matérialisation de l’artefact de référence, avec empreinte et version, utilisable aussi pour la consultation via un lecteur borné. Les sources locales restent archivées ; la disponibilité du texte public ne doit pas dépendre du lancement de l’outil de revue. Ne pas copier les réponses 2019 dans cette table. L’adaptateur 2019 dérive le document présenté de `answer_id` et ses unités des tables existantes.

Ne stocker le texte des passages en plus du texte intégral que si cela simplifie utilement l’indexation/lecture ; les offsets permettent de l’extraire. Un `tsvector` et un embedding sont déjà des représentations dérivées, pas une raison de recopier toute la structure source.

Identité commune de résultat : `(corpus_id, document_key)` ; conserver les IDs historiques et les IDs `TextUnit` sans changement. Distinguer identité documentaire stable, version d’étendue et version de contenu. Les IDs de passage dépendent notamment des bornes et des empreintes de préparation : stables pour une version donnée, pas promesse d’immuabilité après correction de texte. Prévoir résolution des anciens liens via une correspondance documentée, sans assimiler des étendues simplement chevauchantes.

JSONB contient les métadonnées propres ; les champs communs de filtrage, publication, identité, version et ordre restent typés. Ajouter des colonnes/index spécialisés seulement lorsqu’un usage le justifie. Aucun code postal fictif pour 1789.

### 5.2 Ensemble admissible avant recherche

La requête explicite : corpus sélectionnés, critères documentaires obligatoires, texte recherché. Sélection absente = tous les corpus publiés ; plusieurs corpus = union des périmètres. Canonicaliser et valider la liste de corpus ; un corpus inconnu ne doit pas élargir silencieusement la recherche.

La publication et les filtres doivent s’appliquer aux deux branches **avant leurs top-K**. Pour 1789, sélectionner les documents admissibles puis leurs passages. Pour une recherche combinée « clergé d’Agen » + sujet, les premiers critères peuvent être documentaires et le sujet textuel. Une simple boîte libre ne permet pas de deviner infailliblement ces rôles : prévoir des filtres explicites ou une syntaxe documentée, sans extraction implicite opaque.

Titres, lieux et ordres sont cherchables lexicalement, séparément du texte encodé. Conserver la provenance et éviter d’indexer sans distinction tous les ancêtres bibliographiques, identiques sur des centaines de cahiers. Un titre apparié sans passage textuel pertinent doit pouvoir produire un résultat documentaire avec un extrait d’ouverture clairement choisi comme tel.

### 5.3 Deux listes globales, puis une RRF documentaire

**Ne pas appliquer une RRF aux premiers rangs locaux de chaque corpus.** Le premier de chaque petit corpus recevrait artificiellement le même poids que le premier de tout 2019. Ne pas non plus fusionner des scores hybrides indépendants par corpus.

Procédure recommandée :

1. Encoder la requête une seule fois avec le modèle existant. Chaque adaptateur produit des candidats lexicaux et vectoriels admissibles avec scores, identité documentaire et passage/unité témoin.
2. Pour la branche vectorielle, score documentaire = meilleure similarité cosinus de ses passages/segments/unités. Regrouper par réponse pour 2019, par cahier pour 1789. Réunir les candidats des stockages et les trier ensemble par distance et clé stable ; attribuer alors les rangs vectoriels globaux.
3. Pour la branche lexicale, calculer une formule commune de pertinence, agréger au document par meilleur score de passage/unité avec signal documentaire maîtrisé, puis réunir et classer globalement. Métadonnées indexées une fois par cahier ; éviter qu’elles multiplient les voix avec le nombre de passages.
4. Appliquer la RRF à ces **deux listes de documents**, une contribution par branche et document. Ne pas sommer les scores de tous les passages d’un long cahier. Un cahier peut avoir son meilleur témoin lexical différent de son meilleur témoin vectoriel : c’est acceptable et doit être traçable.
5. Choisir le passage présenté parmi les témoins, selon une règle déterministe évaluée : préférence pour un passage soutenu par les deux branches, sinon meilleur témoin de la branche contributrice. Conserver passage, offsets et version dans l’instantané. Le score du document ne doit pas varier avec un choix cosmétique d’extrait.

Pour un top-K global fondé sur un score commun, récupérer au moins K **documents distincts** par stockage suffit à constituer son union de candidats, si chaque top-K local est exact et les départages identiques. Ce sont des profondeurs techniques, pas des places réservées à l’affichage. Avec ANN, ce raisonnement reste conditionné au rappel local. La limite actuelle sur 50 unités GDN avant regroupement n’offre pas cette garantie : déplacer le regroupement par réponse dans la génération de chaque branche et sur-échantillonner jusqu’à une profondeur documentaire bornée. Au-delà du plafond, signaler la sélection bornée ; ne pas promettre une exhaustivité.

Le regroupement par meilleur passage favorise moins les longs documents qu’une somme, mais ils gardent davantage d’occasions d’obtenir une forte similarité. Mesurer ce biais et le nombre de documents distincts récupérés. Les doublons documentaires historiques connus ne doivent pas être fusionnés automatiquement sur simple ressemblance textuelle ; les passages chevauchants d’un même document, eux, ne créent jamais plusieurs résultats.

### 5.4 Comparabilité lexicale et sémantique : point de validation majeur

RRF élimine le besoin de comparer directement un score lexical et une distance. Elle n’élimine pas le besoin de comparer les **scores d’une même branche entre stockages** avant d’établir ses rangs globaux.

Le GDN utilise un IDF global figé à l’échelle des `TextUnit`. Recalculer un IDF uniquement sur 1789 puis mélanger les scores bruts serait incohérent. Proposition initiale : conserver les fréquences GDN existantes et les compléter, hors ligne lors d’une future préparation autorisée, par les fréquences des nouvelles unités ; total et fréquences combinés dans une génération multicorpus versionnée. Cela évite un nouveau balayage intégral GDN pour chaque ajout. Il faut définir précisément l’unité statistique et le traitement des champs de métadonnées ; mélanger un nombre de cahiers avec des fréquences par passage serait erroné.

Deux variantes à départager : statistiques communes d’unités puis maximum documentaire, proches de H1 ; ou statistiques au niveau des documents affichés, plus homogènes conceptuellement mais exigeant un calcul initial des fréquences distinctes par réponse 2019. Ne pas annoncer ce second calcul gratuit. Une composante métadonnées avec sa propre normalisation doit être calibrée et versionnée ; conserver les statistiques et la recette H1 pour les parcours 2019 existants jusqu’à validation.

Les distances cosinus sont comparables numériquement si modèle, révision, normalisation et dimension concordent. Leur qualité peut néanmoins différer : questions ajoutées aux réponses 2019, passages longs sans préfixe en 1789, lexique ancien, OCR, orthographe, notes éditoriales et décalage sémantique historique. Mesurer les distributions et juger des requêtes historiques et transversales ; un même score ne garantit pas une même pertinence humaine. Ne pas réencoder 2019 pour uniformiser les préfixes avant d’avoir démontré un problème.

### 5.5 Pagination, publication et disponibilité

Conserver les instantanés bornés. Figer la liste **après regroupement documentaire et fusion**, avant découpage en pages ; pas de dédoublonnage isolé sur chaque page. Ajouter au hash de requête les corpus triés, critères documentaires, mode et paramètres de classement ; une modification de filtre invalide le curseur.

La génération multicorpus référence les versions et empreintes de toutes les collections participantes, les recettes d’embedding et les statistiques. Une nouvelle publication invalide les instantanés concernés. Généraliser `UnitReference`, `CardReference` et l’hydratation avec un type discriminant ; conserver la vérification d’intégrité et l’accès uniquement aux champs publics. Les identifiants opaques historiques ne passent pas par le type numérique `PublicId`.

Une indisponibilité d’un corpus ne doit pas être dissimulée dans une recherche annoncée « tous corpus » : choisir entre erreur globale et réponse partielle explicitement signalée. La vérification GDN reste inchangée dans son adaptateur ; la publication historique vérifie manifeste, autorisations éditoriales, modèle, offsets et disponibilité du texte. Étendre aussi les contrôles de rôle SQL aux nouveaux schémas et les droits de transfert/publication : les listes de schémas actuelles sont explicites.

## 6. Frontend et navigation documentaire

[routes.ts](../frontend/app/routes.ts) expose `/recherche`, `/enquetes`, formulaires, questions et contributions. [surveys.tsx](../frontend/app/routes/surveys.tsx) charge actuellement `listForms()` et affiche `SurveyCatalogue` : une enquête est donc aujourd’hui un questionnaire, pas un corpus. Les routes `form`, `question`, `form-contributions` et `contribution` composent la consultation 2019 ; les services `forms`, `questions`, `answers`, `contributions` et leurs routeurs API portent ces données.

Recommandations sans refonte graphique :

- Remplacer l’entrée principale par **Parcourir**, avec accueil par corpus. Dans 2019, conserver le catalogue des formulaires et les routes existantes ; ce corpus peut contenir plusieurs questionnaires. Choisir une URL canonique `/parcourir` et rediriger `/enquetes`, plutôt que casser les liens publics.
- Ajouter un catalogue 1789 et une page de texte intégral utilisant les composants de mise en page existants. Trier par une clé gelée de l’édition : proposition `(volume, source_start, source_end, id)`, après contrôle des chevauchements et confrontation avec `catalogue_order`/`local_order`. Cet ordre représente la séquence de la collection éditée, pas une chronologie historique certifiée.
- Calculer précédent/suivant sur le même ensemble publié et le même ordre, indépendamment de la recherche courante. Pagination du catalogue par clé d’ordre stable ; ne pas réutiliser les dates de contributions 2019. [contribution_neighbors()](../app/services/contributions.py:49) fournit le principe de navigation, pas ses critères historiques.
- Réutiliser [DocumentNavigation](../frontend/app/components/layout/document-navigation.tsx), `PageContainer`, les états vide/erreur et `ListNavigation`. Réutiliser prudemment `CitizenText` pour afficher du texte sûr ; prévoir sauts/notes et ancres propres aux sources historiques. Le lecteur local de revue peut inspirer le découpage par offsets, sans embarquer ses journaux privés ni ses commandes de validation.
- Ajouter une ancre stable liée au passage et à sa version. Produire le focus et le défilement vers l’extrait ; conserver le texte intégral et la citation/source, pages et scan. Distinguer transcriptions, métadonnées éditoriales et incertitudes. Une page longue peut être découpée en blocs rendus, avec correspondance exacte au texte canonique.
- Étendre [search-url.ts](../frontend/app/features/search/search-url.ts), le loader SSR et [search-results.tsx](../frontend/app/features/search/search-results.tsx) : sélection des corpus persistée dans l’URL, défaut tous, suppression du curseur au changement, badge/source corpus et cartes typées. Les clés React et la fusion progressive doivent utiliser l’identité documentaire commune, pas `answer_id` seul.
- Généraliser les libellés « réponses citoyennes », « enquête », le lien de lecture et le compteur `answer_count` pour la recherche commune ; conserver les informations question/formulaire sur les cartes GDN. [hybrid_search.py](../app/schemas/hybrid_search.py) et les types API frontend exigent une évolution coordonnée, avec génération du contrat OpenAPI et tests de compatibilité.

La navigation géographique reste hors périmètre. Préserver des métadonnées territoriales extensibles sans géocodage imposé.

## 7. Coûts, risques et réversibilité

| Adaptation future | Coût/risque principal | Réduction du risque |
|---|---|---|
| Stockage historique additif | Faible volume relatif ; nouveaux textes, vecteurs et index ; permissions à étendre | Même base dédiée, schéma générique pour plusieurs corpus ; aucun backfill GDN |
| Orchestration et contrat documentaire | Coût de développement modéré ; changement de niveau de classement | Adaptateurs, identité explicite, traces de classement et comparaison H1 |
| Fusion globale lexicale | Calibration/statistiques ; régressions de pertinence possibles | Recette versionnée, fréquences GDN conservées, évaluation humaine |
| Exact historique sur toute recherche globale | IO/CPU supplémentaires et latence de file | Mesures cache froid/chaud et concurrence ; HNSW local seulement si nécessaire |
| Déduplication avant RRF | Ordre 2019 potentiellement différent de H1 | Mode H1 de référence conservé, jugement documentaire des écarts |
| Publication et corpus mixtes | Mise en ligne de textes mal classés ; sources partielles | Décisions éditoriales explicites et manifests de publication |
| Consultation avec offsets | Mauvais extrait après normalisation/UTF-16 ou correction source | Texte canonique, hash, version, ancres et tests Unicode |
| Sources locales ignorées | Clone Git insuffisant, restauration incomplète | Archive vérifiée des fichiers, manifestes, provenance et correspondances |

Les tables génériques ne réclament ni copie massive de 2019 ni reconstruction de son HNSW. Le coût principal initial est logiciel et documentaire, pas vectoriel. Ajouter un HNSW commun ultérieurement ou généraliser davantage les tables reste possible via les mêmes contrats, après preuve d’utilité.

Le retour arrière le plus sûr est de désactiver l’activation multicorpus, restaurer la publication/API précédente et conserver le stockage additif inactif. Ne pas supposer qu’un `downgrade` destructeur est le bon mécanisme de rollback. Les éventuels index partiels sur les tables GDN ou changements de contraintes feraient monter le coût opérationnel ; ils ne sont pas nécessaires à la première proposition.

Les fichiers de référence, sources et journaux ne sont pas tous versionnés : [LOCAL_DATA.md](../1789/docs/LOCAL_DATA.md), [manifest.json](../1789/data/documents/reference-documents-2-7cbcaea79991/manifest.json), [cahier1789_paths.py](../1789/cahier1789_paths.py). Préparer une archive restaurable et vérifier les empreintes ; ne pas traiter un chemin historique dans un manifeste comme un chemin à réécrire.

## 8. Plan de validation avant toute migration

Les opérations suivantes sont **proposées**, non exécutées. Les essais nécessitant restauration, import de test, embeddings ou construction d’index demandent une phase d’implémentation/expérimentation distincte autorisée. Pas d’`EXPLAIN ANALYZE` lourd en production pendant l’audit.

1. **État réel et inventaire.** En lecture seule sur un environnement identifié : versions serveur/extension, révisions Alembic, DDL et validité des index, nombres de réponses/unités/segments, tailles tables/index, paramètres HNSW, RAM et espace disque. Vérifier la présence du B-tree de question. Distinguer configuration prévue et installation effective.
2. **Restauration isolée.** Restaurer un exemplaire représentatif de la recherche GDN et une source applicative compatible, avec rôles séparés. Vérifier qu’aucune URL ne pointe vers la production et que les gardes restent actifs. Une petite maquette valide les contrats ; elle ne suffit pas à comparer le rappel filtré dans cinq millions de vecteurs.
3. **Intégrité 1789.** Refaire empreintes, liens passage/document/version, bornes, Unicode, ordre et voisinage, chevauchements, correspondances des deux réparations. Confirmer périmètre publié et exclusion des textes non arbitrés. Le contrôle local réalisé dans cet audit est un premier point de comparaison.
4. **Référence de pertinence.** Constituer des requêtes jugées : 2019, historique avec vocabulaire ancien/moderne, titres/lieux/ordres, sujet transversal, critères mixtes, expressions/exclusions, zéro résultat, filtres très sélectifs et multi-corpus. Juger au niveau réponse/cahier et au niveau du passage témoin.
5. **Comparaison vectorielle A–E.** Sur les mêmes vecteurs historiques, comparer exact de référence, HNSW commun, exact filtré, HNSW local/partiel et partitions ou fédération. Mesurer recall@10/50 des documents et passages, résultats manquants, visites, candidats avant/après filtre, répétitions par document, temps SQL et buffers. Varier `ef_search`, bornes itératives, mémoire et profondeur ; relever les plans effectifs, y compris avec jointure et requêtes préparées.
6. **Coût global.** Cache froid/chaud, p50/p95/p99, débit, CPU, RAM, IO/TOAST, attente du worker et temps d’encodage séparés. Mesurer recherche globale, 2019 seul, 1789 seul, plusieurs corpus et métadonnées très restrictives. Comparer explicitement le surcoût global de l’exact historique au H1 de référence.
7. **Classement hybride.** Comparer H1 actuel, regroupement après fusion, regroupement par branche avant RRF ; statistiques communes d’unités versus documentaires. Mesurer nDCG@10, précision, rappel, nombre de documents distincts, qualité de l’extrait et biais de longueur/corpus. Observer la composition des résultats sans imposer de quota ni considérer la seule proportion historique comme une métrique de qualité.
8. **Pagination et UI.** Aucun doublon entre pages, rangs stables, retour/précédent/rechargement et « afficher plus », invalidation après changement de corpus/critères/génération, expiration du curseur, source absente, liens directs et Unicode non BMP. Tester catalogue, précédent/suivant, exclusions éditoriales et routes 2019 conservées.
9. **Restauration et retour arrière.** Répéter publication, désactivation et restauration ; comparer comptes et empreintes GDN avant/après. Vérifier qu’aucun test ne reconstruit son index et qu’un nouveau corpus n’altère pas ses identifiants ou vecteurs.

Les suites existantes `tests/test_hybrid_search.py`, `tests/test_hybrid_search_integration.py`, `tests/test_search_packaging.py`, les tests de service sous `rag/tests/`, les tests `search`/`consultation` frontend et les e2e constituent des points de départ. Elles n’ont pas été exécutées ici : elles ne mesurent pas à elles seules la pertinence multicorpus ni le coût de l’exact historique.

Critères de décision à convenir **avant** l’expérience : budget acceptable de latence et de débit global, rappel minimal filtré face à l’exact, tolérance aux changements de rang GDN, qualité des extraits et procédure éditoriale. Sans ces seuils, un benchmark peut décrire les compromis mais ne tranche pas le choix produit.

## 9. Arbitrages humains encore nécessaires

1. Valider le stockage additif générique dans la base de recherche et l’exact historique initial, plutôt qu’une généralisation immédiate des tables GDN.
2. Définir qui autorise la publication des 43 autres textes, des cahiers aux frontières suspectes et des documents mixtes ; distinguer catalogue, lecture et recherche.
3. Fixer la place des notes éditoriales et la présentation des incertitudes et sources.
4. Accepter ou différer le passage à une RRF au niveau du document, et la modification possible des rangs 2019 en recherche commune.
5. Choisir après mesures l’unité des statistiques lexicales, le poids des métadonnées et la règle du passage affiché.
6. Valider les critères documentaires explicites et la sémantique des expressions/exclusions sur les deux branches.
7. Valider l’ordre de parcours de l’édition, le traitement des recouvrements documentaires, les URLs publiques et la compatibilité des anciens liens.
8. Fixer les objectifs de performance/rappel et le comportement en cas de corpus indisponible : erreur ou résultats partiels signalés.
9. Confirmer le maintien d’une fenêtre de résultats bornée, son éventuelle augmentation et le périmètre de l’expérimentation isolée à autoriser ultérieurement.

## 10. Composants à conserver et à faire évoluer

**À conserver** : tables source GDN, identifiants, unités et embeddings existants, HNSW complet, encodeur BGE-M3 persistant, protection lecture seule, budgets/annulation, principes RRF et instantanés, routes documentaires 2019, composants de mise en page/navigation.

**À adapter** : orchestration des candidats et regroupement documentaire, contrat interne commun en complément de `TextUnit`, API de résultats typée, empreinte de requête/curseurs, hydratation historique, validation des publications et rôles des nouveaux schémas, champs et statistiques lexicaux, filtre corpus, accueil « Parcourir ».

**À ajouter dans une phase ultérieure autorisée** : stockage générique des nouveaux corpus, préparation/import historique idempotent fondé sur les artefacts existants, décisions éditoriales versionnées, catalogue et lecteur intégral 1789, protocole d’évaluation multicorpus. Aucun de ces changements n’est implémenté par le présent audit.
