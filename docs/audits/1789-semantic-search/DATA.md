# Données et reproduction

Tout se trouve dans ce dossier. Les scripts sont autonomes vis-à-vis des bases, services et routes de l’application. Ils importent en lecture les primitives Python du moteur sous `rag/src` pour encoder, préparer les requêtes et fusionner. Aucun import de configuration privée n’est nécessaire. Les textes et embeddings existants sont lus, jamais modifiés.

## Environnement effectivement utilisé

Exécuter depuis la racine du dépôt avec `.venv/bin/python` : Python 3.11, Torch 2.10.0+cpu, Transformers 4.57.6, NumPy 2.2.6, psutil 7.2.2 et les dépendances du package RAG déjà installées, dont SQLAlchemy. Aucun paquet supplémentaire n’a été ajouté. Le BM25 utilise la bibliothèque système `libstemmer.so.0d`, algorithme `french/UTF_8`, et la copie locale des stopwords PostgreSQL14 dans [data/french.stop](data/french.stop). Cette copie et le fichier de bibliothèque sont empreintés dans la provenance.

Le lien Python de `rag/.cache/embeddings-venv` pointe vers un ancien interpréteur temporaire absent. Il n’est ni réparé ni utilisé. Le `.venv` racine disponible possède les versions attendues. Pas de `uv sync`, installation Torch/CUDA ou téléchargement de poids effectué.

## Relire et rechercher avec les fichiers livrés

Les classements et vecteurs fournis sont utilisables sans modèle chargé :

```bash
.venv/bin/python docs/audits/1789-semantic-search/verify.py
.venv/bin/python docs/audits/1789-semantic-search/search.py
.venv/bin/python docs/audits/1789-semantic-search/evaluate.py
.venv/bin/python docs/audits/1789-semantic-search/diagnostics.py
```

Ces commandes réécrivent uniquement les sorties calculées du nouveau dossier. Les temps de recherche varient, les rangs, jugements et métriques restent identiques dans cet environnement.

Reprise complète à vecteurs figés, incluant relecture des artefacts contemporains d’origine et vérification des deux exécutions :

```bash
.venv/bin/python docs/audits/1789-semantic-search/reproduce.py
```

Elle suppose les artefacts locaux RAG-007/RAG-013 présents et intacts. Pour un lecteur ne possédant que ce dossier, `search.py`, `evaluate.py`, `diagnostics.py` et `query.py` fonctionnent avec les copies livrées ; `prepare.py` et la vérification complète des sources nécessitent le dépôt et les artefacts d’origine. Les index PostgreSQL ne sont jamais requis.

## Soumettre une requête

```bash
.venv/bin/python docs/audits/1789-semantic-search/query.py \
  'Comment rendre la justice moins coûteuse pour les justiciables ?' \
  --population mixed --method vector_A --limit 10
```

Choix : `historical` ou `mixed`, puis `lexical`, `vector_A`, `vector_B`, `hybrid_A`, `hybrid_B`. Sortie JSON : rang, score typé, texte, corpus, parent et références. Une requête déjà figée utilise son vecteur livré. Une nouvelle requête vectorielle charge hors ligne le même snapshot BGE local et encode uniquement cette requête ; aucun fichier d’évaluation n’est modifié. La référence lexicale ne charge pas le modèle.

Les résultats d’une nouvelle requête n’ont aucune note de pertinence implicite. Les scores ne sont pas des probabilités. Ne pas modifier `queries.json` pour transformer un essai interactif en résultat du jeu figé.

## Refaire l’encodage limité, si nécessaire

Le snapshot local vérifiable doit exister sous `rag/models/bge-m3/5617a9f61b028005a4858fdac845db406aefb181/`. Le script ne le télécharge pas.

```bash
.venv/bin/python docs/audits/1789-semantic-search/prepare.py
.venv/bin/python docs/audits/1789-semantic-search/encode.py
.venv/bin/python docs/audits/1789-semantic-search/search.py
.venv/bin/python docs/audits/1789-semantic-search/review-decisions.py
.venv/bin/python docs/audits/1789-semantic-search/evaluate.py
.venv/bin/python docs/audits/1789-semantic-search/diagnostics.py
.venv/bin/python docs/audits/1789-semantic-search/verify.py
```

`prepare.py` réutilise les240 vecteurs locaux compatibles et contrôle leurs fichiers. `encode.py` calcule uniquement les deux variantes historiques, les30 requêtes et les16 vérifications de précision. Il réécrit les vecteurs du nouveau dossier ; aucune publication ou base n’est accessible. Le matériel et les bibliothèques doivent être contrôlés avant de comparer des sorties numériques : le pilote ne garantit pas une identité binaire entre CPU/GPU ou versions différentes.

`review-decisions.py` matérialise des décisions manuelles explicites de Codex ; il ne crée aucune note par analyse automatique de mots ou scores. Il n’ajoute pas une nouvelle validation indépendante. Un nouveau jeu nécessite de nouveaux jugements, pas un remplissage automatique à partir de ce fichier.

## Schémas

### `corpus.jsonl`

Une ligne par unité documentaire,509 lignes. Champs : `id` source immuable, `short_id` d’affichage local (`h001`–`h269`, `m001`–`m240`), `corpus`, `parent_id`, `text` exact, `source_text_sha256`, `status`, `title`, `context_prefix`, `references`. Historiques : métadonnées du pilote, section, ordre, étiquette et numéro littéral. Contemporains : question, identifiants réponse/formulaire/contribution et chemin existant de retour à la contribution. Pas d’auteur, date ou question ID inventés.

`short_id` n’est ni un identifiant historique ni une clé applicative. L’identité historique, les XPath, les plages et ancres du pilote restent canoniques pour cet essai. Le titre et le contexte ne remplacent jamais `text`.

### Segments et vecteurs

`historical-segments.jsonl` contient540 lignes : variante, unité, indice, début/fin Unicode dans son `text`, texte réellement encodé, tokens et empreinte. Les270 lignes A correspondent dans l’ordre aux270 lignes de `historical_A.npy`, idem pour B. `contemporary-segments.jsonl` décrit240 vecteurs dans l’ordre de `contemporary.npy`. `queries.npy` suit l’ordre des30 objets dans `queries.json`.

Les fichiers sont des tableaux NumPy float32 à1024 colonnes, lus avec `allow_pickle=False`. Tous les vecteurs sont L2 normalisés. `precision-check-fp32.npy` contient16 vecteurs diagnostiques, dans l’ordre de `encoding.precision_check` ; ils ne font pas partie de l’index évalué.

Les offsets sont des points de code Unicode `[start,end)`, pas des positions d’octets XML ni UTF-16 JavaScript. Les coordonnées historiques `text_spans` recopiées dans `references` concernent le texte décodé du volume, selon les conventions du pilote. Les offsets des segments concernent l’article exact exporté. Leur couverture et leur correspondance avec ce texte sont contrôlées.

### Classements et annotations

`rankings.jsonl` :300 objets `(query_id,population,method)`, scores et jusqu’à50 résultats ordonnés avec ID et segment gagnant lorsque la méthode est vectorielle. La fusion conserve ses traces de rangs par branche.

`results.jsonl` : mêmes300 objets avec seulement les dix premiers enrichis du texte intégral du passage, de sa question éventuelle, des références et du jugement. Le top50 complet reste dans `rankings.jsonl` et le corpus permet d’en résoudre tous les textes.

`review-pool.jsonl` :1139 paires distinctes de top10, présentées sans rang, score ou méthode. `annotations.json` :1155 jugements avec note0–3, raison, texte de preuve et origine `pooled_top10_review` ou témoin complémentaire. Toute note est liée à l’empreinte du corpus, des requêtes et du pool.

`metrics.json` conserve les mesures par requête et agrégées, les dénominateurs et la distinction nDCG gradué/nDCG utile. Un idéal nul donne `null`. Les résultats non jugés au-delà du pool ne deviennent pas automatiquement non pertinents : on ne calcule pas de rappel exhaustif avec eux.

## Traçabilité, contrôles et limites

Les empreintes des trois anciens audits ont été enregistrées avant traitement ; les fichiers originaux restent inchangés. Les empreintes des434 fichiers locaux d’entrées contemporaines et du snapshot sont contrôlées. Les scripts livrent leurs résultats, références et paramètres ; [provenance.json](data/provenance.json) décrit l’état final du code et du périmètre.

`verify.py` vérifie les textes, statuts, parents, offsets, dimensions/normes, annotations et classements. Il injecte en mémoire doublon, texte altéré, mauvais parent, mauvais statut, plage invalide et texte d’encodage réécrit ; les six sont rejetés. Il vérifie aussi que les corrections d’une annotation ne se propagent pas aux autres éléments du même groupe.

Les textes des fichiers de `review/` réduisent les blancs pour la lecture seulement. Ils ne sont pas les entrées des embeddings et ne font pas autorité sur `corpus.text`. Aucun texte n’a été corrigé pour contourner une erreur OCR.

Les scripts ne publient rien ; les conditions des textes numériques et images restent celles signalées dans les audits documentaires. Les résultats restent des artefacts locaux d’étude.
