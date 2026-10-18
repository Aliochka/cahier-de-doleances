# RAG-016 — Deux juges locaux

Les jugements automatiques constituent une source distincte des jugements humains.
Ils ne sont jamais importés dans les sessions RAG-010/015 ni considérés comme une
vérité de référence. Les moteurs et leurs configurations restent inchangés.

## Modèles et environnement

Deux checkpoints instruct de la même famille sont configurés :

| Clé | Dépôt officiel | Révision immuable | Paramètres | Licence |
|---|---|---|---|---|
| `qwen3-8b` | [Qwen/Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) | `b968826d9c46dd6066d109eabc6255188de91218` | 8,2 milliards | Apache-2.0 |
| `qwen3-14b` | [Qwen/Qwen3-14B](https://huggingface.co/Qwen/Qwen3-14B) | `40c069824f4251a91eefaf281ebe4c544efd3e18` | 14,8 milliards | Apache-2.0 |

Ces modèles multilingues prennent en charge le français, un contexte natif de
32 768 tokens et la désactivation explicite du mode thinking. Ce ne sont pas les
Qwen les plus récents : [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)
introduit une pile multimodale et des exigences Transformers différentes de la
version déjà verrouillée pour les embeddings. Qwen3 permet ici une comparaison
8B/14B sans modifier cette pile. Les checkpoints sont distincts, mais leur
parenté peut corréler leurs erreurs : leur indépendance est opérationnelle,
pas statistique.

Les poids Safetensors officiels sont quantifiés **au chargement** en NF4 4 bits,
avec double quantification et calcul bfloat16. Ils occupent environ 46 Go sur
le disque avant quantification. Aucun checkpoint communautaire n'est utilisé.
[bitsandbytes](https://huggingface.co/docs/bitsandbytes/main/en/installation)
prend en charge Blackwell avec CUDA 12.8. Les modèles s'exécutent successivement.

Depuis `rag/`, installer un environnement séparé pour préserver l'annotation :

```bash
UV_PROJECT_ENVIRONMENT=.cache/judges-venv uv sync --locked --extra judges
.cache/judges-venv/bin/cahier-rag-judge models
.cache/judges-venv/bin/cahier-rag-judge download --judge qwen3-8b
.cache/judges-venv/bin/cahier-rag-judge download --judge qwen3-14b
```

Le téléchargement utilise par défaut le transfert HTTP reprenable
(`HF_HUB_DISABLE_XET=1`), avec quatre transferts bornés. Une valeur explicite
`HF_HUB_DISABLE_XET=0` permet de choisir Xet sur une autre installation.
Seule la commande `download` contacte les dépôts de modèles. Le snapshot exact,
la liste fermée des fichiers et leurs SHA-256 sont enregistrés et vérifiés avant
utilisation. L'inférence force `local_files_only`, le mode hors ligne et
`trust_remote_code=False`. Aucun texte documentaire n'est envoyé au réseau.
Les poids sont dans `models/judges/`, les résultats dans `evaluation/local/` :
ces emplacements sont ignorés par Git. Ne pas synchroniser `.venv/` avec cet
extra si une session humaine l'utilise. Le backend public reste indépendant.

## Préparer les plans

Les commandes de préparation lisent PostgreSQL RAG en lecture seule. Elles ne
lisent pas la base source. Fournir uniquement `RAG_DATABASE_URL` ou un fichier
explicitement choisi avec l'option globale `--env-file`.

```bash
.venv/bin/python -m cahier_rag.judges.cli prepare --kind human60 --output evaluation/local/rag016/human60
.venv/bin/python -m cahier_rag.judges.cli prepare --kind pools800 --output evaluation/local/rag016/pools800
.venv/bin/python -m cahier_rag.judges.cli prepare --kind top10 --output evaluation/local/rag016/top10
```

Un dossier de plan existant est refusé, jamais écrasé. La référence initiale
exige exactement 60 couples humains résolus. Les 800 couples dédupliquent les
deux pools immuables. Le complément top 10 prend les trois classements de
développement gelés RAG-014 et exclut les couples déjà dans les pools.
Aucune requête d'évaluation réservée n'est utilisée.

Chaque manifeste conserve les empreintes du corpus, des requêtes, du prompt,
des sources, des entrées et la graine `20261023`. Les groupes partageant une
contribution ou un texte identique restent du même côté de la séparation
calibration/validation. La séparation n'utilise pas les notes ; elle vise
25 % de validation sous réserve de conserver assez de groupes. Ce n'est pas
une séparation par requête : la validation reste limitée par les trois
requêtes déjà annotées. Aucun réglage du prompt n'est effectué sur cette
référence ni sur sa partie réservée.

`inputs.jsonl` ne contient aucune note ni commentaire humain. Le prompt ne
reçoit que la requête, la réponse intégrale, la question et le titre facultatif.
Les identifiants, moteurs, rangs, scores et autres juges sont masqués. Les textes
sont explicitement déclarés non fiables : leurs instructions doivent être ignorées.
Cette défense ne garantit pas l'absence d'injection de prompt.

## Référence humaine indépendante

Avant l'inférence, figer séparément les notes pour permettre de poursuivre
l'annotation humaine sans invalider l'expérience :

```bash
.venv/bin/python -m cahier_rag.judges.cli freeze-reference \
  --plan evaluation/local/rag016/human60 --output evaluation/local/rag016/human-reference
```

Ce snapshot privé conserve uniquement notes, identités, évaluateurs, dates et
versions, sans commentaires. Il valide l'empreinte originale du plan et des
sources et refuse d'écraser un dossier existant. L'inférence ne le lit jamais.

## Exécution, reprise et résultats

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .cache/judges-venv/bin/cahier-rag-judge run \
  --plan evaluation/local/rag016/human60 --judge qwen3-8b --limit 60 --stop-after 2
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .cache/judges-venv/bin/cahier-rag-judge run \
  --plan evaluation/local/rag016/human60 --judge qwen3-8b --limit 60
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .cache/judges-venv/bin/cahier-rag-judge run \
  --plan evaluation/local/rag016/human60 --judge qwen3-14b --limit 60
.venv/bin/python -m cahier_rag.judges.cli compare --plan evaluation/local/rag016/human60 \
  --output evaluation/local/rag016/calibration-v1 \
  --reference evaluation/local/rag016/human-reference/reference.json
```

Les lots font deux couples par défaut, avec génération gloutonne, graine 42,
thinking désactivé, entrée limitée à 24 576 tokens et sortie à 192 tokens. Les
tokens incluent le gabarit et les instructions. Une entrée trop longue est
signalée `too_long`, jamais tronquée. Une sortie invalide est `invalid`, sans
note ; aucun jugement n'est inventé pour compléter la couverture. L'option
`--retry-failed` réessaie uniquement les échecs. Une erreur GPU interrompt le
lot non validé et laisse les lots précédents disponibles pour la reprise.

La sortie doit être exactement un JSON contenant `grade` (entier 0 à 3),
`justification` (1 à 500 caractères) et `uncertain` (booléen). Les champs
inconnus, doublons JSON et types incorrects sont refusés. Le prompt français
`relevance-fr-v1` est conservé dans `judges/contracts.py` ; son empreinte et les
versions des bibliothèques font partie de la recette.

Le cache SQLite local `evaluation/local/rag016/cache.sqlite3` persiste chaque
lot atomiquement. Sa clé combine la recette complète et l'empreinte de l'entrée.
Les juges ne partagent pas leurs notes. Relancer la même recette réutilise ses
résultats, y compris entre plans ; une modification de modèle, prompt ou
paramètres crée une nouvelle recette. Les tentatives échouées restent tracées.
Les écritures de rapports sont atomiques, avec permissions privées. Chaque
résultat porte sa date, son origine LLM et sa provenance ; les rapports
conservent aussi les empreintes du code. Les sorties brutes peuvent contenir
des fragments du corpus : ne pas les publier ni les ajouter à Git.

**Les campagnes complètes ne sont pas lancées automatiquement.** Après examen
humain de la calibration, une exécution de `pools800` exige explicitement
`--limit 800 --allow-full`, pour chaque juge. Le complément utilise sa taille
exacte et la même autorisation. Ne pas modifier les plans existants. Après décision explicite de lancer les
800 couples, les commandes seraient les suivantes (non exécutées par RAG-016) :

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .cache/judges-venv/bin/cahier-rag-judge run \
  --plan evaluation/local/rag016/pools800 --judge qwen3-8b --limit 800 --allow-full
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .cache/judges-venv/bin/cahier-rag-judge run \
  --plan evaluation/local/rag016/pools800 --judge qwen3-14b --limit 800 --allow-full
```

Avec les mêmes paramètres, chaque juge réutilisera ses 60 résultats déjà
calculés et traitera seulement les autres couples. Les notes humaines restent
une référence séparée ; aucune fusion automatique avec elles n'est effectuée.

## Comparaison et limites

`compare` charge les notes humaines seulement après l'exécution des deux juges.
Avec `--reference`, il utilise le snapshot humain figé et vérifié, même si
la session vivante a progressé entre-temps. Sans cette option, il refuse une
référence humaine modifiée depuis le gel du plan. Les commentaires humains ne
sont jamais utilisés.

Les rapports distinguent calibration, validation et ensemble descriptif :
accord exact, écart maximal d'un point, pertinence binaire (`0–1` / `2–3`),
matrice de confusion (lignes humaines, colonnes LLM), kappa de Cohen pondéré
linéairement par `|a-b|/3`. Le kappa est indéfini si l'accord attendu ne permet
pas son calcul. Les échecs sont comptés séparément, exclus des dénominateurs
d'accord. `human-review.json` recense écarts majeurs (au moins deux points),
divergences binaires, incertitudes et sorties invalides, sans texte personnel.

L'accord entre juges ne valide pas leur vérité. Cette petite référence ne
permet pas de remplacer les jugements humains ni de conclure définitivement
sur la qualité des moteurs. Aucun score de recherche fondé sur les LLM n'est
mélangé aux métriques humaines de RAG-015. L'outil ne modifie pas les moteurs,
les pools, les sessions ou leurs jugements.

## Tests

```bash
uv lock --check
.venv/bin/ruff check .
.venv/bin/pytest
```

Les tests simulés couvrent notamment les contrats stricts, l'aveuglement,
l'atomicité, les conflits, la reprise, le cache indépendant des deux juges,
les limites de contexte, les groupes anti-fuite et les accords connus.
Ils fonctionnent sans poids, GPU ou installation de l'extra `judges`.
