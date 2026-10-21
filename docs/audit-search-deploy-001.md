# SEARCH-DEPLOY-001 — Audit du déploiement de la recherche hybride publique

**Date : 21 octobre 2026. Collecte strictement en lecture seule.**

Le dépôt, les configurations locales, les artefacts d’évaluation et les catalogues
des deux bases PostgreSQL locales ont été inspectés. Les connexions SQL ont imposé
la lecture seule, un délai de connexion de 3 secondes et un `statement_timeout`
de 3 secondes.

Pendant la collecte : **aucun fichier modifié, aucun modèle chargé, aucun benchmark
exécuté, aucun transfert et aucune connexion à Wallace**. L’état matériel et logiciel
de Wallace décrit ci-dessous provient du contexte fourni, sans vérification distante.
Le présent rapport a ensuite été enregistré à la demande de l’utilisateur ; aucune
implémentation n’a été engagée.

Les mentions suivantes distinguent les niveaux de preuve :

- **Vérifié** : constat dans le code, les fichiers locaux ou PostgreSQL.
- **Historique** : mesure enregistrée dans une évaluation existante, non réexécutée.
- **Estimation** : enveloppe de préparation, à mesurer.
- **À vérifier** : information manquante, notamment sur Wallace.

## 1. Résumé exécutif

**Le déploiement paraît réalisable sur Wallace, mais une simple activation de
`HYBRID_SEARCH_ENABLED` ne suffit pas.**

Le moteur public existe déjà et respecte le périmètre demandé : recherche lexicale
pondérée, BGE-M3 dense, HNSW et fusion RRF, sans génération ni reranking neuronal.
Les embeddings documentaires sont réutilisables.

Les principaux obstacles sont les suivants :

| Point | Conclusion |
|---|---|
| Stratégie publique | **H1 est effectivement retenue et implémentée.** BM25 ne fait pas partie du service public actuel. |
| Stockage | La base spécialisée occupe **77,91 Gio**, dont **36,04 Gio pour le HNSW principal**. Le SSD annoncé semble suffisant, sous réserve du stockage temporaire et du WAL. |
| BGE-M3 sur CPU | Supporté par le code et déjà mesuré sur CPU local. Les performances du Xeon restent inconnues. |
| Portabilité des données | **Bloquant :** le manifeste vérifie l’identité physique de la base applicative locale. Une restauration sur Wallace échouerait à ce contrôle sans adaptation contrôlée. |
| Deux workers Gunicorn | **Bloquant :** modèles et instantanés de pagination sont propres à chaque processus. La pagination peut retourner 410 en changeant de worker. |
| Image backend actuelle | Elle n’installe pas l’extra d’encodage et ne contient ni modèle ni configuration du lecteur. |
| Objectif P95 < 2 s | **Non démontré.** Le lexical seul avait un P95 local historique de **5,15 s**, sur une machine plus puissante. |
| Qualité ANN | Le profil retenu est un compromis documenté ; il n’a pas satisfait les seuils de qualification existants. |
| Filtres publics | **Absents du contrat actuel** : les paramètres de filtre sont explicitement refusés. |

La voie initiale la plus simple serait de conserver les deux bases dans une instance
PostgreSQL 17 compatible avec pgvector, et de démarrer avec **un seul processus
FastAPI possédant un seul modèle et un seul cache de curseurs**. L’opportunité d’un
service de recherche séparé doit ensuite être décidée à partir des mesures d’impact
sur le site.

## 2. Architecture constatée

### 2.1. Parcours réel

Le chemin d’exécution public est :

1. Formulaire GET sur `/recherche`, rendu par React SSR.
2. Appel à `GET /api/v1/search`.
3. Validation et admission dans une file bornée.
4. Encodage de la requête avec BGE-M3.
5. Recherche lexicale puis vectorielle dans la base spécialisée.
6. Fusion RRF et sélection des premiers documents.
7. Regroupement des documents par réponse historique.
8. Hydratation depuis la base applicative.
9. Conservation temporaire des références pour la pagination.

Les résultats présentent les réponses originales, leur question et leurs liens
documentaires. Le contenu JSONB de la base spécialisée n’est pas directement exposé
au navigateur.

**Sources :** [hybrid_runtime.py](../app/hybrid_runtime.py),
[api_hybrid_search.py](../app/routers/api_hybrid_search.py),
[search_hydration.py](../app/services/search_hydration.py).

### 2.2. Indépendance du RAG

**Vérifié :** le service réutilisable n’appelle ni générateur, ni Qwen, ni reranker.
Le nom du paquet `cahier_rag` ne signifie pas que la recherche publique dépend du
pipeline génératif.

Le moteur utilise uniquement :

- les contrats documentaires ;
- l’encodeur BGE-M3 ;
- les lecteurs PostgreSQL ;
- le lexical optimisé ;
- HNSW ;
- RRF.

Aucun GPU n’est nécessaire pour RRF. L’encodage CPU est explicitement supporté.

**Sources :** [service/__init__.py](../rag/src/cahier_rag/search/service/__init__.py),
[service/core.py](../rag/src/cahier_rag/search/service/core.py).

## 3. Stratégie effectivement retenue

### 3.1. Recette publique

La recette versionnée est **`h1-public-v1`**.

| Paramètre | Valeur constatée |
|---|---|
| Branche lexicale | Lexical pondéré optimisé RAG-027 |
| Statistiques lexicales | Fréquences documentaires exactes, précalculées |
| Préfiltrage approximatif | Désactivé |
| Poids du score lexical | Couverture IDF 0,5 ; couverture des termes 0,3 ; fréquence/proximité 0,2 |
| Branche vectorielle | BGE-M3 dense, 1 024 dimensions, cosinus |
| Profondeur par branche | 50 documents |
| HNSW | `ef_search=1000` |
| Segments candidats initiaux | 400 |
| Parcours itératif | `strict_order` |
| Plafond de parcours | 20 000 tuples |
| Fusion | RRF non pondérée, `k=60`, rangs à partir de 1 |
| Sortie initiale | 50 documents au maximum, puis regroupement par réponse |

Les 400 candidats initiaux ne constituent pas une limite absolue : le lecteur peut
augmenter ce nombre, sous budget, jusqu’à 50 000.

La représentation vectorielle documentaire inclut **question et réponse**, avec des
segments de **1 024 tokens** et un recouvrement de **128 tokens**. Le lexical porte
sur le texte de l’unité.

**Sources :** [service/core.py](../rag/src/cahier_rag/search/service/core.py),
[tuning/lexical.py](../rag/src/cahier_rag/tuning/lexical.py),
[tuning/vector.py](../rag/src/cahier_rag/tuning/vector.py),
[vector/preparation.py](../rag/src/cahier_rag/vector/preparation.py).

### 3.2. Ce que montrent les évaluations H1–H4

RAG-019 compare les variantes sur un corpus expérimental de **20 000 unités**, avec
**17 requêtes entièrement jugées par les deux juges historiques**. Il ne s’agit pas
d’une évaluation humaine exhaustive ni d’une mesure sur les 5,17 millions d’unités.

Extrait des résultats à profondeur 10 :

| Variante | Precision@10, juge 8B / 14B | nDCG poolée@10, juge 8B / 14B |
|---|---:|---:|
| H1 | 0,935 / 0,894 | **0,634 / 0,720** |
| H2 | 0,912 / 0,865 | 0,572 / 0,652 |
| H3 | 0,935 / 0,865 | 0,576 / 0,648 |
| H4 | 0,906 / 0,853 | 0,577 / 0,652 |

H1 présente ici la meilleure nDCG@10 des quatre variantes pour les deux
référentiels. D’autres configurations obtiennent de meilleurs résultats sur certains
autres indicateurs : cela ne démontre pas une supériorité universelle de H1.

**La décision d’intégration est néanmoins explicite** dans SEARCH-002, puis appliquée
dans SEARCH-003/004 : H1, lexical optimisé et ANN ef1000.

**Sources :** [rapport comparatif RAG-019](../rag/evaluation/local/rag019/comparison/report.md),
[architecture SEARCH-002](architecture-search-002.md).

### 3.3. Limite de qualification ANN

Le fichier `rag027/selection.json` indique **`qualified: false`**. Son empreinte et
celles des trois fichiers de preuve référencés ont été vérifiées pendant cet audit.

RAG-027 rapporte, pour ef1000 :

- recouvrement moyen des IDs : **91,9 % au top 10**, **91,8 % au top 50** ;
- médiane/P95 vectoriels historiques : **23,5 / 59,4 ms** ;
- aucun profil testé ne satisfait les seuils de qualification figés.

Il faut donc distinguer **profil sélectionné pour l’interactivité** et **qualité ANN
pleinement qualifiée**.

**Sources :** [rapport RAG-027](../rag/rapport-rag-027.md),
[sélection enregistrée](../rag/evaluation/local/rag027/selection.json).

## 4. Inventaire PostgreSQL et données à transférer

### 4.1. Base spécialisée locale

**Mesures actuelles, vérifiées par SQL :**

| Élément | Valeur |
|---|---|
| Base | `cahier_rag` |
| PostgreSQL | **17.11** |
| Extensions | `plpgsql` 1.0 ; **`vector` 0.8.7** |
| Révision spécialisée | **`rag_0007`** |
| Taille totale | **83 649 935 027 octets — 77,91 Gio** |
| Encodage | UTF8 |
| Collation / ctype | `fr_FR.UTF-8` |

Aucune extension BM25 n’est installée dans cette base.

### 4.2. Documents, segments et embeddings

L’espace public `full` déclare :

| Compteur persistant | Valeur |
|---|---:|
| Unités textuelles attendues et extraites | **5 172 356** |
| Unités dont l’encodage est terminé | **5 172 356** |
| Segments / embeddings | **5 187 190** |
| Lexèmes dans les statistiques lexicales | **314 656** |
| Extraction complète | `true` |
| Vecteurs complets | `true` |
| État vérifié | `true` |

Ces valeurs ont été lues dans les états persistants et concordent avec les artefacts
de fin de construction. **Aucun nouveau `COUNT(*)` intégral des grandes tables n’a
été lancé.** Les estimations `pg_class.reltuples` ne doivent pas remplacer ces
compteurs : certaines sont déjà différentes.

Les vecteurs sont stockés en **`vector(1024)`**, avec des coordonnées float32 et une
normalisation L2. Un échantillon SQL confirme 1 024 dimensions et une norme proche
de 1.

Les 5,17 millions de documents sont des **unités textuelles**, pas des contributions
distinctes :

- une réponse ouverte produit une unité ;
- une réponse à choix peut produire plusieurs unités « Autre » ;
- une unité longue peut produire plusieurs segments vectoriels ;
- les identifiants des réponses, questions, contributions et formulaires sont conservés.

**Sources :** tables `rag_full.spaces`, `rag_tuning.statistics`,
[migration du corpus complet](../rag/src/cahier_rag/migrations/versions/rag_0004_fullcorpus.py),
[sources/gdn.py](../rag/src/cahier_rag/sources/gdn.py).

### 4.3. Tables et index importants

Les tailles totales ci-dessous **incluent les index** : ne pas les additionner une
seconde fois.

| Table ou ensemble | Taille totale mesurée |
|---|---:|
| `rag_full.segments_full` | **65,70 Gio** |
| `rag_full.documents_full` | **10,38 Gio** |
| `rag_full.segments_pilot100k` | 1,30 Gio |
| `rag_full.documents_pilot100k` | 0,21 Gio |
| `rag.vector_representations` | 155,2 Mo |
| `rag.text_units` | 59,2 Mo |
| `rag.lexical_vectors` | 52,6 Mo |
| `rag_tuning.term_statistics` | 36,1 Mo |
| `rag.extraction_documents` | 17,9 Mo |
| `rag.lexical_members` | 7,4 Mo |

Les petites tables auxiliaires comprennent `rag_full.spaces`,
`rag_tuning.statistics`, `rag.extractions`, `rag.vector_spaces`,
`rag.lexical_corpora`, `rag.checkpoints` et `public.rag_alembic_version`.

| Index principal | Taille mesurée |
|---|---:|
| `segments_full_hnsw` | **36,04 Gio** |
| Unicité des représentations des segments | 739 Mio |
| Clé primaire des segments | 659 Mio |
| Clé primaire des documents | 654 Mio |
| GIN des `search_vector` documentaires | **378 Mio** |
| Unicité des ordinaux documentaires | 156 Mio |
| Index des contributions | 60 Mio |
| Index formulaire/type d’unité | 44 Mio |

Tous les index inspectés sont marqués valides et prêts. Le HNSW principal utilise
**cosinus, `m=16`, `ef_construction=64`**.

### 4.4. Où se trouve BM25 ?

**Vérifié : BM25 est un index inversé SQLite expérimental**, et non une structure
PostgreSQL du service public.

| Fichier | Taille | Documents |
|---|---:|---:|
| `rag018/bm25-A.sqlite3` | 87,7 Mo | 20 000 |
| `rag018/bm25-B.sqlite3` | 122,3 Mo | 20 000 |

Les statistiques SQLite indiquent 17 612 documents de développement et 2 388
d’évaluation. Les tables sont `documents`, `postings`, `stats`, `df` et `state`.

La recette BM25 est figée à `k1=1.2`, `b=0.75`. A indexe la réponse seule ; B ajoute
la question.

**Conséquence :** ces deux fichiers ne constituent pas un BM25 prêt pour le corpus
public complet. Leur déploiement n’est pas nécessaire pour H1.

**Source :** [bm25/index.py](../rag/src/cahier_rag/search/bm25/index.py).

### 4.5. Classement des données et choix de copie

| Catégorie | Contenu |
|---|---|
| **A — Indispensable à H1** | Espace `full`, documents et `record` JSONB, `tsvector`, segments et embeddings, HNSW/GIN/index relationnels, statistiques lexicales, manifeste, version spécialisée |
| **B — Expérimental** | Espace `pilot100k`, tables historiques `rag.*`, fichiers SQLite BM25, campagnes, jugements et sorties d’essais |
| **C — Reconstructible** | Index PostgreSQL et statistiques lexicales ; instantanés de pagination en mémoire. Leur reconstruction peut rester coûteuse. |

Le sous-ensemble principal représente environ **76,12 Gio**, contre **77,91 Gio**
pour toute la base : le gain potentiel d’un allègement est d’environ **1,8 Gio,
soit 2,3 %**.

**Recommandation : première copie intégrale de la base spécialisée.** Elle réduit
le risque d’omettre des dépendances, partitions ou métadonnées. Ne transférer, parmi
les fichiers de modèles, que le snapshot BGE-M3 requis. Les modèles génératifs,
rerankers et artefacts d’évaluation restent locaux.

## 5. BGE-M3 : dépendances et faisabilité CPU

### 5.1. Modèle constaté

| Élément | Valeur |
|---|---|
| Modèle | `BAAI/bge-m3` |
| Révision | `5617a9f61b028005a4858fdac845db406aefb181` |
| Emplacement | `rag/models/bge-m3/<révision>/` |
| Poids | `pytorch_model.bin`, **2 271 145 830 octets** |
| Architecture | XLM-RoBERTa, environ 568 millions de paramètres |
| Représentation utilisée | Dense, CLS, 1 024 dimensions, normalisation L2 |
| Limite de tokens | 8 192 |
| Inférence CPU actuelle | float32, SDPA, `torch.inference_mode()` |

Le manifeste du snapshot est cohérent et tous ses fichiers déclarés sont présents.
**Les 2,27 Go de poids n’ont pas été relus pour recalculer leur SHA-256 pendant cet
audit.**

L’implémentation charge uniquement des fichiers locaux, interdit le code distant
et désactive le réseau Hugging Face.

**Sources :** [registre des modèles](../rag/src/cahier_rag/embeddings/registry.py),
[backend Transformers](../rag/src/cahier_rag/embeddings/transformers_backend.py).

### 5.2. Dépendances

Les versions existantes comprennent :

- Python 3.11 ;
- PyTorch 2.10.0 ;
- Transformers 4.57.6 ;
- huggingface-hub 0.36.0 ;
- NumPy 2.2.6 ;
- psutil 7.2.2.

**L’image backend actuelle n’installe pas l’extra `search`.** De plus, le verrou
de cet extra sélectionne actuellement la distribution PyTorch CUDA 12.8 sur Linux
x86_64.

Il faut préparer et valider un assemblage **CPU reproductible**, en conservant le
modèle et le runtime PyTorch existants. Ajouter simplement `--extra search`
importerait actuellement des dépendances CUDA inutiles à Wallace.

**Sources :** [pyproject.toml](../pyproject.toml),
[Dockerfile backend](../Dockerfile),
[documentation PyTorch des installations CPU](https://pytorch.org/get-started/additional-platforms/).

### 5.3. Mesures CPU déjà disponibles

RAG-012 a réellement mesuré BGE-M3 sur le **Ryzen 9 7950X local**, en float32,
quatre threads, batch 1 :

| Indicateur historique | Valeur |
|---|---:|
| Chargement | 3,96 s |
| Encodage P50 | **62,56 ms** |
| Encodage P95 | **68,41 ms** |
| RSS maximal, chargement inclus | **2 916 Mio — 2,85 Gio** |

Limite importante : seulement **8 requêtes synthétiques, deux passages**, donc
16 observations. Ces chiffres ne prédisent pas Wallace.

Le Xeon E-2134 possède bien quatre cœurs, huit threads et AVX2. Une exécution
float32 est techniquement plausible ; il faut mesurer les performances réelles de
la roue CPU et du matériel.
[Spécifications Intel](https://www.intel.com/content/www/us/en/products/sku/134858/intel-xeon-e2134-processor-8m-cache-up-to-4-50-ghz/specifications.html).

**Source des mesures :** [manifeste CPU BGE-M3](../rag/evaluation/local/rag012/cpu-bge-m3/manifest.json).

### 5.4. Optimisations compatibles

Déjà présentes :

- chargement unique et réutilisation du modèle ;
- une seule inférence active par processus ;
- absence de gradients ;
- batch de requête égal à 1 ;
- aucun recalcul pendant la pagination.

À préparer :

- exposer explicitement le nombre de threads CPU : le constructeur accepte
  `threads`, mais `build_backend()` utilise actuellement le défaut **4** ;
- comparer 1, 2 et 4 threads, en tenant compte des cœurs utilisés par PostgreSQL ;
- monter le snapshot en lecture seule ;
- mesurer le pic de chargement, pas seulement le régime stable.

Il n’existe pas actuellement de cache distinct des embeddings de requêtes. Ce n’est
pas une condition préalable : mesurer d’abord l’intérêt d’un cache borné.

Le passage GPU/bfloat16 → CPU/float32 reste dans le même espace vectoriel, mais les
vecteurs ne sont pas identiques bit à bit. Les huit comparaisons historiques BGE-M3
avaient un cosinus minimal de **0,999887** ; les classements devront être contrôlés.

**Aucune quantification, conversion ONNX ou substitution de modèle n’est justifiée
à ce stade.** Remplacer l’encodeur de requêtes par E5 serait incompatible avec les
embeddings BGE-M3 existants.

## 6. Intégration FastAPI et React SSR

### 6.1. Connexions et droits

Trois pools supplémentaires sont créés par la recherche :

| Pool | Destination | Taille maximale |
|---|---|---:|
| Contrôles source | Base applicative, rôle lecteur | 2 |
| Recherche | Base spécialisée, rôle lecteur | 2 |
| Hydratation | Base applicative, identifiants applicatifs actuels | 2 |

Ils utilisent `max_overflow=0`, une attente de pool de 1 seconde et des transactions
READ ONLY.

Le rôle local `cahier_search_reader` a été testé sur les deux bases :

- lecture des tables requises autorisée ;
- écriture sur documents et segments refusée ;
- création de schéma/base refusée ;
- accès ciblé à `pg_control_system()` autorisé ;
- limite de **4 connexions**.

Cette limite doit être réévaluée si plusieurs processus sont conservés.

**Attention :** le `statement_timeout=1s` de session est une protection initiale.
Le lecteur public ajuste ensuite le délai SQL au budget restant ; ce n’est donc pas
une limite effective d’une seconde pour toute recherche.

**Sources :** [service/reader.py](../rag/src/cahier_rag/search/service/reader.py),
[provisionnement local du lecteur](../rag/sql/search-reader.sql).

### 6.2. Blocage de portabilité du manifeste

Le manifeste contient l’identité source :

- identifiant du cluster ;
- OID de la base ;
- nom `cahier_doleances_local` ;
- révision du schéma.

Le lecteur compare ces champs à la source réelle. La compatibilité ajoutée pour
`forms_statistics_v1` autorise uniquement cette évolution de révision : elle
**n’autorise pas le changement de cluster, d’OID ou de nom**.

**Une restauration fidèle de `cahier_rag` sur Wallace serait donc refusée telle
quelle.**

Il faut préparer une procédure contrôlée de publication sur la nouvelle source :

1. conserver la provenance et les empreintes d’origine ;
2. établir la correspondance des données applicatives de Wallace avec le corpus indexé ;
3. associer explicitement la copie à l’identité cible ;
4. recalculer les empreintes de métadonnées concernées ;
5. invalider les générations de curseurs correspondantes ;
6. tester les refus de sources incompatibles.

Il ne faut pas neutraliser le garde ni remplacer simplement le nom de base sans
contrôle des données. Cette adaptation ne nécessite pas de recalculer les embeddings.

**Sources :** [service/reader.py](../rag/src/cahier_rag/search/service/reader.py),
[safety.py](../rag/src/cahier_rag/safety.py),
[fullcorpus/store.py](../rag/src/cahier_rag/fullcorpus/store.py).

### 6.3. Initialisation, isolation et délais

Le chargement se déroule en arrière-plan. Un échec laisse les routes documentaires
accessibles et la recherche en 503.

Les limites existantes sont :

| Étape | Limite |
|---|---:|
| Travaux de classement admis | 1 actif + 2 en attente |
| Admission | 1 s |
| Encodage | 3 s |
| Lexical et vectoriel réunis | 10 s |
| Hydratation | 2 s |
| Budget API global | 18 s |
| Timeout frontend | 20 s |

L’inférence s’exécute hors de l’event loop. Une annulation ne tue toutefois pas un
thread PyTorch : le travail conserve sa place jusqu’à sa fin. Les instructions SQL
peuvent être annulées par le moniteur psycopg2.

`/healthz` teste uniquement la base applicative. Il peut légitimement répondre 200
alors que la recherche est indisponible. Une vérification opérationnelle spécifique
de l’état du moteur sera nécessaire, sans rendre tout le site dépendant du
chargement de BGE-M3.

**Sources :** [service/worker.py](../rag/src/cahier_rag/search/service/worker.py),
[service/control.py](../rag/src/cahier_rag/search/service/control.py),
[api_hybrid_search.py](../app/routers/api_hybrid_search.py),
[health.py](../app/routers/health.py).

### 6.4. Deux workers : incompatibilité fonctionnelle

Chaque worker Gunicorn crée son propre modèle et son propre cache LRU :

- TTL absolu : 600 secondes ;
- capacité : 256 instantanés ;
- charge utile maximale : 16 Mio, hors overhead Python.

Une clé HMAC commune ne partage pas ces instantanés. Un curseur créé par un worker
peut donc être inconnu du suivant. Cela peut affecter **la redirection initiale SSR
vers `first_cursor`**, avant même de cliquer sur « page suivante ».

**Il faut résoudre ce point avant toute ouverture publique.**

**Sources :** [search_snapshots.py](../app/services/search_snapshots.py),
[Dockerfile](../Dockerfile), [contrat de recherche](api-search.md).

### 6.5. Frontend et configuration

Le frontend dispose déjà du parcours nécessaire :

- `/recherche` ;
- formulaire GET et rendu sans JavaScript ;
- pagination par curseurs ;
- états de chargement, expiration et indisponibilité ;
- liens vers `/forms/{id}/contributions/{id}#answer-{id}` ;
- sérialisation des BIGINT en chaînes.

La correction DEPLOY-002 couvre les GET internes de `/api/v1/search`. Aucun
changement frontend n’apparaît nécessaire pour activer **H1 non filtrée**.

En revanche, **les filtres ne sont pas implémentés dans ce contrat**. Seuls `q`,
`page_size` et `cursor` sont acceptés ; les autres paramètres renvoient 422. Les
essais RAG-027 signalent aussi des difficultés de performance avec les filtres.

Configuration future nécessaire :

| Élément | Préparation |
|---|---|
| `SEARCH_DEVICE` | `cpu` |
| `SEARCH_PRECISION` | `float32` |
| `SEARCH_CURSOR_KEY` | Secret privé stable, au moins 32 octets |
| `SEARCH_MODELS_DIR` | Répertoire contenant uniquement le snapshot BGE requis |
| `SEARCH_READER_ENV` | Fichier privé contenant les deux URL explicites |
| `HYBRID_SEARCH_ENABLED` | Maintenir `false` jusqu’à validation |

Le fichier lecteur doit réellement être disponible : `load_settings()` tente de
l’ouvrir même si des URL sont fournies dans l’environnement. L’image et Compose
actuels ne le montent pas.

**Sources :** [route React de recherche](../frontend/app/routes/search.tsx),
[hybrid_runtime.py](../app/hybrid_runtime.py),
[compose.deploy.yml](../compose.deploy.yml).

## 7. Architecture cible et transfert PostgreSQL

### 7.1. Comparaison des deux options PostgreSQL

| Critère | Deux bases, même instance | Deux instances |
|---|---|---|
| Simplicité | Meilleure réutilisation de l’existant | Conteneur, configuration et supervision supplémentaires |
| Isolation des données | Bases et rôles distincts | Bases, rôles et processus distincts |
| Isolation CPU/RAM | Ressources PostgreSQL partagées | Limites de conteneur possibles ; CPU et SSD restent partagés |
| Mémoire | Cache et processus communs | Deux ensembles de processus et de buffers |
| Extensions | Binaires pgvector à rendre disponibles dans l’instance existante | Image spécialisée sans modifier celle du site |
| Sauvegardes logiques | Séparables par base | Séparables par instance |
| Pannes et maintenance | Redémarrage commun | Redémarrages séparés |
| Sauvegarde physique/PITR | Ensemble du cluster | Périmètre propre à chaque cluster |

**Recommandation conditionnelle : deux bases dans l’instance actuelle**, si pgvector
0.8.7 peut y être installé proprement et si les mesures montrent un impact
acceptable sur le site.

Si l’image actuelle ne permet pas cette installation sans changement risqué, ou si
l’isolation des ressources devient nécessaire, une seconde instance est justifiée.
L’état de l’image PostgreSQL de Wallace reste à vérifier.

### 7.2. Processus applicatifs

Pour la première validation, **un worker FastAPI unique** est la solution la plus
simple compatible avec le modèle et les curseurs existants.

Un service dédié devient pertinent si :

- le site nécessite de conserver plusieurs workers applicatifs ;
- l’encodage ou le classement dégrade les autres routes ;
- une isolation de mémoire ou de redémarrage est nécessaire.

Dans ce cas, lui confier **le modèle et les instantanés de recherche** : extraire
seulement l’encodeur ne résoudrait pas la pagination entre workers. Il faudrait
aussi adapter le chemin SSR interne, pas seulement le routage public de Caddy.

Aucun nouveau service permanent n’est donc recommandé avant ces mesures.

### 7.3. Transfert logique et HNSW

**Méthode privilégiée : `pg_dump`/`pg_restore` de la base spécialisée vers une
nouvelle base.**

Les embeddings, textes et métadonnées sont conservés. En revanche, l’archive logique
contient les **définitions des index**, qui sont reconstruits lors de la
restauration. Le graphe HNSW physique n’est pas transporté. Une copie logique par
tables aurait la même conséquence.
[Documentation PostgreSQL 17](https://www.postgresql.org/docs/17/app-pgrestore.html).

Points importants :

- préparer pgvector **0.8.7** pour limiter les écarts ;
- restaurer avec un propriétaire de maintenance distinct du lecteur public ;
- conserver les tables et index de l’application existante ;
- vérifier collation, contraintes, partitions et révision spécialisée ;
- restaurer les index avec les mêmes paramètres, puis recontrôler les résultats ANN.

La reconstruction historique du HNSW a pris **environ 18,1 minutes** sur la machine
locale. Cette durée n’est pas transposable à Wallace : la migration utilisait
**`maintenance_work_mem=40GB`**, incompatible avec ses 32 Go de RAM.

**Ne pas réexécuter aveuglément cette migration sur Wallace.** La restauration
logique n’impose pas ce réglage de migration, mais la mémoire de construction devra
être choisie explicitement. Le coût avec un graphe dépassant la mémoire disponible
peut être beaucoup plus élevé. Le parallélisme doit aussi tenir compte du
`/dev/shm` Docker. [Documentation pgvector](https://github.com/pgvector/pgvector).

Une sauvegarde physique peut conserver les index, mais concerne le cluster entier
et impose davantage de contraintes. Elle ne permet pas de greffer simplement les
fichiers d’un index dans l’instance existante. Elle n’est pas recommandée comme
première approche.
[Documentation PostgreSQL](https://www.postgresql.org/docs/17/continuous-archiving.html).

**Sources locales :**
[migration HNSW](../rag/src/cahier_rag/migrations/versions/rag_0006_fullcorpus_ann_full.py),
[fin de construction RAG-026](../rag/evaluation/local/rag026/completion.json).

## 8. Ressources : mesures, estimations et inconnues

### 8.1. Stockage

| Besoin | Évaluation |
|---|---|
| Base spécialisée restaurée | Environ **78 Gio**, mesure source actuelle |
| Snapshot BGE-M3 | Environ **2,14 Gio**, fichiers existants |
| Archive de transfert | **Inconnue** ; mesurer sa taille, sans supposer le taux de compression |
| WAL, construction et fichiers temporaires | Enveloppe provisoire de **80 à 160 Gio**, à surveiller et réviser |
| Réserve de fonctionnement proposée | **Au moins 50 Gio** disponibles |

Les 402 Gio disponibles annoncés paraissent compatibles avec cette opération.
Ce constat reste conditionné par l’espace **actuel**, la taille de l’archive et la
rétention du WAL. Les gros fichiers ne doivent pas être placés dans `/var`.

### 8.2. RAM

Les seuls vecteurs bruts représentent déjà **19,79 Gio**, auxquels s’ajoutent
tables, métadonnées et index. Le HNSW de 36 Gio dépassera la RAM disponible au cache
après prise en compte du site et du modèle.

**Cela n’impose pas de charger tout l’index en RAM.** En revanche, les lectures
aléatoires sur le SSD SATA peuvent devenir déterminantes. Les observations locales,
avec 128 Go de RAM, ne permettent pas de prédire ce comportement.

Exemple d’enveloppe initiale de travail, **non mesurée sur Wallace** :

| Usage | Budget indicatif |
|---|---:|
| OS et services hors processus de recherche | 3 Gio |
| FastAPI unique avec BGE-M3 | 5 Gio |
| `shared_buffers` PostgreSQL | 4 Gio |
| Backends SQL et allocations temporaires | 3 Gio |
| Cache de fichiers récupérable | 12 Gio |
| Marge non engagée | 5 Gio |

Ce tableau sert à préparer les mesures, pas à appliquer immédiatement ces réglages.
Le pic de chargement, les allocations par requête et les usages actuels du site
devront le remplacer.

### 8.3. CPU et performances

Le lexical est déjà un coût dominant :

| Mesure historique | Résultat |
|---|---:|
| Lexical optimisé, médiane chaude | 1,87 s |
| Lexical optimisé, P95 empirique | **5,15 s** |
| Deux recherches API réelles, encodage GPU inclus | 2,686 s et 2,694 s |
| Fusion RRF correspondante | Environ 0,6 ms |

Ces valeurs proviennent de RAG-027 et SEARCH-004, sans concurrence publique
représentative.

**Le P95 inférieur à deux secondes ne peut pas être annoncé aujourd’hui.** Réduire
les candidats lexicaux changerait potentiellement les classements : ce serait une
expérimentation de pertinence distincte, pas un simple réglage de déploiement.

**Sources :** [rapport RAG-027](../rag/rapport-rag-027.md),
[rapport SEARCH-004](rapport-search-004.md).

## 9. Risques techniques

| Gravité | Problème et impact | Preuve | Prévention |
|---|---|---|---|
| **Bloquant** | Manifeste lié à la source locale : moteur refusé au démarrage | `SearchReader.validate`, identité persistée | Publication contrôlée et attestation de correspondance des données |
| **Bloquant** | Deux workers : curseurs introuvables et modèles multiples | Dockerfile, `SnapshotCache` | Un propriétaire du modèle et du cache |
| **Bloquant avant activation** | Image sans dépendances, modèle et fichier lecteur | Dockerfile, `.dockerignore`, runtime | Image CPU reproductible et montages privés en lecture seule |
| **Majeur** | Reconstruction HNSW très coûteuse ou manque de mémoire | Index de 36 Gio ; migration à 40 Go | Répétition de restauration, mémoire bornée et suivi des ressources |
| **Majeur** | Dégradation du site par CPU/I/O de recherche | Lexical sur millions de candidats ; ressources partagées | Benchmarks mixtes, admission bornée, activation limitée |
| **Majeur** | Objectif de latence non atteint | P95 lexical historique de 5,15 s | Mesure complète, décision explicite sur le niveau de service |
| **Majeur qualité** | ANN sélectionné mais non qualifié | `qualified:false` | Acceptation documentée et contrôles après restauration |
| **Majeur fonctionnel** | Filtres demandés mais non disponibles | API refuse les paramètres supplémentaires | Décider du périmètre initial ; chantier distinct si filtres obligatoires |
| **Majeur** | Mauvais rôle, privilèges hérités ou connexions insuffisantes | Garde de lecture et limite locale à 4 | Provisionnement adapté à Wallace, tests sous le vrai lecteur |
| **Modéré** | Modèle CPU ou recherche indisponible malgré `/healthz` vert | Readiness applicative indépendante | Suivi explicite de l’état du moteur et des erreurs 503/504 |

## 10. Protocole de benchmark à préparer

**Ce protocole n’a pas été exécuté.** Il doit d’abord être utilisé sur une instance
de validation non publiée, avec le même matériel et les mêmes données que la cible.

### 10.1. Gel de la configuration

Enregistrer pour chaque campagne :

- versions des images, PostgreSQL, pgvector, PyTorch et Transformers ;
- révision et empreinte du modèle ;
- génération du corpus et empreinte de recette ;
- paramètres ANN, threads CPU et paramètres SQL ;
- nombre de processus, limites de file et timeouts ;
- charge documentaire concurrente.

Réutiliser les **32 requêtes de `performance-rag027.json`**, puis ajouter un petit
jeu figé de requêtes longues et de cas limites. Ne pas utiliser silencieusement le
jeu réservé pour régler les paramètres.

### 10.2. Mesures séparées

| Composant | Mesure prévue |
|---|---|
| Encodage BGE-M3 CPU | Tokenisation, inférence, normalisation ; batch 1 ; threads 1/2/4 |
| Lexical | Recette exacte retenue, temps SQL et restauration documentaire |
| BM25 | Diagnostic séparé sur les 20 000 documents existants ; **hors SLA H1** |
| HNSW | Même recette, temps SQL et restauration ; vecteurs de requête précalculés pour isoler SQL |
| RRF | Rejeu des listes enregistrées, sans modèle |
| Hybride complet | Validation, admission, encodage, SQL, fusion, hydratation et sérialisation |
| Parcours SSR | Première recherche avec redirection, pagination, retour et rechargement |

Les timings actuels couvrent plusieurs composants mais pas toute l’attente
d’admission séparément. Les erreurs ne produisent pas toutes le même événement de
métriques que les succès : le générateur de charge doit donc compter tous les statuts.

### 10.3. Charge et indicateurs

Prévoir les niveaux **1, 5 et 20 utilisateurs simultanés**, avec :

- nouvelles recherches non servies par un instantané ;
- navigation sur des curseurs existants ;
- mélange représentatif des deux ;
- trafic documentaire et statistiques concurrent.

Faire plusieurs passages du même jeu dans un ordre reproductible, puis un ordre
mélangé. Conserver au moins quelques centaines d’observations par scénario pour
éviter un P95 fondé sur quelques requêtes.

Relever :

- P50/P95 et débit des recherches réussies ;
- proportion et codes des erreurs, refus et timeouts ;
- CPU, `MemAvailable`, RSS/PSS, swap et OOM ;
- mémoire et activité PostgreSQL ;
- lectures disque, latence I/O et fichiers temporaires ;
- occupation de la file ;
- P50/P95 des pages et API documentaires.

**Les 503 de saturation ne doivent pas être exclus pour présenter artificiellement
un bon P95.** À 20 utilisateurs, le moteur actuel n’admet pas 20 classements : il
limite à trois travaux par processus, avec une admission d’une seconde.

### 10.4. Caches froids et chauds

Distinguer :

1. modèle froid ;
2. modèle chaud et PostgreSQL chaud ;
3. buffers PostgreSQL froids avec cache OS encore chaud ;
4. véritable état froid OS/PostgreSQL.

Ne pas vider les caches du serveur public pour fabriquer un résultat à froid.
Les essais réellement froids nécessitent une cible isolée ou une fenêtre de
maintenance explicitement validée.

### 10.5. Critères d’ouverture

À valider humainement :

- objectif indicatif **P95 < 2 s**, encodage et attente inclus ;
- taux d’erreur et limite de concurrence acceptables ;
- absence de swap soutenu et de pression mémoire dangereuse ;
- budget de régression des performances documentaires ;
- acceptation du compromis ANN ;
- fidélité des sources et stabilité de la pagination.

La qualité doit être recontrôlée après reconstruction HNSW et passage aux requêtes
CPU. Reprendre les paramètres ne garantit pas un graphe ANN ni des classements
bit à bit identiques.

## 11. Plan de déploiement progressif

### Phase 1 — Préparation

1. Confirmer **H1 comme périmètre initial**, et décider du sort des filtres.
2. Résoudre la portabilité de l’identité source, sans supprimer les gardes.
3. Préparer l’image CPU et tester ses dépendances verrouillées.
4. Préparer un seul propriétaire du modèle et des curseurs.
5. Exposer le réglage des threads CPU.
6. Préparer les fichiers privés et le montage BGE-M3 en lecture seule.
7. Adapter le provisionnement des rôles aux noms de bases de Wallace.
8. Vérifier l’installation possible de pgvector dans l’instance actuelle.
9. Préparer la répétition de restauration et les critères d’arrêt sur espace/mémoire.

**Sortie attendue :** configuration et procédure examinables, sans activation publique.

### Phase 2 — Installation de la base

1. Relever sur Wallace l’espace disponible, les montages, le WAL et les sauvegardes.
2. Sauvegarder l’application existante et vérifier la procédure de restauration avant
   une éventuelle intervention sur son instance PostgreSQL.
3. Produire une archive logique cohérente de la base spécialisée.
4. Mesurer l’archive et vérifier son intégrité après transfert.
5. Restaurer dans **une nouvelle base distincte**, sans écraser `cahier_doleances`.
6. Reconstruire les index avec une enveloppe mémoire compatible.
7. Contrôler révision, extensions, partitions, contraintes, états et index.
8. Vérifier les effectifs, empreintes et vecteurs sur un échantillon déterministe.
9. Vérifier la correspondance avec les données applicatives et publier l’identité
   cible selon la procédure préparée.
10. Tester les droits avec les identifiants du vrai lecteur public.

Les contrôles d’effectifs et de chaîne peuvent nécessiter des lectures complètes
pendant cette phase future ; ils n’ont pas été exécutés pendant l’audit.

### Phase 3 — Installation du moteur

1. Démarrer une instance de validation non publiée.
2. Charger le snapshot existant sur CPU, sans téléchargement.
3. Vérifier les deux connexions et l’hydratation.
4. Tester H1, les erreurs, l’annulation et la pagination.
5. Vérifier que les routes documentaires restent accessibles pendant le chargement
   ou une panne de recherche.

### Phase 4 — Benchmarks

1. Mesurer composants, mémoire et chargement.
2. Exécuter les scénarios 1/5/20.
3. Mesurer simultanément l’impact sur le site.
4. Ajuster threads, mémoire SQL et concurrence sans modifier la recette de pertinence.
5. Décider si un worker unique suffit ou si l’isolation par service est nécessaire.
6. Prononcer explicitement l’acceptation ou le refus de l’objectif initial.

### Phase 5 — Activation publique

1. Déployer les éléments validés avec des images identifiées et conservées pour
   retour arrière.
2. Activer la recherche après validation des contrôles.
3. Vérifier `/recherche`, les curseurs, les liens et le parcours sans JavaScript.
4. Surveiller latences, erreurs, file, mémoire, I/O et routes documentaires.
5. En cas d’échec, remettre `HYBRID_SEARCH_ENABLED=false` : le site documentaire
   reste disponible et les données de recherche sont conservées.

**Une activation limitée nécessite une restriction réelle des accès pendant la
recette.** Passer simplement le flag à `true` sur l’application publique ouvrirait
immédiatement la route aux visiteurs.

## 12. Questions ouvertes et décision attendue

Avant l’implémentation :

1. **H1 sans BM25 et sans filtres convient-elle à la première ouverture ?** C’est
   le moteur public réellement prêt côté algorithme.
2. Accepte-t-on un premier déploiement avec **un seul worker FastAPI** ?
3. Quelle procédure de validation des données autorisera l’association du corpus
   à l’identité applicative de Wallace ?
4. Quel niveau de qualité ANN est acceptable malgré `qualified:false` ?
5. Le P95 de deux secondes est-il un objectif d’amélioration ou une condition stricte
   d’ouverture ?

À vérifier sur Wallace :

- image PostgreSQL exacte et disponibilité de pgvector 0.8.7 ;
- capacité à conserver la même instance sans risque pour l’application ;
- espace actuel, WAL, rétention et sauvegardes ;
- mémoire et CPU réellement consommés par le site et les statistiques ;
- paramètres PostgreSQL et `/dev/shm` ;
- droits et limites de connexions ;
- performances CPU de BGE-M3, lexicales et I/O ;
- correspondance des données applicatives avec le corpus local.

**Avis final : faisabilité technique favorable, ouverture publique non validée.**
Les données et le moteur sont réutilisables sans recalcul des embeddings. La
prochaine étape doit traiter la portabilité du manifeste, le propriétaire unique
des curseurs et l’image CPU, puis mesurer la restauration et la charge réelle avant
activation.
