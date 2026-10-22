# RAG-027 P3 — Composantes du scoring, accès aux vecteurs et parité

Date : 22 octobre 2026. **Audit et proposition d’instrumentation à valider. Aucun essai sur Wallace, aucun changement du moteur, des outils P1/P2 ou de PostgreSQL.** Seul ce rapport est ajouté. Les gabarits SQL ci-dessous décrivent des expériences futures ; ce ne sont pas des commandes prêtes à lancer.

## 1. Conclusion et décision proposée

Les mesures P2 transmises étayent fortement un coût lié au scoring. Elles ne permettent pas encore de choisir entre tests de présence, calcul positionnel et travail répété sur la représentation du vecteur. La priorité P3 est de mesurer séparément les trois composantes et leurs combinaisons, avec les mêmes filtres et des agrégations comparables, puis de rapprocher ces mesures des compteurs TOAST.

Un fait de code renforce la piste des accès répétés : dans PostgreSQL 17.11 amont, `@@`, `ts_rank_cd` et même `length(tsvector)` passent par l’accès détoasté au vecteur. Le cache de l’attribut dans un slot d’exécution n’est pas une garantie de cache de sa version décompressée entre appels. **C’est une possibilité mécanique vérifiée dans les sources, pas une mesure du nombre de décompressions sur Wallace.**

Proposition de première tranche :

1. Matrice agrégée des composantes sur `democratie-02` et `fiscalite-01`, JIT off constant, sans matérialisation forcée.
2. Relevés légers du stockage et, si les vues sont déjà accessibles, des compteurs TOAST avant/après chaque mesure.
3. Un contrôle `length(tsvector)` et une classification bornée des tailles/compressions, sans exporter de vecteurs.
4. Choix du premier prototype seulement après analyse. Toute réécriture doit ensuite satisfaire un contrat de parité strict ; aucune réassociation de calculs flottants n’est présumée exacte.

L’expérience `work_mem=16MB` et son gain moyen rapporté de 5,1 % sur `fiscalite-05` restent une piste distincte. Aucun réglage permanent n’est retenu, ni appliqué par cette phase.

## 2. Ce qui est connu et ce qui reste ouvert

Les chiffres suivants proviennent du compte rendu P2 fourni, sans nouvelle collecte :

| Requête | Filtrage P2 | Score agrégé | Top-50 H1 |
|---|---:|---:|---:|
| `democratie-02` | 1,217 s | 8,732 s | 8,550 s |
| `fiscalite-01` | 1,224 s | 11,152 s | 10,784 s |

Les variantes ont conservé un Parallel Sequential Scan, deux workers et les mêmes cardinalités par requête. Plusieurs millions d’accès supplémentaires à des blocs déjà en cache ont été observés avec le score. Cela rend peu crédible une explication limitée au petit tri top-N ou à la préparation IDF.

Il manque cependant une attribution des blocs supplémentaires à des relations précises, les distributions de stockage de `search_vector` et des mesures par composante. Les plans et fichiers bruts P2 n’ont pas été relus ici : les constats de campagne sont ceux transmis. Un plan de scan semblable ne garantit pas une projection, une agrégation ou un travail interne identiques.

Les différences entre filtrage et score ne sont pas des temps CPU purs ; les différences négatives entre score agrégé et top-50 ne représentent pas un « coût négatif du tri ».

## 3. Audit du scoring exact

### 3.1 Chemin de production et filtres

[service/core.py](../rag/src/cahier_rag/search/service/core.py), L179–190, instancie `TunedSearch(statistics=True, prefilter=None)` et exécute le lexical avant l’ANN. [tuning/lexical.py](../rag/src/cahier_rag/tuning/lexical.py), L75–103, effectue la normalisation, charge les statistiques, construit le score puis classe les résultats. Le préfiltrage expérimental L92–99 est désactivé dans H1 public.

Les filtres viennent de [fullcorpus/search.py](../rag/src/cahier_rag/fullcorpus/search.py), L14–16 et L23–40 :

```sql
d.space_id=:space
AND (:form IS NULL OR d.questionnaire_id=:form)
AND (:kind IS NULL OR d.unit_type=:kind)
AND (:split IS NULL OR d.historical_split=:split)
AND d.search_vector @@ CAST(:query AS tsquery)
```

Le public emploie `space='full'`, trois filtres NULL et une profondeur 50. Normalisation française, phrases et exclusions restent celles de [search/preparation.py](../rag/src/cahier_rag/search/preparation.py), L89–125. La liste des lexèmes positifs est unique et ordonnée ; elle inclut ceux des expressions citées. Les exclusions participent à Q, pas aux couvertures positives.

En Seq Scan, le prédicat global peut consulter le vecteur de chaque document examiné, y compris les documents rejetés. La projection du score concerne ensuite les correspondants consommés par le classement. Il faut donc distinguer le corpus parcouru, environ 5,17 millions de documents, du nombre de correspondants, environ 2,54 ou 2,85 millions ici.

### 3.2 Trois composantes, sans réécriture

`score_expression()` est défini dans [tuning/lexical.py](../rag/src/cahier_rag/tuning/lexical.py), L62–73. Posons, pour expliquer le code uniquement :

```text
P_i(d) = d.search_vector @@ CAST(:t_i AS tsquery)
A(d)   = :idf_coverage * somme(CASE P_i THEN float8(:w_i) ELSE float8(0))
         / float8(:total_idf)
B(d)   = :term_coverage * float8(somme(CASE P_i THEN 1 ELSE 0)) / :term_count
C(d)   = :frequency_proximity * float8(ts_rank_cd(d.search_vector, Q, 32))
S(d)   = (A(d) + B(d)) + C(d)
```

Les coefficients 0,5/0,3/0,2 sont définis dans [search/flexible.py](../rag/src/cahier_rag/search/flexible.py), L19. L’IDF est calculée une fois par terme depuis les DF figées, avec contrôle du corpus : `lexical.py:L23–46`. Son logarithme n’est pas recalculé par document. Les opérations par document portent sur les tests, CASE, sommes, conversions et rang ; les termes/poids et leurs dénominateurs sont des paramètres constants.

Le code construit une somme gauche-associative des poids sélectionnés et une somme entière des indicateurs, puis réalise les conversions, multiplications et divisions dans cet ordre. Il faut conserver cet arbre arithmétique, pas seulement la formule écrite en notation mathématique.

`ORDER BY score DESC, document_id COLLATE "C" LIMIT 50` apparaît L100–102. Il exige le score des candidats au classement ; la limite n’en plafonne pas l’évaluation. L’hydratation documentaire L105 est postérieure et reste exclue des diagnostics.

### 3.3 Répétitions et évaluations physiques

Pour m lexèmes, la projection contient m tests dans A et les mêmes m tests dans B, plus un appel de rang dans C. Au maximum contractuel m=32, il y a 64 occurrences de `@@` dans la projection, en plus du prédicat global Q.

Trois distinctions sont essentielles :

- Les paramètres `CAST(:t_i AS tsquery)` peuvent être convertis en constantes du plan ; la présence du cast dans le SQL n’implique pas une conversion par ligne.
- La sélection OR/AND peut s’arrêter dès qu’elle détermine le résultat et être réorganisée. Elle ne fait pas forcément le même travail que la somme des m indicateurs. Les CASE ne rendent pas automatiquement les deux ensembles de tests communs.
- Deux expressions SQL identiques ne prouvent ni deux appels physiques, ni un appel partagé. La lecture des `Output` dans EXPLAIN permet de localiser des expressions, pas de compter les appels C internes. [Règles d’évaluation PostgreSQL](https://www.postgresql.org/docs/17/sql-expressions.html#SYNTAX-EXPRESS-EVAL).

Dans l’exécuteur 17.11 amont, chaque nœud d’opérateur/fonction est initialisé en étapes d’évaluation ; l’interpréteur récupère un attribut depuis `tts_values` puis appelle la fonction correspondante. Cela rend plausibles des chemins séparés pour les deux occurrences qui subsistent dans le plan, surtout JIT off, sans constituer une trace des appels de Wallace. Un éventuel état interne d’une fonction n’est pas un cache général des résultats de toutes les expressions. [Initialisation des expressions](https://github.com/postgres/postgres/blob/REL_17_11/src/backend/executor/execExpr.c), [interpréteur](https://github.com/postgres/postgres/blob/REL_17_11/src/backend/executor/execExprInterp.c).

## 4. Accès au vecteur : constats des sources PostgreSQL

Cette section décrit **les sources amont étiquetées REL_17_11**, pas une inspection binaire du paquet installé sur Wallace.

| Opération | Chemin source pertinent | Conséquence vérifiée dans ce code |
|---|---|---|
| `tsvector @@ tsquery` | `tsvector_op.c`, `ts_match_vq`, L2217–2243 ; `checkcondition_str`, à partir de L1298 | Accès au vecteur, exécution de Q, recherche des lexèmes ; libération d’une éventuelle copie. |
| Accès au type | `ts_type.h`, `DatumGetTSVector`, L134–138 et macro L152 | `PG_GETARG_TSVECTOR` passe par `PG_DETOAST_DATUM`. |
| `ts_rank_cd(...,32)` | `tsrank.c`, `ts_rankcd_ttf`, L986–997 ; `calc_rank_cd`, à partir de L850 | Accès au vecteur, représentation positionnelle, calcul des couvertures, normalisation ; résultat retourné en float4, puis élargi en float8 par H1. |
| Valeur externalisée/compressée | `detoast.c`, `detoast_attr`, à partir de L116 | Récupération TOAST si externe et décompression si nécessaire ; le chemin dépend du Datum effectivement fourni. |

Sources : [tsvector_op.c](https://github.com/postgres/postgres/blob/REL_17_11/src/backend/utils/adt/tsvector_op.c), [ts_type.h](https://github.com/postgres/postgres/blob/REL_17_11/src/include/tsearch/ts_type.h), [tsrank.c](https://github.com/postgres/postgres/blob/REL_17_11/src/backend/utils/adt/tsrank.c), [detoast.c](https://github.com/postgres/postgres/blob/REL_17_11/src/backend/access/common/detoast.c).

Si le slot fournit encore un pointeur externe ou une valeur compressée à plusieurs fonctions, ces fonctions peuvent reprendre le chemin de récupération/décompression. Si la valeur est déjà dans une représentation directement utilisable, ce travail est différent. Le fait de récupérer une colonne une seule fois dans un slot ne prouve pas que la copie détoastée produite dans un appel remplace ce Datum pour les suivants.

Il faut séparer les couches de cache : attribut du tuple, buffers PostgreSQL, cache OS et représentation décompressée. Des chunks TOAST retrouvés en shared buffers peuvent encore nécessiter recherches, assemblage, allocation et décompression. Inversement, une valeur compressée inline peut coûter du CPU de décompression sans augmenter les compteurs de la relation TOAST. [Stockage TOAST](https://www.postgresql.org/docs/17/storage-toast.html).

**Hypothèse forte à tester :** les couvertures provoquent plusieurs acquisitions du même vecteur par document. **Non établi :** la proportion de vecteurs concernés, le nombre réel de récupérations/décompressions, leur coût et leur domination sur le calcul positionnel.

## 5. Protocole principal : composantes et combinaisons

### 5.1 Gabarit commun

Réutiliser les paramètres, termes, IDF, FROM et WHERE capturés au point d’interception H1. Générer A, B et C avec les mêmes CASE, types, paramètres et parenthèses que la production, puis vérifier que leur recomposition reproduit le score original avant tout accès de mesure.

Chaque variante agrégée emploie ce gabarit diagnostique :

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS, FORMAT JSON)
SELECT count(*) AS matched, sum((<E>)) AS sink
FROM rag_full.documents d
WHERE <WHERE H1 original, paramètres originaux>;
```

Aucun LIMIT sur les candidats ni remplacement de Q. `sum(E)` impose une utilisation de l’expression : un `count(*)` sur une sous-requête projetant E sans la consommer pourrait permettre sa suppression. Les valeurs de count/sum ne sont pas retournées par EXPLAIN et ne doivent pas être inventées dans le rapport.

| Variante | Expression E | Question testée |
|---|---|---|
| `zero` | `0::float8` | Témoin filtrage + deux agrégats, sans fonction supplémentaire sur le vecteur. |
| `idf` | A inchangé | Coût observé de la couverture pondérée, acquisitions du vecteur incluses. |
| `terms` | B inchangé | Coût observé de la couverture simple, avec les mêmes tests de présence. |
| `rank` | C inchangé | Coût observé du rang normalisé et pondéré, acquisition incluse. |
| `idf-terms` | `(A+B)` | Interaction entre deux couvertures à tests redondants. |
| `idf-rank` | `(A+C)` | Interaction couverture IDF/rang. |
| `terms-rank` | `(B+C)` | Interaction couverture simple/rang. |
| `full` | `((A+B)+C)` exactement comme H1 | Référence agrégée commune avec P2. |

Le témoin `zero` n’est pas exactement le `count(*)` seul de P2 : il ajoute un agrégat float8. Son plan doit être vérifié ; les constantes peuvent recevoir un traitement spécifique. Le couple count/sum et le nombre de colonnes restent néanmoins plus proches des variantes de score que le filtrage seul.

Un témoin `top50` conserve aussi **le SQL H1 complet**, pour relier les agrégats à l’usage réel. Les combinaisons à composantes retirées restent des diagnostics ; elles ne sont jamais proposées comme scores de recherche.

### 5.2 Conditions et déroulement

Pour chaque requête, fixer corpus/génération, source, DF/IDF, paramètres, rôle, JIT off, work_mem effectif et instrumentation I/O. **Ne pas profiter de P3 pour appliquer 16 Mo** : conserver et enregistrer la valeur effective du lecteur dans la série. Ne modifier ni les méthodes de scan, ni le nombre de workers, ni les seuils de planification.

Ordre proposé :

1. Relevés légers, puis un premier passage individuel des huit variantes et du témoin top50, d’abord sur `democratie-02`.
2. Examen des plans avant de poursuivre ; puis même passage sur `fiscalite-01`.
3. Pour les variantes comparables, trois blocs répétés avec ordres prédéfinis et archivés, alternance/inversion des positions pour réduire les effets de chauffe. Chaque variante apparaît une fois par bloc ; trois blocs ne constituent pas un équilibrage complet des huit positions.
4. Si l’incertitude de position reste importante, un carré latin à huit blocs équilibre complètement les huit variantes agrégées. Ce volume supplémentaire demande une validation distincte ; il ne fait pas partie du premier passage.

Ne pas lancer toutes les combinaisons et répétitions automatiquement par défaut. Les deux requêtes ont des populations et distributions de vecteurs différentes : comparer d’abord **à l’intérieur de chaque requête**. Aucun vidage des caches ni redémarrage n’est prévu.

### 5.3 Critères de comparabilité

Avant toute différence temporelle, vérifier :

- Même filtre/paramètres et même génération ; cardinalités et loops cohérents, en distinguant moyennes arrondies et comptages exacts.
- Même partition et stratégie de scan, conditions d’accès/recheck, mêmes workers prévus **et lancés**, participation du leader enregistrée.
- Même organisation Partial/Finalize Aggregate, emplacement de la projection du score, nombre/type d’agrégats, largeur des tuples et volume traversant Gather.
- Réglages identiques hors expression diagnostique ; aucun JIT réellement compilé dans la série off ; pas de spill nouveau.
- Buffers, temps des workers et écarts entre blocs analysés sans additionner les temps inclusifs ni les compteurs parents/enfants.

Les expressions peuvent se déplacer du scan vers un agrégat ou le leader. Les `Output` du plan brut doivent être comparés ; les synthèses n’exposeront que des catégories telles que « présence », « rang » et leur emplacement. Un dessin d’arbre identique ne suffit pas.

On pourra afficher les différences observées et des résidus d’interaction, par exemple `T(idf-terms) − T(idf) − T(terms) + T(zero)`. Ce résidu n’est ni un compteur de mutualisations ni un temps de fonction. Cache, agrégation, allocations et planification peuvent le rendre non nul. **Aucun pourcentage du CPU total ne sera attribué automatiquement à A, B ou C.**

## 6. Distinguer présence, calcul positionnel et accès aux données

### 6.1 Contrôle léger d’acquisition du vecteur

Ajouter seulement après la matrice un diagnostic `touch` :

```sql
SELECT count(*), sum((length(d.search_vector)::float8))
FROM rag_full.documents d
WHERE <WHERE H1 original>;
```

Dans le code amont consulté, `length(tsvector)` accède au vecteur via le même mécanisme de détoastage, puis lit son nombre de lexèmes (`tsvector_length`, L202–208 de `tsvector_op.c`). Il offre un contrôle plus léger qu’une sérialisation texte/binaire ou un calcul de rang.

Ce n’est pas une mesure pure du coût d’accès : fonction, éventuelle copie, cast et somme demeurent. Il s’agit d’un appel supplémentaire par correspondant, contre m tests dans chaque couverture. Un touch peu coûteux ne suffit donc pas à exclure un coût répété m fois. Des variantes à nombres croissants de termes, toujours avec Q complet dans WHERE, pourront ensuite rechercher une tendance ; elles devront être explicitement bornées et identifiées comme diagnostics partiels.

### 6.2 Métadonnées et compteurs TOAST

Relevés à préparer avec le lecteur et les permissions déjà disponibles :

- `pg_class.reltoastrelid` pour `rag_full.documents_full`, tailles des relations et index associés ; aucune lecture de `chunk_data`.
- `pg_attribute.attstorage/attcompression` pour `search_vector`, et `pg_stats.avg_width` si accessible, sans exporter lexèmes ou valeurs fréquentes.
- `pg_statio_all_tables` sur la **partition**, avec `heap_blks_hit/read`, `idx_blks_hit/read`, `toast_blks_hit/read` et `tidx_blks_hit/read` avant/après.
- Horodatages, marqueurs de redémarrage/remise à zéro disponibles et nombre de correspondants approximatif pour contextualiser les deltas.

Exemple de lecture de compteurs à valider, jamais exécutée dans cette préparation :

```sql
SELECT relid, heap_blks_hit, heap_blks_read, idx_blks_hit, idx_blks_read,
       toast_blks_hit, toast_blks_read, tidx_blks_hit, tidx_blks_read
FROM pg_statio_all_tables
WHERE relid = 'rag_full.documents_full'::regclass;
```

Ces statistiques sont cumulatives, peuvent être publiées avec retard et peuvent être mises en cache à l’échelle d’une transaction. Prélever les états dans de courtes transactions d’observation distinctes, avant la mesure puis après son rollback ; pas de troisième connexion occupée pendant les transactions imbriquées H1. Prévoir seulement quelques vérifications retardées et bornées si nécessaire, sans remise à zéro ou forçage de flush. Si une vue est interdite ou un delta ambigu, noter l’indisponibilité plutôt que demander un droit. [Statistiques cumulatives PostgreSQL](https://www.postgresql.org/docs/17/monitoring-stats.html).

Les deltas portent sur les autres activités touchant la relation autant que sur la mesure. La même relation TOAST peut contenir les valeurs de `record` et de `search_vector` ; son existence et sa taille ne prouvent pas que les vecteurs y sont externalisés. Le diagnostic ne sélectionne pas `record`, mais une activité concurrente peut le faire. Des deltas TOAST répétés et cohérents avec les variantes, dans une fenêtre calme, constituent un indice fort, pas une attribution exacte par appel. Des deltas nuls n’excluent ni décompression inline ni retard de publication.

### 6.3 Distribution des représentations

Une tranche séparée peut classer tailles et compressions avec `pg_column_size(search_vector)`, `pg_column_compression(search_vector)` et `length(search_vector)`. Elle ne doit exporter que des effectifs, distributions de tailles et méthodes de compression. La taille stockée seule ne prouve pas le caractère inline/externe ; des informations de stockage de la colonne ne décrivent pas toutes ses valeurs.

Proposition initiale à valider : échantillonnage de blocs `TABLESAMPLE SYSTEM` de faible taux, graine fixée, plafond de 512 correspondants et timeout de deux secondes, sans relance pour compléter un échantillon trop petit. Le taux devra être inscrit dans le manifeste avant exécution. Ce diagnostic de stockage restreint la population : il conserve Q à l’intérieur de l’échantillon, mais **n’est pas une variante de performance pleine population**. Il ne doit pas être soustrait aux durées de la matrice principale. Un échantillon de blocs ou de premiers documents est biaisé et ne suffit pas à estimer précisément la proportion de vecteurs TOAST de tous les correspondants.

### 6.4 Ce qui restera impossible sans autre instrumentation

EXPLAIN standard ne compte pas les appels à `ts_match_vq`, les détoastages, les décompressions ou les octets décompressés. Les buffers ne localisent pas chaque instruction CPU ; les instantanés mémoire après une requête ne comptent pas les allocations transitoires ni celles de tous les workers.

Aucun `track_functions`, extension, fonction de comptage, séquence, instrumentation par écriture, profiler privilégié ou nouvelle permission n’est demandé. Si les preuves convergent sans permettre de départager récupération et décompression, le rapport conservera cette limite. Un profil natif ne sera envisagé que s’il existe déjà un accès autorisé et une validation spécifique ; il ne conditionne pas cette première tranche.

`track_io_timing` reste à son état effectif commun à toutes les variantes. Même s’il est déjà activé, il ne mesure pas le CPU de décompression. L’activer globalement ou élargir les droits n’est pas une solution proposée.

## 7. Premiers résultats attendus : observations discriminantes

Ces résultats sont **des scénarios à rechercher**, sans prédiction chiffrée :

| Observation future | Hypothèse renforcée | Ce qu’elle ne prouve pas |
|---|---|---|
| `idf` et `terms` proches, avec des profils d’accès semblables | Leurs tests/acquisitions communs coûtent plus que les différences d’arithmétique. | Que les fonctions sont appelées exactement m fois ou que l’IDF n’a aucun coût. |
| `rank` nettement plus coûteux à stratégie stable | Calcul positionnel et/ou acquisition de C importants. | Que tout son surcoût est du calcul de positions, sans accès au vecteur. |
| `idf-terms` accroît fortement temps et compteurs TOAST par rapport à chaque couverture | Travail d’acquisition répété plausible entre les deux couvertures. | Une correspondance exacte « une occurrence = un fetch ». |
| Combinaisons proches du maximum des composantes isolées | Réutilisation ou effets de cache possibles ; vérifier aussi agrégats et projection. | Une mutualisation automatique démontrée par PostgreSQL. |
| `touch` provoque des accès TOAST supplémentaires cohérents ; tailles/compressions confirment de grandes valeurs | Coût de récupération/décompression à investiguer prioritairement. | Le nombre exact de décompressions ou leur temps CPU isolé. |
| Peu de deltas TOAST mais couverture coûteuse | Tests, overhead d’appels, valeurs inline compressées ou visibilité statistique limitée à examiner. | Absence de coût de détoastage ou de cache. |

## 8. Optimisations envisageables, classées sous conditions

| Piste | Gain potentiel | Complexité et risques | Condition avant prototype |
|---|---|---|---|
| Mutualiser les booléens P_i entre A et B | Élevé si leurs chemins répétés dominent ; plus limité si C domine. | Moyen. Conserver les mêmes CASE et opérations flottantes. Une sous-requête/LATERAL peut être aplatie et n’apporte aucune garantie seule. | Matrice idf/terms/combinaisons, localisation des projections et preuve du partage dans le plan/prototype. |
| Réutiliser une représentation lexicale acquise une fois | Élevé si les récupérations du vecteur dominent. | Moyen à élevé. Un simple alias de colonne ne promet pas de cache décompressé. Matérialiser un tsvector n’est pas une preuve de cette propriété non plus. | Indices TOAST + contrôle touch ; comparer le coût de création et de consommation de la représentation. |
| Construire une fois la liste des lexèmes pour les tests de présence | Potentiellement utile si elle évite de nombreux accès répétés. | Moyen. Conversion/allocations et recherches linéaires peuvent coûter plus que la recherche dans le vecteur. Validité limitée aux tests exacts de lexème, avec collation maîtrisée ; garder le vecteur positionnel pour C et Q. | Démontrer l’équivalence des booléens, y compris échappements, puis conserver l’arbre arithmétique original. |
| Simplifier les tests logiquement imposés par Q | Gain ciblé ; parfois important sur une requête fréquente particulière. | Faible à moyen. Nécessite une preuve sur le tsquery normalisé, pas les mots bruts. | Tests mono-lexème, phrases, exclusions et égalités ; remplacer uniquement les branches dont la valeur est prouvée. |
| Élaguer avec une borne supérieure conservative du score | Potentiellement élevé si beaucoup de candidats ne peuvent atteindre la frontière top-50. | Élevé. Gestion des arrondis et du départage indispensable ; aucune coupe fixe de candidats. | Comprendre d’abord le coût dominant et définir une preuve de non-élimination d’un gagnant. |
| Cache des classements de requêtes fréquentes | Très élevé sur répétitions exactes, aucun gain sur requête nouvelle. | Moyen à élevé : clé incluant requête, recette, génération, réglages pertinents ; invalidation et place mémoire. | Distinguer cache lexical exact et cache H1 : figer une sortie ANN change la sémantique d’une nouvelle exécution hybride si ce cache n’appartient pas déjà au contrat. Pas de cache silencieux proposé. |
| Optimiser/remplacer le rang positionnel | Potentiel seulement si C domine réellement. | Très élevé pour un remplacement ; changer `ts_rank_cd`, ses positions ou sa normalisation modifie généralement les scores. | Préférer d’abord réutilisation de ses entrées ; remplacement exclu des optimisations dites exactes sans preuve indépendante. |

Un essai de booléens dans une CTE `MATERIALIZED` peut rendre leur calcul explicite, mais ajoute stockage, lecture et parfois temporaires. Les scans de CTE sont restreints au regard du parallélisme. Ce n’est pas le premier essai pleine population : plusieurs millions de lignes peuvent déborder et déplacer le travail vers le leader. Il faut un contrôle avec une barrière comparable et accepter que largeur/plan puissent changer. Une CTE sans matérialisation explicite peut au contraire être fusionnée. [Matérialisation des CTE](https://www.postgresql.org/docs/17/queries-with.html#QUERIES-WITH-CTE-MATERIALIZATION), [sécurité parallèle](https://www.postgresql.org/docs/17/parallel-safety.html).

Ni `strip(tsvector)`, ni `array_to_tsvector` ne remplace le vecteur positionnel de H1 sans altérer le rang. Préagréger les coefficients des lexèmes ou distribuer les divisions dans les sommes peut changer les arrondis, même lorsque l’équation réelle semble identique. Ces transformations ne seront pas étiquetées strictement identiques par simple argument algébrique.

## 9. Contrat de parité proposé avant toute optimisation

Les tests existants [test_tuning.py](../rag/tests/integration/test_tuning.py), L51–70, comparent les couples `(document_id, score)` par égalité Python sur cinq documents synthétiques. Les rapports précédents demandent une égalité stricte ; aucun document unique définissant une tolérance numérique différente n’a été identifié. **Le contrat ci-dessous est donc une formalisation proposée à valider, sans assouplissement implicite.**

### 9.1 Admissibilité et classement lexical

- Q, termes positifs, DF/IDF, filtres et génération identiques. Préserver le domaine admissible ; une cardinalité approximative égale ne prouve pas l’égalité des ensembles.
- Même liste ordonnée des 50 identifiants, même ordre score DESC puis collation C, même gestion des requêtes vides et des égalités.
- Contrat numérique conservateur proposé : égalité des octets float8 du score final retourné par PostgreSQL (`float8send`) ou représentation binaire équivalente côté client. Aucun epsilon, arrondi décimal ou budget ULP par défaut. Cette exigence distingue même les zéros signés ; elle est plus explicite que l’égalité Python actuelle.
- Conserver l’élargissement du résultat float4 de `ts_rank_cd` en float8 au même endroit, l’ordre des sommes, les casts et le regroupement `(A+B)+C`. L’ordre de visite des documents ne doit pas changer les opérations internes au score d’un document.

La somme agrégée `sum(S)` est un témoin de performance, **pas une preuve de parité numérique par document** : son ordre de réduction parallèle peut varier. Une somme ou un hash non ordonné des scores n’est pas un substitut à la comparaison des documents et rangs.

La validation future devra inclure tous les candidats pertinents pour vérifier la frontière, et pas seulement comparer les 50 documents communs. Une vérification complète ou des écarts d’ensemble/score sur copie représentative pourra être autorisée séparément. Ce contrôle coûteux n’est pas ajouté automatiquement à la première campagne P3.

### 9.2 Fusion RRF

[hybrid/core.py](../rag/src/cahier_rag/search/hybrid/core.py), L37–62, fusionne les rangs par fractions exactes `1/(60+rang)` et départage par identifiant. À liste vectorielle identique, la liste lexicale doit produire exactement les mêmes rangs, scores et identifiants RRF.

Pour isoler l’optimisation lexicale, réutiliser **la même liste vectorielle archivée**, de même génération ; ne pas attribuer une variation HNSW à la transformation lexicale. Aucun modèle ou HNSW n’est chargé pour les diagnostics P3. Les validations hybrides et leur fixture vectorielle feront partie du protocole de parité distinct.

### 9.3 Cas de validation et conditions d’acceptation

Prévoir les 32 requêtes de développement existantes et des cas adverses synthétiques : lexème seul, termes fréquents/rares/absents, 32 lexèmes, répétitions avant normalisation, phrases, exclusions, apostrophes, accents, longues réponses, nombreuses positions et égalités proches de la coupure. L’échantillon de cinq documents actuel ne suffit pas.

Si un candidat exige une tolérance numérique, il doit être classé comme contrat différent et soumis explicitement à revue, même si les premiers top-50 sont identiques. Aucun changement public n’est accepté sur la seule base d’un gain de temps ou d’un recouvrement d’ensembles.

## 10. Proposition d’instrumentation à valider

**Aucun outil P3 n’est implémenté dans cette livraison.** Les outils P1/P2 restent utilisables pour leurs variantes existantes, mais ne savent pas encore exécuter la matrice ci-dessus. Ne pas leur passer de nouveaux noms de composantes.

Après validation du périmètre, préparer un outil diagnostique distinct ou une extension isolée de l’émetteur de variantes, sans modifier H1 :

- Capturer l’appel final réel de `TunedSearch.lexical` et son dictionnaire de paramètres ; reconstruire les seules composantes autorisées, vérifier la recomposition exacte et refuser toute divergence ou SQL arbitraire.
- Réutiliser empreintes des sources et du corpus, rôle lecteur existant, READ ONLY explicite, rollback systématique, annulation et exécution séquentielle.
- Garder les limites P1/P2 : préparation 2 s, mesure 60 s et cas 90 s par défaut ; plafonds 300/360 s, verrou 200 ms par défaut ; aucune hausse des budgets publics ni retry.
- Conserver quota de diagnostics, répertoires 0700/fichiers 0600, écritures atomiques et réserve de rapports ; aucun tableau de taille corpus ou fichier par document. Les éventuels temporaires SQL ne sont pas couverts par le quota des fichiers clients : pas de matérialisation pleine population par défaut.
- Proposer des mesures individuelles, puis des blocs explicitement sélectionnés. La matrice complète, les répétitions, le contrôle touch et la classification échantillonnée doivent avoir des sélections distinctes.
- Ajouter une liste fermée de lectures de métadonnées/compteurs, sans exporter de contenu de vecteur, de texte, de valeurs de lexèmes, de `chunk_data` ou de secrets. Si une lecture est interdite, produire `unavailable`, sans changer les droits.

Rapports proposés :

| Sortie | Contenu |
|---|---|
| Manifeste privé | Sources, SQL H1 et diagnostic, types/empreintes des paramètres, génération, réglages effectifs, m, ordre des blocs, horodatages et statuts. |
| Plan JSON privé | Plan complet, sorties des expressions, nœuds, workers, buffers, agrégats, JIT et temporaires. |
| Détail expurgé | Temps inclusifs, lignes/loops, accès, catégories de projections, compteurs bruts et leur disponibilité ; aucune expression avec valeurs. |
| Tableau comparatif | Query ID, composante, bloc/position, durée, cardinalité approximative, workers, buffers et deltas TOAST contextualisés. |
| Analyse | Dispersion/médianes par variante et requête, changements de plan, activité concurrente connue et statut de comparabilité ; aucun pourcentage CPU fictif par fonction. |

Les snapshots cumulés seront étiquetés comme observation relationnelle globale avec fenêtre temporelle, retard possible et éventuelle contamination. Ils ne seront pas présentés comme des compteurs privés du backend de mesure.

Tests locaux à prévoir avec l’outil : fidélité des fragments et binds, consommation des expressions, refus des SQL inconnus, invariance du filtre, lecture seule/rollback/timeouts, non-chargement du modèle, expurgation, limites de stockage, détection de changements de plan, statistiques absentes/remises à zéro/retardées et aucun retry. Les essais de parité devront être séparés des sommes diagnostiques.

**Validation attendue : matrice initiale, relevés TOAST accessibles, témoin touch, portée de l’échantillonnage et contrat numérique. Aucune expérimentation sur Wallace ni intervention sur le moteur n’est engagée par ce rapport.**
