# Collecte des trois plans lexicaux H1 sur Wallace

Préparation du 22 octobre 2026. **Outil et tests locaux prêts ; aucune collecte sur Wallace effectuée.** La recette de recherche et les services publics ne sont pas modifiés. L’instrumentation P0 des timeouts reste un chantier séparé.

## Fonctionnement et garanties

[explain_h1_lexical.py](../scripts/explain_h1_lexical.py) appelle le véritable `TunedSearch.lexical`, avec statistiques figées, sans préfiltrage, filtres NULL et limite 50. Il exécute la tokenisation, la normalisation française dans PostgreSQL, les contrôles d’état et la lecture des statistiques IDF existantes. Il ne compte pas les documents et ne recalcule pas les DF depuis le corpus.

La connexion de diagnostic reconnaît l’appel final à `execute` par son code appelant, son SQL et l’identité de son dictionnaire de paramètres. Elle transmet uniquement :

```sql
EXPLAIN (VERBOSE, COSTS, SETTINGS, FORMAT JSON)
<SQL final original, avec ses paramètres liés originaux>
```

Le SQL, ses définitions de paramètres, les valeurs Python et leurs types sont conservés. L’outil n’ajoute ni préparation serveur, ni simplification de la formule, ni modification des filtres. Après le plan, une exception interne dédiée interrompt immédiatement l’appel avant l’hydratation. Aucune ligne documentaire n’est retournée.

Toute autre instruction applicative doit appartenir à une liste de lectures fixes de préparation, d’identité ou de métadonnées, extraite des fonctions H1 vérifiées. Une lecture documentaire, un comptage du corpus, un EXPLAIN fourni autrement ou une instruction inconnue est refusé avant le driver. Il n’existe pas de chemin de repli exécutant le classement.

L’outil vérifie avant connexion les empreintes de sept fichiers H1 de référence, ainsi que SQLAlchemy 2.0.43, psycopg2-binary 2.9.10 et l’empreinte du jeu de 32 requêtes. Une image contenant une autre version de ces fichiers ou dépendances est refusée, sans adapter silencieusement le diagnostic. `base_commit` désigne la référence H1 ; les empreintes attestent les fichiers concernés, pas la totalité d’un checkout Git dans l’image.

Les deux bases configurées sont contrôlées avec les gardes d’identité existantes ; les rôles sont vérifiés par `check_reader_role`. Les connexions sont explicitement en lecture seule, chaque transaction commence par `SET TRANSACTION READ ONLY`, puis l’état effectif est vérifié. Toutes les transactions finissent par rollback, y compris en échec et après capture du plan.

Les limites par défaut sont : connexion 1 s, instruction au plus 2 s, verrou 200 ms et échéance commune de 10 s par cas. Le `statement_timeout` est plafonné au reliquat avant chaque instruction. L’état effectif des deux timeouts est contrôlé. Le `SET LOCAL ...='30s'` historique de `TunedSearch` est neutralisé dans cette connexion de diagnostic. Le moniteur d’échéance peut annuler la connexion empruntée. Les limites CLI peuvent être réduites, jamais augmentées au-delà de ces plafonds.

Les trois cas sont traités une fois, séquentiellement et dans cet ordre :

1. `fiscalite-05` — rapide selon les relevés transmis.
2. `democratie-02` — lente selon les relevés transmis.
3. `fiscalite-01` — timeout selon les relevés transmis.

À la première erreur, la collecte s’arrête : aucun nouvel essai ni délai supérieur automatique. Les fichiers de synthèse signalent les cas tentés ; les cas absents n’ont pas été tentés. La comparaison des trois générations du corpus doit rester identique.

L’outil n’initialise pas le backend applicatif, BGE-M3 ou HNSW ; il importe seulement les composants nécessaires au lecteur et à la recherche lexicale. Aucun modèle n’est monté dans le conteneur proposé. Aucun nouveau paquet n’est installé.

## Validation locale

Commande exécutée sur HAL9000, sans réseau ni connexion PostgreSQL :

```bash
.cache/search-cpu-venv/bin/python -m pytest tests/test_explain_h1_lexical.py -q
```

Résultat : **33 tests réussis**. Un avertissement de dépréciation déjà présent provient de l’import de `fastapi.testclient` par la configuration générale des tests ; il est sans rapport avec la collecte.

Les tests couvrent le chemin lexical réel avec transports simulés, les trois cas, l’équivalence du SQL compilé pour psycopg2 et des types/valeurs liés, l’interception unique, l’absence d’hydratation, le refus des SQL inattendus et d’EXPLAIN ANALYZE, la lecture seule, les timeouts effectifs et résiduels, les rollbacks de réussite/échec, les empreintes, les sorties privées et leur expurgation. Les connexions psycopg2 et réseau sont interdites dans les tests. Un sous-processus vérifie aussi que l’import ne charge ni `torch` ni `transformers`.

Ces tests **ne constituent pas une validation PostgreSQL réelle ou Docker sur Wallace**. La première collecte reste soumise aux permissions du lecteur, à l’accessibilité des bases et aux fichiers installés dans l’image.

## Commandes Docker pour Wallace

Les commandes suivantes sont destinées à l’opérateur ; elles n’ont pas été exécutées par l’agent. Elles utilisent l’image CPU existante et le réseau PostgreSQL externe documentés dans le dépôt. Le nouveau script est monté séparément : aucune reconstruction d’image ni relance du site n’est nécessaire.

Préconditions :

- Le script approuvé est présent à `/srv/cahier-de-doleances-app/scripts/explain_h1_lexical.py` sur Wallace, et le jeu existant est dans ce même checkout.
- L’image locale CPU est `cahier-de-doleances-app:search-cpu-001` ; ses sources H1 doivent correspondre à la référence. Si le tag local est différent, remplacer seulement le nom d’image par celui déjà installé.
- Le lecteur privé existant est `/srv/cahier-search/private/reader.env` et ses destinations sont joignables depuis `cahier-de-doleances_cahier-internal`.
- L’opérateur a le droit Docker, peut lire ce fichier privé et peut écrire dans `/srv/cahier-search/diagnostics`. Le conteneur prend son UID/GID ; aucune permission du fichier lecteur n’est élargie.

Vérifier les fichiers et l’image sans afficher de configuration privée :

```bash
cd /srv/cahier-de-doleances-app

git rev-parse HEAD
sha256sum rag/evaluation/performance-rag027.json
test -r scripts/explain_h1_lexical.py
test -r /srv/cahier-search/private/reader.env
docker image inspect --format '{{.Id}}' cahier-de-doleances-app:search-cpu-001
docker network inspect --format '{{.Name}}' cahier-de-doleances_cahier-internal
```

La référence H1 est `0eebaecbd0f14bc88ae12d85cc6fba35d0fd5a73`. Un commit ultérieur ne doit contenir que les ajouts approuvés ; le contrôle embarqué refuse les modifications des sept sources épinglées. Le SHA-256 du jeu doit être :

```text
f1ad4fef0eae346ce9a2413426ecf7214406440d0e89ea4821fe6913e2e7583e
```

Créer le répertoire privé de sorties, puis lancer le conteneur ponctuel :

```bash
umask 077
mkdir -p /srv/cahier-search/diagnostics

docker run --rm --pull=never \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --network cahier-de-doleances_cahier-internal \
  --user "$(id -u):$(id -g)" \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --memory 512m --memory-swap 512m --cpus 1 --pids-limit 64 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env HF_HUB_OFFLINE=1 \
  --env TRANSFORMERS_OFFLINE=1 \
  --mount type=bind,src=/srv/cahier-de-doleances-app/scripts/explain_h1_lexical.py,dst=/diagnostic/explain_h1_lexical.py,readonly \
  --mount type=bind,src=/srv/cahier-de-doleances-app/rag/evaluation/performance-rag027.json,dst=/diagnostic/queries.json,readonly \
  --mount type=bind,src=/srv/cahier-search/private/reader.env,dst=/run/reader.env,readonly \
  --mount type=bind,src=/srv/cahier-search/diagnostics,dst=/results \
  --entrypoint /opt/venv/bin/python \
  cahier-de-doleances-app:search-cpu-001 \
  /diagnostic/explain_h1_lexical.py \
  --reader-env /run/reader.env \
  --queries /diagnostic/queries.json \
  --query-ids fiscalite-05 democratie-02 fiscalite-01 \
  --statement-timeout-ms 2000 \
  --lock-timeout-ms 200 \
  --case-deadline-seconds 10 \
  --output-dir /results/h1-explain-wallace-001
```

Ne pas créer au préalable le sous-répertoire `h1-explain-wallace-001` : l’outil le crée en mode 0700 et refuse de réutiliser un répertoire existant. Le répertoire parent `diagnostics` doit être privé ; s’il existait déjà, vérifier ses permissions avant la collecte. Aucun mot de passe n’est passé en argument ou dans une variable shell. Ne pas exécuter `docker inspect` sans format ni afficher le fichier lecteur : cela pourrait exposer d’autres valeurs privées.

Cette commande crée un nouveau conteneur sans ports publiés, sans montage du modèle et sans commande Compose. Elle ne modifie aucun service existant. Les limites mémoire/CPU ci-dessus concernent **le client de collecte**, pas les ressources PostgreSQL du serveur.

Sortie terminal attendue : uniquement un statut JSON. Code retour 0 si les trois plans ont été collectés ; 1 en cas de collecte incomplète ou de refus ; 2 pour des arguments invalides. Ne pas relancer automatiquement sur erreur. Si la sortie indique un échec avant création du répertoire, vérifier les préconditions et empreintes sans publier le fichier lecteur ni une exception brute.

## Résultats et partage

En réussite, cinq fichiers sont créés en mode 0600 :

| Fichier | Contenu | Diffusion |
|---|---|---|
| `fiscalite-05.plan.json` | EXPLAIN JSON brut du cas rapide | Privé |
| `democratie-02.plan.json` | EXPLAIN JSON brut du cas lent | Privé |
| `fiscalite-01.plan.json` | EXPLAIN JSON brut du cas en timeout | Privé |
| `manifest.private.json` | Empreintes, types des paramètres, génération, réglages de session et transactions | Privé |
| `summary.redacted.json` | Projection structurelle expurgée des trois plans | Fichier à transmettre pour l’analyse initiale |

Afficher uniquement la synthèse :

```bash
cat /srv/cahier-search/diagnostics/h1-explain-wallace-001/summary.redacted.json
```

La synthèse conserve les types de nœuds, noms d’index/relations, coûts, lignes/largeurs estimées, parallélisme, workers et options JIT. Les clés de tri sont classées en `weighted_score`, `document_id_collate_C` ou `expression_redacted`. Les filtres, conditions d’index/recheck, expressions `Output`, valeurs liées et réglages bruts du plan ne sont jamais copiés dans cette synthèse. Les noms techniques de relations/index restent visibles pour permettre la comparaison.

Les plans bruts peuvent contenir des constantes issues des requêtes de test ; ils restent privés. Aucun texte documentaire du corpus n’est sélectionné ou exporté. Les erreurs publiques n’exposent ni SQL, ni paramètres, ni URL, ni message brut PostgreSQL.

Les estimations permettront de comparer les partitions/index utilisés, les scans séquentiels ou bitmap, la cardinalité entrant dans le tri, l’emplacement du `Limit`, le parallélisme et le JIT prévu. Elles ne donnent pas de temps réel, de buffers lus, de pages lossy effectives ou de débordement effectif du tri. Aucun benchmark, EXPLAIN ANALYZE, ANALYZE statistique, changement permanent de paramètre ou reconstruction d’index ne fait partie de cette procédure.
