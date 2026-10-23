# RAG-027 — P5 : comparaison de ts_rank_cd et ts_rank sur Wallace

État au 23 octobre 2026 : **outil préparé et testé localement uniquement. Aucune connexion, copie de fichiers, commande ou campagne exécutée sur Wallace.** Les commandes d’exécution ci-dessous attendent l’accord de l’utilisateur. Aucun moteur public, outil P1/P2/P3, index ou donnée n’est modifié.

## Périmètre et fidélité SQL

Le nouvel outil [compare_h1_rank.py](../scripts/compare_h1_rank.py) importe les protections historiques P3 → P2 → P1 → EXPLAIN et vérifie leurs empreintes, celles des sept sources H1 épinglées, du catalogue de requêtes et des pilotes SQLAlchemy/psycopg2. Aucun modèle, serveur d’inférence ou extension n’est utilisé.

Les deux seules requêtes autorisées sont `democratie-02` et `fiscalite-01`, issues du catalogue `rag/evaluation/performance-rag027.json`. Les valeurs ≈ 8,7 s et ≈ 11 s servent de contexte ; ce ne sont pas des résultats P5. La génération effective du corpus, dont le nombre de documents, est relevée depuis le manifeste vérifié. Le diagnostic porte sur l’espace `full` (5 172 356 documents attendus), sans nouveau comptage pleine table.

Le SQL est intercepté sur l’appel final **réel** de `TunedSearch.lexical()`, après sa préparation, normalisation, lecture des DF et calcul IDF. L’identité du code appelant, du dictionnaire de paramètres, le gabarit complet SELECT/WHERE/ORDER/LIMIT et la recomposition du score sont contrôlés. Un SQL arbitraire ou un classement appelé depuis un autre contexte est refusé avant le pilote.

Deux variantes fermées :

```sql
-- original : SQL H1 inchangé
:frequency_proximity * ts_rank_cd(d.search_vector, CAST(:query AS tsquery), 32)::float8

-- ts_rank : seul le nom de la fonction change
:frequency_proximity * ts_rank(d.search_vector, CAST(:query AS tsquery), 32)::float8
```

L’outil exige exactement une occurrence du fragment attendu et vérifie la réversibilité de sa substitution. Il conserve les paramètres Python et les définitions de binds SQLAlchemy, le cast float8, les coefficients 0,5 / 0,3 / 0,2, les deux couvertures, tous les filtres, l’ordre `score DESC, document_id COLLATE "C"`, la limite 50, les statistiques matérialisées et l’absence de préfiltrage. Il ne reconstruit pas une formule approximative. Les deux gabarits et leurs empreintes sont enregistrés dans le manifeste privé ; les valeurs liées ne sont jamais exportées dans les synthèses.

Le seul préfixe ajouté pour l’instrumentation est celui de P1 :

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS, FORMAT JSON)
```

Il exécute réellement le classement. L’exception de capture interrompt ensuite H1 avant l’hydratation : aucun texte documentaire, embedding ou résultat de recherche n’est exporté. Cette campagne mesure **le classement lexical SQL instrumenté**, pas l’encodage BGE-M3, la fusion RRF ni la requête publique complète. La variante est une recette différente, pas une optimisation de parité des classements.

## Protections et limites

- Fichier lecteur explicite, chargé sans variables de connexion ambiantes ; aucun repli sur `DATABASE_URL`.
- Rôle lecteur vérifié sur chaque connexion ; bases source/cible et génération vérifiées avec les gardes existantes.
- `SET TRANSACTION READ ONLY` en première instruction de chaque transaction et vérification de l’état effectif ; rollback systématique, succès et échec inclus.
- Aucun `SET` de JIT, work_mem, parallélisme, track_io_timing ou autre réglage de planification. **La valeur existante de JIT est acceptée aussi bien à on qu’à off.** Les réglages collectés sont comparés avant/après et leur empreinte intervient dans l’appariement.
- Seuls READ ONLY et les timeouts de la connexion diagnostique sont fixés localement. Aucun réglage global ou persistant, aucun changement des droits, aucune purge des caches ou des statistiques.
- Pas de retry automatique. Après un timeout, seule la prochaine mesure déjà programmée peut démarrer. Une erreur autre qu’un timeout arrête la campagne et marque le reste `skipped`.
- Aucun nouveau modèle, extension, dépendance, rebuild d’image ou déploiement du moteur.

| Limite | Par défaut | Plafond |
|---|---:|---:|
| Connexion / attente pool | 1 s | Fixe, hérité |
| Préparation avant configuration de la mesure | 2 s par instruction | Fixe |
| Classement diagnostique | 60 s | 300 s |
| Échéance d’un cas, préparation incluse | 90 s | 360 s |
| Attente de verrou | 200 ms | 1 000 ms |
| Paires mesurées par requête | 4 | 20 |
| Paires de réchauffement | 1 | 2 |
| Sorties d’une campagne | 128 Mio | 256 Mio |
| Réserve de disque libre | 512 Mio | Plancher 64 Mio |

Le timeout effectif de chaque instruction est plafonné par le reliquat du cas ; le moniteur de budget peut annuler la connexion active. Le `SET LOCAL statement_timeout='30s'` historique n’est pas transmis. Chaque cas a un budget propre ; les répétitions explicitement programmées constituent la campagne, sans renouvellement interne d’une recherche. Au réglage par défaut, dix cas donnent un plafond cumulé de budgets de cas de 900 s par requête, auquel s’ajoutent les écritures et ouvertures/fermetures de connexion hors cas. Ce n’est pas une échéance globale de processus.

**Le budget SQL public de 10 s reste inchangé.** Le diagnostic a son propre plafond de 60 s pour pouvoir observer un original plus lent que 10 s et examiner son plan complet. Il indique les succès instrumentés au-dessus de 10 s comme repère ; cela ne prouve pas qu’une recherche publique passerait ou échouerait son budget, compte tenu de l’instrumentation et des autres étapes.

Les sorties héritent des répertoires 0700, fichiers 0600, création exclusive, écritures atomiques et verrou `.h1-analyze.lock` commun au parent des diagnostics. Un répertoire de sortie existant est refusé. Chaque plan et détail est limité à 4 Mio ; chaque rapport global à 8 Mio. Le quota et la marge libre sont contrôlés avant chaque mesure. Un nombre élevé de répétitions peut épuiser le quota : arrêt explicite, jamais troncature ni purge des anciennes sorties. Les quotas clients ne bornent pas les temporaires PostgreSQL ; `temp_file_limit` existant est seulement observé.

## Répétitions et lecture des résultats

Par requête, la séquence par défaut comprend :

1. Une paire de réchauffement : original, puis ts_rank. Plans et statuts conservés, exclus des agrégats.
2. Quatre paires mesurées : **original / ts_rank ; ts_rank / original ; original / ts_rank ; ts_rank / original**.

Les mesures sont séquentielles, avec transactions neuves. Elles ne constituent pas un test à cache froid ; ni les buffers PostgreSQL ni le cache du système ne sont vidés. Les premières observations et les deux ordres restent visibles. Une autre charge sur Wallace peut affecter les résultats ; les empreintes égales ne suffisent pas à exclure ce biais.

Les synthèses fournissent, par variante : effectifs programmés, succès, timeouts, erreurs et mesures sautées ; médiane, minimum et maximum des temps d’exécution réussis ; nombre de succès au-delà de 10 s. Les colonnes individuelles conservent temps de planification/exécution, workers prévus/lancés, buffers partagés et temporaires. Les détails expurgés contiennent l’arbre du plan, les temps des nœuds/workers, les compteurs I/O disponibles, tris et phases JIT.

Un gain apparié n’est calculé que si les deux mesures réussissent et si leurs empreintes SQL original, paramètres, génération, réglages, outil et limites coïncident. Le SQL mesuré diffère volontairement entre les variantes. L’outil présente :

- `gain_percent = 100 × (1 − temps_ts_rank / temps_original)` : positif = plus rapide ;
- `delta_ms = temps_ts_rank − temps_original` : positif = régression ;
- médiane/minimum/maximum des gains appariés, nombre de régressions et médiane séparée selon l’ordre AB ou BA ;
- changements d’accès, de workers et de structure du plan. Pour ce dernier contrôle, seul le nom `ts_rank_cd` est normalisé en `ts_rank` dans les expressions structurelles : une simple différence de nom ne constitue pas un changement de plan.

**Un timeout n’a ni temps SQL exact ni plan partiel inventé.** Son statut, sa phase, sa durée client et son plafond effectif sont conservés. Il est exclu des calculs de gain ; la médiane des seuls succès peut donc être biaisée. Si l’original échoue et ts_rank réussit, conserver cette observation mais ne pas inventer un ratio. Un SQLSTATE 57014 peut aussi correspondre à une annulation externe. Les erreurs publiées sont des codes fermés, jamais le message brut PostgreSQL.

Les temps de nœuds et workers sont inclusifs et se recouvrent : ne pas les additionner. Les buffers globaux viennent de la racine, sans sommer parents/enfants/workers. Une métrique absente reste absente ou null. Les compteurs TOAST globaux P3 ne sont pas recollectés : ils ne sont pas nécessaires à cette comparaison du classement complet.

Quatre paires constituent un premier diagnostic, pas une preuve de significativité statistique ni un test de charge. Après examen, une nouvelle campagne peut explicitement demander davantage de paires équilibrées avec un nombre pair de répétitions. Toute extension au catalogue de requêtes est hors de ce premier outil.

## Sorties

| Fichier | Contenu |
|---|---|
| `manifest.private.json` | Sources, SQL, types/empreintes de paramètres, génération, réglages, budgets, phases et rollbacks. Privé. |
| `<phase>-<paire>-<variante>.plan.private.json` | Plan brut complet, susceptible de contenir constantes et expressions. Privé. |
| `<phase>-<paire>-<variante>.summary.redacted.json` | Projection positive des métriques et de la structure, détails workers/JIT/buffers. |
| `comparison.redacted.json` | Mesures expurgées, effectifs, agrégats, conditions d’appariement et gains. |
| `comparison.redacted.md` | Tableau et synthèse lisibles. |

Les synthèses omettent textes de requêtes, lexèmes, paramètres liés, URL, secrets, expressions Output/Filter/Index Cond/Recheck Cond et clés de tri. Les noms techniques de relations/index restent visibles. Partager uniquement les fichiers `*.redacted.*` après vérification ; conserver le parent privé.

## Commandes prêtes pour Wallace — à utiliser après accord

Les cinq scripts diagnostiques doivent être disponibles sous `/srv/cahier-de-doleances-app/scripts/`. Seul `compare_h1_rank.py` est nouveau ; les quatre autres doivent conserver leurs empreintes. Aucun transfert n’a été effectué dans cette livraison.

Précontrôles sur Wallace, sans requête SQL et sans affichage des secrets :

```bash
cd /srv/cahier-de-doleances-app
sha256sum scripts/compare_h1_rank.py scripts/components_h1_lexical.py \
  scripts/decompose_h1_lexical.py scripts/analyze_h1_lexical.py \
  scripts/explain_h1_lexical.py rag/evaluation/performance-rag027.json
test -r rag/search-reader.env
docker image inspect --format '{{.Id}}' cahier-de-doleances-app:search-cpu-001
docker network inspect --format '{{.Name}}' cahier-de-doleances_cahier-internal
```

Empreintes historiques attendues (P5 vérifie toute la chaîne) :

```text
components_h1_lexical.py  56ed64dfb9d765609c29b34f4d8224bfc8971eb8115326b852bca50b67e97777
decompose_h1_lexical.py   0c4474464e8389cd537ccb82533d87f1678b3dc87c5c968c77e434d4b803039d
analyze_h1_lexical.py     3d3b9f4cba9530e57cf3cf6f58ce92f4ad4e76a3fe372c06c4f9316735b5e937
explain_h1_lexical.py     8e7e00ca1a1cafb1e63b7bfd61069a8e585ffe28b3eec702ae117d6c3c401511
performance-rag027.json  f1ad4fef0eae346ce9a2413426ecf7214406440d0e89ea4821fe6913e2e7583e
```

Le SHA du nouveau script doit correspondre à celui du livrable local approuvé, obtenu avec `sha256sum scripts/compare_h1_rank.py`. Il est également inscrit dans le manifeste de chaque campagne.

Le compte opérateur doit déjà disposer de la lecture du fichier lecteur et de l’écriture du parent privé. Aucun élargissement de permissions n’est proposé. Définir la fonction suivante sur Wallace :

```bash
umask 077
mkdir -p /srv/cahier-search/diagnostics

h1_rank_p5() {
  docker run --rm --pull=never \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=16m \
    --network cahier-de-doleances_cahier-internal \
    --user "$(id -u):$(id -g)" \
    --cap-drop ALL --security-opt no-new-privileges:true \
    --memory 512m --memory-swap 512m --cpus 1 --pids-limit 64 \
    --env PYTHONDONTWRITEBYTECODE=1 \
    --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/compare_h1_rank.py,dst=/diagnostic/compare_h1_rank.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/components_h1_lexical.py,dst=/diagnostic/components_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/decompose_h1_lexical.py,dst=/diagnostic/decompose_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/analyze_h1_lexical.py,dst=/diagnostic/analyze_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/explain_h1_lexical.py,dst=/diagnostic/explain_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/rag/evaluation/performance-rag027.json,dst=/diagnostic/queries.json,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/rag/search-reader.env,dst=/run/reader.env,readonly \
    --mount type=bind,src=/srv/cahier-search/diagnostics,dst=/results \
    --entrypoint /opt/venv/bin/python \
    cahier-de-doleances-app:search-cpu-001 \
    /diagnostic/compare_h1_rank.py "$@" \
    --queries /diagnostic/queries.json \
    --repeats 4 --warmups 1 \
    --statement-timeout-ms 60000 --case-deadline-seconds 90 --lock-timeout-ms 200
}
```

Afficher le calendrier sans ouvrir de connexion PostgreSQL :

```bash
h1_rank_p5 plan --query democratie-02
h1_rank_p5 plan --query fiscalite-01
```

Après accord, exécuter d’abord la campagne démocratie seule, puis examiner ses rapports avant d’engager fiscalité. Les répertoires finaux doivent être nouveaux ; ne pas les créer à l’avance.

```bash
h1_rank_p5 run --execute --query democratie-02 \
  --reader-env /run/reader.env \
  --output-dir /results/p5-01-democratie02-rank
```

```bash
h1_rank_p5 run --execute --query fiscalite-01 \
  --reader-env /run/reader.env \
  --output-dir /results/p5-02-fiscalite01-rank
```

Les deux appels représentent chacun dix classements SQL réels au réglage par défaut. Le flag `--execute` est obligatoire pour `run`. Ils ne modifient pas le moteur servi par l’application. Le code retour est 0 uniquement si tous les cas, réchauffements inclus, réussissent ; 1 signale notamment un timeout, une mesure sautée ou un refus. Les détails restent dans les rapports. Ne pas relancer automatiquement un code 1.

Lire uniquement les synthèses pour une première inspection :

```bash
cat /srv/cahier-search/diagnostics/p5-01-democratie02-rank/comparison.redacted.md
cat /srv/cahier-search/diagnostics/p5-02-fiscalite01-rank/comparison.redacted.md
```

## Validation locale

Les tests [test_compare_h1_rank.py](../tests/test_compare_h1_rank.py) bloquent explicitement les connexions psycopg2, les sockets et l’hydratation documentaire. Ils vérifient la substitution exacte avec compilation PostgreSQL et binds inchangés, la chaîne d’empreintes, les rôles et transactions, les rollbacks, JIT on/off sans modification, les délais et timeouts, l’ordre équilibré, les agrégats appariés, la censure, la dérive de réglages, le refus du SQL hors appel autorisé, le quota de disque avant requête, les modes de fichiers, l’expurgation et l’arrêt après erreur. Les tests historiques P1/P2/P3/EXPLAIN sont aussi exécutés : **171 tests réussis**, Ruff et formatage conformes. Les blocs de commandes shell ont été vérifiés localement avec `bash -n`, sans les exécuter.

Reproduire localement, sans réseau ni base réels :

```bash
.cache/search-cpu-venv/bin/python -m pytest \
  tests/test_compare_h1_rank.py tests/test_components_h1_lexical.py \
  tests/test_decompose_h1_lexical.py tests/test_analyze_h1_lexical.py \
  tests/test_explain_h1_lexical.py -q
.cache/search-cpu-venv/bin/python -m ruff check \
  scripts/compare_h1_rank.py tests/test_compare_h1_rank.py
```

Résultats de performance : **non mesurés**. La décision de remplacement sera prise après les campagnes autorisées, en regardant les gains, les régressions, les timeouts et les changements de plans pour chacune des deux requêtes.
