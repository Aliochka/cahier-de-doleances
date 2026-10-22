# Audit technique — Recherche lexicale H1

Date : 22 octobre 2026. Référence inspectée : commit `0eebaecbd0f14bc88ae12d85cc6fba35d0fd5a73`.

**Statut : audit uniquement ; propositions à valider avant toute implémentation.** Seul ce rapport a été créé. Aucun code, paramètre, schéma ou contenu de base modifié ; aucun service démarré, arrêté ou redémarré ; aucun modèle chargé ou téléchargé ; aucun benchmark, EXPLAIN ou EXPLAIN ANALYZE exécuté.

Les références `fichier:Lx–Ly` désignent les lignes du code inspecté. Les liens ouvrent les fichiers correspondants dans le dépôt.

## 1. Synthèse exécutive

**Le coût lexical dépend du nombre de documents qui correspondent à la requête, pas des 50 résultats retournés.** Le service public emploie déjà une version optimisée, `TunedSearch(statistics=True, prefilter=None)` : les fréquences documentaires sont précalculées, mais tous les documents admissibles doivent encore recevoir le score pondéré avant le classement. Une requête comportant des mots ordinaires recherche leur union (« OU »). Des termes fréquents peuvent donc produire un ensemble important à lire, noter et départager.

Les chiffres transmis — 26 réussites sur 32, six timeouts, P50 1,899 s, P95 9,113 s, lexical jusqu’à 8,7 s, encodage généralement 0,13–0,15 s, HNSW généralement 0,05–0,07 s — étayent fortement le diagnostic sur les réussites. **Ils ne suffisent pas à attribuer les six timeouts au lexical.** Les deux branches partagent une phase de dix secondes nommée `sql` et le script perd les chronométrages partiels en cas d’échec.

Constats les plus utiles :

1. Le `LIMIT 50` arrive après le calcul du score et son ordre global. Il ne plafonne pas le nombre de candidats à noter.
2. Le score exprime deux fois chaque test d’appartenance à un lexème, puis appelle `ts_rank_cd`. Cela représente jusqu’à 64 occurrences de `@@` dans l’expression de score, en plus du prédicat de sélection. Le nombre d’évaluations physiques reste à vérifier dans PostgreSQL.
3. Le prédicat principal est compatible avec le GIN défini dans les migrations. Aucun `to_tsvector` par document, `unaccent` ou cast de la colonne ne bloque manifestement cet accès. L’utilisation effective du GIN sur Wallace reste inconnue.
4. Le service public ne recalcule pas les DF par comptage du corpus. Cette dépense existe dans la référence `FullSearch` et les recherches filtrées, mais ce n’est pas le chemin public observé dans le code.
5. Des contrôles et connexions répétés s’ajoutent au coût lexical ; ils expliquent potentiellement une partie du temps mesuré, sans preuve qu’ils expliquent les secondes les plus élevées.

**Recommandation : commencer par obtenir les plans sans exécution et rendre les échecs attribuables à une sous-étape.** Comme première modification du calcul, tester ensuite une spécialisation exacte des requêtes à un lexème obligatoire : leurs deux couvertures sont déjà connues grâce au `WHERE`. Cette modification est limitée, sans nouvel index ni mémoire de travail supplémentaire, et doit conserver l’expression arithmétique et le départage actuels. Son gain sera probablement partiel ; elle ne constitue pas une promesse de résolution des six timeouts. Pour les requêtes longues, le choix suivant dépendra des plans et des mesures.

## 2. Périmètre, preuves et limites

### 2.1 Ce qui a été effectivement vérifié

Lecture du code, migrations RAG et applicatives, script de benchmark, inventaires de restauration et documentation de déploiement. Le jeu [performance-rag027.json](../rag/evaluation/performance-rag027.json) contient **32 requêtes**, toutes marquées `development`. Son SHA-256 est :

```text
f1ad4fef0eae346ce9a2413426ecf7214406440d0e89ea4821fe6913e2e7583e
```

Il reste à comparer cette empreinte à celle du benchmark Wallace : même nombre de requêtes ne signifie pas automatiquement même jeu. Les résultats bruts de la campagne décrite n’ont pas été fournis à cet audit ; les latences et caractéristiques de Wallace sont des informations transmises, non des observations distantes.

### 2.2 Accès PostgreSQL

La configuration du lecteur présente dans l’espace de travail désigne des adresses de boucle locale et des rôles portant un nom de lecteur. La machine courante n’est pas identifiée comme Wallace. Aucun accès ou tunnel attesté vers sa base réelle n’a été identifié ; aucune connexion PostgreSQL n’a été tentée. Les valeurs de connexion et secrets n’ont pas été affichés.

Par conséquent, **aucun plan ni état d’index de Wallace n’est présenté comme vérifié**. Les index ci-dessous sont établis par le code et les inventaires du transfert, pas par le catalogue de production. La section 5 fournit les relevés nécessaires à l’opérateur ou à une session disposant d’un accès en lecture seule identifié.

## 3. Fonctionnement actuel

### 3.1 Chemin réellement appelé

| Composant | Rôle dans H1 public |
|---|---|
| [service/core.py](../rag/src/cahier_rag/search/service/core.py), L152–224 | Validation du corpus, encodage, `TunedSearch.lexical`, `ann_search`, fusion RRF et chronométrages. |
| [tuning/lexical.py](../rag/src/cahier_rag/tuning/lexical.py), L23–115 | Statistiques figées, génération du score et SQL lexical réellement utilisé. |
| [fullcorpus/search.py](../rag/src/cahier_rag/fullcorpus/search.py), L23–58 | Paramètres, état du corpus et hydratation des documents sélectionnés, hérités par `TunedSearch`. |
| [fullcorpus/search.py](../rag/src/cahier_rag/fullcorpus/search.py), L60–87 | Référence lexicale historique avec DF comptés à la demande ; sa méthode `lexical` est remplacée par celle de `TunedSearch` dans le service public. |
| [tuning/retrieval.py](../rag/src/cahier_rag/tuning/retrieval.py), L12–64 | Aiguillage vectoriel expérimental, notamment recherche exacte avec filtres. Ce fichier ne définit pas le lexical et n’est pas appelé par `HybridSearch.retrieve`. |
| [tuning/vector.py](../rag/src/cahier_rag/tuning/vector.py), L52–111 | Branche ANN appelée directement par le service. |

Le service public refuse actuellement le filtre par question ; les autres filtres ne sont pas transmis à la recherche lexicale publique. La recette par défaut est profondeur 50 par branche, limite finale 50, RRF 60, ANN `ef_search=1000`, 400 segments demandés au premier passage (`core.py:L27–39,152–190`).

### 3.2 Préparation de la requête

[search/preparation.py](../rag/src/cahier_rag/search/preparation.py), L65–125 :

- Normalisation Unicode, extraction des mots, expressions entre guillemets et exclusions ; retrait d’une liste précise de mots génériques. `OR` est ignoré comme mot et n’établit pas une grammaire booléenne générale.
- PostgreSQL produit les lexèmes uniques par `tsvector_to_array(to_tsvector('pg_catalog.french', :value))`. Maximum : 32 lexèmes positifs significatifs.
- Les lexèmes positifs sont échappés par `quote_literal` puis reliés par `|` lorsque des mots hors guillemets sont présents.
- Chaque expression citée produit un `phraseto_tsquery`, ajouté par `&`. Les exclusions produisent `& !(...)`. Huit expressions et huit exclusions au maximum.
- Une requête sans lexème positif significatif retourne une branche lexicale vide. Une expression citée entièrement composée de mots vides ne peut pas être vérifiée et retourne également vide.

Subtilité à préserver : la liste des lexèmes positifs est construite avec **les mots et les expressions citées**. En présence de mots libres, la partie OR contient donc aussi les lexèmes des expressions ; les contraintes de phrase restent obligatoires. Le calcul de couverture porte sur cette liste positive, pas sur les exclusions.

### 3.3 Tables, colonnes et index

[rag_0004_fullcorpus.py](../rag/src/cahier_rag/migrations/versions/rag_0004_fullcorpus.py), L13–62 :

| Objet | Utilisation et index définis |
|---|---|
| `rag_full.spaces` | Une ligne par espace : compte documentaire, manifeste, empreintes, états de vérification. PK `space_id`. |
| `rag_full.documents` | Parent partitionné par liste sur `space_id`. Colonnes utiles : `document_id`, `search_vector`, filtres `questionnaire_id`, `unit_type`, `historical_split`, puis `record` pour l’hydratation. |
| `rag_full.documents_full` | Partition attendue pour `space_id='full'`. Le pruning doit éviter la partition pilote ; à vérifier dans le plan réel. |
| `full_lexical_gin` | GIN de `search_vector` déclaré sur le parent ; index enfant attendu sur la partition complète. |
| PK `(space_id, document_id)` | Accès aux documents gagnants par leur identifiant ; ne fournit pas l’ordre du score lexical. |
| UNIQUE `(space_id, ordinal)` | Parcours d’import/lecture ordinale ; sans avantage direct pour le classement lexical. |
| B-tree `(space_id, questionnaire_id, unit_type)` | Potentiellement utile avec filtres ; peu discriminant pour le chemin public sans filtre. |
| B-tree `(space_id, contribution_id)` | Utile à d’autres accès ; aucune jointure par contribution dans le SQL lexical public. |
| `rag_tuning.statistics` | Compte et empreinte du corpus ; PK `space_id`. |
| `rag_tuning.term_statistics` | DF exacte de chaque lexème ; PK `(space_id, term)`. |

Les deux dernières tables sont définies dans [rag_0007_lexical_statistics.py](../rag/src/cahier_rag/migrations/versions/rag_0007_lexical_statistics.py), L13–20. Les DF sont construites par `ts_stat` et liées à l’empreinte du corpus ([tuning/statistics.py](../rag/src/cahier_rag/tuning/statistics.py), L24–49), sans reconstruction pendant la recherche publique.

Le vecteur lexical est calculé à l’import depuis **le texte du document**, par `setweight(to_tsvector('pg_catalog.french', r->>'text'), 'A')` ([fullcorpus/store.py](../rag/src/cahier_rag/fullcorpus/store.py), L119–129). Il conserve les positions. Les poids 0,5/0,3/0,2 ci-dessous sont des coefficients du score ; ils sont distincts du marquage A du `tsvector`.

L’[inventaire de restauration](../search-transfer/cahier-search.restore.toc), L74–110, mentionne notamment `documents_full_search_vector_idx`, son attachement, la PK documentaire et `term_statistics_pkey`. Il confirme la présence prévue de ces objets dans le transfert, **pas leur définition ou validité actuelle sur Wallace**.

Les migrations applicatives `f839a0433a71`, `1770ad98b7c6` et `performance_fix_001` concernent surtout `public.forms`, `questions`, `answers`, `contributions`. Leurs index ne servent pas le classement dans `rag_full.documents`. Les modifier ne traiterait pas directement ce goulet.

### 3.4 Requêtes SQL exécutées par le lexical public

Les marqueurs `:nom` ci-dessous représentent des valeurs liées ; ils ne désignent pas une interpolation utilisateur. Outre les contrôles du lecteur décrits plus bas, la séquence est :

1. Lecture de `rag_full.spaces` pour les paramètres et le compte `N` ; aucun `count(*)` documentaire dans ce chemin.
2. Préparation PostgreSQL décrite en 3.2.
3. Nouvelle lecture d’état et contrôle du manifeste de statistiques :

```sql
SELECT documents, corpus_hash
FROM rag_tuning.statistics WHERE space_id = :space;
```

4. Récupération des DF et calcul des IDF (`tuning/lexical.py:L41–46`) :

```sql
WITH term_stats AS (
  SELECT t.term, t.ord,
    ln(1.0 + (:n - coalesce(s.documents,0) + 0.5)::float8
             / (coalesce(s.documents,0) + 0.5)::float8) AS idf
  FROM unnest(CAST(:terms AS text[])) WITH ORDINALITY t(term,ord)
  LEFT JOIN rag_tuning.term_statistics s
    ON s.space_id = :space AND s.term = t.term
)
SELECT term, quote_literal(term) AS query, idf,
  sum(idf) OVER (
    ORDER BY ord ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
  ) AS total
FROM term_stats ORDER BY ord;
```

Cette petite fenêtre et ce tri concernent au plus 32 termes, pas les millions de documents.

5. Sélection et classement (`tuning/lexical.py:L62–73,100–103`). Pour deux lexèmes, la forme développée est :

```sql
SELECT d.document_id,
  :idf_coverage * (
    CASE WHEN d.search_vector @@ CAST(:t0 AS tsquery)
      THEN CAST(:w0 AS float8) ELSE 0::float8 END
    + CASE WHEN d.search_vector @@ CAST(:t1 AS tsquery)
      THEN CAST(:w1 AS float8) ELSE 0::float8 END
  ) / CAST(:total_idf AS float8)
  + :term_coverage * CAST((
    CASE WHEN d.search_vector @@ CAST(:t0 AS tsquery) THEN 1 ELSE 0 END
    + CASE WHEN d.search_vector @@ CAST(:t1 AS tsquery) THEN 1 ELSE 0 END
  ) AS float8) / :term_count
  + :frequency_proximity
    * ts_rank_cd(d.search_vector, CAST(:query AS tsquery), 32)::float8 AS score
FROM rag_full.documents d
WHERE d.space_id = :space
  AND (:form IS NULL OR d.questionnaire_id = :form)
  AND (:kind IS NULL OR d.unit_type = :kind)
  AND (:split IS NULL OR d.historical_split = :split)
  AND d.search_vector @@ CAST(:query AS tsquery)
ORDER BY score DESC, d.document_id COLLATE "C"
LIMIT :limit;
```

Public : `space='full'`, trois filtres NULL, `limit=50`. Pour `m` termes, les deux sommes sont développées en Python avec `m` branches chacune. **Aucune CTE de préfiltrage dans cette configuration.**

6. Hydratation des seuls gagnants (`fullcorpus/search.py:L43–58`) :

```sql
SELECT document_id, record FROM rag_full.documents
WHERE space_id = :space AND document_id = ANY(:ids);
```

Le dictionnaire Python rétablit l’ordre fourni par le classement ; l’absence d’`ORDER BY` dans cette lecture ne change donc pas le classement.

### 3.5 Score et fusion

Avec `I_i(d)` indicateur de présence du lexème, `w_i = ln(1 + (N-df_i+0,5)/(df_i+0,5))`, le score est :

```text
S(d) = 0,5 × somme(w_i × I_i(d)) / somme(w_i)
     + 0,3 × somme(I_i(d)) / m
     + 0,2 × float8(ts_rank_cd(search_vector, Q, 32))
```

Les coefficients sont définis dans [search/flexible.py](../rag/src/cahier_rag/search/flexible.py), L19. `ts_rank_cd` tient compte des occurrences et positions ; l’option 32 transforme le rang en `rang/(rang+1)`. Cette option ne rend pas le rang accessible en ordre d’index. Voir la [documentation PostgreSQL 17 sur le classement](https://www.postgresql.org/docs/17/textsearch-controls.html#TEXTSEARCH-RANKING).

L’ordre est score décroissant puis identifiant en collation C. Les deux listes de 50 résultats sont fusionnées par somme de `1/(60+rang)`, rangs à partir de 1, fractions exactes, départage documentaire ([hybrid/core.py](../rag/src/cahier_rag/search/hybrid/core.py), L37–62). **Un changement d’ordre lexical, même sans changement de contenu, peut modifier H1.** L’égalité du seul ensemble top-50 n’est donc pas une validation suffisante.

### 3.6 Coûts : résultats retournés contre documents examinés

Soient `M` le nombre de documents qui satisfont la requête, `E` le nombre de lignes visitées/revérifiées, `m≤32` le nombre de lexèmes, et `K=50`.

| Opération | Dépendance dominante |
|---|---|
| Tokenisation et normalisation | Taille de la requête et nombre d’expressions ; indépendante de `K` et du corpus. |
| DF figées / IDF | Au plus `m` recherches de termes dans la table statistique, selon le plan choisi. |
| Parcours GIN | Taille des listes de correspondances et combinaison booléenne ; ne se limite pas à `K`. |
| Lecture des lignes / vecteurs, revérification | `E`, largeur physique et positions des documents, état des caches ; `E` peut dépasser `M`. |
| Couvertures lexicales | Expression de l’ordre de `M×m` tests, modulée par le travail interne des opérateurs et le plan. |
| `ts_rank_cd` | Tous les `M` candidats, leur contenu positionnel et la complexité de `Q`. |
| Classement | Tous les `M` scores doivent être considérés. Un tri top-N peut limiter la mémoire et approcher `M log K`, sans supprimer ces calculs. Un autre plan peut faire un tri plus large. |
| Hydratation et restauration Python | Au plus `K` documents ; coût variable avec leur taille. |
| RRF | Union d’au plus 100 résultats, puis 50 retenus. |

Un GIN est un index inversé de correspondances lexicales, pas un index ordonné par ce score dépendant de la requête. Voir [types d’index de recherche PostgreSQL 17](https://www.postgresql.org/docs/17/textsearch-indexes.html). Il faut distinguer un parcours séquentiel réellement choisi d’un accès GIN pourtant coûteux à cause d’un très grand ensemble de correspondances.

### 3.7 Budgets et contrôles

`core.py:L163–191` : budget global de 18 s par défaut ; encodage borné à 3 s ; lexical puis ANN dans **la même phase de 10 s**. Les paramètres, statistiques, contrôles, lectures d’identité, transferts et hydratations des branches consomment aussi cette durée. Ce n’est pas dix secondes pour chaque branche.

[service/reader.py](../rag/src/cahier_rag/search/service/reader.py), L49–123 : chaque instruction reçoit le budget résiduel via `set_config('statement_timeout', ...)`. Les `SET LOCAL statement_timeout='30s'` historiques sont remplacés par le reliquat avant l’instruction suivante. Ils ne donnent pas trente secondes au SQL public. Le moniteur annule la connexion empruntée à l’échéance ([control.py](../rag/src/cahier_rag/search/service/control.py), L59–119).

`FullSearch.parameters()` appelle `store.state()` ; `_terms()` le rappelle sans transmettre sa connexion courante. `FullStore.state()` ouvre alors sa propre transaction (`store.py:L60–79`). Chaque transaction du `ReadGuard` relit les identités source/cible et contrôle la séparation des bases. Cela entraîne des allers-retours répétés, et `_terms()` peut emprunter une deuxième connexion cible alors que la première reste ouverte. Le pool est de taille 2 sans débordement (`reader.py:L31–46`). C’est un surcoût certain dans le chemin, pas une preuve de saturation du pool en production. Le worker sérialise le calcul de recherche dans son processus ([worker.py](../rag/src/cahier_rag/search/service/worker.py), L10–46).

Les temps `Timings.lexical` et `Timings.vector` mesurent les appels complets, pas seulement les instructions de classement. Les sous-temps de `TunedSearch.last_lexical_timings` ne sont pas exposés par le service public et ne sont renseignés complètement qu’à la réussite.

## 4. Causes identifiées et hypothèses

### 4.1 Constats établis par le code

| Constat | Référence | Implication |
|---|---|---|
| Union des lexèmes libres | `preparation.py:L108–125` | Une longue question peut élargir fortement les correspondances ; le nombre de résultats finaux reste 50. |
| Aucun plafond avant score pondéré | `core.py:L181`, `lexical.py:L90–103` | Tous les candidats admissibles restent dans la compétition. C’est cohérent avec la pertinence exacte. |
| Tests de présence répétés dans les deux couvertures | `lexical.py:L62–73` | Travail potentiellement évitable, multiplié par le nombre de candidats et de termes. |
| Appel à `ts_rank_cd` avant limite | `lexical.py:L73,100–103` | Coût positionnel sur les candidats du classement. |
| Statistiques figées déjà actives | `core.py:L181`, `lexical.py:L23–46` | « Précalculer les DF » ne serait pas une nouvelle optimisation du public. |
| Branche filtrée différente | `lexical.py:L47–58`, `fullcorpus/search.py:L69–85` | Comptages population/DF supplémentaires en expérimentation filtrée ; ne pas extrapoler leur coût au public. |
| Hydratation après classement | `lexical.py:L103–105` | Bonne séparation existante ; pas de JSON complet transmis à Python pour tous les candidats. |
| Contrôles d’état répétés | `fullcorpus/search.py:L30`, `lexical.py:L25`, `reader.py:L102–123` | Temps lexical incluant autre chose que score et tri. |
| Timeouts SQL non attribuables à une branche | `core.py:L182–190`, `benchmark_public_search.py:L179–190` | Impossible de conclure pour les six échecs avec les seules métriques actuelles. |

### 4.2 Hypothèses à vérifier, sans les présenter comme des mesures

1. **Grand `M` sur les requêtes lentes.** Priorité élevée : comparer termes fréquents, questions longues et expressions citées. Les DF unitaires donnent une indication ; elles ne donnent pas exactement la taille d’une union/intersection.
2. **Lecture heap/TOAST et décompression des vecteurs.** La table contient aussi `record jsonb` et les vecteurs positionnels. La requête ne sélectionne pas `record` au classement, mais la disposition physique et les vecteurs volumineux peuvent peser sur les lectures. Aucun volume lu ou taux de cache Wallace n’est connu.
3. **Bitmap devenu lossy, nombreuses revérifications**, si la mémoire du bitmap est insuffisante. Les contraintes de phrase peuvent elles aussi demander des vérifications positionnelles. À confirmer ultérieurement par mesures exécutées autorisées ; un plan estimé ne donne pas les comptes réels de pages lossy.
4. **Parcours séquentiel ou mauvaise estimation de sélectivité.** Cela peut être rationnel pour des termes très fréquents ; ce n’est pas en soi une erreur. Vérifier statistiques de la partition et du parent après restauration, dates d’analyse et estimations. Les DF de `rag_tuning` ne remplacent pas les statistiques du planificateur.
5. **JIT coûteux sur le score développé.** Le nombre d’expressions peut produire un coût de compilation disproportionné pour certains plans. Vérifier configuration et présence du bloc JIT ; ne pas désactiver globalement sur simple intuition.
6. **Tri complet ou débordement temporaire.** Possible, non démontré. Un top-N de 50 lignes étroites peut au contraire être peu coûteux : ne pas recommander plus de `work_mem` sans preuve.
7. **Plan générique moins adapté.** Les filtres `(:x IS NULL OR ...)` peuvent être simplifiés avec des paramètres connus. Un plan générique peut moins bien estimer certains cas. Le mécanisme effectif de préparation des requêtes et le driver déployé doivent être relevés ; SQLAlchemy n’implique pas à lui seul un plan serveur générique.
8. **Interférences sur Wallace** : cache partagé entre ANN et lexical, I/O, CPU, swap ou concurrence du site public. Ni les ressources réellement disponibles ni les attentes SQL n’ont été relevées ici.
9. **Épuisement du reliquat dans ANN après un lexical lent**, ou attente dans les gardes/connexions. Compatible avec le code ; les six échecs doivent être localisés individuellement.

## 5. Analyse PostgreSQL préparée

### 5.1 Collecte légère proposée

Ces instructions sont **préparées, non exécutées**. Utiliser le rôle lecteur déjà autorisé et vérifier la cible par un canal privé. Ne pas lancer le script de validation de restauration : [verify-search.sql](../deploy/postgres/verify-search.sql), L15–16, compte intégralement documents et segments avec un délai de 30 minutes.

Pour les seuls catalogues et plans sans exécution, une transaction courte peut être enveloppée ainsi ; les limites ci-dessous protègent la collecte et ne changent pas le budget de H1 :

```sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = '1000ms';
SET LOCAL lock_timeout = '200ms';
-- Une ou quelques lectures de catalogue, ou un EXPLAIN sans ANALYZE.
ROLLBACK;
```

À relever en petites requêtes bornées :

```sql
SELECT c.relname AS table_name, ix.relname AS index_name,
       am.amname, i.indisvalid, i.indisready,
       pg_get_indexdef(i.indexrelid) AS definition
FROM pg_index i
JOIN pg_class c ON c.oid = i.indrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_class ix ON ix.oid = i.indexrelid
JOIN pg_am am ON am.oid = ix.relam
WHERE (n.nspname = 'rag_full'
       AND c.relname IN ('documents','documents_full','segments_full'))
   OR (n.nspname = 'rag_tuning'
       AND c.relname IN ('statistics','term_statistics'))
ORDER BY n.nspname, c.relname, ix.relname;

SELECT relname, n_live_tup, n_dead_tup,
       last_analyze, last_autoanalyze, n_mod_since_analyze
FROM pg_stat_all_tables
WHERE schemaname = 'rag_full'
  AND relname IN ('documents','documents_full');

SELECT tablename, attname, inherited, null_frac, avg_width, n_distinct
FROM pg_stats
WHERE schemaname = 'rag_full'
  AND tablename IN ('documents','documents_full')
  AND attname IN ('space_id','search_vector','questionnaire_id',
                 'unit_type','historical_split');
```

Ajouter `pg_class.reltuples`, `relpages`, `reltoastrelid` pour parent/partition et tailles des relations/index/TOAST via les fonctions de taille ; relever séparément l’existence et le volume des statistiques du planificateur sur `search_vector`, sans exporter le vocabulaire citoyen. Ces métadonnées ne demandent pas de parcourir les documents. Une absence dans `pg_stats` peut aussi être liée aux privilèges : la signaler sans modifier les ACL.

Relever les paramètres effectifs de la **session de recherche** : `work_mem`, `shared_buffers`, `effective_cache_size`, `jit`, seuils JIT, `random_page_cost`, `seq_page_cost`, `default_statistics_target`, `max_parallel_workers_per_gather`, `plan_cache_mode`, `enable_partition_pruning`, `enable_bitmapscan`, `enable_seqscan`, `enable_indexscan`. Les réglages d’un rôle administrateur ne sont pas nécessairement ceux du lecteur.

### 5.2 Requêtes prioritaires pour EXPLAIN sans ANALYZE

Utiliser `EXPLAIN (VERBOSE, COSTS, SETTINGS, FORMAT JSON)` devant **le SQL exact de la section 3.4**, avec ses valeurs liées réelles : termes normalisés, Q complet, IDF calculées par `_terms`, coefficients existants, filtres NULL, profondeur 50. Ne pas remplacer le score par `ts_rank_cd` seul : cela changerait l’objet du diagnostic. Les sorties `VERBOSE` peuvent contenir les valeurs liées ; les conserver en accès restreint et ne diffuser que les plans expurgés.

Ordre proposé :

1. Classement pondéré d’un cas rapide, d’un cas réussi proche de la limite et de chacun des six cas en échec, identifiés par `query_id`. Limiter le premier lot ; inutile de planifier les 32 immédiatement.
2. Dans ces cas, couvrir au moins un lexème fréquent, une union longue, une expression citée et une exclusion si le jeu en comporte. Les IDs exploratoires 01–04 sont des entrées brutes à un mot ; 05–06 sont des expressions citées. Ce sont des repères de forme, pas une attribution des timeouts.
3. Requête IDF et lookup documentaire par `ANY(:ids)` de la section 3.4, pour vérifier les accès PK et écarter un détour inattendu.
4. Seulement si les plans/diagnostics le justifient, requête ANN exacte du service (`tuning/vector.py:L85–95`), avec ses `SET LOCAL hnsw.*` réels. Ne pas la remplacer par la variante vectorielle exacte de `tuning/retrieval.py`.

Pour chaque plan, relever : partition(s) conservée(s), index réellement choisi, `Bitmap Index Scan`/`Bitmap Heap Scan` ou `Seq Scan`, prédicats d’index et filtres résiduels, lignes estimées à l’entrée du tri, largeur, `Sort Key`, `Limit`, éventuels `Gather`/workers et bloc JIT. Vérifier l’absence de sous-plan documentaire de DF dans le chemin public. Un simple `EXPLAIN` ne révèle ni durée effective, ni buffers lus, ni méthode de tri réellement employée, ni nombre réel de revérifications. Il ne prouve donc pas la causalité d’un timeout. Voir [documentation EXPLAIN PostgreSQL 17](https://www.postgresql.org/docs/17/using-explain.html).

Si le driver utilise effectivement des préparations serveur, comparer plus tard le plan dans les mêmes conditions de préparation ; ne pas imposer `force_custom_plan` ou `force_generic_plan` à la production sans besoin établi. Aucun `enable_seqscan=off` ne doit être ajouté au lexical pour « prouver » le GIN : ce réglage est propre à l’ANN dans le code actuel et ses transactions distinctes ne l’appliquent pas au classement lexical.

## 6. Optimisations possibles, par priorité

Les gains sont qualitatifs, **aucun gain de temps n’a été mesuré dans cet audit**. Toutes les propositions restent soumises à validation.

### P0 — Lever l’incertitude, avant modification du moteur

**Problème :** erreurs non attribuables et chronométrage lexical trop agrégé. **Principe :** conserver, y compris en échec, le dernier jalon atteint : préparation, statistiques, classement lexical, hydratation lexicale, configuration ANN, requête ANN, hydratation ANN. Garder une échéance SQL unique de dix secondes ; des jalons internes ne doivent pas réinitialiser `Budget.phase`. Exporter les sous-temps déjà disponibles à la réussite et les temps partiels dans un bloc de terminaison adapté.

**Gain attendu :** aucun gain direct ; permet de choisir une optimisation et de confirmer les timeouts. **Classement :** inchangé. **Coût :** faible à moyen, avec tests d’erreur et d’annulation. **Wallace :** quelques métriques scalaires par requête, sans texte citoyen ni requête SQL supplémentaire de comptage. **Validation :** simulations locales d’échec de chaque branche, puis observation d’une campagne explicitement autorisée. Examiner d’abord d’éventuelles traces déjà disponibles, sans générer de nouvelles requêtes de recherche.

### P1 — Spécialisation exacte du score à un lexème obligatoire

**Problème :** des tests `@@` calculent une information déjà imposée par la sélection. **Principe :** pour le cas strictement prouvé où Q exige le seul lexème positif `t0`, remplacer les deux `CASE WHEN ...` de couverture par leurs branches vraies. Garder exactement les mêmes conversions, parenthèses, coefficients, IDF, normalisation du rang et collation C. Les autres requêtes conservent le chemin général. Ne pas décider sur le seul nombre de mots bruts : il faut la normalisation et la sémantique de Q.

**Gain attendu :** baisse du CPU de couverture sur ces requêtes, amplifiée par un grand nombre de correspondances ; pas de réduction des candidats, lectures, rangs positionnels ou tri. Gain limité si ces derniers dominent. **Classement :** inchangé par construction si la garde est correcte ; vérifier aussi l’égalité numérique des scores. Éviter de réécrire toute la couverture en une constante `0.8`, susceptible de modifier les arrondis. **Coût :** faible. **Wallace :** aucune structure supplémentaire ni pression mémoire prévue ; même SQL de sélection. **Validation :** comparaison exacte des IDs, ordre et scores sur cas synthétiques puis sous-ensemble mono-lexème du jeu de 32 ; inclure exclusions, mots vides et lexèmes absents. Mesurer le temps de classement, pas seulement le temps total.

### P2 — Réduire les répétitions du calcul de couverture général

**Problème :** chaque appartenance est exprimée deux fois. **Principe :** calculer une fois les indicateurs de présence puis les réutiliser dans les deux sommes, sans changer leur ordre d’addition ni les types. Examiner également les termes nécessairement présents du fait des phrases obligatoires, uniquement avec preuve sémantique.

**Gain attendu :** baisse potentielle du CPU sur requêtes multiterme et grand M. **Classement :** exact si expressions et arithmétique restent identiques. **Coût :** moyen ; SQL et vérification du plan. Un alias dans une sous-requête ou un `LATERAL` ne garantit pas une évaluation unique : PostgreSQL peut l’aplatir. À l’inverse, forcer une CTE `MATERIALIZED` pour tous les candidats peut ajouter écritures temporaires, stockage des vecteurs et obstacle au parallélisme. **Wallace :** bénéfice CPU possible, risque mémoire/I/O si matérialisation ; ne retenir qu’une forme mesurée. **Validation :** égalité des scores et ordres sur phrases, exclusions, égalités et 32 requêtes ; nombre d’évaluations/coût via mesures autorisées. Ne pas supposer que le moteur n’effectue déjà aucune simplification.

### P2 — Corriger la planification seulement si les plans le demandent

**Problème :** statistiques PostgreSQL manquantes/périmées, mauvais choix estimé, JIT ou bitmap excessif. **Principe :** après relevés, choisir une intervention ciblée : analyse statistique de la relation concernée dans une fenêtre validée ; cible statistique adaptée ; essai de JIT désactivé localement pour le SQL lexical si la compilation domine ; adaptation locale et plafonnée de mémoire si des pages lossy ou tris temporaires sont effectivement coûteux. La [documentation du planificateur PostgreSQL 17](https://www.postgresql.org/docs/17/runtime-config-query.html) privilégie notamment l’amélioration des statistiques plutôt que le forçage durable des méthodes d’accès.

**Gain attendu :** potentiellement important si une anomalie est confirmée, nul ou négatif sinon. **Classement :** normalement inchangé pour le score déterministe et son ordre total ; contrôler les arrondis et conserver le départage. **Coût :** faible à moyen selon l’intervention. **Wallace :** `ANALYZE` lit des données et consomme des ressources ; il est exclu de cet audit. `work_mem` se multiplie par opération, worker et session ; le site et HNSW partagent 32 Go. Aucune hausse globale proposée. **Validation :** plans comparés, ressources surveillées et essai A/B autorisé ; une seule variable à la fois.

### P3 — Réutiliser l’état vérifié et limiter les transactions redondantes

**Problème :** lectures d’état, identités et acquisitions répétées ; seconde connexion imbriquée dans `_terms`. **Principe :** réutiliser la connexion existante pour `state(connection)` ou transmettre un état validé dans un périmètre transactionnel défini. Conserver vérifications d’identité, empreintes et détection de changement de génération. Éviter un cache global non invalidé qui affaiblirait ces garanties.

**Gain attendu :** réduction des allers-retours, de la pression sur le pool et du coût fixe ; probablement secondaire face à des millions de scores, mais utile si la base est distante. **Classement :** inchangé à corpus constant ; définir explicitement les garanties en cas de publication concurrente. **Coût :** moyen, car le lecteur partagé possède une fonction de sûreté. **Wallace :** moins de connexions et requêtes de métadonnées ; pas de nouvel index. **Validation :** tests de changement de manifeste/génération, séparation des bases, pool, timeout et annulation, puis comparaison des sous-temps de préparation et classement.

### P3 — Éviter des rangs coûteux avec une borne exacte

**Problème :** `ts_rank_cd` calculé pour des candidats incapables de gagner. **Principe :** le score de couverture C est connu et la contribution normalisée du rang est bornée par 0,2 ; un candidat a donc une borne supérieure conservatrice proche de `C+0,2`. Après obtention d’un seuil provenant de K vrais candidats, éliminer seulement ceux dont la borne est strictement inférieure au seuil. Scorer tous les autres avec la formule actuelle. Prévoir marge d’arrondi sûre et traitement des égalités par identifiant.

**Gain attendu :** potentiellement important si la couverture sépare bien les candidats ; nul si les bornes restent proches. **Classement :** peut rester exactement identique avec preuve et borne conservatrice, contrairement à une coupe arbitraire. **Coût :** élevé : algorithme, transactions, bornes numériques et tests. **Wallace :** couvertures toujours à calculer, possibles passes/stockages supplémentaires ; pas automatiquement moins d’I/O. **Validation :** preuve de non-élimination d’un gagnant, jeux adverses et égalités, puis comparaison exhaustive des top-K à la référence sur copie représentative. Ne pas l’introduire en premier sur le site public.

### P4 — Structure lexicale plus étroite ou moteur de top-K indexé

**Problème :** coût de lecture des vecteurs et absence d’accès ordonné au score. **Principe :** étudier une table lexicale dédiée plus compacte si les lectures dominent ; à plus long terme, un index/moteur prenant en charge un top-K avec bornes adaptées à cette formule.

**Gain attendu :** amélioration possible des caches et I/O avec table étroite ; gains plus structurels possibles avec top-K indexé. **Classement :** exact pour une copie fidèle du même vecteur et SQL, pas garanti pour un moteur BM25 ou une autre fonction de score. **Coût :** élevé à très élevé. **Wallace :** duplication, espace disque, WAL, construction, maintenance et pression cache ; aucune création ni reconstruction autorisée ici. **Validation :** prototype sur une copie, parité des vecteurs/scores et capacité sous charge représentative avant tout projet de migration.

### P5 — Préfiltrage approximatif, uniquement en dernier recours

**Problème :** trop de candidats au score pondéré. **Principe existant :** activer `prefilter` pour conserver les premiers documents par `ts_rank_cd` avant calcul pondéré (`lexical.py:L92–99`).

**Gain attendu :** réduit les calculs de couverture sur le sous-ensemble, mais **calcule encore `ts_rank_cd` pour tous les correspondants et ajoute un premier classement** ; une accélération n’est pas acquise. **Classement :** risque explicite et significatif : le rang de proximité n’est pas une borne du score pondéré. Un document excellent en couverture peut disparaître. **Coût :** code faible, qualification de pertinence importante. **Wallace :** double étape de classement et matérialisation bornée. **Validation :** recouvrement et ordre top-50 lexical, effet RRF, jugements de pertinence, cas rares et longs. Le jeu de performances seul ne constitue pas une évaluation de pertinence. Aucun seuil recommandé arbitrairement.

Ne pas remplacer OR par AND, retirer les mots fréquents au-delà des règles actuelles, supprimer les positions ou changer les coefficients pour accélérer : ces modifications changeraient le comportement de recherche. Ni une augmentation des timeouts, ni une réduction arbitraire des profondeurs, ni une modification RRF/HNSW n’est recommandée.

## 7. Première optimisation recommandée

**Ordre de décision : P0, plans estimés, puis P1 comme première modification ciblée du calcul.**

La spécialisation mono-lexème présente une propriété utile : le prédicat sélectionne précisément les documents pour lesquels les tests de couverture valent vrai. Les remplacer par leur résultat connu ne retire aucun candidat et ne modifie ni proximité ni départage. Les entrées à un mot du jeu existant permettent d’examiner ce cas sans inventer un benchmark différent ; leur normalisation exacte reste à relever.

La preuve doit porter sur la requête normalisée, pas sur une supposition concernant la langue. La première implémentation peut se limiter à Q réduit à un unique lexème positif sans phrase ni exclusion ; élargir le domaine plus tard seulement avec une garde et des tests adaptés. Conserver la formule arithmétique dans son ordre actuel permet d’éviter une régression sur les égalités numériques.

Cette recommandation privilégie une modification facile à revoir et à annuler, sans travaux PostgreSQL ni mémoire supplémentaire. **Elle ne réduit pas M et ne traite pas à elle seule les unions longues.** Si les plans ou mesures montrent que les cas critiques sont entièrement dominés par lecture/rang positionnel, son gain sera faible ; il faudra privilégier l’intervention P2 justifiée par ces observations, et non étendre arbitrairement la spécialisation.

## 8. Protocole avant/après sur les mêmes 32 requêtes

**Protocole à exécuter après validation explicite ; aucune étape de charge n’a été lancée.**

### 8.1 Figer les conditions

1. Récupérer le JSON du premier benchmark : mode, ordre, répétitions, empreinte des requêtes, threads, état déclaré des caches, version de code, détails des six erreurs. Vérifier l’identité avec le SHA-256 ci-dessus. Archiver les fichiers sans écraser l’original.
2. Figer corpus/génération, statistiques/empreinte, recette 50/50, coefficients 0,5/0,3/0,2, RRF 60, paramètres ANN existants, budgets et versions PostgreSQL/pgvector/modèle. Une différence d’index HNSW entre campagnes doit être signalée.
3. Faire une seule modification à la fois sur un environnement représentatif, préférablement une copie isolée. Pour un essai Wallace, convenir d’une fenêtre et de critères d’arrêt avec l’opérateur ; surveiller le site et les ressources. Aucun redémarrage, purge de cache, reconstruction d’index ou nettoyage des caches système nécessaire.

### 8.2 Adapter la collecte sans changer la recette

[benchmark_public_search.py](../scripts/benchmark_public_search.py) nécessite plusieurs précautions :

- Le mode `components` appelle directement `service.retrieve`, avec les budgets SQL du service, mais contourne admission du worker, HTTP et hydratation publique (`L165–193`). Il charge aussi son propre modèle. Ne pas le lancer à côté du service sur Wallace sans budget mémoire validé.
- En échec, `components={}` et seul le code d’erreur est conservé (`L179–190`). Il faut une future collecte des sous-étapes et temps partiels ; enregistrer `SearchTimeout.stage` seul ne séparera toujours pas lexical et ANN.
- Le mode HTTP enregistre statut, durée et code d’erreur, pas les temps internes (`L64–82`). Les métriques API de réussite peuvent être corrélées avec un identifiant technique, sans texte de recherche. La route actuelle journalise ces métriques après réussite ; son traitement des timeouts ne produit pas les mêmes métriques (`api_hybrid_search.py:L247–278`).
- Aucun mode ne sauvegarde actuellement les classements permettant de vérifier la parité. Prévoir une sortie de diagnostic restreinte : IDs documentaires, scores lexicaux, rangs de chaque branche, ordre RRF et empreintes ; aucun texte citoyen ou secret.
- Les options ont des valeurs par défaut potentiellement trompeuses : `--repeats=10`, donc 320 recherches et non 32 ; `--users` ne parallélise pas le mode composants, mais est néanmoins écrit dans les métadonnées (`L176–177,210–211,235–240`).
- `--cache-state` est une étiquette déclarative (`L220–240`) : le script ne réalise ni ne vérifie cet état. Les sondes HTTP ajoutent des requêtes sur le site (`L84–100`) ; leur coût doit être accepté. Le premier passage après démarrage ne doit pas être mélangé silencieusement aux passages chauds.

### 8.3 Exécution future graduée

1. Vérifier localement sur données synthétiques la parité de score, départage C, expressions/exclusions et règles de préparation. Les tests existants comparent déjà `TunedSearch` à `FullSearch` sur cinq documents ([test_tuning.py](../rag/tests/integration/test_tuning.py), L51–70) ; ils ne suffisent pas à qualifier un changement sur cinq millions de documents. Ne pas lancer ces tests d’intégration sur la production : leurs fixtures écrivent des données.
2. À conditions comparables, faire d’abord un passage séquentiel de la référence sur **32 requêtes, une répétition**, puis du candidat sur les mêmes 32 dans le même ordre. Cela représente deux passages, à autoriser. Si le premier résultat historique ne contient pas les diagnostics nécessaires, ne pas le traiter comme une référence instrumentée équivalente.
3. Si l’essai initial est acceptable, convenir du nombre de passages complémentaires ; alterner l’ordre référence/candidat pour réduire le biais de chauffe, conserver le même ordre des 32 cas dans chaque passage et séparer première observation/passes chaudes. Ne pas passer directement aux charges 5 ou 20 utilisateurs.
4. Pour valider H1 indépendamment des petites variations ANN, comparer les deux classements lexicaux et refaire hors SQL la fusion avec **la même liste vectorielle capturée**. Conserver aussi une vérification de bout en bout : les résultats HNSW peuvent varier indépendamment de l’optimisation lexicale.
5. Pour un cas où la référence expire, la campagne sous budget ne peut pas fournir son classement exact complet. Comparer si possible à un classement déjà archivé et de même génération ; sinon la parité sur ce cas reste non démontrée. Un calcul de référence supplémentaire sur copie demande une validation distincte ; ne pas augmenter le timeout public pour obtenir cette preuve.

### 8.4 Critères et restitution

Pour chaque `query_id`, produire statut, phase exacte en échec, temps total, encodage, préparation/statistiques, SQL de classement, hydratation lexicale, ANN, fusion, ainsi que différences d’IDs/rangs/scores. Contrôler les 50 éléments de branche, y compris leur frontière, et l’ordre final H1. Pour une optimisation annoncée exacte, **aucune différence de classement lexical n’est acceptable** ; toute différence de score doit être expliquée, même si le rang reste identique.

Mesurer P50/P95 des réussites avec la même convention que le script (`ceil(p×n)-1`, `L23–35`), et publier séparément : taux d’échec sur 32, six cas initialement en timeout, latences sur l’intersection des requêtes réussies avant/après, et latences de toutes les réussites de chaque campagne. Un P95 sur 26 réussites ne décrit pas les six échecs ; une amélioration peut même augmenter le P95 des réussites si elle fait aboutir des requêtes auparavant interrompues. Ne pas remplacer les échecs par dix secondes dans un percentile de réussite.

Relever CPU, mémoire disponible/RSS, swap, I/O, attentes et latence documentaire pendant les seuls essais approuvés ; ne pas réinitialiser les statistiques de production. Utiliser les métriques existantes si disponibles. `rss_peak_bytes` du script ne couvre que son processus, pas PostgreSQL ni tout le site (`L194–200`). Consigner le coût des sondes et arrêter la campagne si les critères convenus sur disponibilité et ressources sont franchis.

Les comptages exacts de candidats et `EXPLAIN (ANALYZE, BUFFERS, ...)` restent hors du protocole initial sans validation spécifique. S’ils deviennent nécessaires, les réserver d’abord à une copie et à quelques cas représentatifs ; ils exécutent effectivement le travail coûteux. `pg_stat_statements` peut aider seulement s’il est déjà disponible, sans installation, activation ou remise à zéro dans cet audit ; ses agrégats ne remplacent pas l’attribution par requête et étape.

## 9. Informations nécessaires pour poursuivre

| Information | Pourquoi elle est nécessaire |
|---|---|
| JSON brut du benchmark, empreinte du jeu, IDs des six échecs, mode exact | Reproduire la campagne et éviter d’attribuer des timeouts sans preuve. |
| Accès identifié à la base Wallace avec rôle lecteur déjà autorisé, ou relevés expurgés par l’opérateur | Confirmer index, plans et paramètres sans chercher ni publier de secrets. |
| Définitions, attachements et validité des index parent/enfant ; tailles heap/index/TOAST | Confirmer la structure réelle et évaluer l’hypothèse I/O/cache. |
| Statistiques du planificateur, dates d’analyse parent/partition, estimations de cardinalité | Détecter une restauration insuffisamment analysée ou des erreurs de sélectivité. |
| Plans estimés du SQL pondéré exact pour cas rapides/lents/échoués | Séparer mauvais accès, cardinalité large, tri et JIT potentiels. |
| Driver et comportement de préparation serveur, paramètres de la session lecteur | Reproduire les décisions du planificateur. |
| Diagnostics partiels conservés en échec | Confirmer si lexical, ANN, hydratation ou contrôles consomment le budget. |
| Ressources réelles et activité concurrente de Wallace lors de la première campagne | Évaluer concurrence CPU/I/O, cache, mémoire et protection du site. |
| Classements de référence de même génération, s’ils existent | Prouver la conservation des résultats, notamment pour les cas interrompus. |

**Décision attendue : validation du rapport et choix du premier essai. Aucune implémentation, collecte distante ou nouvelle campagne n’est engagée par ce document.**
