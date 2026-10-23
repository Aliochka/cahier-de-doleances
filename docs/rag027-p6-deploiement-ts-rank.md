# RAG-027 — P6 : H1 public avec ts_rank

Préparation locale uniquement. **Aucune connexion, copie, construction ou mise en production sur Wallace. Les commandes Wallace ci-dessous attendent un accord explicite de déploiement.** La validation de la recette dans la demande P6 autorise cette modification locale ; elle ne vaut pas autorisation de déployer.

## Changement livré

Le service public utilise maintenant `H1LexicalSearch`, une variante de `TunedSearch` qui hérite de toute sa recherche et remplace uniquement le fragment :

```sql
ts_rank_cd(d.search_vector,CAST(:query AS tsquery),32)::float8
-- devient
ts_rank(d.search_vector,CAST(:query AS tsquery),32)::float8
```

Le remplacement exige une occurrence exacte ; une formule inattendue est refusée. Les coefficients 0,5 / 0,3 / 0,2, le calcul IDF et les DF, les couvertures, normalisation 32, paramètres, filtres, ordre score décroissant puis identifiant COLLATE C, profondeur 50, ANN et fusion RRF k60 sont conservés. La méthode `lexical()` et `_terms()` sont les mêmes objets Python que dans le moteur historique. Aucun préfiltrage n’est activé. Le budget commun lexical + vectoriel reste `budget.phase("sql", 10)` et le budget global reste 18 s.

La recette publique devient **`h1-public-v2-ts-rank`**, ce qui change son empreinte. Les classements et curseurs de l’ancienne recette ne doivent pas être réutilisés ; la recréation du conteneur vide son cache en mémoire. Les anciens curseurs expirent, l’utilisateur doit relancer sa recherche.

Le moteur historique `tuning/lexical.py` reste figé pour les benchmarks et outils diagnostiques. Le parcours RAG personnel expérimental reste sur sa recette historique ; ce changement concerne le H1 public. Les scripts P1 à P5, leurs empreintes, catalogues, plans et résultats ne changent pas. Les diagnostics épinglés continuent donc d’évaluer leur recette historique, et ne doivent pas être utilisés comme une preuve de la formule désormais servie par le public.

Fichiers de la livraison :

- `rag/src/cahier_rag/search/service/core.py` : variante lexicale, sélection par H1 public et version de recette.
- `rag/tests/unit/test_search_service.py` : contrôle exact de la substitution, binds, paramètres inchangés, version et simulations du service.
- `tests/test_search_deploy_pg.py` : version attendue et vérification du SQL réellement exécuté par H1 sur un PostgreSQL temporaire avec encodeur factice.
- `deploy/search-p6.Dockerfile` : couche applicative dérivée de l’image CPU déjà utilisée, avec contrôle de son module initial ; aucune installation de paquet ou modèle.
- Ce document : commandes, contrôles et retour arrière.

Les gains Wallace de 64 à 68 % sont ceux **rapportés par l’utilisateur pour P5** ; aucune nouvelle mesure Wallace n’a été réalisée ici. La faible baisse de pertinence hybride reste celle de l’ablation expérimentale, sans validation nouvelle par les juges.

## Validation locale

Les tests vérifient que la formule complète diffère uniquement du nom de fonction, avec un, deux et 32 lexèmes, et que les valeurs et binds compilés pour PostgreSQL sont identiques. Les contrôles de fusion RRF, fenêtres top50, provenance/BIGINT, curseurs, API, lecture seule, annulation et échéances sont réexécutés. Les suites P1 à P5 restent inchangées.

Le test PostgreSQL utilise un **nouveau cluster temporaire local PostgreSQL 17**, isolé des bases de travail, et l’extension pgvector déjà installée. Il exécute réellement H1, avec un encodeur factice, et vérifie que le SQL lexical contient `ts_rank` et aucun `ts_rank_cd`. Il ne mesure pas les performances du corpus complet et ne charge aucun modèle. Aucun test ne contacte Wallace.

Résultats locaux : **469 tests applicatifs réussis (122 ignorés faute de bases optionnelles), 530 tests unitaires RAG réussis (16 ignorés faute d’extra optionnel), et 1 test d’intégration PostgreSQL 17 temporaire réussi**. Ruff, formatage et contrôle de diff conformes. Les tests ignorés n’ont pas été présentés comme exécutés ; le test PostgreSQL de déploiement, ignoré dans la suite générale, a été lancé séparément avec son opt-in.

Commandes locales :

```bash
.cache/search-cpu-venv/bin/python -m pytest tests -q
(cd rag && ../.cache/search-cpu-venv/bin/python -m pytest tests/unit -q)
SEARCH_DEPLOY_TEST_PG_BIN=/usr/lib/postgresql/17/bin \
  .cache/search-cpu-venv/bin/python -m pytest tests/test_search_deploy_pg.py -q
.cache/search-cpu-venv/bin/python -m ruff check \
  rag/src/cahier_rag/search/service/core.py \
  rag/tests/unit/test_search_service.py tests/test_search_deploy_pg.py
git diff --check
```

Docker n’est pas disponible dans l’environnement de préparation : la construction de l’image dérivée et sa recréation Compose restent à valider après accord. Les commandes shell sont vérifiées syntaxiquement localement ; cela ne valide ni les fichiers privés ni le Compose effectivement installé sur Wallace.

## Préparation de l’image et capture du retour arrière — Wallace après accord

Utiliser le dépôt préparé sous `/srv/cahier-de-doleances-app`. Les fichiers nouveaux/modifiés doivent y avoir été transférés après accord, sans écraser `.env.deploy` ni les fichiers privés. Aucune récupération Git distante n’est lancée automatiquement.

Les commandes suivantes sont prévues pour **Bash**, dans le même shell. Elles reprennent la liste ordonnée des fichiers Compose du conteneur en service et son nom de projet, pour conserver les overlays réseau/recherche existants. `.env.deploy` doit rester le fichier d’environnement de cette installation. Si le service n’est pas identifié de façon unique, si ce fichier n’est plus la configuration courante ou si des overrides éphémères étaient utilisés, arrêter et faire correspondre les paramètres au déploiement existant avant de poursuivre.

```bash
set -euo pipefail
cd /srv/cahier-de-doleances-app
umask 077
p6_stamp=$(date -u +%Y%m%dT%H%M%SZ)
p6_private="/srv/cahier-search/diagnostics/p6-$p6_stamp"
mkdir -m 700 "$p6_private"
mapfile -t p6_candidates < <(docker ps -q \
  --filter label=com.docker.compose.service=app \
  --filter label=com.docker.compose.project=cahier-de-doleances-app)
[ "${#p6_candidates[@]}" -eq 1 ] || { echo 'Service app non unique'; exit 1; }
p6_old_container=${p6_candidates[0]}
p6_old_id=$(docker inspect --format '{{.Image}}' "$p6_old_container")
p6_project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$p6_old_container")
p6_compose_csv=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$p6_old_container")
[ -n "$p6_compose_csv" ] && [ "$p6_compose_csv" != '<no value>' ] || exit 1
IFS=',' read -r -a p6_compose_files <<< "$p6_compose_csv"
p6_compose=(docker compose --project-name "$p6_project" \
  --project-directory /srv/cahier-de-doleances-app --env-file .env.deploy)
for p6_file in "${p6_compose_files[@]}"; do
  test -r "$p6_file" || exit 1
  p6_compose+=(-f "$p6_file")
done
p6_rollback_tag="search-cpu-p6-rollback-$p6_stamp"
p6_new_tag="search-cpu-p6-ts-rank-$p6_stamp"
docker image tag "$p6_old_id" "cahier-de-doleances-app:$p6_rollback_tag"
printf '%s\n' "$p6_old_id" > "$p6_private/old-image-id"
printf '%s\n' "$p6_rollback_tag" > "$p6_private/rollback-tag"
printf '%s\n' "$p6_new_tag" > "$p6_private/new-tag"
printf '%s\n' "$p6_project" > "$p6_private/project"
printf '%s\n' "${p6_compose_files[@]}" > "$p6_private/compose-files"
```

Exécuter dans un shell Bash dédié avec arrêt sur erreur (`set -euo pipefail`). Un contrôle échoué arrête ce shell ; ne pas poursuivre les blocs suivants après un échec. Conserver ces fichiers et les deux images jusqu’à validation durable. Le tag de rollback est attaché à l’ID exact de l’image en service, indépendamment d’un éventuel tag amont réutilisé.

Contrôler que les paramètres Compose calculés correspondent au conteneur courant **avant** de changer de tag, sans imprimer de secrets. Les fichiers ci-dessous contiennent une configuration privée et restent dans le répertoire 0700 :

```bash
"${p6_compose[@]}" config --format json > "$p6_private/compose.private.json"
docker inspect "$p6_old_container" > "$p6_private/container.private.json"
python3 - "$p6_private" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
cfg = json.loads((p/'compose.private.json').read_text())['services']['app']
old = json.loads((p/'container.private.json').read_text())[0]
env = dict(v.split('=', 1) for v in old['Config']['Env'])
assert all(env.get(k) == str(v) for k, v in cfg['environment'].items()), 'Environnement Compose divergent'
assert env.get('HYBRID_SEARCH_ENABLED', '').lower() in ('true', '1'), 'H1 public non actif : ne pas activer implicitement'
assert cfg['image'] == old['Config']['Image'], 'Image Compose divergente'
print('Environnement et image Compose concordent ; recherche publique active.')
PY
```

Examiner aussi que la liste de montages/réseaux du Compose conservé correspond bien au conteneur : la validation ci-dessus compare l’environnement et l’image, pas toute la configuration Docker. Ne pas afficher les JSON privés dans un rapport partagé. Ne modifier aucun chemin de modèle, fichier lecteur, publication, clé de curseur, thread CPU ou flag d’activation.

Construire une couche à partir de cette image existante :

```bash
docker build --pull=false -f deploy/search-p6.Dockerfile \
  --build-arg "P6_BASE_IMAGE=cahier-de-doleances-app:$p6_rollback_tag" \
  -t "cahier-de-doleances-app:$p6_new_tag" .
```

Cette construction ne relance aucun modèle. Elle contrôle que le module initial correspond au baseline approuvé (`core.py` SHA-256 `8ad39615726d51748cc9b2ca1e7ad1ad791274607a599bfe57201e813e449813`) et qu’il est chargé depuis `/build/rag/src/cahier_rag/search/service/core.py`. Si l’image réelle diffère, la construction échoue : aucune substitution à l’aveugle dans une autre installation. Aucun outil P1–P5, dépendance, modèle ou index n’est copié/reconstruit.

## Déploiement applicatif — après accord explicite

Précontrôle de configuration, puis recréation du seul service app :

```bash
APP_IMAGE_TAG="$p6_new_tag" "${p6_compose[@]}" config --quiet
APP_IMAGE_TAG="$p6_new_tag" "${p6_compose[@]}" \
  up -d --no-deps --no-build --force-recreate app
p6_new_container=$("${p6_compose[@]}" ps -q app)
docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$p6_new_container"
docker exec "$p6_new_container" /opt/venv/bin/python -c \
  'from cahier_rag.search.service.core import SearchRecipe; assert SearchRecipe().version == "h1-public-v2-ts-rank"; print(SearchRecipe().version)'
```

Le redémarrage recharge normalement le snapshot BGE-M3 existant dans le service ; aucun téléchargement, réencodage du corpus, campagne de modèles ou jugement n’est lancé. Une courte indisponibilité et l’invalidation des anciens curseurs sont attendues. Le healthcheck `/healthz` ne suffit pas à attester que H1 est prêt : vérifier aussi de vraies recherches ci-dessous. Un code initial `search_not_ready` peut correspondre au chargement du worker ; attendre son initialisation (budget de démarrage existant de 120 s), puis refaire la validation dans une nouvelle fenêtre. Ne pas confondre ce démarrage avec une latence SQL ; si le refus persiste, revenir en arrière. Une erreur persistante de chargement, de corpus, de lecture ou de budget déclenche le retour arrière.

**Ne pas modifier `.env.deploy` à ce stade** : le tag candidat est fourni dans l’environnement des commandes. Après validation, enregistrer uniquement la nouvelle valeur d’`APP_IMAGE_TAG` par la procédure habituelle de gestion de configuration pour les futurs redémarrages ; conserver le tag précédent dans le dossier de rollback. Aucune commande de migration, extension, SQL administratif, restauration ou reconstruction d’index n’est nécessaire.

## Vérifications après déploiement

Effectuer une série séquentielle de trois appels pour chacune des deux requêtes problématiques, sans curseur : chaque appel déclenche bien H1, pas seulement la pagination d’un ancien instantané. Utiliser l’URL publique actuelle (valeur `BASE_URL` de l’application), avec TLS et sans contourner les limites d’admission.

Le script ci-dessous utilise l’API existante et l’encodeur déjà chargé dans le service. Il ne crée aucun autre runtime modèle et n’ouvre pas de connexion SQL. Il affiche seulement des mesures techniques, aucun texte citoyen ni identifiant de réponse. Il ne réutilise et ne modifie aucun résultat de benchmark P5.

```bash
p6_since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
p6_public_url=$(docker inspect "$p6_new_container" | python3 -c \
  'import json,sys; e=dict(v.split("=",1) for v in json.load(sys.stdin)[0]["Config"]["Env"]); print(e["BASE_URL"])')
python3 - "$p6_public_url" "$p6_private" <<'PY'
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path
origin = sys.argv[1].rstrip('/')
assert urllib.parse.urlsplit(origin).scheme == 'https', 'Origine HTTPS publique attendue'
catalog = json.loads(Path('rag/evaluation/performance-rag027.json').read_text())['queries']
cases = [q for q in catalog if q['query_id'] in ('democratie-02','fiscalite-01')]
assert len(cases) == 2 and all(q['split'] != 'evaluation' for q in cases)
rows = []
for case in cases:
    for repetition in range(1, 4):
        started = time.monotonic()
        url = origin + '/api/v1/search?' + urllib.parse.urlencode({'q': case['text'], 'page_size': 20})
        try:
            with urllib.request.urlopen(url, timeout=25) as response:
                data = json.load(response)
                assert data['mode'] == 'hybrid'
                assert data['recipe_version'] == 'h1-public-v2-ts-rank'
                assert data['window']['retrieval_depth'] == data['window']['document_limit'] == 50
                assert data['state'] == 'results' and data['items']
                rows.append(dict(query_id=case['query_id'], repetition=repetition,
                    status=response.status, seconds=time.monotonic()-started,
                    cards=len(data['items']), request_id=response.headers.get('X-Request-ID')))
        except urllib.error.HTTPError as error:
            detail = json.load(error).get('error', {})
            rows.append(dict(query_id=case['query_id'], repetition=repetition,
                status=error.code, code=detail.get('code'), seconds=time.monotonic()-started))
result = dict(recipe='h1-public-v2-ts-rank', runs=rows)
path = Path(sys.argv[2])/'validation-http.redacted.json'
with path.open('x', opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
    json.dump(result, stream, indent=2)
print(json.dumps(result, indent=2))
assert all(r['status'] == 200 for r in rows), 'Validation HTTP échouée : examiner les codes avant de poursuivre'
PY
```

Conserver ensuite uniquement les métriques applicatives expurgées, sans exporter les lignes d’accès HTTP qui peuvent contenir les requêtes :

```bash
docker logs --since "$p6_since" "$p6_new_container" 2>&1 \
  | python3 -c 'import sys; print("".join(l for l in sys.stdin if "hybrid_search_metrics " in l), end="")' \
  > "$p6_private/metrics.private.log"
python3 - "$p6_private/metrics.private.log" <<'PY'
import json, sys
from pathlib import Path
rows = [json.loads(l.split('hybrid_search_metrics ',1)[1]) for l in Path(sys.argv[1]).read_text().splitlines()]
rows = [r for r in rows if r.get('cache_hit') is False and 'lexical' in r and 'vector' in r]
assert len(rows) >= 6, 'Métriques insuffisantes ; ne pas conclure sur le seul temps HTTP'
for r in rows:
    assert r['lexical'] >= 0 and r['vector'] >= 0
    assert r['lexical'] + r['vector'] <= 10, 'Phase SQL publique hors budget'
    print(json.dumps({k:r[k] for k in ('lexical','vector','encoding','fusion','total') if k in r}))
PY
```

Les métriques existantes n’incluent pas de request_id : cette fenêtre peut contenir d’autres recherches publiques. Ne pas attribuer toutes ses lignes aux six appels si du trafic concurrent est présent. Les journaux et les latences HTTP sont complémentaires ; le timeout reste assuré par le code de budget testé, pas par une comparaison du seul temps HTTP à 10 s. Les deux branches lexical + ANN partagent ces 10 s ; le HTTP comprend aussi l’encodage, l’hydratation et le réseau.

Critères de passage : version de recette attendue, six réponses hybrides réussies et non vides, profondeur/sortie 50, liens et pagination utilisables, absence d’erreur 504 `search_sql_timeout`, phase lexical + vectoriel dans le budget, pas de dégradation visible des routes documentaires et métadonnées. Vérifier aussi dans un navigateur les résultats pour les deux requêtes et un cas court, puis ouvrir un résultat et paginer. Les résultats peuvent différer de l’ancienne formule ; l’identité de classement n’est pas un critère de P6. Aucun juge n’est relancé.

Ce contrôle est un smoke test, pas une preuve de latence sous charge. Si les temps augmentent, si les timeouts apparaissent ou si les réponses sont incomplètes, conserver les synthèses et revenir à l’image précédente. Une comparaison de médianes n’est interprétable qu’avec une fenêtre et une charge comparables aux mesures P5.

## Retour arrière

Dans le shell de déploiement, le rollback ne change que l’image de l’app, avec les mêmes Compose, fichiers privés, paramètres et services dépendants :

```bash
APP_IMAGE_TAG="$p6_rollback_tag" "${p6_compose[@]}" config --quiet
APP_IMAGE_TAG="$p6_rollback_tag" "${p6_compose[@]}" \
  up -d --no-deps --no-build --force-recreate app
p6_restored_container=$("${p6_compose[@]}" ps -q app)
[ "$(docker inspect --format '{{.Image}}' "$p6_restored_container")" = "$p6_old_id" ]
docker exec "$p6_restored_container" /opt/venv/bin/python -c \
  'from cahier_rag.search.service.core import SearchRecipe; assert SearchRecipe().version == "h1-public-v1"; print(SearchRecipe().version)'
```

Si le shell a été perdu, reprendre le chemin exact du dossier privé de cette opération et reconstruire les variables avant ces commandes :

```bash
# Affecter p6_private au dossier /srv/cahier-search/diagnostics/p6-... de cette opération.
p6_old_id=$(cat "$p6_private/old-image-id")
p6_rollback_tag=$(cat "$p6_private/rollback-tag")
p6_project=$(cat "$p6_private/project")
mapfile -t p6_compose_files < "$p6_private/compose-files"
p6_compose=(docker compose --project-name "$p6_project" \
  --project-directory /srv/cahier-de-doleances-app --env-file .env.deploy)
for p6_file in "${p6_compose_files[@]}"; do p6_compose+=(-f "$p6_file"); done
```

Si le nouveau tag a déjà été enregistré durablement dans `.env.deploy`, remettre également `APP_IMAGE_TAG` sur le tag de rollback, sans modifier les autres entrées. Vérifier l’état du conteneur, une recherche réelle et les routes existantes. Les curseurs sont à nouveau invalidés par le redémarrage. Aucun retour de données, d’index, de publication ou d’image PostgreSQL n’est requis. Ne pas utiliser `down`, purge d’images, restauration de base ou suppression de volumes.

## Risques résiduels

- La baisse de pertinence hybride et les changements d’ex æquo sont acceptés sur le benchmark expérimental, sans garantie sur toutes les requêtes du corpus complet.
- Les gains P5 sur deux requêtes ne garantissent ni un facteur identique partout, ni le passage de toutes les recherches dans 10 s, particulièrement sous charge.
- La construction Docker et le Compose réel n’ont pas été exécutés pendant cette préparation. Le contrôle du baseline refuse un runtime différent ; il faudra examiner tout refus plutôt que le contourner.
- Le redémarrage du worker peut prendre le temps du chargement CPU du snapshot existant ; une fenêtre d’indisponibilité et l’expiration des curseurs sont attendues.
- Les outils P1–P5 restent historiques. Leur réussite ne prouve pas le déploiement de v2 ; vérifier l’image, la recette retournée et les recherches publiques.
