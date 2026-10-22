# RAG-027 P3 — Outil livré et commandes Wallace

22 octobre 2026. Implémentation locale uniquement. Aucune connexion à Wallace, aucun changement du moteur H1, de PostgreSQL, des données, des index ou des services publics. Le [rapport d’audit validé](rag027-p3-composantes-scoring.md) reste la référence méthodologique.

## Livraison

Le nouvel outil [components_h1_lexical.py](../scripts/components_h1_lexical.py) importe P2/P1 sans les modifier. Chaque invocation sélectionne **une seule variante et une seule requête**. Il ne propose ni `all`, ni répétition, ni campagne automatique. Les mesures répétées pourront être ordonnées manuellement, dans des répertoires distincts, après revue des premiers plans.

Variantes disponibles :

| Variante | Opération |
|---|---|
| `observe` | Préparation H1, corpus/IDF et réglages effectifs, arrêt avant classement ; métadonnées de stockage et compteurs. Première étape. |
| `zero` | `count(*)` et `sum(0::float8)`, filtre H1 inchangé. |
| `idf`, `terms`, `rank` | Composante originale pondérée, consommée dans `sum(...)`. |
| `idf-terms`, `idf-rank`, `terms-rank` | Somme des deux composantes sélectionnées, sans réassociation interne. |
| `full` | Expression de score H1 entière, textuellement inchangée, consommée dans `sum(...)`. |
| `top50` | SQL H1 original entier, types et paramètres conservés, `LIMIT 50`. |
| `touch` | `count(*)` et `sum(length(search_vector)::float8)`, filtre H1 inchangé. |
| `classify` | Effectifs compressés/non compressés, pglz/lz4, tailles stockées min/max/moyenne, moyenne du nombre de lexèmes, sur un échantillon borné. |

Seul l’appel final dans la méthode réelle et épinglée `TunedSearch.lexical()` est intercepté. L’outil vérifie le SQL complet, la recette, les filtres publics, les poids et la recomposition des trois fragments produits par le constructeur original. Il conserve le dictionnaire de paramètres et les définitions des binds encore utilisés. L’appel original n’est jamais transmis seul : seules les variantes autorisées sont émises. Une exception de capture arrête le moteur avant hydratation. Aucun encodeur, modèle ou HNSW n’est initialisé.

Pour les agrégats et `touch`, l’instrumentation est `EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS, FORMAT JSON)`. `top50` emploie exactement le même préfixe avec le SQL H1 original. `observe` ne lance aucun EXPLAIN. `classify` retourne un unique résultat agrégé numérique, sans plan, identifiant documentaire, lexème ou texte citoyen.

### Consommation et emplacement des expressions

La projection utilise directement `sum(expression)` ; aucun calcul n’est laissé dans une projection inutilisée. L’analyse de `Output` relève les CASE, le rang, `length` et les sommes par chemin de nœud, ainsi que les agrégats Partial/Finalize et leur stratégie. Les littéraux SQL sont ignorés pour éviter qu’un texte de tsquery ressemble à une fonction.

`consumption_evidence=sum_argument_present` signifie que les motifs attendus subsistent dans l’argument de somme d’un nœud exécuté. Cela ne compte pas les appels physiques. Une simplification, un déplacement vers une colonne intermédiaire ou une absence de statistiques peut produire `unverified_expression_removed_or_rewritten` et `review_required=true`. Le plan doit alors être relu avant toute interprétation du coût ; une exécution SQL réussie reste de statut `ok`, sans prétendre que l’instrumentation de consommation a été validée. Le témoin exact porte `original_top50`.

La comparaison hors ligne signale séparément accès documentaire, workers prévus/lancés, cardinalité approximative, organisation des agrégats et emplacement des projections. Un changement déclenche `review_required`. Des conditions contrôlées et des arbres proches ne démontrent pas un coût CPU causal.

## Protections conservées

- Connexions dédiées au lecteur existant, identité source/cible et corpus vérifiés par le chemin H1 ; aucune URL ou mot de passe imprimé.
- `default_transaction_read_only=on`, option SQLAlchemy de lecture seule, `SET TRANSACTION READ ONLY` explicite, vérification du rôle non propriétaire/non écrivain et des limites, rollback dans les chemins succès, refus et timeout.
- Connexion 1 s ; préparation 2 s par instruction ; mesure 60 s et budget de collecte H1 90 s par défaut ; plafonds 300/360 s ; verrou 200 ms, plafond 1 s. Aucun retry.
- JIT **off local par défaut**, conforme au protocole P3 ; `--jit current` impose un JIT initial on et conserve ses seuils. Aucun changement du JIT global, de `work_mem`, de `track_io_timing`, des permissions ou des méthodes de scan.
- Observations indépendantes en transactions courtes : instruction 2 s, budget 5 s et verrou 200 ms. Elles sont terminées avant les transactions H1 ou démarrent après leur rollback. Leur temps s’ajoute au budget de collecte H1, sans allonger la requête mesurée.
- Une mesure par invocation, verrou non bloquant commun aux outils P1/P2/P3 dans le parent des résultats. Réutiliser le même parent ; ce verrou ne coordonne pas les autres applications ou des parents différents.
- Plans/détails limités à 4 Mio, rapports à 8 Mio, collection à 64 Mio par défaut ; contrôle de 512 Mio libres et réserve pour les rapports, fichiers atomiques 0600 et répertoires 0700. Pas de matérialisation pleine population ni de sortie par document. Ces limites client ne plafonnent pas les temporaires PostgreSQL ; ils sont relevés dans les plans.

Les relevés optionnels refusés par PostgreSQL deviennent `unavailable`, sans demande de droits ni nouvelle tentative. Les statuts de la mesure principale sont distincts des statuts d’observation : `ok`, `observed`, `timeout` ou `error`. En arrêt brutal, un statut `running` n’est pas un résultat confirmé.

### Stockage et limites TOAST

Les compteurs `pg_statio_all_tables` de `documents_full` sont lus avant/après, avec marqueurs privés de redémarrage/reset. Les deltas négatifs ou marqueurs différents signalent `reset_detected`. Sans compteur ou marqueur accessible, le delta est indisponible. Il n’y a ni reset, ni flush forcé, ni polling, ni extension.

Ces compteurs sont globaux, publiés avec retard et affectés par la concurrence. Les champs `toast_*` et `tidx_*` concernent une relation TOAST partagée par les colonnes toastables ; ils ne comptent **ni décompressions, ni appels, ni lectures physiques SSD**. Un delta nul peut être incomplet. Les snapshots et leurs fenêtres sont conservés ; aucune attribution exacte au backend n’est annoncée.

La classification utilise `TABLESAMPLE SYSTEM (0.1) REPEATABLE (2703)` sur la partition physique `rag_full.documents_full`, puis le filtre H1 exact et `LIMIT 512`. Le parent partitionné n’est pas échantillonné. Timeout de l’instruction : 2 s, sans relance si l’échantillon est vide ou insuffisant. Le petit sous-ensemble peut être biaisé par les blocs et la coupure ; il ne représente pas une variante de performance pleine population.

`pg_column_compression` permet de distinguer valeurs compressées et non compressées ; `pg_column_size` et les métadonnées `attstorage/attcompression` ne prouvent pas leur emplacement. **Les effectifs inline compressé et externalisé restent donc `null`**, avec une raison explicite. Une valeur non compressée peut aussi être externe. Une valeur compressée peut être inline ou externe. Aucun accès à `chunk_data` ou inspecteur de pages n’est ajouté.

## Résultats locaux et empreintes

[Tests P3](../tests/test_components_h1_lexical.py) : **49 tests réussis**. Suite cumulée EXPLAIN/P1/P2/P3 : **153 tests réussis**. Les tests interdisent sockets et connexions PostgreSQL, utilisent les méthodes H1 réelles avec transports simulés et vérifient notamment les poids/binds, le SQL complet, les refus, timeouts sans retry, rollbacks, sorties privées/expurgées, limites disque, consommation, comparabilité, métadonnées interdites et absence de chargement de modèle.

Commandes locales utilisées, sans installation de dépendances :

```bash
.cache/search-cpu-venv/bin/python -m pytest -q tests/test_components_h1_lexical.py tests/test_explain_h1_lexical.py tests/test_analyze_h1_lexical.py tests/test_decompose_h1_lexical.py
.cache/search-cpu-venv/bin/python -m ruff check scripts/components_h1_lexical.py tests/test_components_h1_lexical.py
.cache/search-cpu-venv/bin/python -m ruff format --check scripts/components_h1_lexical.py tests/test_components_h1_lexical.py
```

Un avertissement de dépréciation Starlette/httpx préexistant est émis par l’environnement de test. Aucun test réel de planificateur PostgreSQL n’est revendiqué : la validation locale vérifie le contrat d’émission et l’interprétation de fixtures, pas les plans futurs de Wallace.

SHA-256 attendus :

```text
56ed64dfb9d765609c29b34f4d8224bfc8971eb8115326b852bca50b67e97777  scripts/components_h1_lexical.py
f55cf4e30ab8f8339805851409b1aa5be6e14765d162a042465b94632f6b53d3  tests/test_components_h1_lexical.py
0c4474464e8389cd537ccb82533d87f1678b3dc87c5c968c77e434d4b803039d  scripts/decompose_h1_lexical.py
3d3b9f4cba9530e57cf3cf6f58ce92f4ad4e76a3fe372c06c4f9316735b5e937  scripts/analyze_h1_lexical.py
8e7e00ca1a1cafb1e63b7bfd61069a8e585ffe28b3eec702ae117d6c3c401511  scripts/explain_h1_lexical.py
f1ad4fef0eae346ce9a2413426ecf7214406440d0e89ea4821fe6913e2e7583e  rag/evaluation/performance-rag027.json
```

La chaîne de contrôle vérifie P2, puis P1, puis EXPLAIN et les sept sources H1 épinglées à la référence `0eebaecbd0f14bc88ae12d85cc6fba35d0fd5a73`, ainsi que les versions des pilotes. Le jeu d’évaluation est vérifié à sa lecture. Les rapports ajoutent les empreintes du SQL H1, du SQL diagnostique, des paramètres/types, de la génération, des réglages effectifs et des limites. Les empreintes SQL/paramètres effectives nécessitent la préparation réelle et ne sont donc pas inventées localement.

## Commandes Wallace — préparées, non exécutées

Faire parvenir ces fichiers au checkout selon votre procédure habituelle, puis contrôler sans SQL :

```bash
cd /srv/cahier-de-doleances-app
sha256sum scripts/components_h1_lexical.py tests/test_components_h1_lexical.py scripts/decompose_h1_lexical.py scripts/analyze_h1_lexical.py scripts/explain_h1_lexical.py rag/evaluation/performance-rag027.json
test -r /srv/cahier-de-doleances-app/rag/search-reader.env
docker image inspect --format '{{.Id}}' cahier-de-doleances-app:search-cpu-001
```

Définir la fonction suivante. Elle réutilise l’image CPU existante et ne touche pas aux conteneurs publics. Les plafonds Docker concernent le client, pas les workers PostgreSQL du serveur.

```bash
umask 077
mkdir -p /srv/cahier-search/diagnostics

h1_p3() {
  docker run --rm --pull=never --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=16m \
    --network cahier-de-doleances_cahier-internal \
    --user "$(id -u):$(id -g)" \
    --cap-drop ALL --security-opt no-new-privileges:true \
    --memory 512m --memory-swap 512m --cpus 1 --pids-limit 64 \
    --env PYTHONDONTWRITEBYTECODE=1 \
    --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/components_h1_lexical.py,dst=/diagnostic/components_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/decompose_h1_lexical.py,dst=/diagnostic/decompose_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/analyze_h1_lexical.py,dst=/diagnostic/analyze_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/explain_h1_lexical.py,dst=/diagnostic/explain_h1_lexical.py,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/rag/evaluation/performance-rag027.json,dst=/diagnostic/queries.json,readonly \
    --mount type=bind,src=/srv/cahier-de-doleances-app/rag/search-reader.env,dst=/run/reader.env,readonly \
    --mount type=bind,src=/srv/cahier-search/diagnostics,dst=/results \
    --entrypoint /opt/venv/bin/python \
    cahier-de-doleances-app:search-cpu-001 \
    /diagnostic/components_h1_lexical.py "$@"
}

h1_p3_measure() {
  h1_p3 --execute --reader-env /run/reader.env --queries /diagnostic/queries.json \
    --query democratie-02 --jit off \
    --statement-timeout-ms 60000 --case-deadline-seconds 90 --lock-timeout-ms 200 \
    --max-output-mib 64 --min-free-mib 512 "$@"
}
```

Première commande SQL, **relevés légers seulement** :

```bash
h1_p3_measure --variant observe --output-dir /results/p3-democratie-observe-001
cat /srv/cahier-search/diagnostics/p3-democratie-observe-001/summary.redacted.json
```

Vérifier corpus, réglages, statuts des observations et valeur effective de work_mem. S’arrêter pour revue si les contrôles échouent. Les neuf commandes suivantes sont **indépendantes** : les exécuter une par une après validation du relevé, sans coller tous les blocs comme une campagne. Aucun essai sur `fiscalite-01` ni répétition n’est déclenché.

```bash
h1_p3_measure --variant zero --output-dir /results/p3-democratie-zero-001
```

```bash
h1_p3_measure --variant idf --output-dir /results/p3-democratie-idf-001
```

```bash
h1_p3_measure --variant terms --output-dir /results/p3-democratie-terms-001
```

```bash
h1_p3_measure --variant rank --output-dir /results/p3-democratie-rank-001
```

```bash
h1_p3_measure --variant idf-terms --output-dir /results/p3-democratie-idf-terms-001
```

```bash
h1_p3_measure --variant idf-rank --output-dir /results/p3-democratie-idf-rank-001
```

```bash
h1_p3_measure --variant terms-rank --output-dir /results/p3-democratie-terms-rank-001
```

```bash
h1_p3_measure --variant full --output-dir /results/p3-democratie-full-001
```

```bash
h1_p3_measure --variant top50 --output-dir /results/p3-democratie-top50-001
```

Contrôles complémentaires validés dans le périmètre, à sélectionner séparément après examen de la matrice :

```bash
h1_p3_measure --variant touch --output-dir /results/p3-democratie-touch-001
```

```bash
h1_p3_measure --variant classify --output-dir /results/p3-democratie-classify-001
```

Comparer les neuf mesures **hors ligne et sans identifiants de connexion**, en montant les mêmes fichiers via la fonction commune :

```bash
h1_p3 --compare \
  /results/p3-democratie-zero-001 /results/p3-democratie-idf-001 \
  /results/p3-democratie-terms-001 /results/p3-democratie-rank-001 \
  /results/p3-democratie-idf-terms-001 /results/p3-democratie-idf-rank-001 \
  /results/p3-democratie-terms-rank-001 /results/p3-democratie-full-001 \
  /results/p3-democratie-top50-001 \
  --output-dir /results/p3-democratie-comparison-001
```

La fonction Docker monte le fichier lecteur, mais le chemin `--compare` ne le lit pas et ne crée aucune connexion. Il peut aussi être exécuté localement sans réseau après copie des seules synthèses expurgées. Ne pas copier les plans privés vers un canal public.

## Rapports, revue et interprétation

Chaque répertoire contient `manifest.private.json`, `summary.redacted.json` et un tableau `comparison.redacted.md`. Les variantes instrumentées ajoutent `plan.private.json` et `plan.summary.redacted.json`. Le relevé et la classification n’ont pas de plan ; un timeout n’a pas de plan partiel inventé. Le comparateur produit `comparison.redacted.json` et le tableau des mesures.

Le manifeste conserve gabarits SQL, réglages et phases de transactions ; les plans bruts restent privés. Les synthèses n’exportent pas les expressions, valeurs des binds, requêtes normalisées, secrets ou textes. Elles conservent temps inclusifs, lignes/loops, workers, buffers, temporaires, agrégats, catégories de projection et fenêtres TOAST. Ne pas sommer les temps de nœuds ou leurs compteurs inclusifs ; les workers se chevauchent. Les cardinalités issues de lignes moyennes multipliées par loops sont approximatives.

Avant répétition, examiner `consumption_evidence`, `review_required`, mêmes réglages/corpus/paramètres, même stratégie documentaire et même parallélisme, puis les positions des projections et agrégats. Un top50 n’a pas la même agrégation que les autres variantes : la différence doit être visible, pas masquée. Une première passe unique est exploratoire ; les écarts de cache et de concurrence empêchent une attribution CPU précise. Aucun écart temporel ni delta TOAST ne constitue une mesure exacte d’une fonction ou de la décompression.

Le contrat de parité des futures optimisations reste strict : mêmes admissibles, top-50 ordonné, scores binaires float8 et fusion RRF à classement vectoriel fixé, conformément au rapport validé. **Aucune somme agrégée de P3 ne teste cette parité.** Cette livraison mesure les composantes et n’optimise pas la formule publique.
