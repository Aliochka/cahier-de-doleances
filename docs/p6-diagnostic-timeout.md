# P6 — Diagnostic du timeout hybride (23 octobre 2026)

Audit local ; aucune commande Wallace exécutée, aucun changement de H1, base,
index, embeddings ou configuration. Les observations Wallace sont celles de
l’opérateur. L’étape lente n’est pas encore identifiée.

## Conclusions confirmées

Le parcours réel est : HTTP → admission → vérification du corpus/publication →
BGE-M3 → lexical (normalisation, statistiques, classement, lecture des documents)
→ ANN HNSW (et lecture des documents) → RRF → regroupement → hydratation dans
la base applicative → cache/curseurs → sérialisation → réponse.

| Étape | Protection réellement présente |
|---|---|
| HTTP | `Budget(18)` créé dans la route, après réception/routage ; pas de minuterie indépendante imposant une réponse réseau |
| Admission | 1 seconde, un thread de recherche, au plus trois travaux admis |
| Corpus | Reliquat du budget global, contrôles effectués à chaque nouvelle recherche |
| Encodage | Phase 3 secondes ; l’inférence ne peut pas être tuée, le worker reste occupé jusqu’à sa fin |
| Lexical + HNSW | **Une phase commune de 10 secondes**, comprenant les lectures auxiliaires et boucles ANN |
| Fusion | Reliquat global, vérification avant/après |
| Hydratation | Phase de 2 secondes, pool de threads distinct, échéance globale partagée |
| Sérialisation | Reliquat global, vérification avant/après le travail synchrone |

Sources : [route HTTP](../app/routers/api_hybrid_search.py),
[service H1](../rag/src/cahier_rag/search/service/core.py),
[worker](../rag/src/cahier_rag/search/service/worker.py),
[budgets](../rag/src/cahier_rag/search/service/control.py),
[hydratation](../app/services/search_hydration.py).

Le worker et l’hydratateur vérifient l’échéance depuis asyncio environ toutes
les 25ms. **Avec une boucle événementielle disponible, une requête SQL lente
devrait donc produire un 504 avant le timeout client de 25s.** La lenteur SQL
seule n’explique pas l’observation : il faut aussi examiner la disponibilité
de la boucle, l’annulation, le trajet HTTP et le code réellement chargé.

### PostgreSQL et annulation

[ReadConnection](../rag/src/cahier_rag/search/service/reader.py) réapplique
`statement_timeout` avec le budget restant avant chaque instruction.
Les `SET LOCAL ...='30s'` historiques ne donnent donc pas automatiquement 30s
au classement suivant. Ils laissent toutefois une fenêtre avant le prochain
réglage ; ce réglage, les ouvertures/pré-ping, fins de transaction et transports
ne sont pas une échéance réseau absolue. Pool et connexion sont bornés à 1s,
attente de verrou à 500ms. Une attente I/O ou une annulation non traitée
immédiatement reste à observer ; ne pas conclure à un contournement de 10s sur
la seule présence du SET30s.

Le moniteur appelle `connection.cancel()` sous verrou et son arrêt fait un
`join()` sans timeout. Dans le
[code psycopg2 2.9.10 verrouillé](https://github.com/psycopg/psycopg2/blob/2.9.10/psycopg/connection_type.c#L1068),
`psyco_conn_cancel` appelle `PQcancel` sans libérer le GIL. **Si cette annulation
réseau bloque, elle peut empêcher le thread asyncio de renvoyer le 504.**
C’est une vulnérabilité du mécanisme à une annulation bloquante, confirmée par
lecture du code ; sa survenue sur Wallace n’est pas démontrée. Le join seul
bloquerait le thread de recherche, pas nécessairement la réponse HTTP.

### Pourquoi les métriques sont absentes

[observe](../app/hybrid_runtime.py) utilise `app.hybrid_runtime` au niveau INFO.
La configuration Gunicorn du [Dockerfile](../Dockerfile) équipe ses loggers
Gunicorn/Uvicorn mais ne configure pas celui-ci. Reproduction locale avec
Gunicorn23 et les options de logs de l’image : **niveau effectif WARNING,
INFO désactivé, aucun handler racine**. Les logs d’accès200 restent possibles.
Un simple `--log-level info` Gunicorn ne suffit pas à corriger ce logger.

De plus, `observe(metrics)` est appelé seulement après une recherche et une
sérialisation réussies : aucun événement de progression ni métrique d’échec.
Même avec INFO activé, une recherche bloquée ne donne pas sa phase.
Le nombre des200 ne permet pas d’identifier formellement les requêtes sans
corrélation. `healthy` est un état échantillonné, pas une preuve de réactivité
pendant les25s ; `/healthz` ne teste pas H1.

## Hypothèses, par priorité de diagnostic

1. **SQL non couvert par P5, notamment HNSW/lectures disque**, puis difficulté
   d’annulation ou boucle HTTP indisponible. P5 mesurait le classement lexical
   isolé ; ses3,2s n’incluent pas BGE, corpus, statistiques/lectures documentaires,
   ANN ou hydratation. Cache/charge/plans différents peuvent aussi rallonger le
   lexical complet. Ces causes expliquent une phase lente, pas à elles seules
   l’absence de504 : tester l’annulation en parallèle.
2. **Blocage natif/GIL ou pression CPU/mémoire**, lors de l’encodage, d’une
   conversion ou de l’annulation. L’encodage spécifique à la requête reste
   possible, mais ses3s et le contrôle asyncio devraient normalement le borner
   côté client. Les recherches fiscales réussies rendent un défaut général de
   chargement du modèle moins probable.
3. **Écart entre image/code exécutés et audités, ou attente hors parcours attendu**
   (client/proxy). Contrôler l’ID et tester directement le port loopback du labo.
   La version de recette seule ne prouve pas celle de tous les modules.
4. **Hydratation/pool/transport de réponse**, moins probable pour une si petite
   sortie, à confirmer si aucun SQL de recherche n’est actif. Une saturation
   d’admission doit normalement échouer rapidement, pas attendre25s.

Ordre qualitatif, sans probabilité chiffrée ni cause attribuée prématurément.

## Diagnostic minimal proposé — après accord uniquement

**Une seule nouvelle requête `democratie-02`, pas une campagne P5.**

1. Relever l’ID de l’image du laboratoire, sa commande et le contrôle
   `python -m app.search_packaging`. Comparer les empreintes des fichiers
   `worker.py`, `control.py`, `reader.py`, `core.py`, de la route et de
   l’hydratateur aux sources approuvées si l’ID est incertain. Ne pas afficher
   `docker inspect` complet ni l’environnement privé.
2. Avec l’accès administratif **existant**, ouvrir une observation SQL en lecture
   seule dans `cahier_search`. Réutiliser le principe de
   [monitor-search-restore.sql](../deploy/postgres/monitor-search-restore.sql),
   avec la sélection ci-dessous. Affecter `lab_ip` dans psql à l’IP du seul
   laboratoire relevée par inspection Docker. Ne pas accorder de nouveaux droits.

```sql
-- Exemple d'affectation : \set lab_ip 'ADRESSE_PRIVEE_RELEVEE'
SELECT clock_timestamp() AS observed_at, pid, leader_pid, datname, state,
       clock_timestamp()-query_start AS elapsed,
       wait_event_type, wait_event, pg_blocking_pids(pid) AS blockers,
       CASE WHEN state <> 'active' THEN 'not_active'
            WHEN query LIKE '%WITH nearest AS MATERIALIZED%' THEN 'HNSW'
            WHEN query LIKE '%ts_rank(%' THEN 'lexical_rank'
            WHEN query LIKE '%term_stats%' THEN 'lexical_statistics'
            WHEN query LIKE '%set_config%' THEN 'session_budget_or_ANN_settings'
            WHEN datname='cahier_doleances' AND query LIKE '%WHERE a.id=ANY%'
                 THEN 'hydration'
            ELSE 'identity_or_document_fetch_or_other' END AS stage_hint
FROM pg_stat_activity
WHERE (client_addr = :'lab_ip'::inet OR leader_pid IN (
    SELECT pid FROM pg_stat_activity WHERE client_addr = :'lab_ip'::inet))
  AND pid <> pg_backend_pid()
ORDER BY pid;
\watch 1
```

Cette sélection n’affiche ni SQL brut, ni vecteur, ni texte citoyen. Les noms
de phase sont des indices, pas une classification exhaustive. Si l’IP observée
est traduite par NAT, identifier d’abord le client réel avant de filtrer.

3. Reprendre le bloc Python de validation de la
   [procédure P6](rag027-p6-deploiement-ts-rank.md), limité à `democratie-02`,
   **une répétition**, `http://127.0.0.1:8015`, nouveau fichier de sortie.
   Conserver25s pour reproduire le phénomène ; consigner aussi `TimeoutError`
   /`URLError` (le bloc actuel traite surtout `HTTPError`). Ne pas augmenter
   les budgets serveur. En parallèle, à environ5,12 et20s :

```bash
curl --max-time 2 -sS -o /dev/null -w '%{http_code} %{time_total}\n' \
  http://127.0.0.1:8015/healthz
```

Utiliser un Host déjà autorisé si nécessaire. Relever `docker stats --no-stream`
pour le labo et PostgreSQL, ainsi que `free -h`, une fois pendant l’attente.
Arrêter l’observation après environ35s ; vérifier si la session SQL subsiste
après déconnexion HTTP, sans l’annuler administrativement.

4. Interpréter : HNSW actif/IO → branche vectorielle ; ts_rank actif → lexical ;
   `Lock` → PID bloqueur ; hydratation active → base applicative.
   **Si `/healthz` se bloque simultanément**, suspecter GIL/boucle/native,
   spécialement l’annulation à l’expiration SQL. Si santé rapide et SQL terminé
   mais recherche sans réponse, vérifier image/route et attente applicative.
   Un `ClientRead` au repos n’est pas une recherche SQL encore en cours.

5. Seulement si cette observation ne tranche pas : préparer une instrumentation
   **du labo seul** (logger INFO ciblé et capture des piles de threads pendant
   l’attente), sans valeurs locales, SQL ou paramètres. Une pile dans `cancel`
   permettrait de tester directement la piste GIL ; une pile encoder/lexical/ANN/
   hydratation identifierait l’étape. Aucun patch H1 ou instrumentation n’est
   nécessaire pour la première observation proposée ; aucun n’a été appliqué ici.

Ne pas relancer les outils P1–P5 : ils sont utiles pour comparer un plan une fois
la branche identifiée, mais n’observent pas ce parcours HTTP complet.

## Validation de cet audit

Lecture du code applicatif, des dépendances Gunicorn/Uvicorn installées et du
code source psycopg2 verrouillé ; reproduction locale du filtrage INFO sans
connexion ni modèle. Aucun benchmark, recherche réelle, test PostgreSQL ou
intervention sur Wallace. Seul ce rapport est ajouté. Activation publique à
maintenir en attente jusqu’à identification et traitement du dépassement.
