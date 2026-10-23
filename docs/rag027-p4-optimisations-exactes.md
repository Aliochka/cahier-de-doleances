# RAG-027 P4 — Optimisations exactes du classement lexical H1

23 octobre 2026. **Audit technique et algorithmique uniquement.** Aucun outil, moteur, paramètre, index ou corpus modifié ; aucune requête sur Wallace, aucun benchmark et aucune expérimentation. Seul ce rapport est ajouté.

**Complément du 23 octobre :** la [vérification de dominance OR-A](rag027-p4-dominance-or-a.md) démontre que, pour le domaine H1 précisément défini dans ce complément, tout document complet précède strictement tout incomplet, arrondis compris. Dans ce domaine vérifié, 50 résultats du vrai classement du sous-ensemble complet suffisent : le certificat numérique ci-dessous est redondant. La méthode générale conserve son intérêt lorsque les préconditions de cette spécialisation ne sont pas établies.

## 1. Recommandation exécutive

La priorité est de diminuer les évaluations de `ts_rank_cd`, sous certificat de non-élimination d’un gagnant. Une méthode exacte est démontrable pour H1 : calculer le top-50 du sous-ensemble couvrant tous les lexèmes positifs, puis vérifier qu’une borne supérieure des autres documents est strictement inférieure au score du cinquantième. **Le sous-ensemble ne devient le résultat final que si cette preuve réussit. Sinon, retour au classement original complet.**

C’est la première optimisation dont je recommande une **expérience de faisabilité**, après validation : elle conserve l’appel PostgreSQL de rang et l’expression numérique originale, peut exploiter le GIN existant et n’exige ni nouvel index ni extension. Son gain reste entièrement conditionnel à la sélectivité du sous-ensemble et à la réussite du certificat. Un échec peut au contraire ajouter une recherche au coût initial.

Une seconde piste mérite une preuve numérique dédiée : pour une disjonction pure de lexèmes et des positions toutes de poids A, le rang normalisé se réduit au comptage des positions stockées des lexèmes recherchés. Cette spécialisation pourrait éviter le mécanisme général de couvertures, mais un chemin SQL utilisant `unnest(tsvector)` peut coûter cher et changer le parallélisme. Un chemin natif efficace exigerait une intervention supplémentaire hors du périmètre actuel. Aucun remplacement n’est considéré validé sur Wallace.

Mutualiser les couvertures est moins prioritaire depuis P3 : utile éventuellement, mais cela ne supprime pas le coût dominant associé au rang. Aucun facteur d’accélération n’est annoncé.

## 2. Preuves disponibles et limites

Le contexte transmis indique environ 8,7 s pour 2,54 millions de correspondants sur `democratie-02`, 11 s pour 2,85 millions sur `fiscalite-01`, et un surcoût P3 principalement associé à `ts_rank_cd`. Les couvertures coûtent moins. Ces constats sont ceux de votre campagne ; ses plans bruts et scores détaillés ne sont pas présents dans les rapports relus ici.

Il manque notamment : nombre de lexèmes normalisés et IDF effectifs, scores à la frontière top-50, cardinalité de la conjonction complète, proportion de certificats réussis, distributions des occurrences et profils CPU. Le temps associé au rang comprend ses accès aux données et allocations ; P3 ne mesure pas séparément chacune de ces opérations.

Les sources PostgreSQL examinées sont celles de l’étiquette amont **REL_17_11**. Elles décrivent l’implémentation attendue de PostgreSQL 17.11, pas une vérification du binaire installé sur Wallace. Les variantes de compilation et correctifs du paquet restent à inventorier avant validation native.

## 3. Contrat et formule à préserver

[tuning/lexical.py](../rag/src/cahier_rag/tuning/lexical.py), L23–46 et L62–73, utilise les IDF figées et produit :

```text
P_i(d) = d.search_vector @@ CAST(:t_i AS tsquery)
A(d)   = 0,5 × somme gauche-associative des IDF présentes / total_idf
B(d)   = 0,3 × float8(nombre de lexèmes présents) / nombre de lexèmes
R(d)   = float8(ts_rank_cd(d.search_vector, Q, 32))
S(d)   = (A(d) + B(d)) + 0,2 × R(d)
```

Cette notation ne remplace pas les casts et parenthèses du SQL. Les coefficients viennent de [search/flexible.py](../rag/src/cahier_rag/search/flexible.py), L19. La requête finale, [lexical.py](../rag/src/cahier_rag/tuning/lexical.py), L100–103, applique les filtres et Q puis `ORDER BY score DESC, document_id COLLATE "C" LIMIT 50`. La limite exige de comparer les candidats ; elle ne limite pas à 50 les appels au rang.

La normalisation est [search/preparation.py](../rag/src/cahier_rag/search/preparation.py), L89–125. Les termes positifs uniques alimentent les couvertures ; les phrases et exclusions restent dans Q. Les deux questions lentes du [jeu de développement](../rag/evaluation/performance-rag027.json) n’ont ni expression citée ni exclusion : ce chemin construit une disjonction positive, lorsque sa normalisation est non vide. Le nombre et la valeur exacts des lexèmes ne sont pas inférés de leur texte brut.

[fullcorpus/store.py](../rag/src/cahier_rag/fullcorpus/store.py), L120–126, construit les vecteurs par `setweight(to_tsvector('pg_catalog.french', text),'A')`. **C’est un invariant du producteur inspecté, pas un contrôle exhaustif du corpus installé.** Il conditionne la spécialisation de la section 6.

Le contrat strict du [rapport P3 validé](rag027-p3-composantes-scoring.md#9-contrat-de-parité-proposé-avant-toute-optimisation) reste : mêmes admissibles, mêmes 50 identifiants et ordre, mêmes scores binaires float8, mêmes égalités et collation C. Une élimination certifiée évite de calculer un score sans changer sa définition ni l’admissibilité sémantique du document. La fusion doit être identique à liste vectorielle fixée : [hybrid/core.py](../rag/src/cahier_rag/search/hybrid/core.py), L37–62. Aucun HNSW ou modèle ne doit intervenir dans la validation lexicale.

## 4. Chemin interne du rang et travail évitable

Références dans [tsrank.c REL_17_11](https://github.com/postgres/postgres/blob/REL_17_11/src/backend/utils/adt/tsrank.c) :

| Étape | Fonctions/lignes | Travail identifié |
|---|---|---|
| Entrée | `ts_rankcd_ttf`, L986–997 | Accès au vecteur et à Q ; appel du calcul ; retour float4. |
| Préparation | `calc_rank_cd`, L865–879 | Poids inverses ; allocation initialisée par nœud de Q. |
| Représentation | `get_docrep`, L727–846 | Recherches de lexèmes, collecte des positions, agrandissements, tri positionnel, regroupements et allocations. |
| Couvertures | `Cover`, L645–724 | Parcours avant/arrière, réinitialisations, évaluations de Q ; phrases traitées positionnellement. |
| Contribution | `calc_rank_cd`, L887–920 | Parcours des couvertures, poids et bruit, accumulation du rang. |
| Sortie | L942–949 | Normalisation 32 en double puis conversion float4. |

`QueryRepresentationOperand` contient un tableau de 16 384 positions. Sa réservation est de l’ordre de 32 Kio par nœud de Q, hors autres structures. Cela suggère un coût d’allocation/initialisation à profiler ; ni mémoire résidente cumulée, ni bande passante effectivement consommée ne sont mesurées ici. La taille de Q inclut ses opérateurs.

Ces mécanismes expliquent des pistes, sans attribuer les secondes P3 à une fonction interne précise. Un tri interne des positions ne doit pas être confondu avec le petit tri top-N SQL.

L’accès au type passe par le détoastage : [ts_type.h](https://github.com/postgres/postgres/blob/REL_17_11/src/include/tsearch/ts_type.h), L134–152. Récupération externe et décompression inline/externe suivent des chemins différents dans [detoast.c](https://github.com/postgres/postgres/blob/REL_17_11/src/backend/access/common/detoast.c). Plusieurs fonctions peuvent reprendre ces chemins si leur argument reste toasté ; un alias de colonne ne garantit pas une représentation décompressée partagée. Les hits TOAST ne comptent pas les décompressions. Réutiliser la requête constante n’évite pas de reconstruire sa représentation dépendant du document.

## 5. Réduire exactement le nombre d’appels au rang

### 5.1 Borne générale compatible avec les flottants H1

Notons `fl64` l’arrondi de chaque opération float8, et `r` le résultat float4 du rang, ensuite élargi exactement en float8. Pour le rang PostgreSQL avec poids par défaut positifs, normalisation 32 et entrées valides finies :

```text
0 ≤ r ≤ 1
H(d) = fl64(A(d) + B(d))
S(d) = fl64(H(d) + fl64(w_rank × r))
U(d) = fl64(H(d) + fl64(w_rank × 1::float8))
```

`w_rank` est le paramètre float8 original 0,2. Les opérations non négatives étant monotones, **S(d) ≤ U(d)**. La borne utilise les mêmes opérations et constantes binaires, sans réassociation. La plage normalisée est documentée dans [le classement PostgreSQL](https://www.postgresql.org/docs/17/textsearch-controls.html#TEXTSEARCH-RANKING) ; la borne fermée 1 reste conservative face à l’arrondi float4.

Préconditions à vérifier : IDF finies non négatives, total strictement positif, coefficients H1 attendus, absence de NULL/NaN et de débordement. Il ne faut pas remplacer H(d) par la constante 0,8 : la sommation des IDF au dénominateur n’autorise pas à présumer l’identité binaire avec toute autre association de la somme.

Si 50 documents admissibles ont déjà été évalués exactement et que leur cinquantième score est τ, tout document tel que **U(d) < τ** peut être écarté du calcul positionnel. Leur sous-ensemble suffit à fournir un seuil inférieur ou égal à celui du vrai top-50. Garder U(d)=τ évite toute erreur de départage par identifiant. Aucune coupe fixe de candidats n’est justifiée par cette preuve.

Cette borne est possible, mais peut être peu discriminante : les couvertures ne distinguent pas deux documents ayant les mêmes lexèmes présents. Si U reste au-dessus du seuil pour la majorité, le parcours et les tests sont payés sans éviter beaucoup de rangs.

### 5.2 Certificat par couverture complète : première expérience recommandée

Cette spécialisation évite d’évaluer H pour tous les documents afin de décider de la première coupe.

Soit D l’ensemble admissible original et C son sous-ensemble ayant **tous** les lexèmes positifs. Q, les phrases, exclusions et filtres restent imposés ; la conjonction est une condition supplémentaire de sélection de travail, pas une nouvelle définition de pertinence.

Pour chaque i, calculer `U_i` avec le SQL arithmétique H1 exact, mais en fixant les indicateurs de présence à vrai sauf celui de i, fixé à faux, et le rang à sa borne 1. Poser `U_incomplet = max_i U_i`. Cela demande au plus 32 évaluations de petits arbres constants, pas un parcours documentaire.

**Preuve de majoration.** Tout document de D\C manque au moins un lexème i. Son masque de présence est inférieur ou égal, composante par composante, au masque « tous sauf i ». Avec IDF non négatives et dénominateurs constants positifs, les opérations originales sont monotones, y compris leurs arrondis. Donc son score est au plus U_i, donc au plus U_incomplet. Cette preuve n’utilise ni estimation de fréquence ni hypothèse de proximité.

Procédure conceptuelle à expérimenter :

1. Calculer **le vrai top-50 de C**, avec l’expression de score originale et son départage original. Il faut comparer tous les candidats nécessaires dans C ; ce n’est pas noter seulement 50 documents arbitraires.
2. Si C fournit moins de 50 résultats, revenir au classement complet.
3. Sinon, noter τ son cinquantième score. Si **τ > U_incomplet**, retourner ces 50 résultats : aucun document de D\C ne peut les rejoindre ou les dépasser.
4. Si τ ≤ U_incomplet, revenir au classement original de D. Aucun résultat restreint n’est accepté par défaut.

Les égalités dans C restent départagées exactement ; les égalités avec la borne provoquent le repli. Cas sans lexème, valeurs non finies ou préconditions invalides : aucun raccourci. Une conjonction déjà imposée par Q ou un seul lexème apporte peu ou aucun bénéfice ; ne pas promettre un gain dans ces cas.

**Exactitude et snapshot.** Les étapes et statistiques doivent partager la même version logique du corpus. Deux SELECT en READ COMMITTED peuvent voir des états différents, même dans une transaction. Le futur prototype devra utiliser un seul snapshot cohérent, par exemple une transaction READ ONLY REPEATABLE READ sur la connexion de mesure, ou une instruction unique correctement structurée. Aucun réglage permanent n’est nécessaire. Les transactions parallèles existantes de préparation ne suffisent pas, à elles seules, à démontrer cette cohérence. [Isolation PostgreSQL](https://www.postgresql.org/docs/17/transaction-iso.html).

**Potentiel et risque.** Le GIN existant peut sélectionner la conjonction. Si C est petit et le certificat réussit, beaucoup d’appels au rang disparaissent. Si C reste massif ou le certificat échoue, le gain disparaît et le travail préalable peut dégrader la latence. Les limites publiques, notamment le budget SQL partagé, ne doivent pas être augmentées pour absorber cette régression.

### 5.3 Généralisation et obstacles SQL

Si le certificat global échoue, la borne U(d) peut encore éliminer certains masques de couverture après un seuil fourni par un sous-ensemble. Une exploration de classes de masques, ou de documents par bornes décroissantes, peut s’arrêter lorsque la meilleure borne restante est strictement sous le seuil. C’est un algorithme de recherche avec preuve d’arrêt ; `ORDER BY couverture LIMIT N` suivi d’un reclassement ne constitue pas cette preuve.

En SQL, écrire `WHERE U>=τ AND ts_rank_cd(...) ...` ne garantit pas l’ordre des calculs. Un futur prototype devra imposer le contrôle des appels par une construction appropriée, puis vérifier son exécution. Une branche CASE peut protéger un appel dépendant de la ligne, mais un aplatissement peut dupliquer des expressions. Un alias ou LATERAL ne promet pas un calcul partagé. [Règles d’évaluation](https://www.postgresql.org/docs/17/sql-expressions.html#SYNTAX-EXPRESS-EVAL).

Une CTE matérialisant le **résultat top-50** reste bornée à 50 lignes ; matérialiser les millions de vecteurs ou de masques avant classement ne l’est pas. Même un résultat borné peut demander un scan coûteux pour être produit. Vérifier les branches effectivement sautées, les loops et le parallélisme ; ne pas considérer la seule forme SQL comme une preuve d’économie. [CTE PostgreSQL](https://www.postgresql.org/docs/17/queries-with.html#QUERIES-WITH-CTE-MATERIALIZATION).

## 6. Spécialisation exacte d’une disjonction avec poids A

### 6.1 Déduction algorithmique à vérifier numériquement

Hypothèses restreintes : Q est une disjonction pure de lexèmes uniques et exacts, sans préfixe, restriction de poids, AND, NOT ou phrase ; les positions concernées sont de poids A ; poids PostgreSQL par défaut, normalisation exactement 32.

Posons K la somme des nombres de **positions stockées** des lexèmes de Q présents dans le document. Une entrée sans positions contribue zéro. Ne pas compter les occurrences du texte original : la représentation PostgreSQL plafonne les positions et peut les fusionner. Elle accepte au plus 256 positions par lexème et des positions de 1 à 16 383. Avec au plus 32 lexèmes, K≤8192. [Limites PostgreSQL 17](https://www.postgresql.org/docs/17/textsearch-limitations.html).

Déduction à partir du chemin source de la section 4 :

1. Une occurrence positionnée satisfait seule cette disjonction. Une couverture se réduit donc à une entrée positionnelle ; les K entrées sont consommées successivement.
2. Son poids A vaut exactement 1, son bruit est nul, donc elle ajoute exactement 1 au rang brut.
3. L’accumulation des K unités en double est exacte à cette échelle. La normalisation puis le retour donnent :

```text
rang_brut = K
r = round_float4(float8(K) / (float8(K) + float8(1)))
R = float8(r)
```

Il s’agit d’une dérivation sous hypothèses explicites, **pas d’une parité expérimentalement constatée**. Le cas K=0 donne zéro. Des lexèmes différents à la même position restent des entrées différentes : ne pas faire un `COUNT(DISTINCT position)` entre lexèmes. Les doublons d’opérandes doivent être exclus ou traités conformément au regroupement natif.

Cette transformation préserve les étapes numériques de la division double, du retour float4 et de l’élargissement float8. En revanche, `1−1/(K+1)`, une division entière, une division numeric ou la suppression du passage float4 ne sont pas des remplacements acceptables.

### 6.2 Chemins techniques et limites

Une référence SQL sur petit jeu peut obtenir K depuis les tableaux de positions de `unnest(tsvector)`, en comparant les lexèmes exacts avec une collation appropriée. `length(tsvector)` compte les lexèmes et ne convient pas. [Fonctions de recherche textuelle](https://www.postgresql.org/docs/17/functions-textsearch.html).

Le code de [`tsvector_unnest`](https://github.com/postgres/postgres/blob/REL_17_11/src/backend/utils/adt/tsvector_op.c), L630–710, copie le vecteur et construit lignes et tableaux de positions/poids pour ses entrées. Ce chemin peut être plus lent que le rang natif malgré une formule plus simple ; un sous-plan corrélé peut également déplacer le travail hors des workers. Le même parcours pourrait fournir les présences, mais les CASE et sommes IDF doivent conserver leur ordre original. Une entrée présente sans positions ne doit pas être déclarée absente.

Un chemin natif pourrait détoaster une fois, chercher chaque lexème et lire son nombre de positions, sans construire ni trier toutes les occurrences. C’est un potentiel algorithmique, pas un outil disponible dans ce dépôt. Fonction native, extension ou modification PostgreSQL impliqueraient une nouvelle revue et un environnement isolé ; aucune création ni demande de privilège n’est proposée ici.

Le routage doit vérifier les hypothèses sur Q et la représentation ; un échantillon de vecteurs A ne prouve pas un invariant global. Tout cas non couvert garde `ts_rank_cd` original. Une restriction aux deux identifiants de benchmark ne serait pas une preuve sémantique suffisante.

## 7. Autres stratégies comparées

Les gains du tableau sont des hypothèses ; **aucune optimisation P4 n’a été mesurée**. Les coûts sont relatifs au moteur actuel et à Wallace.

| Stratégie | Mécanisme et garantie | Gain potentiel | Risques et difficulté | Validation nécessaire |
|---|---|---|---|---|
| Certificat de couverture complète | Top-50 de C, borne des documents incomplets, repli si non certifié. Scores natifs conservés. | Élevé si C sélectif et certificat réussi ; négatif possible sinon. | Moyenne : snapshot, double travail en échec, budget partagé. Aucun index nouveau. | Seuil/bornes, fréquence des succès, coût des deux chemins, top-50 binaire et frontières. |
| Bornes par document/classe | Éviter les rangs dont U<τ, sans limite heuristique. | Élevé si beaucoup de masques éliminables. | Élevée : calcul des couvertures partout, ordre d’exploration, appels déplacés/dupliqués, perte de parallélisme. | Nombre d’évaluations évitées et plan réel, coût global et preuve du seuil. |
| Rang spécialisé OR-A | Comptage K, même division double et passage float4 ; repli hors domaine prouvé. | Élevé possible sur les requêtes simples fréquentes. | SQL : moyenne, SRF et allocations coûteuses ; natif : élevée, hors périmètre opérationnel actuel. | Preuve des invariants, comparaison binaire par document, mesure sur plusieurs distributions. |
| Mutualisation des `@@` | Calculer chaque P_i une fois, réutiliser son booléen dans les CASE originaux. | Limité par la part des couvertures ; ne retire pas le rang dominant. | Moyenne : alias aplatis, barrière de calcul, matérialisation et mémoire. | Montrer le partage effectif ; contrôler projections, CPU et parité sans réassociation. |
| Représentation détoastée partagée | Une acquisition par document pour filtre/couvertures/rang, sans perdre positions/poids. | Important seulement si acquisition répétée dominante. | Élevée : alias ou CTE ne garantit pas ce cache ; représentation native et durée de vie à maîtriser. | Attribution du coût, plan/profil autorisé, copies/allocation et mémoire par worker. |
| Réemploi de structures internes du rang | Préparer des éléments de Q invariants, réutiliser les buffers dépendant du document après réinitialisation correcte. | Inconnu, potentiellement notable si allocations dominent. | Très élevée : évolution native, contexte mémoire, réentrance, phrases, version et sûreté parallèle. | Profil CPU, tests PostgreSQL et adverses, parité binaire exhaustive sur cas bornés. |
| Projection compacte / organisation SQL | Limiter les valeurs transportées, préserver filtrage et calcul ; calculs au bon étage parallèle. | Faible à moyen ; le SQL H1 projette déjà identifiant et score. | Faible à moyenne : largeur réellement nécessaire, expressions repoussées au leader. | EXPLAIN complet, workers, lignes, temporaires ; pas seulement forme de la requête. |
| Stockage lexical séparé / occurrences dérivées | Vecteur identique ou compteurs de positions persistés, adaptés au domaine de Q. | Potentiellement élevé sur coût de lecture et OR-A. | Élevée : nouveaux objets, espace disque/RAM, alimentation et invalidation, sauvegardes. Hors contraintes actuelles. | Copie isolée, contenu exact, cohérence transactionnelle et génération, charge de maintenance. |
| Index positionnel / bornes de blocs | Postings avec positions et bornes H1 conservatrices pour éviter des blocs entiers. | Élevé en théorie sur grand corpus. | Très élevée : structure spécialisée, disque, WAL, construction, maintenance ; hors contraintes actuelles. | Preuve de borne pour la formule complète, tests d’index et comparaison exhaustive, modèle de ressources. |
| Cache lexical exact de requêtes fréquentes | Réutiliser le résultat pour même requête normalisée, paramètres, IDF, génération et recette. | Très élevé sur répétitions ; nul à froid. | Moyenne : invalidation, cohérence avec snapshot et mémoire. Pas un cache hybride ANN implicite. | Tests de clés/invalidation/concurrence et résultats binaires ; mesures à froid et à chaud séparées. |
| Partage du scan / parallélisme supplémentaire | Même calcul sur plusieurs processus ou lots, fusion avec départage global exact. | Conditionnel au CPU et à la bande passante. | Moyenne à élevée : plus de ressources et concurrence ; les deux workers existants tournent déjà. | Coût global et latence sous concurrence, pas seulement une requête isolée. Aucun réglage changé ici. |

### 7.1 Ce que les index actuels ne résolvent pas

La [migration rag_0004](../rag/src/cahier_rag/migrations/versions/rag_0004_fullcorpus.py), L24–58, crée la table partitionnée et son GIN lexical. Ce GIN sert à trouver les correspondants ; il ne fournit pas l’ordre composite H1 dépendant de Q et des IDF. Les index GIN textuels ne stockent pas les positions nécessaires à ce calcul de rang ; GiST emploie des signatures avec revérification. Forcer GIN sur des millions de correspondants ne supprime donc pas le calcul des scores et peut aggraver les accès. [Index textuels PostgreSQL](https://www.postgresql.org/docs/17/textsearch-indexes.html).

Un B-tree d’expression ne peut pas couvrir arbitrairement toutes les requêtes et IDF changeantes. Le fait qu’un index permette un ordre pour une expression fixe ne prouve pas qu’il fournisse cet ordre H1. [Index et ORDER BY](https://www.postgresql.org/docs/17/indexes-ordering.html).

[RUM](https://github.com/postgrespro/rum) stocke des positions et propose son propre opérateur de distance. Cette capacité ne démontre ni l’égalité avec `ts_rank_cd(...,32)`, ni l’ordre de la somme H1. Un top-N RUM puis reclassement H1 reste approximatif sans borne d’arrêt certifiée. Installer RUM ou bâtir un index ne fait pas partie de cette mission.

### 7.2 Mutualisation et représentations

Les deux couvertures contiennent chacune m occurrences des mêmes tests, [lexical.py](../rag/src/cahier_rag/tuning/lexical.py), L63–69. Deux occurrences ne prouvent pas deux évaluations physiques ; aucune optimisation ne doit être créditée d’un partage avant observation.

Un masque de booléens peut alimenter les deux sommes originales sans changer les arrondis. Le transformer en une somme de coefficients combinés, remplacer les CASE par une multiplication ou sommer les IDF en agrégation parallèle peut changer les octets du score. Une CTE `MATERIALIZED` est une barrière possible mais non gratuite ; les scans de CTE sont restreints au leader dans un plan parallèle. [Sécurité parallèle PostgreSQL](https://www.postgresql.org/docs/17/parallel-safety.html).

`strip`, reconstruction depuis les seuls lexèmes, BM25, `ts_rank`, autre normalisation ou déplacements de positions ne sont pas des remplacements exacts du rang général. Conserver les mêmes textes ne suffit pas à conserver la même représentation positionnelle ni ses saturations.

## 8. Méthodes qui restent approximatives ou non démontrées

À ne pas présenter comme exactes :

- OR remplacé définitivement par AND sans certificat ; la présence de 50 bons résultats ne borne pas les autres.
- Préfiltrage à N documents par couverture, `ts_rank`, RUM ou ANN ; agrandir N ne transforme pas une heuristique en preuve.
- Élagage à partir de cardinalités estimées, DF, quantiles de fréquence ou observations sur quelques plans ; ce ne sont pas des majorants par document.
- Formule flottante réassociée parce qu’elle est algébriquement égale ; scores proches ou recouvrement top-50 élevé.
- Tri par rang seulement sous prétexte qu’il domine le coût ; les couvertures continuent à participer au score.
- Conclure à un gain important en supprimant `ts_rank_cd` d’un SQL sans consommer un remplacement équivalent.

Le préfiltrage expérimental [lexical.py](../rag/src/cahier_rag/tuning/lexical.py), L92–99, est déjà explicitement approximatif ; H1 public utilise `prefilter=None`, [service/core.py](../rag/src/cahier_rag/search/service/core.py), L179–190. Il ne fournit pas une solution exacte à P4.

## 9. Protocole de validation à préparer après accord

### 9.1 Preuve puis validation locale de l’exactitude

Avant mesure de performance, spécifier le domaine exact de chaque raccourci, ses préconditions numériques, son snapshot et son repli. Tester localement, dans un environnement PostgreSQL isolé autorisé ultérieurement :

- Certificat réussi, échoué, égal à la frontière, C de taille 0/49/50/plus, moins de 50 admissibles globaux, IDF très différentes, masques manquants multiples et valeurs invalides refusées.
- Cas OR-A : K=0/1, occurrences multiples, lexèmes absents, mêmes positions entre lexèmes, positions saturées, 256 positions, 32 lexèmes et tableaux sans positions ; phrases, NOT, préfixes et autres poids doivent déclencher le chemin général.
- Scores comparés par `float8send` et, pour la spécialisation, rang float4 lui-même par sa représentation binaire. Garder l’ordre des additions, casts, divisions et la conversion native float4.
- Comparaison complète sur petits corpus : ensemble admissible, scores par document lorsque calculés, liste ordonnée top-50, égalités et borne de coupure. Une somme agrégée, même identique, n’est pas une preuve.

Une preuve de la borne et des tests de ses arrondis complètent les comparaisons de résultats : tester seulement les documents restants ne prouve pas qu’un gagnant n’a pas été éliminé. Pour le rang spécialisé, l’invariant des poids du corpus doit être démontré par provenance contrôlée ou vérification exhaustive autorisée ; des échantillons ne suffisent pas.

### 9.2 Première expérience de faisabilité du certificat

Sur `democratie-02` d’abord, prévoir un diagnostic distinct, sans intégrer de changement au moteur public :

1. Relever identité/génération, Q, paramètres/types, IDF et réglages effectifs, sous protections P1/P2/P3.
2. Calculer les U_i dans l’arithmétique PostgreSQL originale ; conserver les valeurs binaires et leur maximum privés.
3. Mesurer le classement exact de C avec le GIN existant ou le plan choisi, sans forcer sa stratégie ; récupérer son vrai cinquantième score et sa liste privée.
4. Rapporter le certificat `τ > U_incomplet`, sa marge observée, le nombre de résultats et les limites rencontrées. **EXPLAIN ANALYZE ne retourne pas les scores : un outil futur devra prévoir explicitement leur collecte bornée**, sans hydratation. Le coût d’un SELECT et d’un éventuel EXPLAIN séparé doit être compté, sans le masquer.
5. Si le certificat réussit, comparer au top-50 H1 original sous état cohérent. Sinon, conclure à l’échec de cette première coupe ; ne pas lancer automatiquement un repli coûteux ou une généralisation.

L’outil P3 actuel ne possède pas cette variante : il ne faut pas lui fournir un nouveau nom ou un SQL arbitraire. Ce diagnostic nécessite une nouvelle validation d’implémentation puis d’exécution. Aucune commande Wallace exécutable n’est fournie dans cet audit.

Mesurer ensuite, seulement si la faisabilité est démontrée, **les deux chemins complets** : réussite avec coût du certificat, et échec avec coût du repli, préparation comprise. Une campagne équilibrée avant/après doit garder JIT, work_mem, instrumentation I/O, parallélisme configuré et génération constants ; examiner les workers effectivement lancés, scans, buffers, projections et temporaires. Répéter en alternant les variantes après autorisation, sans vider les caches. Les différences de durée restent des mesures globales, pas des parts CPU exactes par fonction.

Sur les 32 requêtes de développement et cas adverses, conserver tous les échecs et régressions, pas seulement les deux requêtes favorables. `fiscalite-01` ne sera ajoutée qu’après revue de la première expérience. Comparer la fusion RRF avec **la même liste vectorielle archivée**, sans télécharger ni initialiser de modèle.

### 9.3 Sûreté et critères de décision

Conserver le rôle lecteur, READ ONLY explicite, rollback systématique, annulation et timeouts bornés, verrouillage borné, exécution séquentielle et quotas de diagnostics privés. Aucun changement permanent, nouveau privilège ou objet PostgreSQL ; pas de matérialisation de millions de vecteurs. Les métriques publiques et sorties partageables excluent les identifiants, textes, vecteurs et secrets ; les artefacts nécessaires à la parité restent privés.

Accepter une optimisation seulement après preuve des conditions, zéro divergence binaire et de classement dans la validation prévue, économie réelle du chemin complet et coût de repli compatible avec les budgets existants. Un timeout n’est ni un résultat partiel valide, ni une raison d’augmenter arbitrairement le budget.

## 10. Décision proposée

**Première optimisation à expérimenter : le top-50 à couverture complète avec certificat flottant conservateur et repli exact.** Elle répond directement au coût dominant en évitant des appels au rang, garde les scores natifs et possède une preuve simple de non-élimination, incluant les égalités. Sa viabilité se tranche avec les trois données aujourd’hui manquantes : coût/cardinalité de C, score τ et borne U_incomplet.

Si la coupe certifiée échoue ou si C reste trop coûteux, ne pas déployer le changement de prédicat. Passer à la validation de la spécialisation OR-A et à l’étude de son coût d’accès aux positions, avant toute décision native. La mutualisation des couvertures vient ensuite, avec un objectif proportionné à leur coût P3.

Cette recommandation autorise une prochaine étude ciblée après accord ; elle ne constitue ni une implémentation ni une autorisation d’expérimenter sur Wallace.
