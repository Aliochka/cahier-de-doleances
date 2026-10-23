# P6 — Packaging du backend SSR et H1 CPU ts_rank

## Correction

Construire le **code courant approuvé** avec le Dockerfile racine et
`SEARCH_RUNTIME=cpu`. L’image résultante contient le backend FastAPI actuel,
le paquet H1 actuel et les dépendances verrouillées par
`deploy/search-cpu/uv.lock`. Le frontend Node SSR reste son service séparé.
Ne dériver P6 ni de `ssr-002` (sans dépendances BGE), ni de `search-cpu-001`
(dont le code applicatif peut être ancien). L’ancien
`deploy/search-p6.Dockerfile` a été supprimé pour éviter cette voie incorrecte.

Le Dockerfile vérifie maintenant **dans l’image finale CPU**, sous l’utilisateur
`app`, les imports PyTorch/Transformers/tokenizers/NumPy, l’absence de CUDA,
NVIDIA et Triton, une opération tensorielle CPU, la recette
`h1-public-v2-ts-rank` et sa formule `ts_rank` sans `ts_rank_cd`.
Le contrôle est réexécutable avec `python -m app.search_packaging`.
Il ne charge aucun modèle et ne contacte aucune base.

Aucun changement de recette, index, publication, embeddings ou verrou de
dépendances n’est nécessaire. Un worker Gunicorn est conservé.
Le Dockerfile copie l’intégralité du backend courant, notamment la protection
HTTPS et l’exception HTTP SSR ciblée, ainsi que le paquet `rag` courant.
`compose.deploy.yml` conserve `API_BASE_URL=http://app:8000`, le client SSR
172.30.80.4, les proxies explicitement autorisés et les healthchecks.
L’overlay recherche ajoute les trois montages en lecture seule ; il n’active
pas la recherche par défaut. Aucun fichier privé n’est modifié par cette mission.

Toutes les commandes Wallace ci-dessous sont **futures, après accord humain**.
Aucune commande ne remplace PostgreSQL ni ne lance de migration.

## 1. Capturer le retour arrière exact sur Wallace

Dans un shell Bash dédié, arrêter à toute divergence. Vérifier que le code
courant approuvé comprend les évolutions SSR déployées ; l’image historique CPU
ne constitue pas cette preuve. Les images Wallace ne sont pas accessibles ici.

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
[ "${#p6_candidates[@]}" -eq 1 ]
p6_old_container=${p6_candidates[0]}
p6_old_id=$(docker inspect --format '{{.Image}}' "$p6_old_container")
[ "$p6_old_id" = "$(docker image inspect cahier-de-doleances-app:ssr-002 --format '{{.Id}}')" ]
p6_rollback_tag="ssr-002-preserved-$p6_stamp"
p6_new_tag="search-cpu-p6-ts-rank-$p6_stamp"
docker image tag "$p6_old_id" "cahier-de-doleances-app:$p6_rollback_tag"
p6_project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$p6_old_container")
p6_compose_csv=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$p6_old_container")
[ -n "$p6_compose_csv" ] && [ "$p6_compose_csv" != '<no value>' ]
IFS=',' read -r -a p6_compose_files <<< "$p6_compose_csv"
p6_base=(docker compose --project-name "$p6_project" \
  --project-directory /srv/cahier-de-doleances-app --env-file .env.deploy)
for p6_file in "${p6_compose_files[@]}"; do
  test -r "$p6_file"
  p6_base+=(-f "$p6_file")
done
printf '%s\n' "$p6_old_id" > "$p6_private/old-image-id"
printf '%s\n' "$p6_rollback_tag" > "$p6_private/rollback-tag"
printf '%s\n' "$p6_new_tag" > "$p6_private/new-tag"
printf '%s\n' "$p6_project" > "$p6_private/project"
printf '%s\n' "${p6_compose_files[@]}" > "$p6_private/compose-files"
docker inspect "$p6_old_container" > "$p6_private/container.private.json"
"${p6_base[@]}" config --format json > "$p6_private/compose.private.json"
python3 - "$p6_private" <<'CHECK'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
old = json.loads((p/'container.private.json').read_text())[0]
cfg = json.loads((p/'compose.private.json').read_text())['services']['app']
env = dict(v.split('=', 1) for v in old['Config']['Env'])
assert env.get('HYBRID_SEARCH_ENABLED', '').lower() in ('false', '0')
assert all(env.get(k) == str(v) for k, v in cfg['environment'].items())
assert cfg['image'] == old['Config']['Image']
assert not any(m['Destination'].startswith(('/models', '/run/search')) for m in old['Mounts'])
print('Baseline SSR désactivé conforme ; ID exact conservé.')
CHECK
```

Conserver cette image (idéalement aussi `docker image save` sur un emplacement
avec espace suffisant). Ne pas purger `ssr-002` ni son tag de conservation.
Examiner localement les montages et réseaux effectifs sans publier les JSON privés.
Ne pas continuer si des overrides éphémères manquent ou si `.env.deploy` ne
reproduit pas le conteneur courant. Le rollback utilisera **ces Compose initiaux**,
sans ajout de `compose.search.yml`.

## 2. Construire l’image complète

Depuis le code approuvé et propre, relever la révision ; construire avant toute
interruption. Ces commandes sont aussi utilisables sur une machine de build locale.
Le tag candidat ne doit pas déjà exister. Ne pas retaguer `ssr-002`.

```bash
p6_revision=$(git rev-parse HEAD)
test -z "$(git status --porcelain)"
docker build --pull=false -f Dockerfile \
  --build-arg SEARCH_RUNTIME=cpu \
  --label "org.opencontainers.image.revision=$p6_revision" \
  -t "cahier-de-doleances-app:$p6_new_tag" .
p6_new_id=$(docker image inspect "cahier-de-doleances-app:$p6_new_tag" --format '{{.Id}}')
printf '%s\n' "$p6_new_id" > "$p6_private/new-image-id"
docker run --rm --network none --read-only --tmpfs /tmp \
  "cahier-de-doleances-app:$p6_new_tag" python -m app.search_packaging
```

Le build utilise le verrou CPU existant avec `uv sync --locked`, aucun modèle
n’entre dans l’image. Consigner la taille avec `docker image inspect --format
'{{.Size}}' IMAGE` ; elle n’a pas été mesurée ici. Ne pas reconstruire le frontend.

## 3. Prévalidation privée, sans toucher au service public

Les variables `SEARCH_MODELS_HOST_DIR`, `SEARCH_READER_HOST_FILE` et
`SEARCH_PUBLICATION_HOST_FILE` doivent désigner les ressources **déjà existantes**.
Elles peuvent être exportées dans le shell si elles ne figurent pas dans le
fichier privé. Les clés et DSN restent dans les fichiers privés existants ;
ne pas les afficher ou les copier dans des commandes. Si les secrets requis
manquent, arrêter : leur provisionnement séparé est une intervention humaine.
Vérifier lecture par l’utilisateur `app`, espace mémoire disponible et port8015
libre. Le laboratoire charge une seule copie BGE ; ne pas le laisser tourner
lors de l’activation publique.

```bash
p6_search=("${p6_base[@]}" -f compose.search.yml)
APP_IMAGE_TAG="$p6_new_tag" HYBRID_SEARCH_ENABLED=false \
  "${p6_search[@]}" config --quiet
p6_lab=(docker compose --project-name cahier-search-validation \
  --env-file .env.deploy -f compose.search.validation.yml)
APP_IMAGE_TAG="$p6_new_tag" "${p6_lab[@]}" config --quiet
# Contrôle offline du snapshot existant, sans base et sans téléchargement.
APP_IMAGE_TAG="$p6_new_tag" "${p6_lab[@]}" run --rm --no-deps validation \
  python -m app.search_admin model-check --models /models --threads 2
# Contrôle lecteur/corpus en lecture seule, aucune publication automatique.
APP_IMAGE_TAG="$p6_new_tag" "${p6_lab[@]}" run --rm --no-deps validation \
  python -m app.search_admin inspect --reader-env /run/search/reader.env --check-reader
```

Le contrôle administratif doit réussir avec le lecteur public existant.
Le démarrage H1 ci-dessous vérifiera également le lecteur, la publication signée,
les index et l’identité du corpus. Ne pas republier le manifeste pour contourner
un refus.

```bash
APP_IMAGE_TAG="$p6_new_tag" "${p6_lab[@]}" up -d --no-build validation
p6_lab_container=$(APP_IMAGE_TAG="$p6_new_tag" "${p6_lab[@]}" ps -q validation)
docker exec "$p6_lab_container" python -m app.search_packaging
```

Attendre le chargement du worker (budget d’initialisation existant 120s), contrôler
`/healthz`, puis exécuter les six recherches ci-dessous sur le laboratoire.
La santé seule ne prouve pas que H1 fonctionne. L’en-tête Host doit être accepté
par les domaines autorisés existants ; ne pas élargir TrustedHost pour ce test.
Si `127.0.0.1` n’est pas autorisé, utiliser un Host déjà autorisé dans les sondes.

## 4. Contrôler la recherche réelle avant activation

```bash
p6_public_url=http://127.0.0.1:8015
python3 - "$p6_public_url" "$p6_private" "${p6_validation_name:-validation-lab.redacted.json}" <<'PY'
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path
origin = sys.argv[1].rstrip('/')
parts = urllib.parse.urlsplit(origin)
assert parts.scheme == 'https' or (parts.scheme == 'http' and parts.hostname == '127.0.0.1'), 'HTTPS ou laboratoire loopback requis'
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
path = Path(sys.argv[2])/sys.argv[3]
with path.open('x', opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
    json.dump(result, stream, indent=2)
print(json.dumps(result, indent=2))
assert all(r['status'] == 200 for r in rows), 'Validation HTTP échouée : examiner les codes avant de poursuivre'
PY
```


Critères : six réponses non vides en mode `hybrid`, recette v2, profondeur et
limite50, aucune503/504. Tester aussi un curseur retourné, ouvrir un lien vers
une contribution et contrôler les routes formulaires/statistiques. Aucun corpus
n’est réencodé : seules les requêtes du smoke test sont encodées.
Les timings P5 ne constituent pas une mesure de cette image. Conserver les
métriques lexical/vector/encoding/fusion existantes, sans exporter de textes citoyens.

## 5. Installation publique, recherche encore désactivée

Seulement après réussite du laboratoire et accord pour la recréation du backend :

```bash
APP_IMAGE_TAG="$p6_new_tag" "${p6_lab[@]}" stop validation
APP_IMAGE_TAG="$p6_new_tag" "${p6_lab[@]}" rm -f validation
APP_IMAGE_TAG="$p6_new_tag" HYBRID_SEARCH_ENABLED=false \
  "${p6_search[@]}" up -d --no-deps --no-build --force-recreate app
p6_new_container=$(APP_IMAGE_TAG="$p6_new_tag" "${p6_search[@]}" ps -q app)
[ "$(docker inspect --format '{{.Image}}' "$p6_new_container")" = "$p6_new_id" ]
docker exec "$p6_new_container" python -m app.search_packaging
```

Vérifier santé, accueil, `/enquetes`, formulaires et statistiques SSR. Depuis le
conteneur **frontend existant**, tester réellement le trajet HTTP privé :

```bash
p6_frontend=$("${p6_base[@]}" ps -q frontend)
docker exec "$p6_frontend" node -e \
  'fetch("http://app:8000/api/v1/forms", {redirect:"manual"}).then(r=>{console.log(r.status);process.exit(r.status===200?0:1)}).catch(()=>process.exit(1))'
```

Attendu200, aucune redirection vers `https://app:8000`. Conserver Caddy, domaines,
proxies, cookies et frontend actuels. `--no-deps` évite leur recréation.

## 6. Activation distincte, après validation humaine

**Ne pas inclure ce bloc dans un script automatique de build ou de validation.**
Après accord explicite, utiliser la même image et les mêmes montages :

```bash
APP_IMAGE_TAG="$p6_new_tag" HYBRID_SEARCH_ENABLED=true \
  "${p6_search[@]}" up -d --no-deps --no-build --force-recreate app
```

Refaire uniquement le bloc Python des six recherches après avoir réglé
`p6_public_url` sur l’origine HTTPS publique existante et
`p6_validation_name=validation-public.redacted.json` (nouveau fichier). Ne pas
réexécuter l’affectation loopback. Tester le parcours SSR, la pagination et les liens.
Les curseurs mémoire précédents ne survivent pas à la recréation.
Si le chargement, la recherche ou le SSR échouent, revenir immédiatement au baseline.
La pérennisation ultérieure du tag et du flag dans la gestion de configuration
privée est une opération humaine distincte, non effectuée par cette mission.

## 7. Retour arrière exact ssr-002

Ne jamais utiliser l’overlay recherche pour restaurer le baseline sans montages.
Ne pas tester une recette H1 dans cette image : sa recherche était désactivée.

```bash
APP_IMAGE_TAG="$p6_rollback_tag" HYBRID_SEARCH_ENABLED=false \
  "${p6_base[@]}" config --quiet
APP_IMAGE_TAG="$p6_rollback_tag" HYBRID_SEARCH_ENABLED=false \
  "${p6_base[@]}" up -d --no-deps --no-build --force-recreate app
p6_restored=$(APP_IMAGE_TAG="$p6_rollback_tag" "${p6_base[@]}" ps -q app)
[ "$(docker inspect --format '{{.Image}}' "$p6_restored")" = "$p6_old_id" ]
```

Vérifier le flagfalse, l’absence des trois montages, la santé et le trajet HTTP
SSR précédent, puis accueil/enquêtes/statistiques. Aucun retour de données,
publication ou index n’est nécessaire. Conserver modèle, base et images.
Ne pas utiliser `down -v` ni supprimer des ressources PostgreSQL.

Si le shell est perdu, affecter `p6_private` au dossier exact de l’opération,
puis reconstruire les variables et le Compose initial :

```bash
p6_old_id=$(cat "$p6_private/old-image-id")
p6_rollback_tag=$(cat "$p6_private/rollback-tag")
p6_project=$(cat "$p6_private/project")
mapfile -t p6_compose_files < "$p6_private/compose-files"
p6_base=(docker compose --project-name "$p6_project" \
  --project-directory /srv/cahier-de-doleances-app --env-file .env.deploy)
for p6_file in "${p6_compose_files[@]}"; do p6_base+=(-f "$p6_file"); done
```

Ces commandes supposent les fichiers privés et Compose initiaux inchangés.
S’ils ont été modifiés ultérieurement, restaurer leur configuration approuvée
avant de conclure au rollback. Le contrôle d’ID garantit l’image exacte `ssr-002`,
pas seulement un nom de tag.


## Validations de cette correction de packaging

Exécutées localement le 23 octobre 2026 :

- `python -m app.search_packaging` : PyTorch2.10.0+cpu, Transformers4.57.6,
  tokenizers0.22.2, NumPy2.2.6, recette `h1-public-v2-ts-rank`, absence de CUDA.
- `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m app.search_admin model-check
  --models rag/models --threads 2` : snapshot existant chargé, encodage CPU1024D réussi.
- Suites `tests/test_search_packaging.py`, `tests/test_search_preparation.py`,
  `tests/test_deployment.py`, `tests/test_hybrid_search.py` et
  `rag/tests/unit/test_search_service.py` : **130 réussis, 3 ignorés**
  (tests PostgreSQL faute de `TEST_DATABASE_URL`). Les cas SSR HTTP, refus des
  en-têtes usurpés, recherche désactivée/indisponible et recette sont couverts.
- Ruff, formatage et syntaxe des dix blocs Bash vérifiés ; aucun bloc de
  déploiement exécuté. Trois avertissements préexistants : Starlette/httpx et
  identifiants OpenAPI SEO dupliqués.

Non validés ici : build et exécution Docker (Docker absent), identité/contenu
réels des images Wallace, Compose fusionné avec ses fichiers privés, recherche
contre la base Wallace et parcours navigateur de production. Les tests H1 locaux
ne sont pas une recherche réelle sur ce corpus. Aucun accès PostgreSQL, index,
embedding documentaire ou secret n’a été modifié. Aucun modèle téléchargé.

**Prêt sous conditions :** la voie de packaging et les contrôles locaux sont
prêts ; la construction, le laboratoire et la comparaison SSR doivent réussir
avant activation humaine. Le retour arrière est explicitement l’ID de `ssr-002`
capturé avant intervention, recherche désactivée et Compose initial sans montages.
