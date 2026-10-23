# RAG-015 — Campagnes d'annotation et évaluation progressive

## Résultat et préservation

Deux campagnes indépendantes sont disponibles : **`rag010`** et **`rag014`**.
La campagne initiale conserve ses fichiers, son identité et son comportement.
La seconde réutilise le pool final RAG-014 ; sa session réelle **n'a été ni créée
ni lancée**. Une commande explicite permet de l'activer lorsque l'utilisateur
le souhaite.

La session RAG-010 contient **60 jugements**, sur **3 des 20 requêtes** de
développement. Ses notes, commentaires, brouillons, dates et position ont été
validés en lecture seule. Le fichier complet possède la même empreinte avant
et après les bilans :

```text
5d6e8d6a8937f8153dd19b6219b037bd0a94cb42cdd05fa4dae011b759983a87
```

Aucune donnée synthétique n'a été injectée dans les sessions réelles.

## 1. Architecture et compatibilité

Les nouveaux modules sous `src/cahier_rag/annotation/` sont :

- `campaigns.py` : catalogue explicite, validation des pools, création protégée,
  reprise et snapshots en lecture seule.
- `consolidation.py` : référentiel commun et conflits, sans écrire les sources.
- `reporting.py` : validation des classements existants, couverture, métriques
  RAG-006 et listes de documents à annoter.
- `campaign_cli.py` : commandes de gestion, exports et rapport comparatif.

`Session` reçoit des options de lecture seule et de refus de création implicite.
Leur défaut conserve le comportement existant. Aucun champ n'est ajouté à
l'identité de la session RAG-010 ; les nouvelles sessions portent `campaign_id`.
Le format des notes reste compatible RAG-006. L'interface indique seulement le
libellé neutre de la campagne ; les méthodes/rangs/scores restent masqués.

La commande historique fonctionne toujours, sur le même fichier et le même
verrou :

```bash
uv run --locked --extra annotation cahier-rag-annotate --evaluator ro
```

La lecture de la session réelle confirme sa compatibilité sans réécriture.
Les changements HTML/JS ne modifient ni les raccourcis ni les sauvegardes.
Le libellé de campagne dispose d'un repli pour une page servie par un ancien
processus RAG-010, sans imposer de redémarrage pendant une annotation.

## 2. Activation explicite de la seconde campagne

Depuis `rag/`, avec l'environnement d'annotation existant :

```bash
.venv/bin/python -m cahier_rag.annotation.campaign_cli list

# Création d'une session vide seulement, sans serveur ni jugement :
.venv/bin/python -m cahier_rag.annotation.campaign_cli create \
  --campaign rag014 --evaluator ro

# Lancement explicite ensuite :
export RAG_DATABASE_URL=postgresql:///cahier_rag
.venv/bin/python -m cahier_rag.annotation.campaign_cli open --campaign rag014
```

Adresse : **http://127.0.0.1:8765**. Arrêter le serveur de l'autre campagne avant
de réutiliser le port, ou fournir `--port 8766`. La lecture documentaire reste
une transaction PostgreSQL READ ONLY via les primitives RAG-010.

La session complémentaire sera conservée dans :

```text
evaluation/local/rag015/campaigns/rag014/session.json
```

Son pool reste le fichier immuable
`evaluation/local/rag014/candidates-final/pool.json`. Les 400 couples sont
absents du pool initial. Le catalogue, l'état et les rapports ne créent pas
cette session. `create` refuse de remplacer une session existante ; `open`
reprend évaluateur et graine enregistrés. La graine initiale complémentaire
est `20261021`.

## 3. Référentiel consolidé

La clé est **`(query_id, document_id)`**. Chaque observation conserve campagne,
évaluateur, note, commentaire, date, version originale et empreintes du pool,
des requêtes, du corpus et du snapshot source.

Des notes identiques sur le même couple sont dédupliquées pour les métriques.
Un représentant déterministe fournit l'export compact ; tous les commentaires
originaux restent dans les observations de provenance. Un document jugé pour
une autre requête ne reçoit aucune note par propagation.

Des notes différentes créent un conflit explicite. Il n'y a ni priorité
silencieuse à une campagne, ni règle de « dernière note gagnante ». Le couple
reste hors du référentiel résolu et des métriques. `conflicts` retourne un code
3 en présence de désaccord. L'adjudication reste une étape humaine ultérieure,
sans réécriture des sources.

Le bilan réel actuel contient **60 couples distincts résolus, zéro conflit**.
La consolidation a conservé les 60 commentaires/notes comme données sources,
sans modification. Les exports compacts utilisent la version commune
`rag015-consolidated-v1`, tandis que la provenance garde les versions originales.

## 4. Méthode d'évaluation

Les classements profonds déjà calculés dans
`rag014/development-replay/runs.json` fournissent les recettes gelées lexicales,
vectorielles et hybrides. Leur empreinte, le corpus, les requêtes et les
partitions sont validés. Aucun moteur, modèle ou index n'est modifié ou exécuté.
Aucune requête réservée n'est évaluée.

Les mesures reprennent directement RAG-006 :

- Notes 2/3 pertinentes pour les métriques binaires ; notes 0/1 non pertinentes.
- Precision@k seulement si tous les résultats retournés du top k sont jugés
  résolus. Un moteur retournant moins de k documents garde le dénominateur k.
- MRR sur le classement fourni (50 rangs), indépendamment de k. Le préfixe
  jusqu'au premier pertinent doit être intégralement connu ; un inconnu avant
  ce pertinent interdit le calcul.
- Recall@k et nDCG@k stricts seulement avec une référence exhaustive sur la
  partition de la requête. Une référence pertinente/IDCG vide reste indéfinie.
  Les 60 notes ne sont jamais déclarées exhaustives par un paramètre utilisateur.
- Jugements manquants et conflits distincts de la note zéro ; métriques
  impossibles représentées par `null`, avec une explication.

Une section descriptive sur les seuls documents jugés fournit proportion
pertinente et note moyenne dans le top k. Les MRR/nDCG condensées retirent les
inconnus et modifient les rangs ; leur référence est limitée aux notes connues.
Elles sont explicitement étiquetées comme biaisées et ne remplacent pas les
métriques strictes.

Les moyennes affichent le nombre de requêtes calculables. La comparaison
commune retient les mêmes requêtes pour les trois moteurs. Aucun classement
final de moteurs n'est produit.

## 5. Premier état réel de couverture

Progression : **60/400** pour la campagne initiale, **0/400** pour la campagne
complémentaire non créée. Distribution initiale : **24 notes 0**, **11 notes 1**,
**9 notes 2**, **16 notes 3**. Les deux pools représentent 800 couples distincts.

| Moteur | Top 5 jugé | Top 10 jugé | Top 20 jugé |
|---|---:|---:|---:|
| Lexical pondéré | 15/100 (15 %) | 19/200 (9,5 %) | 26/400 (6,5 %) |
| Vectoriel BGE-M3 | 1/100 (1 %) | 2/200 (1 %) | 4/400 (1 %) |
| Hybride RRF | 6/100 (6 %) | 11/200 (5,5 %) | 20/400 (5 %) |

Les dénominateurs sont des couples requête–document : 20 requêtes, jusqu'à k
résultats chacune. Ces colonnes ne sont pas des mesures de pertinence.

Seul le lexical dispose de top 5 entièrement jugés pour **3 requêtes**.
Aucun top 10 ou top 20 n'est entièrement jugé, pour aucun moteur.
Aucune comparaison commune de Precision@k, Recall@k ou nDCG@k n'est donc fondée.
MRR est calculable sur **une seule requête commune**, avec valeur 1 pour les
trois moteurs : ce constat isolé ne permet aucune conclusion générale.
La campagne initiale et son ordre d'annotation induisent une forte sélection
des requêtes/documentaires connus ; aucun jugement n'a servi à régler les moteurs.

La présence des documents dans les deux pools a aussi été vérifiée :

| Moteur | Top 5 présent dans les pools | Top 10 présent | Top 20 présent |
|---|---:|---:|---:|
| Lexical | 98/100 | 189/200 | 327/400 |
| Vectoriel | 62/100 | 111/200 | 187/400 |
| Hybride | 94/100 | 185/200 | 333/400 |

Ces valeurs représentent un plafond de couverture si tous les couples des
pools actuels étaient annotés. **Même terminer les 800 annotations ne suffira
pas à couvrir tous les premiers rangs**, notamment 38 couples du top 5 vectoriel
absents des deux pools. Ils sont identifiés dans le rapport, sans créer de
nouveau pool ni modifier les pools immuables.

## 6. Commandes et fichiers produits

[Documentation complète et procédure de lancement](campagnes-annotation.md).
Depuis `rag/` :

```bash
.venv/bin/python -m cahier_rag.annotation.campaign_cli status --campaign rag010
.venv/bin/python -m cahier_rag.annotation.campaign_cli export \
  --campaign rag010 --output evaluation/local/rag015/exports/initiale-001
.venv/bin/python -m cahier_rag.annotation.campaign_cli consolidate \
  --output evaluation/local/rag015/references/001
.venv/bin/python -m cahier_rag.annotation.campaign_cli conflicts
.venv/bin/python -m cahier_rag.annotation.campaign_cli report \
  --output evaluation/local/rag015/reports/nouveau-bilan
```

`evaluate` est disponible avec les mêmes options de rapport ; `--rankings`
permet de désigner explicitement un dossier d'expérience compatible.
Les sorties doivent être des nouveaux dossiers. Les exports séparés conservent
les commentaires et l'identité de campagne ; les consolidés séparent notes
résolues, provenance et désaccords.

Le bilan réel validé se trouve sous :

```text
rag/evaluation/local/rag015/reports/validated/
```

Il contient `reference.json`, `judgments.json`, `provenance.json`,
`conflicts.json`, `report.json`, `pending.json` et `source-integrity.json`.
`pending.json` contient les couples restant dans chaque campagne ; `report.json`
identifie aussi les documents non jugés des classements et ceux absents des pools.
L'empreinte des sessions et pools, des requêtes et des classements a été vérifiée
avant/après génération. Les six exports/rapports ont été reconstruits octet pour
octet dans `reports/replay/`.

Ces fichiers peuvent contenir des commentaires humains : ils restent locaux,
ignorés par Git et ne doivent pas être partagés automatiquement. Aucun contenu
personnel n'est reproduit dans le présent compte rendu.

## 7. Tests et limites

- **397 tests réussis, 3 ignorés** dans l'environnement sans torch.
- Les 3 tests optionnels de pooling tensoriel ont été exécutés séparément dans
  l'environnement embeddings : **3 réussis**.
- **16 nouveaux tests** : compatibilité RAG-010, campagnes séparées, reprise,
  lecture seule, erreurs de sauvegarde, refus d'écrasement, commentaires,
  consolidation/déduplication/conflits entre évaluateurs, jugements incomplets,
  métriques exhaustives synthétiques, préfixes MRR inconnus, résultats vides,
  BIGINT, provenance, empreintes, séparation des requêtes/partitions,
  commandes CLI et parcours HTTP de la seconde campagne à l'aveugle.
- Les tests d'écriture utilisent uniquement les dossiers temporaires et données
  fictives. Les intégrations PostgreSQL existantes passent sur les bases `_test`.
- Ruff, `uv lock --check --offline` et `git diff --check` conformes.
- La session réelle est toujours à 60 jugements/révision 60, empreinte intacte.

L'avertissement Starlette/httpx déjà connu demeure dans les tests HTTP.
La seconde interface réelle n'a pas été lancée : son activation est réservée
à une action explicite de l'utilisateur. Le parcours web est validé via
TestClient et sessions synthétiques, pas par une annotation réelle simulée.
Les rapports sont des snapshots, pas une synchronisation permanente. Une
modification concurrente détectée pendant leur lecture provoque un refus et
nécessite de relancer. L'adjudication de conflits n'est pas implémentée.

Les changements restent limités au dossier RAG : gestion des campagnes,
options rétrocompatibles de session/CLI, libellé neutre de l'interface, tests,
point d'entrée et documentation. Aucune dépendance ajoutée ; verrou inchangé.
Aucun moteur, index, modèle, backend, frontend public ou déploiement n'est modifié.
Aucun commit ni push effectué.

## 8. Suite recommandée

Poursuivre les annotations existantes et activer la campagne complémentaire
lorsque souhaité. Conserver les deux campagnes indépendantes et les mêmes
consignes de notation ; ne pas interpréter les ratios descriptifs actuels
comme un classement des moteurs.

Actualiser régulièrement le rapport dans un nouveau dossier. Après ces
campagnes, préparer explicitement un complément ciblé sur les couples de
premiers rangs encore absents/non jugés, en fusionnant les trois moteurs sans
révéler leurs origines à l'évaluateur. La liste des absences est déjà disponible,
mais aucun nouveau pool n'est créé dans cette tâche.

Traiter d'abord les conflits éventuels, puis comparer sur les mêmes requêtes
et avec une couverture documentée. Les requêtes réservées doivent rester hors
réglages jusqu'à une évaluation finale explicitement organisée.
