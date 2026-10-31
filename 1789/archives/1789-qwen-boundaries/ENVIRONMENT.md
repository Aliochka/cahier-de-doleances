# Installation locale et ressources

## Modèle effectivement utilisé

`rag/models/judges/qwen3-14b/40c069824f4251a91eefaf281ebe4c544efd3e18/` : huit shards Safetensors, index, configuration, tokenizer, licence Apache-2.0 et manifeste. Les poids originaux sont BF16, environ 28 Go sur disque ; la quantification n’est pas un autre checkpoint : **NF4 quatre bits, double quantification au chargement, calcul BF16**. Manifeste vérifié par `cahier_rag.judges.models.verify` avant chaque session, hash `d3fde2ccf3d22b339b8e586f488fecbc6b5b3648b4f4073f62e20fa30e09b642`.

Le registre existant déclare 14,8 milliards de paramètres, huit shards et un budget conservateur 32 768 tokens. La configuration locale mentionne 40 960 positions ; le protocole garde la limite existante 32 768, avec 24 576 tokens d’entrée et 512 de sortie. Aucun checkpoint 0.6B ni 8B chargé.

## Backend réutilisé

Le chargeur est `rag/src/cahier_rag/judges/backend.py` : `TransformersJudge`, `device_map={"":0}`, SDPA, `local_files_only=True`, `trust_remote_code=False`, aucun repli CPU. Il était déjà utilisé pour les juges et la génération locale décrits dans `rag/docs/rapport-rag-016.md` et les outils de génération contrainte.

L’adaptateur expérimental `constrained.py` réutilise ce chargeur, l’intégration Transformers de **LM Format Enforcer 0.11.3** et `safe_token_ids` déjà présent dans `generation/constrained/backend.py`. Seul le schéma est propre à cette tâche, avec les IDs visibles comme énumérations. Il ne contient aucune référence correcte ni information issue des annotations. XGrammar est installé mais non utilisé. Aucun fichier `rag/` modifié.

## Python existant, sans réinstallation

Les liens `rag/.venv/bin/python` et `rag/.cache/judges-venv/bin/python` pointent vers `/tmp/rag010-python/...`, désormais absent. Leurs packages restent disponibles. `bootstrap.py` utilise le CPython durable 3.11.17 appelé par `.venv/bin/python`, ajoute en lecture les packages déjà installés dans `rag/.cache/judges-venv/lib/python3.11/site-packages` et `rag/src`. **Aucun lien, environnement ou paquet existant n’a été réparé/modifié.** La préparation documentaire utilise `/usr/bin/python3` et le lxml déjà disponible.

| Dépendance | Version mesurée |
| --- | --- |
| torch | 2.10.0+cu128 |
| transformers | 4.57.6 |
| bitsandbytes | 0.50.2 |
| accelerate | 1.15.0 |
| psutil | 7.2.2 |
| lm-format-enforcer | 0.11.3 |
| Python inférence | 3.11.17 |
| Driver NVIDIA | 595.99.02 |
| CUDA du driver | 13.2 |
| CUDA du PyTorch | 12.8 |

## GPU et précautions effectives

RTX 5090, 32 607 MiB détectés. Environ 234–277 MiB occupés par le bureau au départ, aucun processus de calcul GPU. Le bac à sable ne donnait pas accès aux périphériques ; les contrôles puis l’inférence ont donc été autorisés hors bac à sable. CUDA a été confirmé disponible, capacité 12.0 ; ce n’était pas une panne du driver.

Les appels sont séquentiels, batch 1, quatre threads CPU, plafond PyTorch 72 % de la mémoire GPU. Avant le chargement et chaque appel, le script vérifie les autres processus de calcul et s’arrête s’il en apparaît. Pas de service permanent, pas de modification de puissance/fréquences ni arrêt d’un service. `close()` et la sortie du processus libèrent le modèle.

La validation consomme 540,86 s de génération cumulée pour les deux méthodes, environ 9,01 min, plus chargement. Pic alloué 12,58 GiB, pic réservé 13,08 GiB mesurés par PyTorch par appel. Ce ne sont pas des mesures exhaustives de la mémoire globale NVML pendant tout le chargement. À 18:45:14 en fin d’expérience, `nvidia-smi` ne montre plus que GNOME et 179 MiB de mémoire occupée. Le relevé est conservé dans `data/gpu-after.json`.

Le réseau Hugging Face est désactivé (`HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`), la télémétrie également. Aucun modèle téléchargé. Un avertissement bitsandbytes sur des kernels CPU absents a été observé pendant l’inventaire ; l’inférence GPU s’est exécutée sans installation supplémentaire ni repli CPU.
