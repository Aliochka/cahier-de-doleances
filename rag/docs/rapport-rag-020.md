# RAG-020 — Expérimentation du reranking

## Résultat

Les deux rerankers ont été téléchargés depuis leurs dépôts officiels, vérifiés puis exécutés hors ligne sur la RTX 5090. Les neuf pipelines ont été comparés sur les mêmes **17 requêtes entièrement jugées** par les deux référentiels LLM. Les 20 requêtes de développement ont toutes été reclassées ; les 20 requêtes réservées ne sont pas exécutées.

**H1 + Qwen3-Reranker-4B obtient la meilleure moyenne nDCG poolée@10 selon chacun des deux juges.** BGE apporte un compromis de coût intéressant. Ces constats portent sur des jugements automatiques, ne constituent pas une validation humaine et ne justifient pas à eux seuls un choix de production.

## Modèles et protocole figé

| Reranker | Dépôt officiel | Révision | Paramètres | Fenêtre native | Licence |
|---|---|---|---:|---:|---|
| R1 | [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` | 567,755,777 | 8,192 | Apache-2.0 |
| R2 | [Qwen/Qwen3-Reranker-4B](https://huggingface.co/Qwen/Qwen3-Reranker-4B) | `22e683669bc0f0bd69640a1354a6d0aebcfeede5` | 4,021,784,576 | 32,768 | Apache-2.0 |

BGE : cross-encoder XLM-R, état caché 1 024, sortie scalaire logit. Qwen : état caché 2 560, score `logit(yes)-logit(no)` monotone avec la probabilité yes officielle, sans génération. Ces dimensions cachées ne sont pas des dimensions d’embeddings. Qwen annonce 32 768 tokens dans la fiche tandis que sa configuration indique 40 960 : borne native prudente de 32 768 retenue. La fenêtre expérimentale est limitée à 1 024 pour les deux.

Jina v2 multilingue et v3 ont été examinés mais non retenus : CC-BY-NC-4.0, avec code distant requis dans l’exemple v3. Qwen 0.6B a aussi été considéré ; BGE/4B permettent ici de comparer deux architectures de coûts nettement distincts. Pas de quantification, FlashAttention externe ou serveur permanent.

La sélection des modèles, les paramètres et le code critique ont été figés avant toute consultation des notes pour cette expérience. Les deux inférences ont été terminées avant l’ouverture en lecture seule des référentiels RAG-017/018.

- Question originale + réponse, libellés explicites ; alternative réponse seule disponible mais non expérimentée.
- Budget total **1 024 tokens**, requête et gabarits compris, précontrôlé avec les deux tokenizers réels. Segments de réponse identiques pour les deux rerankers, positions Unicode `[start,end)`, chevauchement **128 caractères**, frontières de phrases/paragraphes privilégiées. Aucun tronquage silencieux.
- Maximum des scores de segments fixé avant l’expérience ; une unité originale reste un seul résultat. Départage par identifiant documentaire.
- GPU BF16, CPU float32, SDPA, seed 42, quatre threads, TF32 désactivé. Lot de deux unités, sous-lots de quatre segments maximum.
- Les modèles reçoivent les textes seuls : ni moteurs, rangs, scores RRF, notes, commentaires humains ou jugements des autres modèles.

## Architecture et traçabilité

`src/cahier_rag/reranking/` contient les contrats et recettes, registre officiel, backend Transformers optionnel, segmentation commune, préparation, cache SQLite transactionnel, pipeline avec reprise, micro-benchmark CPU et comparaison. `results.rerank_results` conserve les `SearchResult`/`TextUnit` originaux. Pas de modification du stockage ou des moteurs historiques, aucune migration.

Les dépendances lourdes sont isolées dans l’extra `reranking` et reprennent les versions déjà verrouillées pour les embeddings : torch 2.10.0/cu128, transformers 4.57.6, huggingface-hub 0.36.0, numpy 2.2.6, psutil 7.2.2. Aucun changement de version de dépendance existante. L’expérience réutilise `.cache/embeddings-venv`, compatible ; `.venv` de l’annotation reste intact.

- Plan : `evaluation/local/rag020/plan/manifest.json`, empreinte `95eef1974cf3ee1087f03d38b35aad89ea19dae1d86859167ce6c2eea13501dc`.
- Corpus RAG-007 : `d0173a371df7fc5d6b5d8ca393ea3f230349140b1cfb92a1ec4a2280200033cc` ; configuration gelée RAG-019 : `68a359ab000a61ab4071468224b736c3809d23698e7c6080049a5ddb5a9cfa68`.
- Entrées aveugles et positions : `plan/inputs.jsonl`. Candidats sources inchangés : `plan/candidates.json`.
- Scores et mesures : `evaluation/local/rag020/scores.sqlite3`. Scores des segments et checkpoint du lot dans une même transaction ; recettes et empreintes contrôlées, aucun écrasement de score valide incompatible.
- Progression : `plan/R1-progress.json`, `plan/R2-progress.json` ; historiques : `plan/history/`.
- Rapports finaux : `evaluation/local/rag020/report/{comparison.json,report.md}` ; exports directs `query_id → [document_id]` par pipeline, compatibles RAG-006. Scores de segments conservés séparément.
- CPU : `evaluation/local/rag020/cpu-R1.json`, `cpu-R2.json`. Tous ces artefacts et les poids restent locaux, ignorés par Git.

## Volumes et couverture

Les trois pipelines représentent 3 000 occurrences de classement (20 × 50 × 3), dédupliquées en **1 496 couples**, calculés une seule fois par reranker. **2 016 segments**, dont **136 couples multisegments**, maximum 20 segments pour un couple. Longueur maximale réelle : 924 tokens BGE et 1 024 Qwen, gabarits compris.

Chaque reranker restitue 1 496 scores finis, avec toutes les références et positions vérifiées. L’arrêt contrôlé après deux couples, suivi de la reprise, a réutilisé ces deux scores sans les recalculer. Les classements finaux gardent exactement les mêmes 50 candidats que leurs pipelines de départ.

Qwen3-8B couvre 1 000/1 000 occurrences top 50 de chaque pipeline. Qwen3-14B couvre H1 à 998/1 000, H5 et V à 1 000/1 000. Les trois sorties invalides historiques restent invalides ; deux affectent les candidats H1. Aucun nouveau jugement n’est créé.

La comparaison principale exclut `fiscalite-04`, `fiscalite-05`, `services_publics-01`, car leur référence poolée commune n’est pas entièrement jugée par les deux modèles. Ce filtre conservateur s’applique identiquement aux neuf pipelines, même lorsqu’un top 50 particulier est entièrement couvert.

## Pertinence : mêmes 17 requêtes

Pertinence binaire : notes 2–3. nDCG : gain `2**note-1`, idéal commun sur les **3 254 couples RAG-017/018**, séparé par requête et juge ; aucune note manquante remplacée par zéro, aucun rappel exhaustif. Les rapports JSON détaillent aussi les couvertures et métriques calculables sur les 20 requêtes.

| Juge | Pipeline | P@5 | P@10 | nDCG@5 | nDCG@10 | nDCG@20 | MRR@50 |
|---|---|---:|---:|---:|---:|---:|---:|
| qwen3-14b | H1 | 0.9059 | 0.8941 | 0.7536 | 0.7203 | 0.6836 | 0.9608 |
| qwen3-14b | H1+R1 | 0.9412 | 0.9294 | 0.7915 | 0.7606 | 0.7535 | 1.0000 |
| qwen3-14b | H1+R2 | 0.9529 | 0.9412 | 0.8150 | 0.7985 | 0.7753 | 1.0000 |
| qwen3-14b | H5 | 0.9176 | 0.9118 | 0.7319 | 0.7120 | 0.6781 | 0.9314 |
| qwen3-14b | H5+R1 | 0.9529 | 0.9294 | 0.8052 | 0.7691 | 0.7535 | 1.0000 |
| qwen3-14b | H5+R2 | 0.9412 | 0.9294 | 0.7974 | 0.7740 | 0.7478 | 1.0000 |
| qwen3-14b | V | 0.8941 | 0.8647 | 0.7204 | 0.7048 | 0.6760 | 1.0000 |
| qwen3-14b | V+R1 | 0.9529 | 0.9235 | 0.8162 | 0.7767 | 0.7425 | 0.9706 |
| qwen3-14b | V+R2 | 0.9647 | 0.9471 | 0.8087 | 0.7873 | 0.7460 | 1.0000 |
| qwen3-8b | H1 | 0.9529 | 0.9353 | 0.6366 | 0.6336 | 0.6565 | 0.9118 |
| qwen3-8b | H1+R1 | 0.9765 | 0.9882 | 0.7020 | 0.7025 | 0.7251 | 1.0000 |
| qwen3-8b | H1+R2 | 0.9882 | 0.9824 | 0.7260 | 0.7332 | 0.7483 | 1.0000 |
| qwen3-8b | H5 | 0.9412 | 0.9294 | 0.6116 | 0.6176 | 0.6458 | 0.9706 |
| qwen3-8b | H5+R1 | 0.9882 | 0.9706 | 0.6910 | 0.6876 | 0.7216 | 1.0000 |
| qwen3-8b | H5+R2 | 0.9882 | 0.9647 | 0.7226 | 0.7050 | 0.7227 | 1.0000 |
| qwen3-8b | V | 0.9647 | 0.9353 | 0.6220 | 0.6210 | 0.6485 | 1.0000 |
| qwen3-8b | V+R1 | 0.9882 | 0.9706 | 0.6876 | 0.6754 | 0.7079 | 1.0000 |
| qwen3-8b | V+R2 | 0.9882 | 0.9765 | 0.7138 | 0.7049 | 0.7175 | 1.0000 |

### Gains, régressions et incertitude

H1 + R2 passe de 0,6336 à **0,7332** pour le juge 8B (Δ +0,0996) et de 0,7203 à **0,7985** pour le juge 14B (Δ +0,0781). BGE sur H1 atteint respectivement 0,7025 et 0,7606.

Les six variantes progressent en moyenne selon chaque juge, mais pas sur toutes les requêtes. Exemples sur ΔnDCG@10, sans reproduire de texte citoyen :

| Juge | Pipeline | Requête | Δ nDCG@10 |
|---|---|---|---:|
| qwen3-8b | H1+R2 | ecologie-01 | +0.3262 |
| qwen3-8b | H1+R2 | services_publics-06 | +0.2219 |
| qwen3-8b | H1+R2 | democratie-02 | -0.1158 |
| qwen3-8b | H1+R2 | democratie-01 | -0.0720 |
| qwen3-14b | H1+R2 | fiscalite-01 | +0.3060 |
| qwen3-14b | H1+R2 | ecologie-06 | +0.2339 |
| qwen3-14b | H1+R2 | democratie-02 | -0.0409 |
| qwen3-14b | H1+R2 | democratie-03 | -0.0402 |
| qwen3-14b | H1+R1 | ecologie-03 | -0.1682 |

**23 cas** pipeline/requête ont des signes de gain opposés entre les deux juges ; liste complète dans `comparison.json`. Par exemple, ne pas traiter un gain moyen comme une amélioration systématique de toutes les intentions.

| Comparaison | Gains/égalités/pertes | Δ moyenne | p exact | p Holm (12) |
|---|---|---:|---:|---:|
| qwen3-14b:H1+R1 | 10/1/6 | +0.0402 | 0.1361 | 0.1516 |
| qwen3-14b:H1+R2 | 14/1/2 | +0.0781 | 0.0007 | 0.0081 |
| qwen3-14b:H5+R1 | 11/1/5 | +0.0571 | 0.0258 | 0.1031 |
| qwen3-14b:H5+R2 | 13/0/4 | +0.0620 | 0.0103 | 0.0517 |
| qwen3-14b:V+R1 | 10/0/7 | +0.0719 | 0.0282 | 0.1031 |
| qwen3-14b:V+R2 | 13/0/4 | +0.0825 | 0.0056 | 0.0358 |
| qwen3-8b:H1+R1 | 12/0/5 | +0.0690 | 0.0758 | 0.1516 |
| qwen3-8b:H1+R2 | 12/0/5 | +0.0996 | 0.0045 | 0.0358 |
| qwen3-8b:H5+R1 | 13/0/4 | +0.0700 | 0.0048 | 0.0358 |
| qwen3-8b:H5+R2 | 13/0/4 | +0.0874 | 0.0026 | 0.0231 |
| qwen3-8b:V+R1 | 14/1/2 | +0.0544 | 0.0007 | 0.0081 |
| qwen3-8b:V+R2 | 16/0/1 | +0.0839 | 0.0001 | 0.0009 |

Test exploratoire bilatéral exact par permutation des signes, correction de Holm sur les douze comparaisons fixées avant lecture des notes. H1+R2 et V+R2 dépassent ce contrôle à 5 % selon les deux juges ; H5+R2 manque de peu le seuil selon 14B (0,0517). Cela ne constitue pas une preuve de généralisation : requêtes de développement non aléatoires, notes automatiques et famille Qwen commune au reranker et aux juges.

### Par thématique

| Juge | Pipeline | Domaine | P@10 | nDCG@10 |
|---|---|---|---:|---:|
| qwen3-14b | H1 | democratie | 0.8800 | 0.7178 |
| qwen3-14b | H1 | ecologie | 0.8600 | 0.6646 |
| qwen3-14b | H1 | fiscalite | 0.8667 | 0.7334 |
| qwen3-14b | H1 | services_publics | 0.9750 | 0.7834 |
| qwen3-14b | H1+R1 | democratie | 0.9400 | 0.7946 |
| qwen3-14b | H1+R1 | ecologie | 0.8600 | 0.6637 |
| qwen3-14b | H1+R1 | fiscalite | 0.9333 | 0.8370 |
| qwen3-14b | H1+R1 | services_publics | 1.0000 | 0.7820 |
| qwen3-14b | H1+R2 | democratie | 0.9200 | 0.7697 |
| qwen3-14b | H1+R2 | ecologie | 0.9000 | 0.7451 |
| qwen3-14b | H1+R2 | fiscalite | 0.9667 | 0.9047 |
| qwen3-14b | H1+R2 | services_publics | 1.0000 | 0.8214 |
| qwen3-14b | H5 | democratie | 0.9200 | 0.7051 |
| qwen3-14b | H5 | ecologie | 0.8200 | 0.6282 |
| qwen3-14b | H5 | fiscalite | 0.9667 | 0.8191 |
| qwen3-14b | H5 | services_publics | 0.9750 | 0.7450 |
| qwen3-14b | H5+R1 | democratie | 0.9200 | 0.7840 |
| qwen3-14b | H5+R1 | ecologie | 0.8600 | 0.6774 |
| qwen3-14b | H5+R1 | fiscalite | 0.9667 | 0.8557 |
| qwen3-14b | H5+R1 | services_publics | 1.0000 | 0.8003 |
| qwen3-14b | H5+R2 | democratie | 0.9000 | 0.7819 |
| qwen3-14b | H5+R2 | ecologie | 0.9200 | 0.7278 |
| qwen3-14b | H5+R2 | fiscalite | 0.9667 | 0.8897 |
| qwen3-14b | H5+R2 | services_publics | 0.9500 | 0.7351 |
| qwen3-14b | V | democratie | 0.8600 | 0.7096 |
| qwen3-14b | V | ecologie | 0.7800 | 0.6164 |
| qwen3-14b | V | fiscalite | 0.9667 | 0.7893 |
| qwen3-14b | V | services_publics | 0.9000 | 0.7460 |
| qwen3-14b | V+R1 | democratie | 0.9200 | 0.8185 |
| qwen3-14b | V+R1 | ecologie | 0.8600 | 0.6699 |
| qwen3-14b | V+R1 | fiscalite | 0.9333 | 0.8364 |
| qwen3-14b | V+R1 | services_publics | 1.0000 | 0.8132 |
| qwen3-14b | V+R2 | democratie | 0.9200 | 0.7783 |
| qwen3-14b | V+R2 | ecologie | 0.9200 | 0.7340 |
| qwen3-14b | V+R2 | fiscalite | 0.9667 | 0.8752 |
| qwen3-14b | V+R2 | services_publics | 1.0000 | 0.7991 |
| qwen3-8b | H1 | democratie | 0.9400 | 0.6638 |
| qwen3-8b | H1 | ecologie | 0.8800 | 0.5763 |
| qwen3-8b | H1 | fiscalite | 0.9667 | 0.7296 |
| qwen3-8b | H1 | services_publics | 0.9750 | 0.5953 |
| qwen3-8b | H1+R1 | democratie | 0.9600 | 0.6671 |
| qwen3-8b | H1+R1 | ecologie | 1.0000 | 0.7984 |
| qwen3-8b | H1+R1 | fiscalite | 1.0000 | 0.6994 |
| qwen3-8b | H1+R1 | services_publics | 1.0000 | 0.6294 |
| qwen3-8b | H1+R2 | democratie | 0.9600 | 0.6776 |
| qwen3-8b | H1+R2 | ecologie | 0.9800 | 0.7612 |
| qwen3-8b | H1+R2 | fiscalite | 1.0000 | 0.8607 |
| qwen3-8b | H1+R2 | services_publics | 1.0000 | 0.6720 |
| qwen3-8b | H5 | democratie | 0.9200 | 0.6026 |
| qwen3-8b | H5 | ecologie | 0.8600 | 0.5921 |
| qwen3-8b | H5 | fiscalite | 1.0000 | 0.7243 |
| qwen3-8b | H5 | services_publics | 0.9750 | 0.5883 |
| qwen3-8b | H5+R1 | democratie | 0.9400 | 0.6308 |
| qwen3-8b | H5+R1 | ecologie | 0.9600 | 0.7645 |
| qwen3-8b | H5+R1 | fiscalite | 1.0000 | 0.7416 |
| qwen3-8b | H5+R1 | services_publics | 1.0000 | 0.6219 |
| qwen3-8b | H5+R2 | democratie | 0.9200 | 0.6609 |
| qwen3-8b | H5+R2 | ecologie | 0.9800 | 0.7214 |
| qwen3-8b | H5+R2 | fiscalite | 1.0000 | 0.8475 |
| qwen3-8b | H5+R2 | services_publics | 0.9750 | 0.6329 |
| qwen3-8b | V | democratie | 0.9200 | 0.5882 |
| qwen3-8b | V | ecologie | 0.9000 | 0.6502 |
| qwen3-8b | V | fiscalite | 1.0000 | 0.6927 |
| qwen3-8b | V | services_publics | 0.9500 | 0.5717 |
| qwen3-8b | V+R1 | democratie | 0.9400 | 0.6374 |
| qwen3-8b | V+R1 | ecologie | 0.9600 | 0.7333 |
| qwen3-8b | V+R1 | fiscalite | 1.0000 | 0.7314 |
| qwen3-8b | V+R1 | services_publics | 1.0000 | 0.6085 |
| qwen3-8b | V+R2 | democratie | 0.9400 | 0.6538 |
| qwen3-8b | V+R2 | ecologie | 0.9800 | 0.7207 |
| qwen3-8b | V+R2 | fiscalite | 1.0000 | 0.8333 |
| qwen3-8b | V+R2 | services_publics | 1.0000 | 0.6527 |

## Performances réelles

RTX 5090, temps de score GPU cumulés, dédupliqués. Les chargements de poids ci-dessous sont chauds et excluent le précontrôle, la vérification SHA des snapshots et le téléchargement ; ils ne représentent pas un démarrage complet à froid.

| Modèle | Chargement poids, essai/reprise (s) | Score 1 496 couples (s) | couples/s | tokens/s | RAM pic (Go décimaux) | VRAM allouée/réservée (Go) |
|---|---|---:|---:|---:|---:|---|
| R1 | 0.467 / 0.479 | 11.562 | 129.39 | 60554 | 4.28 | 1.26 / 1.38 |
| R2 | 1.062 / 1.077 | 65.860 | 22.71 | 13470 | 4.93 | 8.46 / 8.92 |

Mesures de préfixes à 10/20/50 **couples uniques par requête dans l’ordre figé des identifiants** ; pas des mesures autonomes des top-k de chaque pipeline. Calculées sans répéter l’inférence GPU.

| Reranker | 10 médiane/P95 (s) | 20 médiane/P95 (s) | 50 médiane/P95 (s) |
|---|---|---|---|
| R1 | 0.072 / 0.210 | 0.142 / 0.289 | 0.422 / 0.481 |
| R2 | 0.405 / 1.693 | 0.799 / 2.215 | 2.858 / 3.356 |

Coûts **estimés** : allocation du temps de lot entre ses unités, puis somme pour les 50 candidats du pipeline ; ajout des temps de récupération historiques RAG-019 par requête. Pas de mesure directe bout en bout, chargement exclu. Les coûts diffèrent avec les longueurs et segments des candidats.

| Reranker | Pipeline | Score estimé médiane/P95 (s) | Pipeline estimé médiane/P95 (s) |
|---|---|---|---|
| R1 | H1 | 0.442/0.520 | 0.679/0.871 |
| R1 | H5 | 0.299/0.379 | 0.742/1.106 |
| R1 | V | 0.304/0.374 | 0.407/0.506 |
| R2 | H1 | 3.069/3.759 | 3.275/3.920 |
| R2 | H5 | 1.275/2.167 | 1.878/2.576 |
| R2 | V | 1.394/2.140 | 1.492/2.240 |

CPU : mêmes trois couples courts, quatre threads Ryzen 7950X, float32, premier passage inclus. Pas de percentile robuste sur trois observations, pas d’extrapolation à Wallace.

| Reranker | Chargement (s) | Latences individuelles (s) | RAM pic (Go) |
|---|---:|---|---:|
| R1 | 0.070 | 0.175 / 0.153 / 0.271 | 2.27 |
| R2 | 1.751 | 3.061 / 3.198 / 4.808 | 20.70 |

Qwen est environ 5,7 fois plus coûteux que BGE sur le score GPU de ce lot et bien plus coûteux sur les trois exemples CPU. Une utilisation CPU interactive des 50 candidats Qwen n’est pas validée ; ne pas transférer ce modèle sur Wallace sur la base de cette expérience.

## Validation

- Suite complète : **480 tests réussis**, 3 tests optionnels PyTorch ignorés dans l’environnement léger ; un avertissement de dépréciation FastAPI/HTTPX préexistant. Les intégrations PostgreSQL utilisent exclusivement les bases de test isolées.
- Ruff conforme, `uv lock --check` conforme (73 paquets résolus), `git diff --check` conforme.
- Quinze nouveaux tests ciblés : interfaces simulées, segmentation et positions, BIGINT, reprise sans recalcul, transactions et conflits, NaN/Inf/bool, panne GPU, adaptation SearchResult, recettes et empreintes, dépendances optionnelles, neuf pipelines, rapports déterministes, métriques incomplètes.
- Les deux essais réels ont été interrompus après deux couples, puis repris ; 2 scores réutilisés et 1 494 nouveaux pour chaque modèle. Aucun couple n’a été recalculé dans la recette GPU.
- Deux générations indépendantes des rapports à partir des mêmes données : 13 fichiers identiques octet pour octet, dont les neuf exports de classement, deux exports de scores et les rapports JSON/Markdown.
- Contrôle SHA-256 de 1 230 fichiers historiques : aucun changement, incluant requêtes, corpus, anciens artefacts, sessions, moteurs et verrou backend. Aucune lecture des notes humaines, aucune nouvelle annotation.
- Aucune écriture PostgreSQL nécessaire pour RAG-020 : lecture des documents depuis la copie SQLite RAG-018 contrôlée par le manifeste. Les intégrations PostgreSQL existantes restent exécutées dans la suite complète.

Les commandes exactes d’installation, téléchargement, préparation, reprise, CPU et rapports sont dans [reranking-local.md](reranking-local.md).

## Limites et recommandation

Conserver **H1 + Qwen3-Reranker-4B comme candidat qualité local GPU**, et **BGE comme candidat économique**. H5 ou V avec reranker peuvent offrir un coût de récupération inférieur ; leurs différences doivent être examinées selon les contraintes réelles du produit. Ne pas éliminer les références sans reranker.

Avant un choix de production : validation humaine indépendante des gains et régressions, test du matériel réellement disponible et protocole gelé sur les requêtes réservées dans une tâche ultérieure. Aucun réglage n’est réalisé ici sur les notes LLM, aucun modèle entraîné.

Le pool est lié aux moteurs ayant fourni ses candidats ; nDCG poolée non exhaustive. Les rerankers ne peuvent récupérer un document absent du top 50. Question partagée et agrégation maximum de nombreux segments peuvent induire des biais ; ils n’ont pas été optimisés. La segmentation à 1 024 tokens n’exploite pas toute la fenêtre native des modèles. Les scores BF16 et float32 ne sont pas promis identiques bit à bit entre matériels ; les classements issus des caches validés sont reproductibles.

Les 20 requêtes réservées restent intactes et non exécutées. Aucun index, moteur, jugement historique, backend, frontend ou élément de Wallace modifié. Aucun commit ou push.
