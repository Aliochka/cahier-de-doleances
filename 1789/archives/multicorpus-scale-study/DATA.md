# Données, méthodes et reproduction

Tous les scripts de ce dossier sont expérimentaux et autonomes vis-à-vis des services applicatifs. Ils lisent le code de préparation lexicale et les artefacts précédents ; ils ne changent ni moteur, ni schéma, ni index. Leurs écritures sont limitées au présent dossier et au cache isolé `/tmp/cahier-multicorpus-scale-study/`. Les deux bases acceptées par `common.connect()` sont locales, par socket Unix, avec transactions en lecture seule, délai SQL borné et parallélisme SQL désactivé. Aucune DSN d'environnement ou distante n'est utilisée.

## Lire et vérifier sans base

Depuis la racine du dépôt, avec l'environnement Python local contenant NumPy :

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python 1789/archives/multicorpus-scale-study/replay_verify.py
```

Ce rejeu ne lit pas PostgreSQL, ne charge pas les quatre gigaoctets de vecteurs et n'encode aucun texte. Il reconstruit les 1 800 fusions à partir des branches brutes, vérifie les trajectoires de témoins et régénère `data/checks.json`. Les audits précédents doivent être présents, inchangés ; leurs 225 empreintes et la référence des requêtes sont vérifiées. L'ordre des identifiants de population suffit pour départager les scores égaux et reproduire la sélection.

Les autres calculs légers depuis les résultats archivés sont :

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python 1789/archives/multicorpus-scale-study/aggregate.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python 1789/archives/multicorpus-scale-study/qualitative_metrics.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python 1789/archives/multicorpus-scale-study/render_reports.py
```

Les annotations sont des décisions documentaires enregistrées, pas des prédictions de pertinence produites à partir des scores. `review_decisions.py` transforme les décisions explicites en fichier structuré ; il ne refait pas la lecture humaine et ne constitue pas une évaluation indépendante.

## Fichiers structurés

| Fichier | Description |
|---|---|
| `protocol.json`, `preregistration.json` | Méthode principale figée, paramètres, horodatage et empreintes avant l'examen des nouveaux classements |
| `queries.json` | Les 30 formulations d'origine, copiées sans modification |
| `prior-audits-sha256.json` | Empreintes des 225 fichiers antérieurs protégés, hors caches Python |
| `data/inventory.json` | Comptages locaux, périmètres, manifestes d'encodage, matériel et contrôles de connexion |
| `data/selection.json` | Graine, population source, référence protégée et empreinte de l'ordre sélectionné |
| `data/population-ids.jsonl.gz` | 1 000 000 lignes en ordre d'inclusion : `i`, `id`, `ordinal`, `parent_id`, `questionnaire_id` |
| `data/export.json`, `data/export-progress.json` | Export, empreintes de tous les fichiers lourds, précision numérique des 240 contrôles, progression et ressources |
| `data/preparation.json` | Termes des requêtes, longueurs globales par palier, composition, temps et empreintes des tableaux de calcul |
| `data/history.jsonl` | 269 objets historiques A, strictement identiques à la première expérience, avec textes exacts et références XML/pages/parents |
| `data/witnesses.jsonl` | 270 couples pertinents hérités, texte, jugement et justification d'origine, indicateurs d'article long et d'OCR |
| `data/raw-branches.jsonl.gz` | 180 couples palier–requête : top 1 000 global et contemporain de chaque branche, rangs et scores de tous les historiques, IDF et fréquences |
| `data/rankings.jsonl.gz` | 2 160 classements : 360 lexical/vectoriel et 1 800 hybrides ; top 100 avec rang, identifiant interne `g` et score |
| `data/result-documents.jsonl.gz`, `data/result-documents.json` | Textes complets, questions et références de tous les résultats des top 100 archivés, dédupliqués par identifiant ; lecture possible sans base ni cache lourd |
| `data/witness-tracking.jsonl.gz` | 19 440 lignes : palier, requête, méthode, profondeur, stratégie, rangs globaux, cosinus, présence dans chaque branche candidate, rang final ou `null` |
| `data/per-query-metrics.json`, `data/summary.json` | Comptages et rappels sur témoins connus, composition des top K ; agrégats micro sur les couples requête–article |
| `data/qualitative-documents.jsonl` | 391 documents distincts relus ou associés aux annotations réutilisées, textes complets, questions, références et liens de contexte |
| `data/qualitative-pool.json`, `data/qualitative-judgments.json` | 445 couples : 215 jugements hérités inchangés et 230 nouveaux jugements exploratoires 0–3, justifications et origine |
| `review/q*.txt` | Dossiers de lecture des dix requêtes retenues, textes et questions, sans rang ni similarité ; pas de certification indépendante |
| `data/qualitative-rankings.jsonl`, `data/qualitative-metrics.json` | Résultats avec annotations ; les inconnus restent inconnus, avec bornes plutôt qu'une note zéro implicite |
| `data/context-control-protocol.json` | Diagnostic secondaire ajouté après les premiers classements, distinct du protocole principal |
| `data/context-control.json`, `data/context-control-documents.jsonl`, `data/context-control-scores.npz` | Contrôle des 510 réponses appariées A/B, empreintes, scores et rangs témoins ; aucune modification des classements principaux |
| `data/representation-diagnostic.jsonl.gz` | Rangs des historiques A/B déjà encodés, à chaque palier ; simple diagnostic de sensibilité |
| `data/performance.json`, `data/ranking-costs.json` | Microbenchmarks et coûts de fusion ; matériel et exclusions explicités |
| `data/reference-reproduction.json`, `data/checks.json` | Identité des 90 références, rejeu et invariants contrôlés |
| `data/verification.json`, `data/deliverables-sha256.json` | Dernières vérifications et empreintes des livrables, hors manifeste lui-même |

L'identifiant `g` sert seulement à compacter les résultats : `0..268` indexe les lignes de `history.jsonl` ; `g >= 269` correspond à `i = g - 269` dans `population-ids.jsonl.gz`. Un palier N retient ces N premières lignes contemporaines. L'identifiant documentaire durable reste le champ `id`, et non `g`. Les champs historiques `parent_id`, `references.anchor`, positions et XPath donnent le retour au cahier ; les contemporains relus conservent `references.context_path`, l'identifiant source et celui de la question.

Un rang final `null` indique l'absence de l'union candidate dans la configuration considérée. Il ne signifie pas « rang supérieur à 100 » : les rangs témoins dans le pool complet sont conservés, y compris lorsqu'ils dépassent 100. Dans les branches brutes, un rang lexical absent correspond à un score nul, pas à une requête de base échouée. Les cosinus ne sont pas des probabilités. Les scores de fusion sont des sommes RRF ; les scores BM25 dépendent de la population.

Les textes affichés dans la galerie peuvent avoir leurs blancs réduits ou être abrégés avec `[…]`. Les fichiers JSONL conservent les textes exacts et leurs références. Une pagination héritée de TEI est reprise telle quelle ; un numéro `pb/@n` ne doit pas être interprété systématiquement comme une pagination imprimée contrôlée. L'identifiant de vue et le service d'image restent disponibles pour vérification.

Pour réexaminer un résultat, joindre son champ `g` dans `rankings.jsonl.gz` à `result-documents.jsonl.gz`. Ce fichier fournit tous les textes des résultats archivés, y compris ceux qui n'ont pas reçu de note de pertinence. Il ne dépend pas du cache temporaire du million d'unités. `archive_results.py` reconstruit cette archive depuis les résultats et le cache existant, sans calcul de scores ni connexion SQL.

## Recalcul depuis le cache local existant

Les grands fichiers ne sont pas dupliqués dans le dépôt. Ils restent isolés dans `/tmp/cahier-multicorpus-scale-study/` :

- `modern.f32` : 1 003 055 × 1 024 valeurs float32 little-endian, soit 4 108 513 280 octets ; vecteurs déjà calculés. Les 240 unités protégées utilisent leurs vecteurs archivés de référence.
- `segment-unit.u32` : indice `i` de l'unité de chaque segment, little-endian uint32.
- `modern.jsonl.gz` : textes exacts, questions, identifiants, références et coordonnées des segments du million de contemporains.
- `ordinals.npy` : ordre d'inclusion ; `term-counts.npy`, `lengths.npy`, `parents.npy`, `forms.npy`, `ids.npy`, `id-order.npy` : statistiques et correspondances.
- `vector-scores.npy` : 30 × 1 000 269 scores float32 déjà agrégés au maximum par unité ; `historical-B-scores.npy` : diagnostic secondaire.
- `export.json`, `scores.json` : inventaires et empreintes. Ensemble du cache : environ 4,82 Gio.

Pour recalculer, sans relire la base ni générer d'embeddings :

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python 1789/archives/multicorpus-scale-study/prepare_scores.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python 1789/archives/multicorpus-scale-study/rank.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python 1789/archives/multicorpus-scale-study/aggregate.py
```

Ces commandes écrasent seulement les résultats de ce nouvel audit et les caches de calcul dédiés. Elles vérifient les empreintes des sources. `prepare_scores.py` n'est nécessaire que pour reconstruire les tableaux ; `rank.py` peut utiliser directement les scores déjà présents. Les durées sont remesurées et peuvent varier. Sauvegarder les résultats archivés avant de les recalculer pour conserver la mesure initiale.

Si le cache `/tmp` disparaît, les classements et fusions livrés restent vérifiables, mais le recalcul exhaustif des similarités et du BM25 nécessite une nouvelle lecture des sources locales. Il est possible de conserver le cache sur un support d'étude durable séparé ; aucun déplacement ni import applicatif n'a été effectué. Les empreintes permettent de vérifier une telle copie.

## Reconstituer le cache depuis les sources locales

`inventory.py`, puis `export_local.py`, réalisent uniquement des SELECT sur les deux bases locales autorisées. Le premier vérifie les périmètres et ressources ; le second s'arrête si un export complet existe, refuse un export partiel déjà présent, utilise des lots de 1 000 documents, un délai SQL de 15 s et une limite d'export de 900 s. Les contrôles de ressources exigent au moins 16 Gio disponibles et 40 Gio libres. Il n'y a pas d'ouverture vers un hôte distant.

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python 1789/archives/multicorpus-scale-study/inventory.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python 1789/archives/multicorpus-scale-study/export_local.py
```

Ce rejeu exige le même espace local `full`, la même empreinte de recette et le même ensemble d'ordinaux. Les sources sont arrêtées à leur état vérifié : ne pas interpréter un inventaire rafraîchi différent comme une reproduction du même tirage. Le protocole principal et ses empreintes ne doivent pas être régénérés pour masquer un changement de population. Les scripts restent volontairement liés à cette expérience ; changer de graine, de source ou de méthode relève d'une nouvelle expérience.

## Versions et dépendances

Calculs : Python 3.11.17, NumPy 2.2.6, psutil 7.2.2, psycopg2 et `libstemmer` système. Le fichier `data/french.stop` reprend la référence de l'expérience précédente ; `lexical.py` reprend sa classe Snowball et appelle uniquement la préparation de requête existante dans `rag/src`. Aucun paquet n'a été ajouté au projet. Les versions installées et empreintes finales sont archivées dans `data/verification.json`.

Encodage : **aucune nouvelle inférence**. Requêtes et historiques reprennent les artefacts float32 CPU antérieurs ; les contemporains proviennent des calculs bfloat16 locaux antérieurs. Modèle BGE-M3 à révision figée, dimension 1 024, CLS/L2. Les écarts numériques documentés ne sont pas assimilés à une égalité bit à bit.

Graphiques : Matplotlib 3.10.7 est installé uniquement dans `/tmp/multicorpus-scale-plot-tools/`, avec son propre NumPy 2.4.6 et ses dépendances ; il n'est pas utilisé pour les calculs de classement. `plot.py` choisit le backend sans interface `Agg` et le cache de fontes `/tmp/multicorpus-scale-mpl`. Les cinq figures sont exportées en SVG/PDF/PNG :

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python 1789/archives/multicorpus-scale-study/plot.py
```

Sans cet environnement graphique isolé, les figures déjà fournies restent consultables et partageables. Recréer ce répertoire avec les mêmes versions est suffisant ; il n'est pas nécessaire de modifier les dépendances de l'application. La mise en page est reproductible, mais les métadonnées de date des PDF/SVG peuvent changer lors d'une régénération.

## Vérifications exécutées

```sh
.venv/bin/ruff check 1789/archives/multicorpus-scale-study
.venv/bin/ruff format --check 1789/archives/multicorpus-scale-study
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python 1789/archives/multicorpus-scale-study/replay_verify.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python 1789/archives/multicorpus-scale-study/verify_artifacts.py
PYTHONPATH=rag/src PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider rag/tests/unit/test_embeddings.py rag/tests/unit/test_hybrid.py
```

Les 36 tests existants d'embeddings et de fusion passent. Le rejeu contrôle les sorties et les invariants ; un contre-exemple démontre qu'une remise à 1 des rangs par corpus changerait abusivement la fusion. Les fichiers structurés sont relus, les liens locaux et empreintes vérifiés. Aucun build frontend ni test d'intégration nécessitant des écritures en base n'est nécessaire pour des scripts d'audit sans modification applicative.
