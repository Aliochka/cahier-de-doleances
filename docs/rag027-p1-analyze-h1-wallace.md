# RAG-027 P1 — Mesures réelles du classement lexical H1

Date : 22 octobre 2026. **Préparation et tests locaux uniquement ; aucune campagne lancée sur Wallace.**

## Livrables et périmètre

L’outil complémentaire [analyze_h1_lexical.py](../scripts/analyze_h1_lexical.py) exécute le classement lexical instrumenté par :

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS, FORMAT JSON)
<SQL de classement lexical H1 original>
```

Contrairement à la collecte précédente, **cette instruction exécute réellement la recherche coûteuse**. Elle ne renvoie pas les documents, mais les statistiques de leur traitement. L’impact CPU, cache et disponibilité est accepté pour cette phase. La présente livraison ne lance pas cette charge. [Référence PostgreSQL 17 sur EXPLAIN](https://www.postgresql.org/docs/17/sql-explain.html).

L’outil précédent [explain_h1_lexical.py](../scripts/explain_h1_lexical.py), ses tests et le moteur H1 sont inchangés. Le nouveau programme importe les protections communes sans remplacer leurs constantes ou modifier leur comportement. Il refuse une version différente de cet outil, des sept sources H1 épinglées ou des versions attendues de SQLAlchemy/psycopg2. La référence du moteur reste `0eebaecbd0f14bc88ae12d85cc6fba35d0fd5a73`, même si le checkout contenant les nouveaux outils porte un commit plus récent.

La tokenisation et la normalisation PostgreSQL, les DF figées, le calcul IDF et `score_expression()` sont ceux de `TunedSearch.lexical()`. Les paramètres restent liés avec leurs types Python et SQLAlchemy originaux, les filtres sont NULL, l’espace est `full`, les coefficients sont 0,5/0,3/0,2, l’ordre est score décroissant puis `document_id COLLATE "C"`, la limite est 50. Il n’y a ni préfiltrage ni substitution de formule.

Seul l’appel final à `execute` du véritable `TunedSearch.lexical()` peut recevoir le préfixe ANALYZE. Il est reconnu par son code appelant, le SQL et l’identité du dictionnaire de paramètres ; le gabarit final est également contrôlé. Les autres instructions applicatives doivent appartenir à la liste de préparation/métadonnées héritée. Tout autre SQL, notamment un classement fourni directement, un comptage du corpus, une lecture documentaire ou une écriture, est refusé avant le driver. Après collecte, une exception interne interrompt la méthode avant `_results()` : aucune hydratation documentaire n’est exécutée.

Aucun encodeur n’est créé ; `torch`, `transformers`, BGE-M3 et la recherche HNSW ne sont pas chargés. L’outil utilise l’image CPU existante sans installation, reconstruction d’image ou montage du modèle.

## Lecture seule, JIT et délais

Le fichier lecteur existant est chargé explicitement, sans reprise de variables de connexion ambiantes. Les deux bases sont distinguées par les gardes d’identité existantes. Les rôles sont contrôlés avec `check_reader_role()`. Chaque transaction commence explicitement par `SET TRANSACTION READ ONLY`, vérifie son état effectif et se termine par rollback, y compris après succès, timeout ou exception.

Deux configurations sont proposées :

- `current` : aucun réglage JIT modifié ; la valeur courante doit être `on`, sinon la mesure est refusée. Les seuils d’inlining et d’optimization restent ceux du serveur.
- `off` : `set_config('jit', 'off', true)` dans la seule transaction cible qui exécutera le classement. Le rollback termine cette modification locale. Les transactions de préparation imbriquées et la base source ne reçoivent pas cette modification.

Les paramètres pertinents de session, dont ceux de la catégorie `Query Tuning`, sont relevés avant/après le changement. L’outil vérifie que seul `jit` diffère, contrôle la valeur effective de JIT et les timeouts, puis conserve le timeout en millisecondes effectivement affecté à l’instruction de classement. Les autres réglages ne sont pas modifiés. `jit=on` ne garantit pas une compilation : PostgreSQL décide selon les coûts et seuils ; les blocs JIT du plan indiquent ce qui a réellement été instrumenté. [Décisions JIT dans PostgreSQL 17](https://www.postgresql.org/docs/17/jit-decision.html).

| Limite | Valeur initiale | Plafond autorisé |
|---|---:|---:|
| Connexion | 1 s | Fixe |
| Pool de connexions | Attente 1 s | Fixe |
| Instruction de préparation | 2 s | Fixe |
| Instruction de classement instrumentée | 60 s | 300 s |
| Échéance commune d’une mesure | 90 s | 360 s |
| Attente d’un verrou | 200 ms | 1 000 ms |
| Répétitions explicites | 1 | 20 |

L’échéance d’une mesure inclut sa préparation. Le timeout de chaque instruction est plafonné par son reliquat. Le moniteur peut annuler la connexion active. Les réglages historiques de 30 s de `TunedSearch` ne sont jamais transmis. L’échéance du cas doit être au moins égale au timeout demandé pour le classement ; une préparation longue peut néanmoins réduire le temps réellement disponible.

Les anciens budgets H1 de 10/18 secondes ne sont pas modifiés : le diagnostic dispose de ses propres limites, explicitement autorisées pour cette phase. Un timeout produit un statut `timeout`, sans tentative supplémentaire automatique et sans plan partiel inventé. Le code SQLSTATE `57014` est classé comme annulation/timeout ; une annulation externe peut aussi produire ce code. La phase et la durée client sont conservées dans le manifeste privé. Une mesure suivante explicitement programmée dans un groupe peut continuer après un timeout ; toute autre erreur arrête le groupe et marque les mesures restantes `skipped`.

## Stockage et confidentialité

Les sorties sont créées dans un nouveau répertoire 0700, avec fichiers 0600. La réutilisation d’un répertoire existant est refusée. Une écriture atomique empêche de remplacer un rapport valide par une moitié de JSON. Les erreurs publiées sont des codes fixes, sans message brut de PostgreSQL, SQL, URL ou secret.

Protections de stockage :

- Budget de sortie par collection : 64 Mio, configurable entre 32 et 256 Mio. Il couvre les fichiers privés et expurgés et tient compte du pic d’une réécriture atomique.
- Plan brut : 4 Mio maximum ; détail expurgé par mesure : 4 Mio maximum ; chaque rapport global : 8 Mio maximum. Les fichiers ne sont jamais tronqués silencieusement : un dépassement est un échec explicite.
- Avant chaque nouvelle mesure, réservation logique de 8 Mio pour les deux sorties du plan, plus 24 Mio pour les rapports/statuts et leurs remplacements.
- Marge libre sur le système de fichiers des résultats : 512 Mio par défaut, configurable avec un plancher de 64 Mio. La marge est contrôlée avant les requêtes et les écritures.
- Verrou exclusif `.h1-analyze.lock` dans le répertoire parent : les instances qui utilisent le même parent s’exécutent séquentiellement. Les commandes ci-dessous utilisent toutes ce parent.

Ces contrôles bornent **les fichiers de diagnostic produits par l’outil**. Ils ne constituent pas une réservation physique contre les écritures d’autres applications et ne plafonnent pas les fichiers temporaires PostgreSQL. La valeur existante de `temp_file_limit` est relevée, sans la modifier. Si la place devient insuffisante à cause d’un acteur externe, l’outil échoue ; le dernier rapport durable peut alors rester à `running`, qui signifie « résultat non confirmé », jamais réussite. Aucune purge automatique, suppression d’anciens diagnostics ou modification du serveur n’est effectuée.

Les plans bruts peuvent contenir des constantes issues des requêtes de test et des expressions SQL ; ils restent privés. Aucune ligne du texte documentaire n’est sélectionnée pour export. La synthèse est une projection positive des champs techniques : elle omet `Output`, `Filter`, `Index Cond`, `Recheck Cond`, les expressions de tri et les paramètres liés. Les noms techniques des relations/index restent visibles.

## Résultats produits

Pour chaque mesure aboutie :

| Fichier | Contenu |
|---|---|
| `r01-<cas>.plan.private.json` | Plan PostgreSQL complet, privé. |
| `r01-<cas>.summary.redacted.json` | Métriques et structure par nœud et par worker, partageables. |

Pour toute collection initialisée, y compris avec timeout :

| Fichier | Contenu |
|---|---|
| `manifest.private.json` | Empreintes, paramètres effectifs, limites, phases, rollback, état des tentatives et résultats finaux. |
| `summary.redacted.json` | Index des mesures, statuts, durées globales, JIT, empreintes de comparaison. |
| `comparison.redacted.json` | Lignes comparatives et comparaison des plans/conditions. |
| `comparison.redacted.md` | Tableau Markdown lisible. |

Les champs de performance conservés lorsqu’ils existent incluent : Planning/Execution Time ; génération, inlining, optimization, emission et total JIT ; temps réels de démarrage/fin, lignes et boucles des nœuds ; workers prévus/lancés et détails de chaque worker ; buffers partagés/locaux et temporaires ; temps I/O ; méthode, espace et type mémoire/disque des tris ; pages bitmap exactes/lossy et autres compteurs mémoire/disque connus.

Le tableau récapitule notamment les temps globaux et les quatre phases JIT, les workers, les blocs partagés et temporaires et une approximation des candidats retournés par le scan documentaire. Les détails par worker et tris sont dans le fichier expurgé de chaque mesure. Une métrique absente reste absente ou `null` : elle n’est pas transformée en zéro mesuré.

Les temps PostgreSQL sont en millisecondes, les compteurs de buffers en blocs, et `Sort Space Used` en kilo-octets selon la convention d’EXPLAIN ; `Sort Space Type` précise s’il s’agit de mémoire ou de disque.

La comparaison hors ligne vérifie, pour une même requête et répétition, l’égalité des empreintes du SQL, des paramètres, de la génération, des sources/outils, des limites demandées et des paramètres de session hors JIT. Elle rapporte séparément :

- `comparable` : conditions techniques enregistrées identiques, hors JIT ; ce booléen ne prouve pas un même état des caches ou une même activité concurrente.
- `structure_equal` : même arbre de nœuds, accès, expressions et parallélisme prévu, sans intégrer les temps réels ni le bloc JIT.
- `estimates_equal` : mêmes coûts et cardinalités/largeurs estimées.

Les expressions complètes sont utilisées uniquement pour leur empreinte ; elles ne sont pas copiées dans les rapports expurgés. Une mesure en timeout n’a pas de comparaison de plan réel disponible.

## Commandes Wallace — cinq mesures indépendantes

Les deux scripts approuvés doivent être présents dans `/srv/cahier-de-doleances-app/scripts/`. Le script EXPLAIN doit conserver son contenu actuel ; aucun rebuild de l’image n’est requis. Le fichier lecteur à utiliser est **`/srv/cahier-de-doleances-app/rag/search-reader.env`**. L’ancien chemin `/srv/cahier-search/private/reader.env` n’est pas utilisé.

Précontrôles locaux à Wallace, sans requête SQL ni affichage des secrets :

```bash
cd /srv/cahier-de-doleances-app
git rev-parse HEAD
sha256sum scripts/explain_h1_lexical.py
sha256sum rag/evaluation/performance-rag027.json
test -r rag/search-reader.env
docker image inspect --format '{{.Id}}' cahier-de-doleances-app:search-cpu-001
docker network inspect --format '{{.Name}}' cahier-de-doleances_cahier-internal
```

Empreintes attendues :

```text
explain_h1_lexical.py : 8e7e00ca1a1cafb1e63b7bfd61069a8e585ffe28b3eec702ae117d6c3c401511
performance-rag027.json : f1ad4fef0eae346ce9a2413426ecf7214406440d0e89ea4821fe6913e2e7583e
```

Le compte de l’opérateur doit pouvoir lire le fichier lecteur et écrire dans le parent des résultats. Le conteneur utilise son UID/GID ; aucune permission du lecteur n’est élargie. Le parent doit être privé. Définir cette fonction dans un shell sur Wallace :

```bash
umask 077
mkdir -p /srv/cahier-search/diagnostics

h1_analyze() {
  [ "$#" -eq 2 ] || return 2
  docker run --rm --pull=never \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=16m \
    --network cahier-de-doleances_cahier-internal \
    --user "$(id -u):$(id -g)" \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --memory 512m --memory-swap 512m --cpus 1 --pids-limit 64 \
    --env PYTHONDONTWRITEBYTECODE=1 \
    --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/analyze_h1_lexical.py,dst=/diagnostic/analyze_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/explain_h1_lexical.py,dst=/diagnostic/explain_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/rag/evaluation/performance-rag027.json,dst=/diagnostic/queries.json,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/rag/search-reader.env,dst=/run/reader.env,readonly \
    --mount type=bind,src=/srv/cahier-search/diagnostics,dst=/results \
    --entrypoint /opt/venv/bin/python \
    cahier-de-doleances-app:search-cpu-001 \
    /diagnostic/analyze_h1_lexical.py \
    --execute --case "$1" \
    --reader-env /run/reader.env --queries /diagnostic/queries.json \
    --statement-timeout-ms 60000 --case-deadline-seconds 90 \
    --lock-timeout-ms 200 --max-output-mib 64 --min-free-mib 512 \
    --output-dir "/results/$2"
}
```

Exécuter **chaque ligne séparément**, examiner son statut et ses rapports avant de choisir la suivante. Les cinq répertoires doivent être inexistants ; ne pas les créer à l’avance :

```bash
h1_analyze fiscalite-05-current p1-01-fiscalite05-current
```

```bash
h1_analyze democratie-02-current p1-02-democratie02-current
```

```bash
h1_analyze democratie-02-off p1-03-democratie02-off
```

```bash
h1_analyze fiscalite-01-current p1-04-fiscalite01-current
```

```bash
h1_analyze fiscalite-01-off p1-05-fiscalite01-off
```

Le terminal reçoit uniquement un statut JSON. Code retour 0 : toutes les mesures demandées ont abouti ; 1 : timeout/erreur ou collecte incomplète ; 2 : arguments invalides. Ne pas placer ces commandes dans une boucle de relance sur échec. Aucun service existant, volume PostgreSQL ou fichier de configuration serveur n’est monté ou modifié par ce conteneur. Les limites mémoire/CPU Docker concernent le client, pas les backends PostgreSQL et leurs workers.

## Comparaison hors ligne des cinq résultats

Cette commande n’a pas accès au lecteur et utilise `--network none`. Elle ne lit que les index de synthèse expurgés, sans charger les plans privés :

```bash
docker run --rm --pull=never --read-only --network none \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --user "$(id -u):$(id -g)" \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --memory 512m --memory-swap 512m --cpus 1 --pids-limit 64 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/analyze_h1_lexical.py,dst=/diagnostic/analyze_h1_lexical.py,readonly \
  --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/explain_h1_lexical.py,dst=/diagnostic/explain_h1_lexical.py,readonly \
  --mount type=bind,src=/srv/cahier-search/diagnostics,dst=/results \
  --entrypoint /opt/venv/bin/python \
  cahier-de-doleances-app:search-cpu-001 \
  /diagnostic/analyze_h1_lexical.py \
  --compare \
    /results/p1-01-fiscalite05-current \
    /results/p1-02-democratie02-current \
    /results/p1-03-democratie02-off \
    /results/p1-04-fiscalite01-current \
    /results/p1-05-fiscalite01-off \
  --output-dir /results/p1-comparaison-001
```

Afficher le tableau partageable :

```bash
cat /srv/cahier-search/diagnostics/p1-comparaison-001/comparison.redacted.md
```

Pour l’analyse approfondie, transmettre aussi `comparison.redacted.json` et les fichiers `r01-*.summary.redacted.json` des cas aboutis. Conserver les fichiers `*.private.json` sur Wallace ou dans un espace privé.

## Répétitions et alternance ultérieures

Une campagne de groupe reste opt-in : remplacer les arguments de cas/répétitions de la commande Docker par exemple par :

```text
--execute --case democratie-pair --repeats 4 --alternate-jit-order
```

Cela exécute huit mesures : `current/off`, puis `off/current`, puis `current/off`, puis `off/current`. `fiscalite-pair` propose le même mécanisme pour `fiscalite-01`. `initial` répète les cinq mesures, en inversant chaque paire sur les passages pairs si l’alternance est demandée. Les cas individuels peuvent être répétés sans alternance. Toutes les mesures restent séquentielles, sans retry et avec un nouveau répertoire. Le quota peut interrompre une grande campagne avant son terme ; ne pas le désactiver.

Conserver les mêmes limites, corpus, statistiques, versions, recette et réglages hors JIT entre deux configurations. Relever l’ordre, l’heure et l’activité concurrente. Séparer les premières observations des répétitions chaudes ; ne pas purger les caches, redémarrer PostgreSQL ou reconstruire un index. L’alternance réduit le biais de cache sans garantir un état identique. Les cinq premières mesures sont descriptives, pas une preuve statistique d’un gain JIT ; une mesure interrompue est une observation censurée, pas un temps d’exécution égal au timeout.

## Limites d’interprétation

Les temps `Actual Startup/Total Time` d’un nœud sont **inclusifs** et, lorsqu’il y a plusieurs boucles, rapportés par boucle. Ne pas additionner les nœuds parents et enfants. En parallèle, les temps des workers se chevauchent : leur somme n’est pas une durée murale. Le temps d’exécution global est la référence pour la comparaison des requêtes instrumentées. [Lecture des mesures EXPLAIN PostgreSQL 17](https://www.postgresql.org/docs/17/using-explain.html).

Les nœuds de scan peuvent inclure lecture des vecteurs, prédicats, projection et calcul du score. EXPLAIN ANALYZE **n’isole pas exactement le CPU de `ts_rank_cd` ou des deux couvertures**. Le tri peut inclure le temps nécessaire à la consommation du scan. Les données permettent de localiser les postes et de tester l’effet du JIT, sans attribuer artificiellement chaque milliseconde au score. Les temps de compilation JIT, notamment en parallèle, ne doivent pas être ajoutés mécaniquement à `Execution Time` ni additionnés une seconde fois avec les blocs des workers.

Les lignes réelles sont conservées par nœud, avec les boucles et lignes éliminées. `candidate_rows_approx` vaut `Actual Rows × Actual Loops` lorsqu’un unique scan de `documents_full` est identifié ; PostgreSQL peut arrondir ses moyennes. Ce n’est ni un comptage exact supplémentaire, ni le nombre des 50 documents finaux, ni nécessairement tous les documents examinés. Les estimations parallèles utilisent leurs propres conventions ; comparer les chiffres à niveau équivalent plutôt que multiplier systématiquement par « workers + leader ».

Les compteurs de buffers du tableau proviennent de la racine, sans sommer ceux des descendants ou des workers. Un `Shared Read Blocks` indique une lecture demandée par PostgreSQL hors de ses shared buffers ; elle peut être satisfaite par le cache du système. Ce n’est pas un compteur direct de lectures physiques du SSD, de blocs uniques ou de volume physique transféré. Les temps I/O ne sont utiles que si l’instrumentation existante les fournit ; `track_io_timing` est relevé, jamais activé par cet outil.

Le chronométrage détaillé d’EXPLAIN ANALYZE introduit un surcoût, particulièrement sur des millions de lignes. `Execution Time` ne représente pas toute la latence de H1 : l’encodage, la recherche vectorielle, l’hydratation et le HTTP sont exclus. `elapsed_seconds` comprend la préparation et les échanges du client. Ne pas comparer directement le temps instrumenté à 0,708 s ou 8,703 s comme si les périmètres étaient identiques.

## Validation de la livraison

Tests locaux uniquement, avec sockets et connexions psycopg2 interdits et transports PostgreSQL simulés :

```bash
.cache/search-cpu-venv/bin/python -m pytest \
  tests/test_analyze_h1_lexical.py tests/test_explain_h1_lexical.py -q
```

Les tests couvrent les cinq mesures, la conservation du SQL/valeurs/types compilés pour psycopg2, le refus de SQL non conforme, les rôles/transactions, les rollbacks, les timeouts, JIT effectif et autres paramètres inchangés, les métriques/worker/tri/I/O, l’expurgation, la comparaison hors ligne, les limites de sortie, le verrou de sérialisation et l’absence de chargement des modèles. Les tests du précédent outil restent inclus pour vérifier sa non-régression. Aucune validation d’exécution réelle PostgreSQL/Docker n’est revendiquée avant la campagne séparée sur Wallace.

Résultat local : **72 tests réussis**, contrôles Ruff et formatage conformes. L’unique avertissement de dépréciation provient de `fastapi.testclient`, importé par la configuration générale des tests. Seuls les trois nouveaux fichiers de cette livraison sont ajoutés ; le moteur et le précédent outil de diagnostic sont inchangés.
