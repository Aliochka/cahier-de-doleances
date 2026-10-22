# RAG-027 P2 — Décomposition des coûts lexicaux H1

Date : 22 octobre 2026. **Préparation locale uniquement. Aucun essai P2 ni connexion à Wallace effectué.** Le moteur, les outils EXPLAIN/P1, les index, les données et les configurations PostgreSQL restent inchangés. Les modifications transactionnelles décrites ci-dessous ne seront appliquées que lors d’une exécution future explicitement demandée par l’opérateur.

## 1. Synthèse et état des preuves

Les résultats P1 transmis montrent que les requêtes fréquentes traitent environ 2,54 et 2,85 millions de correspondances pour ne retourner que 50 documents. Le temps dans les scans **ne mesure pas seulement la lecture des pages** : il peut inclure filtrage, décompression des vecteurs et projection du score. Les tris utilisent peu de mémoire et ne débordent pas, mais cela ne prouve pas que les comparaisons top-N ne consomment aucun CPU.

Deux pistes méritent des mesures séparées :

- Sur les requêtes fréquentes, isoler autant que possible la part du filtrage, du score et de la sélection, en contrôlant les changements de plan.
- Sur `fiscalite-05`, vérifier si un bitmap plus précis réduit les revérifications. Les 11 631 pages lossy et environ 143 679 rejets de recheck sont un signal concret ; l’amélioration de cette requête ne résoudrait toutefois pas automatiquement les recherches à 9–11 secondes.

Les chiffres ci-dessous proviennent de la campagne communiquée, pas d’une nouvelle mesure de cet audit :

| Requête | Execution Time P1, JIT actuel | Correspondances approximatives |
|---|---:|---:|
| `fiscalite-05` | 680 ms | 88 815 |
| `democratie-02` | 8 920 ms | 2 541 714 |
| `fiscalite-01` | 11 070 ms | 2 853 648 |

Deux workers ont effectivement participé ; aucun débordement temporaire n’a été observé. Les premiers gains JIT off de 2,6–4,2 % restent descriptifs : ils ne justifient pas à eux seuls une modification générale. La valeur de `work_mem` du lecteur n’est **pas encore vérifiée** par P2 ; les 4 Mo relevés dans une connexion administrative ne suffisent pas.

Première étape recommandée : le relevé léger `work-mem/observe`. Puis une première série B sur le SQL exact, et une série A pour chaque requête fréquente. Examiner les plans avant les séries répétées. Aucune optimisation du moteur n’est implémentée dans cette livraison.

## 2. Audit du SQL actuel et références

### 2.1 Chemin public et préparation

Le service public appelle `TunedSearch(statistics=True, prefilter=None)` puis `lexical(..., limit=recipe.depth)` : [service/core.py](../rag/src/cahier_rag/search/service/core.py), L179–190. Le lexical et l’ANN partagent toujours la phase SQL de dix secondes ; les délais distincts du diagnostic ne changent pas ceux du service.

[search/preparation.py](../rag/src/cahier_rag/search/preparation.py), L65–125 : tokenisation Unicode, retrait de mots génériques, lexèmes produits par `to_tsvector('pg_catalog.french', ...)`, mots libres réunis par OR, contraintes de phrase et exclusions ajoutées par AND. Les expressions citées contribuent aussi à la liste des lexèmes positifs. Ces règles, les limites et la normalisation sont réutilisées telles quelles.

[fullcorpus/search.py](../rag/src/cahier_rag/fullcorpus/search.py), L14–16 et L23–40, définit les filtres et paramètres. Pour H1 public :

```sql
d.space_id = :space
AND (:form IS NULL OR d.questionnaire_id = :form)
AND (:kind IS NULL OR d.unit_type = :kind)
AND (:split IS NULL OR d.historical_split = :split)
AND d.search_vector @@ CAST(:query AS tsquery)
```

Les valeurs sont `space='full'` et les trois filtres NULL. Le `tsvector` est stocké à l’import avec positions et poids A : [fullcorpus/store.py](../rag/src/cahier_rag/fullcorpus/store.py), L120–126. Le GIN est déclaré sur cette colonne dans [rag_0004_fullcorpus.py](../rag/src/cahier_rag/migrations/versions/rag_0004_fullcorpus.py), L24–35 et L48–62. Aucune conversion du texte documentaire en `tsvector` n’est effectuée par la recherche.

### 2.2 Statistiques et score

[tuning/lexical.py](../rag/src/cahier_rag/tuning/lexical.py), L23–46 : sur le chemin public sans filtre, les DF sont lues dans `rag_tuning.term_statistics` et leur manifeste contrôlé. Les IDF sont calculées en PostgreSQL :

```text
w_i = ln(1 + (N - df_i + 0,5) / (df_i + 0,5))
```

Il n’y a pas de comptage documentaire par lexème pendant cette préparation. La branche alternative L47–58 effectue des comptages pour d’autres configurations ; elle ne doit pas être attribuée au public actuel. La préparation statistique est extérieure à l’instruction de classement instrumentée et à son `Execution Time`.

`score_expression()`, L62–73, produit deux sommes développées. Pour chaque lexème `t_i` :

```sql
CASE WHEN d.search_vector @@ CAST(:t_i AS tsquery)
     THEN CAST(:w_i AS float8) ELSE 0::float8 END
```

et, dans la seconde somme :

```sql
CASE WHEN d.search_vector @@ CAST(:t_i AS tsquery) THEN 1 ELSE 0 END
```

La formule complète, avec `I_i` indicateur de présence et `m` nombre de lexèmes, est :

```text
S(d) = 0,5 × somme(w_i × I_i(d)) / somme(w_i)
     + 0,3 × somme(I_i(d)) / m
     + 0,2 × float8(ts_rank_cd(d.search_vector, Q, 32))
```

Les coefficients sont ceux de [search/flexible.py](../rag/src/cahier_rag/search/flexible.py), L19. Les casts `float8`, l’ordre des additions, la division et la normalisation 32 sont conservés dans tous les diagnostics qui évaluent le score.

### 2.3 Classement et sélection

`TunedSearch.lexical`, L75–105, effectue la préparation puis génère, L100–103 :

```sql
SELECT d.document_id, <S(d) développé exactement> AS score
FROM rag_full.documents d
WHERE <filtres et correspondance ci-dessus>
ORDER BY score DESC, d.document_id COLLATE "C"
LIMIT :limit
```

`limit=50`. Aucun plafond de candidats n’est appliqué avant le score. La sélection top-N doit considérer tous les scores des correspondants. Son faible espace mémoire n’élimine ni ces scores ni les comparaisons. Le GIN sert la correspondance, pas cet ordre dépendant de la requête.

L’hydratation est séparée, après le classement, L105 et [fullcorpus/search.py](../rag/src/cahier_rag/fullcorpus/search.py), L43–58. Le diagnostic s’arrête avant elle et n’exporte pas de texte documentaire.

### 2.4 Redondances : constats et hypothèses

**Vérifié :** chaque test de présence apparaît deux fois dans le SQL du score, soit `2m` occurrences, auxquelles s’ajoutent le prédicat global et `ts_rank_cd`. Au maximum contractuel de 32 lexèmes, cela représente 64 occurrences de `@@` dans la projection du score.

**À mesurer :** cela ne prouve pas 64 appels physiques distincts par document. PostgreSQL, JIT et les accès aux valeurs décompressées peuvent mutualiser une partie du travail. Les casts de paramètres constants peuvent aussi être évalués lors de la planification ; leur présence textuelle n’est pas une preuve de conversion par ligne.

**Hypothèse prioritaire :** couvertures et rang positionnel coûtent cher sur plusieurs millions de documents. Des lectures/décompressions répétées du même vecteur peuvent amplifier ce coût. Un alias SQL ou un LATERAL n’assure pas une évaluation unique ; à l’inverse, forcer une matérialisation de millions de vecteurs peut créer un problème de mémoire et de fichiers temporaires.

## 3. Axe A — Expériences de décomposition

Le nouvel outil [decompose_h1_lexical.py](../scripts/decompose_h1_lexical.py) intercepte le classement exact au même point que P1. Il valide son gabarit puis choisit uniquement parmi des transformations fixes. Il n’accepte aucun SQL arbitraire. `<W>` ci-dessous désigne **le FROM/WHERE original**, sans réécriture ; `<S>` le score exact développé par H1.

| Variante | Instruction mesurée | Interprétation et limites |
|---|---|---|
| `filter` | `SELECT count(*) AS matched <W>` | Filtrage exhaustif plus coût d’agrégation ; pas un coût de lecture pure. |
| `score` | `SELECT count(*) AS matched, sum((<S>)) AS score_sum <W>` | Force l’utilisation de S pour les correspondants ; ajoute une somme et peut déplacer la projection dans les agrégats. |
| `top50` | Classement H1 original, ordre et limite 50 compris | Référence exacte pour le SQL de classement. |
| `filter-stream` | `SELECT d.document_id <W>` | Contrôle complémentaire sans agrégat, ni tri, ni limite. |
| `score-stream` | `SELECT d.document_id, <S> AS score <W>` | Contrôle complémentaire évaluant le score sans top-N. |

Les quatre variantes autres que `top50` sont étiquetées `diagnostic_derived=true`. Elles ne constituent pas des variantes de pertinence et ne seront jamais utilisées pour répondre à une recherche. EXPLAIN consomme leurs résultats sans les exporter. Le `count(*)` et la somme sont exécutés, mais **leurs valeurs ne sont pas renvoyées par EXPLAIN** ; les cardinalités du rapport viennent des nœuds, pas d’un second comptage exécuté en coulisse.

Le couple agrégé limite le trafic de tuples dans Gather ; il peut donc préserver une stratégie parallèle plus comparable que le couple de flux. Les variantes de flux servent à vérifier que l’agrégat ne masque pas une différence essentielle. Elles peuvent transférer des millions de tuples entre workers et leader ; ce coût interne ne disparaît pas parce que le client ne reçoit qu’un plan JSON.

Plan proposé :

1. Pour `democratie-02`, exécuter une fois `filter`, `score`, `top50`, avec JIT off constant. Faire de même pour `fiscalite-01`.
2. Comparer les plans avant de répéter : partitions, Seq/Bitmap/Index Scan, prédicats, parallélisme prévu/lancé, cardinalités des scans, buffers, place du score dans les projections, agrégation partielle et Gather/Gather Merge.
3. Si les stratégies sont suffisamment proches, effectuer trois passages en rotation : `filter/score/top50`, puis `score/top50/filter`, puis `top50/filter/score`. Chaque variante occupe ainsi chaque position une fois.
4. En cas de divergence importante, utiliser le couple de flux en corroboration, lui aussi alterné. Ne pas forcer les scans ou le parallélisme pour obtenir artificiellement les plans attendus.

**Pourquoi JIT off pour cette première série A ?** Les paramètres sont ainsi constants et la suppression d’un calcul ne fait pas franchir un seuil de compilation. Une seconde série complète avec `--jit current` peut ensuite rapprocher les observations du fonctionnement habituel, sans mélanger les séries. `jit=on` identique ne signifie pas compilation identique entre des SQL de coûts estimés différents.

Les différences `score − filter` et `top50 − score` sont des écarts observés entre requêtes : agrégation, projection, transfert parallèle, largeur, compilation et plan peuvent changer. Elles ne doivent pas être publiées comme des mesures exactes du CPU du score ou du tri. Même des accès identiques ne suffisent pas à prouver cette équivalence.

## 4. Axe B — work_mem dans la transaction du lecteur

### 4.1 Relevé initial sans classement

`--axis work-mem --variant observe` traverse le chemin de préparation H1 avec le fichier lecteur réel et relève dans la transaction cible :

```sql
SELECT current_setting('work_mem') AS work_mem,
       pg_size_bytes(current_setting('work_mem'))::bigint AS work_mem_bytes,
       current_setting('track_io_timing') AS track_io_timing,
       has_parameter_privilege(current_user, 'track_io_timing', 'SET') AS can_set_io;
```

La variante s’arrête avant le classement, avec statut `observed`, sans plan ANALYZE. Elle lit aussi les métadonnées et statistiques de préparation habituelles. Par défaut, elle ne modifie ni work_mem ni track_io_timing.

Ce relevé est effectué dans une transaction recréant le chemin H1 avec le lecteur, les options de connexion et les sources épinglées. Il ne mesure pas une connexion administrative. Il suppose que le service public emploie bien ce même fichier lecteur ; il ne prétend pas interroger rétroactivement le GUC d’un backend public déjà emprunté. Le code inspecté ne règle pas work_mem : [service/reader.py](../rag/src/cahier_rag/search/service/reader.py), L31–66.

### 4.2 Trois niveaux, SQL identique

Sur `fiscalite-05`, appliquer successivement **dans la seule transaction cible de mesure** :

```sql
SELECT set_config('work_mem', '4MB', true);
-- ou '16MB', ou '64MB'
```

L’outil vérifie les octets effectifs, puis exécute l’EXPLAIN ANALYZE du SQL H1 original avec le dictionnaire de paramètres original. Il vérifie aussi que les autres réglages contrôlés n’ont pas changé. Rollback restaure le réglage initial. La variante `current` est disponible pour un témoin sans SET ; `all` sélectionne uniquement les trois niveaux demandés.

Conserver JIT actuel sur toute la série B pour observer le comportement de H1 ; une série entière JIT off reste possible. Répéter avec rotation des niveaux : `4/16/64`, `16/64/4`, `64/4/16`. Si le plan change, le signal mesure l’effet global de work_mem, pas exclusivement celui du bitmap.

Comparer Execution Time, bitmap exact/lossy, rechecks rejetés, lignes/loops, buffers, workers, JIT effectif, tris et temporaires. Une hausse de précision accompagnée d’une baisse des rejets et du temps, à plan et cardinalité stables, étayerait la piste mémoire du bitmap. Des pages exactes n’interdisent pas toute revérification : certaines contraintes, notamment positionnelles, peuvent encore la nécessiter. Ne pas imposer « zéro recheck » comme critère universel.

`work_mem` est une limite par opération, pas une réservation pour toute la requête. Les workers peuvent avoir leurs propres tris ou hachages ; par exemple, trois tris indépendants plafonnés chacun à 64 Mio représentent potentiellement 192 Mio, hors autres allocations. Le bitmap d’un Parallel Bitmap Heap Scan est partagé : il ne faut pas multiplier automatiquement sa mémoire par le nombre de workers. Les petits heaps top-N n’allouent pas nécessairement leur plafond. Aucun changement global n’est proposé. [Ressources PostgreSQL 17](https://www.postgresql.org/docs/17/runtime-config-resource.html).

## 5. Axe C — Mesures I/O avec les permissions existantes

`track_io_timing=off` empêche d’obtenir les temps des appels I/O par EXPLAIN. Les compteurs de blocs restent disponibles, mais ne séparent pas attente I/O, calcul et cache du système.

Une activation **locale et réversible** est possible avec le même lecteur uniquement si son droit SET existe déjà. `SET LOCAL`/`set_config(..., true)` ne contourne pas les permissions. PostgreSQL 17 réserve ce changement aux superutilisateurs ou aux rôles disposant du droit SET approprié. [Documentation du paramètre](https://www.postgresql.org/docs/17/runtime-config-statistics.html), [vérification du droit](https://www.postgresql.org/docs/17/functions-info.html).

Le mode par défaut `--io-timing observe` se contente de relever l’état et la capacité. L’option explicite `--io-timing if-permitted` :

- conserve un réglage déjà activé ;
- active localement `track_io_timing` si le droit SET est déjà présent ;
- laisse le paramètre désactivé si ce droit manque, avec la raison `no_existing_set_privilege` ;
- n’accorde aucun droit, ne change pas de rôle et n’utilise aucun compte administrateur.

Toute activation locale est vérifiée et annulée par rollback. Ne pas mélanger une mesure I/O activée et une mesure désactivée dans la même comparaison : l’instrumentation a son propre coût. L’empreinte des réglages contrôlés inclut toujours ce paramètre.

Si le lecteur a `off` et aucun SET, **les temps I/O PostgreSQL par requête sont indisponibles avec ce contrat de connexion**. Une activation dans une autre session administrative ne règle pas le backend du lecteur. Passer par un login administrateur puis changer de rôle serait un protocole de sécurité différent, hors de cet outil et à valider séparément ; aucun contournement ni GRANT n’est préparé. Les métriques OS déjà accessibles peuvent corroborer une activité du stockage, mais elles agrègent les processus et la concurrence ; elles ne fournissent pas automatiquement le temps I/O de cette seule requête. Aucune installation, collecte OS privilégiée ou activation globale n’est lancée.

Même avec le chronométrage actif, un `Shared Read Blocks` n’est pas une lecture physique du SSD : le noyau peut satisfaire la demande depuis son cache. Les temps de nœuds sont inclusifs, ceux des workers se chevauchent et les compteurs parents/enfants ne doivent pas être additionnés. Ces limites de P1 restent applicables.

## 6. Outil, protections et rapports

Le nouvel outil importe P1 sans le modifier et vérifie son empreinte, puis les empreintes H1 et du jeu de requêtes. READ ONLY explicite, vérification du rôle et des identités, rollback systématique, timeouts, moniteur d’annulation, arrêt avant hydratation, sérialisation, fichiers privés et limites disque sont conservés. Aucun BGE-M3, HNSW, modèle ou service public n’est initialisé.

Les limites par défaut restent : connexion 1 s, préparation 2 s par instruction, mesure 60 s, cas 90 s, verrou 200 ms. Plafonds : mesure 300 s, cas 360 s, verrou 1 s, 20 répétitions. Aucun retry automatique. Un timeout est enregistré sans inventer de plan partiel ; les cas suivants explicitement programmés peuvent continuer. Une autre erreur arrête le groupe et marque le reste skipped. Les budgets H1 ne changent pas.

Le stockage hérité limite chaque plan et détail expurgé à 4 Mio, chaque rapport global à 8 Mio, la collection à 64 Mio par défaut (32–256 Mio), avec réserve de rapports et contrôle de 512 Mio libres par défaut. Le quota peut arrêter une grande série avant son terme. Ces protections concernent les diagnostics, pas les fichiers temporaires internes de PostgreSQL ni les écritures d’autres applications. Le verrou commun du répertoire parent sérialise les clients P1/P2 qui l’utilisent. En panne disque externe ou arrêt brutal, un dernier statut running signifie résultat non confirmé, jamais succès.

Fichiers :

| Fichier | Contenu et diffusion |
|---|---|
| `rNN-<requête>-<variante>.plan.private.json` | Plan complet, privé. Absent pour le relevé observe ou un timeout. |
| `rNN-<requête>-<variante>.summary.redacted.json` | Nœuds/workers, métriques et présence du score dans les projections, partageable. |
| `manifest.private.json` | Gabarits SQL H1/mesuré, empreintes, types de paramètres, paramètres effectifs avant/après, capacité I/O, phases et transactions. Privé. |
| `summary.redacted.json` | Index des mesures, distinction diagnostic/H1, statuts, paramètres non sensibles et principaux compteurs. |
| `comparison.redacted.json` | Contrôles de comparabilité, empreintes et écarts observés. |
| `comparison.redacted.md` | Tableau lisible partageable. |

Les expressions, valeurs liées et textes documentaires ne sont pas copiés dans les synthèses. Le dictionnaire original de paramètres reste inchangé ; les variantes dérivées n’emploient qu’un sous-ensemble de ses binds, dont les définitions originales sont conservées. Le SQL mesuré et le SQL H1 ont chacun une empreinte : B exige leur identité, A signale leur différence. Le corpus est vérifié à chaque lecture d’état et entre les mesures.

Critères de comparaison :

1. Même requête, génération, SQL H1 source, paramètres, outil, limites et réglages contrôlés. JIT et track_io_timing sont toujours inclus ; seul work_mem est exclu de l’empreinte de contrôle pour B.
2. Même stratégie d’accès documentaire et même parallélisme prévu/lancé ; comparer aussi les cardinalités et les buffers, sans exiger des hits identiques entre deux passes.
3. Pour B, SQL mesuré identique obligatoire. Pour A, signaler les changements d’agrégats, Gather, projections et structure complète, même si les scans sont similaires.
4. Les rechecks sont donnés avec leurs loops ; `recheck_rows_removed_approx` et `candidate_rows_approx` peuvent être affectés par l’arrondi des moyennes PostgreSQL. Les pages bitmap ne sont pas additionnées aux sections des workers.
5. Les écarts sont étiquetés `observed_difference_not_exact_operation_cost`. `controlled_conditions=true` ne prouve ni caches identiques ni coût causal exact. Une valeur absente ne devient pas un zéro mesuré.

## 7. Commandes Wallace, à exécuter séparément après revue

Image : `cahier-de-doleances-app:search-cpu-001`. Réseau : `cahier-de-doleances_cahier-internal`. Lecteur réel : **`/srv/cahier-de-doleances-app/rag/search-reader.env`**. Aucun rebuild, installation, restart ou montage du modèle nécessaire. Les trois scripts approuvés doivent être présents dans le checkout.

Précontrôles sans SQL :

```bash
cd /srv/cahier-de-doleances-app
sha256sum scripts/analyze_h1_lexical.py scripts/explain_h1_lexical.py
test -r rag/search-reader.env
docker image inspect --format '{{.Id}}' cahier-de-doleances-app:search-cpu-001
```

Empreintes attendues : P1 `3d3b9f4cba9530e57cf3cf6f58ce92f4ad4e76a3fe372c06c4f9316735b5e937` ; EXPLAIN `8e7e00ca1a1cafb1e63b7bfd61069a8e585ffe28b3eec702ae117d6c3c401511`.

Fonction Docker commune, sans secret en argument :

```bash
umask 077
mkdir -p /srv/cahier-search/diagnostics

h1_p2() {
  docker run --rm --pull=never --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=16m \
    --network cahier-de-doleances_cahier-internal \
    --user "$(id -u):$(id -g)" \
    --cap-drop ALL --security-opt no-new-privileges:true \
    --memory 512m --memory-swap 512m --cpus 1 --pids-limit 64 \
    --env PYTHONDONTWRITEBYTECODE=1 \
    --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/decompose_h1_lexical.py,dst=/diagnostic/decompose_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/analyze_h1_lexical.py,dst=/diagnostic/analyze_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/explain_h1_lexical.py,dst=/diagnostic/explain_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/rag/evaluation/performance-rag027.json,dst=/diagnostic/queries.json,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/rag/search-reader.env,dst=/run/reader.env,readonly \
    --mount type=bind,src=/srv/cahier-search/diagnostics,dst=/results \
    --entrypoint /opt/venv/bin/python \
    cahier-de-doleances-app:search-cpu-001 \
    /diagnostic/decompose_h1_lexical.py \
    --execute --reader-env /run/reader.env --queries /diagnostic/queries.json \
    --statement-timeout-ms 60000 --case-deadline-seconds 90 --lock-timeout-ms 200 \
    --max-output-mib 64 --min-free-mib 512 --io-timing observe "$@"
}
```

Commencer par le relevé sans classement, puis examiner sa synthèse :

```bash
h1_p2 --axis work-mem --query fiscalite-05 --variant observe \
  --output-dir /results/p2-probe-001
cat /srv/cahier-search/diagnostics/p2-probe-001/summary.redacted.json
```

Premiers essais B, une commande à la fois :

```bash
h1_p2 --axis work-mem --query fiscalite-05 --variant 4MB --jit current \
  --output-dir /results/p2-mem-4-001
```

```bash
h1_p2 --axis work-mem --query fiscalite-05 --variant 16MB --jit current \
  --output-dir /results/p2-mem-16-001
```

```bash
h1_p2 --axis work-mem --query fiscalite-05 --variant 64MB --jit current \
  --output-dir /results/p2-mem-64-001
```

Premiers essais A : choisir une variante par commande pour contrôler le déroulement. Exemple :

```bash
h1_p2 --axis costs --query democratie-02 --variant filter --jit off \
  --output-dir /results/p2-democratie-filter-001
```

Répéter avec `--variant score`, puis `--variant top50`, dans des répertoires distincts ; faire de même avec `--query fiscalite-01`. Les variantes `filter-stream` et `score-stream` sont des contrôles complémentaires, pas des remplacements de la référence.

Après examen des premiers plans, campagnes répétées explicites :

```bash
h1_p2 --axis costs --query democratie-02 --variant all --jit off \
  --repeats 3 --alternate --output-dir /results/p2-democratie-balanced-001
```

```bash
h1_p2 --axis costs --query fiscalite-01 --variant all --jit off \
  --repeats 3 --alternate --output-dir /results/p2-fiscalite-balanced-001
```

```bash
h1_p2 --axis work-mem --query fiscalite-05 --variant all --jit current \
  --repeats 3 --alternate --output-dir /results/p2-mem-balanced-001
```

Chaque commande ci-dessus contient neuf mesures séquentielles ; ne pas les lancer simultanément. `--variant streams --repeats 2 --alternate` prépare le contrôle croisé à quatre mesures. Ne pas réutiliser les répertoires ni les créer à l’avance. Le terminal n’affiche qu’un statut ; code retour 0 pour succès/observe, 1 pour collecte incomplète, 2 pour arguments invalides. Ne pas boucler sur un échec. Les limites Docker concernent le client, pas la consommation des backends PostgreSQL.

L’activation I/O locale n’est pas incluse dans ces commandes. Si le probe révèle un droit SET existant et que ce supplément de mesure est retenu, ajouter explicitement `--io-timing if-permitted` à **toute** une série, dans de nouveaux répertoires.

### Comparaison hors ligne sans lecteur ni réseau

```bash
docker run --rm --pull=never --read-only --network none \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --user "$(id -u):$(id -g)" \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --memory 512m --memory-swap 512m --cpus 1 --pids-limit 64 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/decompose_h1_lexical.py,dst=/diagnostic/decompose_h1_lexical.py,readonly \
  --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/analyze_h1_lexical.py,dst=/diagnostic/analyze_h1_lexical.py,readonly \
  --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/explain_h1_lexical.py,dst=/diagnostic/explain_h1_lexical.py,readonly \
  --mount type=bind,src=/srv/cahier-search/diagnostics,dst=/results \
  --entrypoint /opt/venv/bin/python \
  cahier-de-doleances-app:search-cpu-001 \
  /diagnostic/decompose_h1_lexical.py \
  --compare /results/p2-mem-4-001 /results/p2-mem-16-001 /results/p2-mem-64-001 \
  --output-dir /results/p2-mem-comparaison-001
```

Lire `comparison.redacted.md` et `.json`. Adapter uniquement les répertoires d’entrée pour comparer des essais A individuels ; une campagne groupée produit déjà son tableau. Transmettre les synthèses et détails expurgés ; garder les plans et manifestes privés.

## 8. Hypothèses et optimisations futures, par priorité

| Priorité et piste | Gain potentiel | Risque pour la pertinence et coût de mise en œuvre | Validation nécessaire |
|---|---|---|---|
| 1 — Bitmap moins lossy par work_mem local adapté | Plausible sur `fiscalite-05`, portée limitée au global si les cas lents restent en Seq Scan. Aucun gain chiffré prédit. | Formule et ensemble admissible inchangés ; coût faible, mémoire à maîtriser par opération/processus. | Série B, plan/rechecks/temps répétés ; vérifier ensuite les mêmes top-50, rangs et scores. Ne retenir que la plus petite valeur justifiée. |
| 2 — Réutilisation des tests de présence dans le score | Potentiellement élevée si A confirme une forte part de calcul sur les millions de correspondants. | Peut rester exacte si types et ordre arithmétique sont conservés ; coût moyen. Une sous-requête peut être aplatie ; matérialiser peut coûter plus cher. | Localiser les projections, comparer aux contrôles de flux, puis prototype isolé avec égalité stricte des classements et scores. |
| 3 — Réduire les accès/décompressions redondants au vecteur | Potentiellement élevée si les calculs répètent du travail sur des vecteurs volumineux ; pas encore démontrée. | Mutualisation exacte possible, mais changements d’expression/stockage plus complexes et éventuelle matérialisation. | P2 et, seulement si nécessaire, mesures complémentaires autorisées ; aucun temps I/O exact déduit des buffers seuls. |
| 4 — Élagage exact par bornes du score | Potentiellement important si beaucoup de candidats ne peuvent entrer dans le top-50. | Preuve numérique et gestion des égalités indispensables ; coût élevé. Une coupe approximative ne convient pas. | Borne conservatrice, cas adverses/arrondis et parité complète sur copie représentative avant production. |
| 5 — Simplifications des termes nécessairement présents | Gain ciblé, notamment cas mono-lexème ou contraintes prouvées ; effet limité sur les deux grandes unions étudiées. | Exact si la logique de Q prouve le test vrai et si les opérations flottantes sont conservées ; coût faible à moyen. | Preuve sur Q normalisé, phrases/exclusions, égalité des scores et du départage ; ne pas remplacer arbitrairement toute la couverture par 0,8. |
| 6 — JIT off local | Faible gain initial rapporté, encore sensible au bruit/cache. | Normalement même sémantique ; coût faible. Ne pas confondre réglage de diagnostic et décision d’exploitation. | Série équilibrée et validation de résultats avant changement, sans désactivation globale ici. |
| Faible priorité actuelle — Accélérer le tri ou augmenter sa mémoire | Gain non démontré : top-N petit et sans spill, mais CPU à vérifier par A. | Réécrire le départage peut changer H1. Un nouvel index ordinaire ne fournit pas l’ordre de ce score. | Mesurer d’abord ; garder score DESC et collation C. |

Le stockage lexical plus compact ou un moteur de top-K indexé seraient des chantiers structurels ultérieurs, avec coûts disque, maintenance et qualification importants. Ils ne sont pas nécessaires pour réaliser P2 et n’autorisent aucune modification de schéma dans cette phase.

Une égalité de plans n’est pas une preuve d’égalité des résultats et EXPLAIN ne renvoie pas le classement. Avant toute optimisation annoncée exacte, prévoir une validation distincte des 50 identifiants **dans leur ordre**, de leurs scores et de l’effet RRF sur une même génération ; pas seulement le recouvrement des ensembles. Ne changer ni poids, ni préparation, ni profondeur, ni budgets H1. Aucune hausse globale de mémoire ou de timeout n’est une conclusion de ce rapport.

## 9. Validation locale et conditions de passage

Tests exécutés uniquement localement, avec connexions psycopg2 et sockets interdits, bases simulées et aucun modèle :

```bash
.cache/search-cpu-venv/bin/python -m pytest \
  tests/test_decompose_h1_lexical.py \
  tests/test_analyze_h1_lexical.py tests/test_explain_h1_lexical.py -q
```

Résultat : **104 tests réussis**, dont 32 nouveaux tests P2 et les 72 tests P1/EXPLAIN. Ils contrôlent notamment le SQL/binds H1 identiques pour B, les dérivations bornées de A, la lecture seule, les rollbacks, le relevé du lecteur, les paramètres effectivement appliqués, l’absence de SET I/O sans droit et sans option, JIT constant, timeouts, stockage, expurgation et comparaison hors ligne. Un avertissement de dépréciation préexistant de `fastapi.testclient` est sans rapport avec l’outil. Les vérifications Ruff sont conformes.

Il n’y a pas de validation d’exécution réelle PostgreSQL/Docker dans cette livraison. Les mesures P2 restent à faire sur Wallace après revue. L’analyse de leurs rapports déterminera le premier prototype ; toute modification du moteur ou de PostgreSQL attend une validation séparée.
