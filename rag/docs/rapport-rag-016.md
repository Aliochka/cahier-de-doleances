# RAG-016 — Annotation automatique locale par deux juges

## Périmètre et architecture

Le module `src/cahier_rag/judges/` est indépendant des moteurs de recherche et
des sessions humaines. Il comprend :

- `contracts.py` : entrée aveugle, interface interchangeable, paramètres et prompt français versionné, validation JSON stricte.
- `models.py` : registre des deux checkpoints officiels, téléchargement explicite et contrôle SHA-256 des snapshots.
- `backend.py` : chargement paresseux Transformers, quantification NF4, tokenization réelle et inférence CUDA hors ligne.
- `planning.py` : plans immuables pour les 60 couples humains, les 800 couples des pools et le complément top 10.
- `cache.py` : transactions SQLite locales par lot, tentatives tracées, idempotence par recette et entrée.
- `pipeline.py` : progression, reprise, refus des dépassements de contexte et mesures de ressources.
- `reference.py` : snapshot humain privé et figé, sans commentaires, indépendant des sessions vivantes.
- `comparison.py` : accords ordinaux et binaires, confusion, kappa pondéré et couples à réviser.
- `cli.py` : préparation, téléchargement, exécution limitée et comparaison.

Aucune migration PostgreSQL, modification des moteurs, session humaine, requête,
partition, annotation, backend, frontend ou configuration Wallace n'est nécessaire.
Aucun développement ANNOT-001 n'est inclus. Les sorties automatiques restent
séparées ; elles ne sont pas converties en référence humaine pour RAG-015.

## Choix des modèles

| Modèle | Révision | Licence | Paramètres | Contexte natif |
|---|---|---|---:|---:|
| [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) | `b968826d9c46dd6066d109eabc6255188de91218` | Apache-2.0 | 8,2 B | 32 768 |
| [Qwen3-14B](https://huggingface.co/Qwen/Qwen3-14B) | `40c069824f4251a91eefaf281ebe4c544efd3e18` | Apache-2.0 | 14,8 B | 32 768 |

La sélection privilégie les capacités instruct multilingues, deux tailles et
la compatibilité avec Transformers 4.57.6 déjà verrouillé. Qwen3 n'est pas la
gamme la plus récente : la fiche officielle de
[Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) décrit une pile multimodale
et des exigences différentes. Son adoption ne se justifie pas ici par une
simple nouveauté, sans essai contrôlé. La licence et les instructions des
checkpoints retenus ont été vérifiées sur leurs dépôts officiels.

Les formats officiels quantifiés existent, mais cette expérience utilise les
Safetensors originaux avec quantification NF4 4 bits au chargement, double
quantification et calcul bfloat16. Ce choix évite une nouvelle pile AWQ/GGUF et
conserve la pile CUDA 12.8. La prise en charge Blackwell est documentée par
[bitsandbytes](https://huggingface.co/docs/bitsandbytes/main/en/installation).
Les deux modèles sont exécutés successivement sur la RTX 5090, sans serveur.
Leur parenté implique des biais potentiellement corrélés malgré des inférences
indépendantes : deux accords ne forment pas une vérité de référence.

L'extra `judges` ajoute uniquement Accelerate 1.15.0 et bitsandbytes 0.50.2 aux
versions lourdes déjà utilisées par les embeddings. L'environnement dédié est
`.cache/judges-venv`. Le `.venv` d'annotation demeure inchangé. Aucun verrou ni
dépendance du backend n'est modifié. La recherche lexicale et l'annotation
s'importent toujours sans PyTorch dans l'environnement léger.

## Protocole figé et plans préparés

Le prompt `relevance-fr-v1` est fixé avant toute génération ou comparaison.
Il conserve les notes 0–3, demande une justification courte et un booléen
d'incertitude, sans raisonnement interne. Les messages ne contiennent que
requête, réponse intégrale, question originale et titre facultatif. Aucune note,
commentaire humain, identité de moteur, rang, score ou sortie de l'autre juge
n'est transmis. Les paramètres sont identiques pour les deux modèles : lot de
2, graine 42, génération gloutonne, thinking désactivé, 24 576 tokens d'entrée et
192 de sortie. Une entrée trop longue est refusée, jamais tronquée ; une sortie
invalide ne reçoit aucune note de substitution.

Les plans locaux préparés sont :

| Plan | Couples | Usage |
|---|---:|---|
| `evaluation/local/rag016/human60/` | 60 | Calibration réelle autorisée : 45 calibration, 15 validation |
| `evaluation/local/rag016/pools800/` | 800 | Préparation uniquement ; exécution non autorisée automatiquement |
| `evaluation/local/rag016/top10/` | 101 | Complément lexical/vectoriel/hybride hors des deux pools ; préparation uniquement |

Empreintes des manifestes :

```text
human60  5d9bbff4ef07d17258a403439809c572923d6a65afe409a589581ef8da898bce
pools800 097f45c5e24c3ccb5e69cc89995a2a26ebd2eb6c7295b3ba7d4e7d163655e4fd
top10    f705a745b05fee6f2428a0c06bbacdfe5db73e4bbdcb145f05663adc9dc5068d
```

La séparation utilise la graine `20261023`, en regroupant les contributions
communes et textes identiques. Les notes ne servent pas à répartir les couples.
La validation ne contient que 15 exemples et partage les trois requêtes déjà
annotées ; elle ne représente donc pas des besoins de recherche inédits. Aucun
prompt n'est réglé à partir de ces résultats.

## Conservation et reprise

Le cache `evaluation/local/rag016/cache.sqlite3` distingue modèle, révision,
snapshot, prompt, paramètres, versions des bibliothèques et empreinte de chaque
entrée. Les lots sont validés dans une seule transaction. Une interruption
laisse les lots précédents réutilisables. Les sorties invalides restent tracées
et peuvent être réessayées explicitement avec `--retry-failed`.

Les rapports sont écrits atomiquement ; les plans existants ne sont pas écrasés.
Les résultats portent `judgment_origin: llm` et ne sont jamais écrits dans les
sessions humaines. Le cache refuse les chemins JSON pour prévenir une confusion
avec ces sessions. Les poids, textes d'entrée, sorties et caches sont ignorés
par Git. Aucun texte n'est journalisé ni envoyé à une API.

La référence humaine RAG-010 contient 60 jugements, notes 0 : 24, 1 : 11,
2 : 9, 3 : 16. Son empreinte avant exécution est :

```text
5d6e8d6a8937f8153dd19b6219b037bd0a94cb42cdd05fa4dae011b759983a87
```

Une référence figée a été créée séparément dans `human-reference/reference.json`,
sans commentaires. Les sessions humaines peuvent continuer ; la comparaison
utilise ce snapshot vérifié, jamais lu par les deux inférences. Sans snapshot,
elle refuse une modification de la référence depuis le gel du plan. Les conflits, divergences binaires et écarts d'au
moins deux points sont signalés pour révision ; ils ne sont pas corrigés
silencieusement.

## Résultats de calibration réelle

Les deux modèles ont produit **60 sorties JSON valides sur 60**, sans troncature, dépassement de fenêtre ni sortie invalide. Chaque modèle a été arrêté avec `--stop-after 2`, puis repris : les deux résultats initiaux ont été réutilisés, et le cache contient exactement 60 jugements par recette. Deux entrées de chaque modèle ont ensuite été régénérées deux fois : sorties brutes identiques et mêmes notes que le cache, sans écriture supplémentaire.

Les notes humaines ont été lues pour la comparaison seulement après les deux générations indépendantes. Aucun prompt ou paramètre n’a été ajusté après observation des accords. Les empreintes des fichiers de code conservées dans les deux manifestes correspondent au code final.

### Accords avec la référence humaine

| Ensemble | Modèle | n | Exact | À ±1 | Binaire | Kappa pondéré | Écarts ≥2 |
|---|---|---:|---:|---:|---:|---:|---:|
| Calibration | qwen3-8b | 45 | 42.2 % | 93.3 % | 82.2 % | 0.438 | 3 |
| Calibration | qwen3-14b | 45 | 53.3 % | 93.3 % | 82.2 % | 0.580 | 3 |
| Validation réservée | qwen3-8b | 15 | 26.7 % | 93.3 % | 86.7 % | 0.419 | 1 |
| Validation réservée | qwen3-14b | 15 | 60.0 % | 80.0 % | 80.0 % | 0.563 | 3 |
| Ensemble descriptif | qwen3-8b | 60 | 38.3 % | 93.3 % | 83.3 % | 0.444 | 4 |
| Ensemble descriptif | qwen3-14b | 60 | 55.0 % | 90.0 % | 81.7 % | 0.587 | 6 |

La référence comprend uniquement `democratie-01`, `democratie-02` et `democratie-03`, à raison de 20 couples chacune : **aucune généralisation aux autres domaines n’est démontrée**. La validation contient 4 notes 0, 3 notes 1, aucune note 2 et 8 notes 3 ; la calibration contient respectivement 20, 8, 9 et 8 notes. La séparation par contribution et texte évite certaines fuites documentaires, mais les mêmes requêtes restent présentes dans les deux ensembles. Les 20 requêtes d’évaluation réservées du protocole de recherche n’ont pas été exécutées.

Le 14B présente ici davantage d’accord exact et un kappa ordinal plus élevé ; le 8B présente légèrement plus d’accord binaire et moins d’écarts majeurs. Ces indicateurs ne désignent donc pas un vainqueur universel. Le 8B tend à ramener la note humaine 3 à 2 (15 cas sur les 16 notes humaines 3). Le 14B attribue notamment la note 1 à cinq documents notés 3 par l’humain. Il s’agit de divergences avec cette référence, pas d’une adjudication définitive de la vérité.

### Matrices de confusion

Lignes : notes humaines 0, 1, 2, 3 ; colonnes : prédictions 0, 1, 2, 3. Matrices sur les 60 couples.

**qwen3-8b**

```text
13  9  2  0
 2  4  4  1
 0  2  6  1
 0  1 15  0
```

**qwen3-14b**

```text
19  5  0  0
 2  5  3  1
 0  2  1  6
 0  5  3  8
```

### Accords entre modèles et révision humaine

- Même note : **33/60** ; écart d’un point : **26/60** ; écart d’au moins deux points : **1/60**.
- Divergence binaire entre modèles : **7/60**. Kappa ordinal entre juges : **0,607**.
- Sur les 33 accords exacts entre modèles, seuls **17** correspondent exactement à la note humaine ; **16** diffèrent.
- Parmi ces accords exacts, **7** divergent aussi de l’humain sur le seuil binaire : un accord entre juges ne suffit pas à accepter automatiquement une note.
- Le 8B signale une incertitude sur **2** couples, le 14B sur **0**, malgré leurs divergences : ce signal n’est pas une confiance calibrée.
- **15 couples** sont signalés pour révision : 8 avec écart humain ≥2, 14 avec divergence binaire d’au moins un juge, 7 avec divergence binaire entre juges et 2 avec incertitude. Ces catégories se recouvrent.

Les huit écarts majeurs avec au moins un juge sont listés ci-dessous sans texte citoyen. Les références documentaires complètes et justifications locales sont dans `calibration-v1/human-review.json`. La colonne « réponse » désigne l’identifiant PostgreSQL source, conservé comme chaîne décimale.

| Requête | Réponse | Sous-ensemble | Humain | 8B | 14B |
|---|---|---|---:|---:|---:|
| democratie-01 | `1533577` | calibration | 3 | 1 | 1 |
| democratie-02 | `21906` | validation | 3 | 2 | 1 |
| democratie-02 | `4105854` | calibration | 3 | 2 | 1 |
| democratie-02 | `4364341` | calibration | 3 | 2 | 1 |
| democratie-03 | `3287842` | validation | 1 | 3 | 3 |
| democratie-03 | `3671751` | validation | 3 | 2 | 1 |
| democratie-03 | `4803856` | calibration | 0 | 2 | 1 |
| democratie-03 | `519189` | calibration | 0 | 2 | 0 |

### Performances observées sur RTX 5090

| Modèle | Chargement à la reprise | 58 nouveaux couples après reprise | 60 couples, deux chargements inclus | Pic GPU PyTorch | Pic RAM du processus |
|---|---:|---:|---:|---:|---:|
| qwen3-8b | 8.65 s | 115.05 s | 126.79 s | 14.26 Gio | 5.89 Gio |
| qwen3-14b | 16.47 s | 167.78 s | 187.64 s | 19.31 Gio | 6.25 Gio |

Les temps des 58 couples incluent leur chargement et excluent les deux résultats repris du cache. Le total de 60 additionne l’essai initial de deux et la reprise de 58 ; le contrôle supplémentaire de répétabilité n’est pas inclus. Le débit global de cette procédure est d’environ 0,47 couple/s pour le 8B et 0,32 pour le 14B. Chaque modèle reçoit les mêmes **143 801 tokens d’entrée** au total ; il produit respectivement 4 384 et 5 386 tokens hors EOS. Les justifications du 14B sont plus longues : ces temps mêlent chargement, préremplissage et décodage et ne constituent pas un benchmark à longueur de sortie fixe. Les pics GPU sont ceux de l’allocateur PyTorch, pas une mesure de toute la mémoire du pilote. Les poids sont NF4 double avec calcul bfloat16, PyTorch 2.10.0/CUDA 12.8, Transformers 4.57.6, Accelerate 1.15.0 et bitsandbytes 0.50.2.

Les 13 fragments Safetensors (5 + 8) correspondent tous aux SHA-256 du dépôt officiel à la révision exacte. Les deux snapshots occupent environ 46 Go décimaux, soit 43 Gio sur disque. Le téléchargement HTTP a été limité par `eno1` négocié à 100 Mbit/s, sans modification réseau ; le PC annonce jusqu’à 2,5 Gbit/s et le partenaire jusqu’à 1 Gbit/s. Cette limitation réseau n’entre pas dans les temps d’inférence.

### Artefacts conservés

```text
evaluation/local/rag016/
├── human60/manifest.json et inputs.jsonl
├── human60/{qwen3-8b,qwen3-14b}-smoke-run.json
├── human60/{qwen3-8b,qwen3-14b}-run.json
├── human60/{qwen3-8b,qwen3-14b}-results.json
├── human60/{qwen3-8b,qwen3-14b}-repeatability.json
├── human60/tokenization-preflight.json
├── human-reference/reference.json
├── pools800/manifest.json et inputs.jsonl
├── top10/manifest.json et inputs.jsonl
├── campaign-tokenization-preflight.json
├── calibration-v1/comparison.json et human-review.json
└── cache.sqlite3
```

Empreintes des recettes :

```text
qwen3-8b  fd51cc1ee0ad59f95dae26bf3e146fc8def5a5503404e13f99d9548e7711067e
qwen3-14b 714b02c8cd866d41d94f96260c5bad042b41513c443cbf8d2c04d5f1cd1c7075
```

Les fichiers locaux contenant les réponses, sorties brutes ou justifications ne sont pas versionnés. Aucun fichier de résultats d’inférence n’a été créé pour `pools800` ou `top10` : ces plans ont uniquement été préparés et tokenizés.

Le précontrôle avec les tokenizers réels donne 393 tokens au minimum, une médiane de 1 118 et un maximum de 16 470 sur les 60 couples. Trois entrées dépassaient le budget envisagé de 8 192 tokens ; celui-ci a été porté à 24 576 **avant toute inférence et comparaison humaine**. Le maximum est de 16 479 tokens pour les 800 couples et 2 462 pour les 101 compléments : aucun dépassement, aucune troncature.

## Validations

Les tests couvrent les sorties JSON invalides, les types stricts, les BIGINT,
l'aveuglement, le cache indépendant des juges, l'atomicité, les conflits,
la reprise, les limites de contexte, les groupes anti-fuite et les accords
connus. Une intégration PostgreSQL synthétique vérifie la lecture seule et le
refus de la partition réservée. Les tests d'écriture utilisent uniquement des
fichiers temporaires et les bases de test, jamais les sessions réelles.

Les commandes et conventions exactes sont dans [juges-locaux.md](juges-locaux.md).
Validation du code : **425 tests réussis, 3 ignorés** dans l'environnement
léger avec les deux bases PostgreSQL de test ; les tests ignorés requièrent
PyTorch. Les **18 tests d'embedding** passent dans l'environnement PyTorch,
y compris ces trois cas. Ruff et `uv lock --check` sont conformes. Le wheel et
la distribution source sont construits. Un avertissement Starlette/httpx
préexistant reste présent.

Les deux essais GPU sont terminés, avec 60/60 sorties valides par modèle et
répétabilité locale sur deux entrées. Les sources et commentaires humains
restent inchangés : l’empreinte finale de `rag010/session.json` est identique à
celle indiquée plus haut. La seconde campagne humaine n’a pas été créée.
Aucune requête de la partition d’évaluation de recherche n’a été exécutée.

## Limites et décision de lancement

Les 60 couples ne sont ni nombreux ni représentatifs : trois requêtes et un
pool issu de recherches lexicales. Les moyennes globales descriptives ne
remplacent pas la validation réservée ni une campagne humaine indépendante.
La grille humaine est elle-même une référence d'un évaluateur, pas une vérité
absolue. Les justifications LLM peuvent rationaliser une mauvaise note.

Les deux checkpoints de même famille risquent de partager leurs erreurs.
La génération gloutonne et les recettes figées améliorent la reproductibilité,
mais ne promettent pas une identité bit à bit entre matériels ou versions.
Le prompt limite les instructions malveillantes dans le corpus sans garantir
une résistance absolue aux injections.

Aucun score de pertinence des moteurs n'est calculé avec ces notes.

**Recommandation : ne pas remplacer maintenant les annotations humaines par
les accords des deux juges.** Commencer par examiner les 15 couples signalés,
y compris les accords communs qui divergent de la référence, puis élargir la
référence humaine aux autres domaines. Ne pas retoucher le prompt sur les
15 exemples de validation déjà consommés ; une nouvelle recette demandera une
nouvelle validation indépendante.

Pour une campagne exploratoire explicitement décidée, le 14B peut servir de
juge ordinal provisoire et le 8B de contre-lecture, en conservant deux notes
séparées et des contrôles humains sur les désaccords **et sur un échantillon des
accords**. Le léger avantage binaire du 8B et les écarts majeurs du 14B interdisent
une désignation définitive d'un « meilleur juge ». Aucun consensus ni moyenne
ne doit être transformé automatiquement en note de référence.

Les commandes manuelles des campagnes sont documentées dans
[juges-locaux.md](juges-locaux.md). Elles exigent `--allow-full` et une limite
explicite ; la même recette réutilisera les 60 résultats de chaque modèle.
**Les 800 annotations complètes et les 101 compléments n'ont pas été exécutés.**
