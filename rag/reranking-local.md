# RAG-020 — Reranking local reproductible

Le reranker reclasse les 50 candidats gelés de H1, H5 et BGE-M3 (V) pour les 20 requêtes de développement de RAG-019. Il ne modifie ni la récupération, ni les index, ni les jugements. Les 20 requêtes réservées ne sont pas exécutées.

## Modèles et dépendances

- R1 : [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3), révision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, Apache-2.0, 567 755 777 paramètres. Cross-encoder XLM-R, état caché 1 024, sortie scalaire (logit). Fenêtre native 8 192 tokens.
- R2 : [Qwen/Qwen3-Reranker-4B](https://huggingface.co/Qwen/Qwen3-Reranker-4B), révision `22e683669bc0f0bd69640a1354a6d0aebcfeede5`, Apache-2.0, 4 021 784 576 paramètres. Modèle causal, état caché 2 560, score scalaire `logit(yes)-logit(no)` suivant le gabarit officiel. Pas de génération de texte. Fenêtre annoncée 32 768 ; le config indique 40 960, nous conservons la borne prudente de la fiche.

Les rerankers n'ont pas de dimension d'embedding de sortie. Les dimensions cachées ne désignent pas un vecteur stocké pour la recherche. Les scores ne sont pas comparables entre modèles.

Jina v2 multilingue et v3 ont été examinés : licence CC-BY-NC-4.0, et intégration avec code distant pour v3. Ils ne sont pas retenus pour cette comparaison à vocation potentiellement publique. Qwen 0.6B existe également ; la comparaison BGE/4B offre deux architectures et coûts distincts. Aucun modèle Jina n'est installé.

L'extra optionnel `reranking` utilise les mêmes versions que `embeddings` : PyTorch 2.10.0 CUDA 12.8, Transformers 4.57.6, Hugging Face Hub 0.36.0, NumPy 2.2.6 et psutil 7.2.2. Aucune dépendance lourde n'est importée par les contrats, le cache ou l'évaluation. La suite normale de tests fonctionne sans cet extra. Les poids locaux et artefacts sont ignorés par Git.

Depuis `rag/`, environnement optionnel dédié possible :

```sh
UV_PROJECT_ENVIRONMENT=.cache/reranking-venv uv sync --locked --extra reranking
.cache/reranking-venv/bin/python -m cahier_rag.reranking.cli models
.cache/reranking-venv/bin/python -m cahier_rag.reranking.cli download
```

L'expérience RAG-020 utilise l'environnement optionnel `.cache/embeddings-venv`, déjà installé avec ces mêmes versions ; l'environnement `.venv` de l'annotation reste intact. Remplacer le chemin de Python dans les commandes si un environnement dédié est utilisé. Les téléchargements viennent exclusivement des dépôts officiels, avec fichiers et SHA-256 vérifiés ; l'inférence charge uniquement les snapshots locaux, sans `trust_remote_code`.

## Recette figée

Texte initial : `Question :\n{question}\n\nRéponse :\n{réponse}`. Alternative `--contextualization answer` disponible, non expérimentée dans ce ticket. Le titre n'est pas ajouté.

Budget commun **1 024 tokens**, gabarit et requête compris, contrôlé avec les deux tokenizers réels. Les segments de réponse ont les mêmes positions Unicode `[start,end)` pour les deux modèles. Recherche déterministe de la plus grande portion admissible ; préférence pour une frontière de paragraphe ou phrase dans sa seconde moitié. Chevauchement de **128 caractères** ; refus si la progression est impossible ou si le contexte seul dépasse le budget. Aucun texte nettoyé, aucun tronquage implicite. Maximum 1 000 segments par unité.

Agrégation fixée avant les notes : maximum des logits des segments. BF16 GPU, float32 CPU, SDPA, seed 42, quatre threads, TF32 désactivé. Lot de deux unités d'une même requête, sous-lots d'au plus quatre segments. Les longs textes produisent plusieurs scores mais une seule unité classée. Égalités départagées par identifiant documentaire.

Les modèles reçoivent exclusivement les textes de requête et document ; aucune note, commentaire humain, origine moteur, rang ou score de récupération. La préparation lit les documents dans la copie SQLite RAG-018 en lecture seule, en contrôlant le manifeste RAG-007 et leurs empreintes. Les identifiants BIGINT restent ceux des `TextUnit` inchangés.

## Exécution et reprise

```sh
.cache/embeddings-venv/bin/python -m cahier_rag.reranking.cli prepare
.cache/embeddings-venv/bin/python -m cahier_rag.reranking.cli run --model R1 --stop-after 2
.cache/embeddings-venv/bin/python -m cahier_rag.reranking.cli run --model R1
.cache/embeddings-venv/bin/python -m cahier_rag.reranking.cli run --model R2
.cache/embeddings-venv/bin/python -m cahier_rag.reranking.cli cpu --model R1 --output evaluation/local/rag020/cpu-R1.json
.cache/embeddings-venv/bin/python -m cahier_rag.reranking.cli cpu --model R2 --output evaluation/local/rag020/cpu-R2.json
uv run --locked python -m cahier_rag.reranking.cli report --output evaluation/local/rag020/new-report
```

La commande `prepare` crée un nouveau plan exclusivement ; elle refuse d'écraser une sortie. `--plan CHEMIN` avant la sous-commande permet un autre plan, sans remplacer l'historique. Les recettes, snapshots, fichiers d'entrée et code critique sont empreintés. Une recette différente refuse la reprise. Une même paire présente dans plusieurs listes n'est calculée qu'une fois par modèle.

Le cache `evaluation/local/rag020/scores.sqlite3` contient les recettes, scores des segments, agrégations et mesures de lots. Scores et checkpoint de lot sont écrits dans la même transaction SQLite. Un lot interrompu est recalculé, les lots validés sont réutilisés sans écrasement. `plan/R1-progress.json` et `R2-progress.json` sont actualisés atomiquement après chaque lot ; les historiques d'exécution et `*-run.json` conservent coûts, ressources et recettes. Pour suivre :

```sh
watch -n 5 cat evaluation/local/rag020/plan/R2-progress.json
```

`reranking.results.rerank_results` adapte des scores validés aux `SearchResult` existants et conserve les `TextUnit` originaux. L'interface backend interchangeable est dans `contracts.py`, l'inférence optionnelle dans `backend.py`, la segmentation dans `preparation.py`, l'orchestration dans `pipeline.py`. Aucun serveur permanent, aucune migration PostgreSQL.

## Mesures et comparaison

Le rapport attend deux calculs complets avant d'ouvrir les jugements historiques en lecture seule. Neuf pipelines : H1/H5/V et leurs variantes R1/R2. Le top 50 conserve exactement les mêmes candidats par pipeline. nDCG poolée : gain `2**note-1`, idéal commun sur l'union RAG-017/018 de 3 254 couples par requête et juge. P@5/10, nDCG@5/10/20, MRR@50, couverture et différences appariées par requête/thématique. Les trois sorties invalides historiques 14B restent absentes ; aucun non-jugé ne devient zéro. Comparaison principale sur les mêmes requêtes entièrement jugées par les deux modèles.

Les tests appariés sur ΔnDCG@10 utilisent un test exact bilatéral de permutation des signes, correction de Holm sur les douze comparaisons prédéfinies (six variantes × deux juges). Analyse exploratoire sur les requêtes de développement, sans optimisation après observation. La correction statistique ne supprime ni les biais du pool, ni ceux de juges de même famille, ni le lien familial Qwen juge/reranker. Une validation humaine indépendante reste nécessaire.

Les latences GPU à 10/20/50 portent sur des préfixes de couples uniques par requête, dans l'ordre des identifiants figés, mesurés pendant le calcul unique : elles ne sont pas les latences de chacun des trois pipelines. Leurs estimations de coûts allouent le temps de chaque lot aux unités puis ajoutent les mesures historiques de récupération. Elles excluent le chargement et sont explicitement séparées des mesures. Pas d'extrapolation CPU directe à Wallace : micro-benchmark de trois couples courts, batch 1, premier passage inclus, sur le Ryzen local.

Les exports `report/{H1,H5,V,...}/runs.json` sont compatibles avec les métriques RAG-006. Le rapport conserve les scores et références de segments séparément ; aucune nouvelle note LLM ou humaine n'est créée. Les fichiers `comparison.json` et `report.md` sont déterministes à partir du cache et des historiques fixés.

## Vérification

```sh
uv run --locked pytest
uv run --locked ruff check .
uv lock --check
```

Les tests synthétiques couvrent limites, texte/provenance, reprises, sorties invalides, déduplication, séparation des recettes, métriques incomplètes et isolement des imports. Les essais réels sont décrits dans `rapport-rag-020.md`. Les 20 requêtes réservées, les campagnes humaines et les artefacts historiques restent inchangés.
