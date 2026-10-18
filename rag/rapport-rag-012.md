# RAG-012 — Intégration et comparaison technique des embeddings

## Résultat

**Trois modèles ont été réellement chargés et testés sur la RTX 5090 puis sur
CPU**, sur les représentations RAG-011. Le moteur est interchangeable, optionnel,
hors ligne à l’inférence et indépendant de l’annotation. Aucune indexation des
20 000 unités, extension pgvector, recherche vectorielle ou migration n’a été faite.

Les comparaisons ci-dessous décrivent des coûts techniques sur un petit lot,
pas la pertinence sur le Grand Débat. Aucun jugement humain n’a été consulté.

## 1. Modèles et choix de sélection

| Modèle | Paramètres mesurés | Dimension | Fenêtre documentée | Licence de la fiche officielle |
|---|---:|---:|---:|---|
| multilingual E5-small | 117 653 760 | 384 | 512 tokens | MIT |
| BGE-M3, sortie dense | 567 754 752 | 1024 | 8192 tokens | MIT |
| Qwen3-Embedding-0.6B | 595 776 512 | 1024 | 32768 tokens | Apache-2.0 |

E5-small constitue le candidat léger, notamment pour de futures requêtes CPU.
BGE et Qwen comparent un encodeur multilingue et un modèle à instruction, à
contexte plus long et de tailles voisines. Les trois couvrent le français et
la recherche asymétrique. Aucun modèle 4B/8B ni serveur d’inférence n’est ajouté.
Les licences sont permissives sous leurs conditions de notices et mentions.

Caractéristiques, licences et recettes ont été vérifiées avant téléchargement
dans les [fiches E5](https://huggingface.co/intfloat/multilingual-e5-small),
[BGE-M3](https://huggingface.co/BAAI/bge-m3) et
[Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B).
Les travaux [multilingual E5](https://arxiv.org/abs/2402.05672),
[M3](https://arxiv.org/abs/2402.03216) et
[Qwen3 Embedding](https://arxiv.org/abs/2506.05176) fournissent les évaluations
multilingues motivant cette sélection. Leurs résultats publiés ne constituent
pas une mesure de notre corpus ; E5-small n’est pas E5-large-instruct.

Révisions exactes :

```text
e5-small     614241f622f53c4eeff9890bdc4f31cfecc418b3
bge-m3       5617a9f61b028005a4858fdac845db406aefb181
qwen3-0.6b   97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3
```

Les fichiers de poids occupent respectivement environ 471 Mo, 2271 Mo et 1192 Mo.
Les snapshots locaux contiennent configurations, tokenizer, notices et SHA-256.
BGE utilise son fichier officiel PyTorch `.bin` avec `weights_only=True` ; E5 et
Qwen utilisent Safetensors. Aucun code distant n’est accepté.

## 2. Architecture et dépendances

Nouveau package `src/cahier_rag/embeddings/` :

| Module | Rôle |
|---|---|
| `registry.py` | Identités, versions, dimensions, fenêtres et instructions officielles |
| `core.py` | Protocole de backend, entrées identifiées, lots, refus de dépassement, normalisation et intégrité |
| `transformers_backend.py` | Chargement explicite CPU/GPU, tokenizer, pooling et fermeture |
| `snapshots.py` | Téléchargement explicite et validation des snapshots |
| `data.py` | Chargement borné de RAG-011 et exemples synthétiques |
| `planning.py` | Comptage réel, intersection commune et alias C → B |
| `probes.py` | Sondes longues en tokenization seule, sans gros encodage |
| `benchmark.py` | Mesures, fichiers float32 ordonnés et inspection d’intégrité |
| `cli.py` | Liste, caractéristiques, téléchargement, tokenization, plan, benchmark et inspection |

L’option uv **`embeddings`** fixe PyTorch 2.10.0, Transformers 4.57.6,
huggingface-hub 0.36.0, NumPy 2.2.6 et psutil 7.2.2. L’index officiel CUDA 12.8
est réservé à PyTorch Linux x86_64. Le verrou résout **2.10.0+cu128** sur ce PC.
Les versions existantes du socle et de l’annotation ne sont pas mises à jour.
La prise en charge Blackwell par les roues CUDA récentes est documentée par
[PyTorch](https://pytorch.org/blog/pytorch-2-7/).

Installation effectivement réalisée dans **`rag/.cache/embeddings-venv/`**,
sans synchroniser `rag/.venv/`. Le téléchargement initial des dépendances CUDA
et leur installation ont pris environ 15 minutes ; ce coût n’est pas inclus
dans les temps de chargement des modèles. Les modèles ont été téléchargés
depuis leurs seuls dépôts officiels. L’inférence interdit les accès réseau.

Autres adaptations : un point d’entrée dans `pyproject.toml`, documentation,
verrou RAG, tests, et ancrage de l’exclusion `/embeddings/` pour permettre de
versionner le package source du même nom. Le test d’isolation admet désormais
la présence des bibliothèques optionnelles, tout en continuant à interdire
leurs imports depuis les composants qui doivent en rester indépendants.
Aucun fichier du backend, du frontend, de Docker ou de Wallace n’est modifié.

## 3. Recettes, tokenization et dépassements

- E5 : `passage: ` pour les documents, `query: ` pour les requêtes, moyenne
  masquée des états cachés.
- BGE-M3 : aucun préfixe, pooling CLS ; sorties sparse et multivecteur non utilisées.
- Qwen : instruction de recherche officielle sur les requêtes, aucune instruction
  documentaire, dernier token avec padding gauche. Aucune génération de texte.

Les modèles calculent en **bfloat16 sur GPU**, en **float32 sur CPU** ; le moteur
normalise les vecteurs L2 et les stocke en float32 little-endian. Les préfixes et
tokens spéciaux sont inclus dans les comptages. Le tokenizer Qwen annonce
131072 tokens alors que le modèle est configuré à 32768 : la limite effective
est **32768**, pas la valeur du tokenizer. BGE conserve sa limite logique de 8192.

Les dépassements produisent un refus avant encodage, avec identifiants et nombres
de tokens, sans texte dans le message. Aucun document n’est tronqué. Il n’y a
pas de repli CPU implicite après erreur GPU.

### Lot et intersection commune

Les artefacts `rag011/final-trial-A/B/C/D` contiennent les mêmes **512 unités de
développement**, soit **513 représentations** par stratégie. La graine et les
paramètres préparatoires RAG-011 sont conservés. Les comparaisons sont faites
sur les mêmes représentations **pour tous les modèles, au sein d’une stratégie**.

| Stratégie | E5 : max / P95 / dépassements | BGE : max / P95 / dépassements | Qwen : max / P95 / dépassements | Commun encodé |
|---|---|---|---|---|
| A | 497 / 152 / 0 | 495 / 150 / 0 | 559 / 158 / 0 | 513 représentations, 512 unités |
| B | 531 / 194 / 1 | 529 / 192 / 0 | 593 / 201 / 0 | 512 représentations, 511 unités |
| D | 531 / 263 / 1 | 529 / 261 / 0 | 593 / 271 / 0 | 512 représentations, 511 unités |

L’entrée trop longue pour E5 est exclue explicitement des trois benchmarks B/D,
sans tronquer son texte. Le plan conserve son identifiant, son empreinte et son
comptage. Cette intersection permet de comparer les coûts des modèles ; elle
ne doit pas devenir une exclusion silencieuse lors de la future indexation.
Les ensembles effectivement encodés ne sont donc pas parfaitement identiques
entre A et B/D : aucune comparaison de pertinence entre stratégies n’en est déduite.

C est vérifié identique à B pour les textes et les paramètres hors stratégie.
**512 alias C → B** sont conservés, avec une exclusion commune ; aucun vecteur C
n’est recalculé. Les 40 requêtes RAG-006 ne servent pas à ces mesures.

### Sondes longues complémentaires

Trois unités de développement ont été lues dans la base RAG, en lecture seule,
et préparées avec la stratégie A sans découpage, à des fins de comptage seulement.

| Caractères sources | Tokens E5 | Tokens BGE | Tokens Qwen |
|---:|---:|---:|---:|
| 56 257 | 15 103 | 15 101 | 16 055 |
| 16 083 | 4114 | 4112 | 4531 |
| 13 548 | 3177 | 3175 | 3455 |

Les trois dépassent E5, la première dépasse BGE ; elles tiennent toutes dans la
fenêtre déclarée de Qwen. **Ces textes longs n’ont pas été encodés entiers.**
Le coût GPU à 16K/32K tokens n’a donc pas été mesuré. Une sonde synthétique
surdimensionnée a aussi vérifié le refus pour chaque tokenizer, y compris Qwen.

## 4. Conditions des benchmarks

PC : **RTX 5090**, capacité CUDA **12.0 / sm_120**, environ 32 Go de VRAM,
**Ryzen 9 7950X**, 128 Go de RAM, Linux. Pilote **595.99.02** ; runtime PyTorch
**CUDA 12.8**, distinct de la capacité CUDA 13.2 annoncée par le pilote.

GPU : bfloat16, SDPA, TF32 désactivé, graine 42, lots **8 puis 32**, quatre threads
CPU. Un processus séparé par modèle. Mesures synchronisées CUDA ; chauffage
synthétique préalable. Les débits incluent comptage, tokenization, inférence,
pooling, normalisation, transfert CPU et écriture locale. Les compteurs de tokens
excluent le padding et dépendent du tokenizer de chaque modèle.

CPU : float32, quatre threads, uniquement un petit benchmark de requêtes et les
contrôles synthétiques. Les latences portent sur **8 requêtes synthétiques,
2 passages à chaud**, batch 1. P50/P95 utilisent les rangs `ceil(p × n)` ; sur
16 observations, P95 est le maximum. Aucune de ces mesures ne représente Wallace.

## 5. Résultats GPU

### Débit par stratégie — représentations/seconde

| Modèle | A lot 8 | A lot 32 | B lot 8 | B lot 32 | D lot 8 | D lot 32 |
|---|---:|---:|---:|---:|---:|---:|
| E5-small | 1066 | 2370 | 1120 | 2080 | 1010 | 1668 |
| BGE-M3 | 609 | 742 | 580 | 677 | 522 | 539 |
| Qwen 0.6B | 334 | 326 | 326 | 311 | 282 | 246 |

### Débit tokenisé — tokens/seconde

| Modèle | A lot 8 | A lot 32 | B lot 8 | B lot 32 | D lot 8 | D lot 32 |
|---|---:|---:|---:|---:|---:|---:|
| E5-small | 47 412 | 105 367 | 83 384 | 154 846 | 126 296 | 208 495 |
| BGE-M3 | 25 861 | 31 507 | 42 004 | 49 058 | 64 145 | 66 296 |
| Qwen 0.6B | 14 825 | 14 476 | 24 487 | 23 326 | 35 791 | 31 255 |

Le lot 32 accélère E5, plus modestement BGE. Il ralentit Qwen sur ce petit lot
non regroupé par longueurs. Le padding, l’architecture, les transferts et le
travail CPU comptent ; un plus gros lot n’est pas automatiquement préférable.
Il s’agit d’un passage par taille de lot, avec caches déjà sollicités, pas d’un
benchmark statistiquement stabilisé. Les durées documentaires vont d’environ
0,22 s à 2,08 s par couple stratégie/taille de lot : les petits coûts fixes ont
un effet notable.

### Chargement et ressources GPU

| Modèle | Chargement local (s) | VRAM pic alloué PyTorch (Mio) | VRAM pic réservé (Mio) | RSS RAM pic (Mio) | Requête P50 / P95 (ms) |
|---|---:|---:|---:|---:|---|
| E5-small | 4,25 | 403 | 648 | 1758 | 4,71 / 5,00 |
| BGE-M3 | 4,41 | 1472 | 2156 | 3929 | 9,09 / 10,09 |
| Qwen 0.6B | 2,60 | 3590 | 4972 | 2085 | 14,84 / 16,26 |

Le chargement inclut vérification des fichiers, tokenizer, bibliothèques,
chargement des poids et transfert/synchronisation GPU. La VRAM est celle du
compteur PyTorch, hors bureau et autres applications. La RAM est le RSS du
processus échantillonné toutes les 20 ms, chargement inclus ; des pics très
courts peuvent être manqués.

## 6. Résultats CPU — requêtes seulement

| Modèle | Chargement (s) | Requête P50 (ms) | P95 (ms) | RSS RAM pic (Mio) |
|---|---:|---:|---:|---:|
| E5-small | 2,64 | 6,65 | 7,97 | 1118 |
| BGE-M3 | 3,96 | 62,56 | 68,41 | 2916 |
| Qwen 0.6B | 2,63 | 131,66 | 141,82 | 4056 |

Ces résultats rendent E5 particulièrement intéressant à tester pour un service
CPU, tout en soulignant sa petite fenêtre. BGE et Qwen restent techniquement
exécutables sur CPU. **Le PC local n’est pas Wallace** : aucune latence serveur
n’est prédite et aucune connexion au serveur n’a été effectuée.

Les requêtes CPU devront employer **le même modèle/révision/espace vectoriel**
que les documents de l’index. Encoder les documents avec BGE et les requêtes
avec E5 serait incorrect, même si une adaptation de dimension était possible.

## 7. Intégrité, stabilité et vérifications synthétiques

**24 matrices et 9270 vecteurs sauvegardés ont été vérifiés hors ligne** :
dimensions, valeurs finies, normes après stockage float32, SHA-256, métadonnées,
ordre des identifiants et empreintes des entrées communes. Aucun contenu du
corpus n’est reproduit dans ce rapport.

Stabilité sur les huit premiers vecteurs documentaires entre lots 8 et 32 :
E5 et BGE ont donné les mêmes valeurs dans cet échantillon ; l’écart absolu
maximal Qwen est **0,00295**, sous la tolérance déclarée de 0,005 et avec cosinus
au moins 0,999. Les deux passages de requêtes à batch 1 ont été identiques pour
chaque modèle/périphérique. Ce contrôle ne garantit pas l’identité de tous les
vecteurs entre matériels ou conditions.

Comparaison des huit requêtes GPU/bfloat16 et CPU/float32 :

| Modèle | Cosinus minimal | Écart absolu maximal |
|---|---:|---:|
| E5-small | 0,999973 | 0,001282 |
| BGE-M3 | 0,999887 | 0,003544 |
| Qwen 0.6B | 0,999753 | 0,003285 |

Les exemples synthétiques couvrent synonymes, polysémie de « banque », réponse
courte contextualisée et vocabulaire distinct. E5/BGE retrouvent les passages
illustratifs attendus en tête sur ces quatre cas. Qwen retrouve les trois
premiers, mais place une réponse générique « Non. » devant le passage sur le
vélo pour le dernier cas. Ce constat mérite une investigation ultérieure ;
**ce n’est ni un score de qualité du corpus ni un motif suffisant pour écarter
ou retenir définitivement un modèle**. Aucun seuil ou préfixe n’a été ajusté
après observation de ces exemples.

## 8. Stockage et manifestes

Stockage théorique pour **20 000 vecteurs float32 uniques**, hors modèle,
métadonnées, segments supplémentaires et index :

| Modèle | Octets/vecteur | Total décimal | Total binaire |
|---|---:|---:|---:|
| E5-small, 384 dimensions | 1536 | 30,72 Mo | 29,30 Mio |
| BGE/Qwen, 1024 dimensions | 4096 | 81,92 Mo | 78,13 Mio |

Les matrices réellement écrites sont limitées aux essais ; le total documentaire
est d’environ 4,72 Mo pour E5 et 12,59 Mo pour chacun des deux autres, duplications
de mesures par tailles de lots comprises. Aucun vecteur n’a été écrit dans PostgreSQL.

Sous `evaluation/local/rag012/` :

```text
common-plan.json                         Modèles, tokenizers, compteurs, exclusions, IDs et alias C
long-probes.json                         Comptages longs et refus synthétiques
protected-hashes.json                    Empreintes des fichiers historiques et de l’environnement
validation.json                          Intégrité des 24 matrices et comparaison numérique CPU/GPU
gpu-e5-small/ gpu-bge-m3/ gpu-qwen3-0.6b/   Mesures, matrices et manifeste par modèle GPU
cpu-e5-small/ cpu-bge-m3/ cpu-qwen3-0.6b/   Mesures CPU et matrices de requêtes
```

Les manifestes conservent modèle/révision, hash du snapshot, tokenizer, paramètres
préparatoires, instructions, précision, normalisation, matériel et pilote,
bibliothèques, source, identifiants, empreintes d’entrée/sortie, tailles de lots,
mesures et hash du code. Les matrices `.f32` ont des JSON d’accompagnement
ordonnés et contrôlables sans charger les modèles.

**130 fichiers protégés ont conservé leurs empreintes**, dont requêtes,
candidats/classements historiques, représentations RAG-011, code d’annotation,
configuration de l’environnement normal et verrous du backend. La session et
les jugements RAG-010 n’ont pas été ouverts ni modifiés. Les artefacts lourds,
snapshots et environnements sont ignorés par Git.

## 9. Commandes et validation

Depuis `rag/` :

```bash
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv \
  uv sync --locked --extra embeddings --dev
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli list
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli inspect evaluation/local/rag012/gpu-bge-m3
```

Voir [embeddings-locaux.md](embeddings-locaux.md) pour téléchargement, comptage,
planification et reproduction des benchmarks. De nouveaux dossiers sont requis ;
aucun résultat existant n’est écrasé.

Résultats des suites complètes sur les bases PostgreSQL `_test` dédiées :

- Environnement normal avec annotation : **329 tests réussis**, **3 ignorés**
  parce que les tenseurs PyTorch optionnels n’y sont pas installés.
- Environnement embeddings sans FastAPI : **324 tests réussis**, **8 ignorés**
  correspondant aux routes HTTP optionnelles d’annotation.
- Sous-suite embeddings dans l’environnement lourd : **22 tests réussis**,
  comprenant les trois recettes de pooling vérifiées avec de vrais tenseurs CPU.
- Les **60 intégrations PostgreSQL** existantes passent dans les deux environnements.
- Ruff et contrôle de formatage : conformes ; **`uv lock --check` : conforme**.
- Wheel et distribution source construits ; point d’entrée embeddings présent,
  sans modèle, cache ni donnée locale dans la distribution source.

Les tests couvrent backends simulés, chargement explicite, limites, instructions,
normalisation, vecteurs invalides, lots, identifiants, snapshots, plans communs,
alias C, erreurs CPU/GPU, matrices, corruption et isolation des imports lourds.
L’avertissement Starlette/httpx déjà présent reste visible dans l’environnement
normal ; aucune nouvelle dépendance n’est ajoutée pour le masquer.

Le premier accès GPU dans le sandbox était impossible. Le contrôle du pilote
et les benchmarks GPU ont ensuite été exécutés avec l’accès local GPU autorisé ;
le runtime reconnaît bien **sm_120**. Aucun pilote système n’a été changé.

## 10. Recommandation pour les premières recherches vectorielles

**Commencer par BGE-M3 dense et la représentation B comme référence technique**,
avec A en contrôle et D comme variante expérimentale. C réutilise B et prépare
la restitution parentale. Cette recommandation repose sur la fenêtre confortable,
le coût GPU mesuré et une recette simple ; elle ne désigne pas le meilleur modèle
de pertinence sur les contributions.

Conserver E5-small comme alternative prioritaire si le coût CPU futur devient
structurant, après préparation en tokens assurant le respect de ses 512 tokens.
Conserver Qwen pour les essais de contexte long et les comparaisons ultérieures :
sa fenêtre et les évaluations publiées sont intéressantes, mais son coût CPU et
le comportement synthétique observé justifient de ne pas le retenir seul maintenant.

Avant une indexation complète :

1. Définir une segmentation/budgétisation liée au tokenizer, y compris question,
   instructions et voisins ; la limite actuelle en caractères n’est pas suffisante.
2. Fixer une identité d’espace vectoriel validée à la lecture : modèle/révision,
   pooling, préfixes, dimension, normalisation et préparation documentaire.
3. Choisir les règles de regroupement des segments vers les unités primaires et
   de réutilisation de C, sans introduire les voisins comme résultats indépendants.
4. Comparer la pertinence avec de vrais jugements humains dans une tâche distincte,
   sans réutiliser la partition réservée pour régler les modèles.
5. Mesurer séparément le futur encodage CPU sur le matériel de déploiement avant
   toute décision d’intégration publique ; aucune intervention Wallace n’est faite ici.

Limites : petit lot, un passage documentaire par taille, fenêtres longues testées
par comptage seulement, P95 sur 16 requêtes synthétiques, VRAM mesurée par PyTorch
et RSS échantillonné. Aucun score Precision/Recall/MRR/nDCG du corpus n’est calculé.
Aucun commit, push, déploiement ou changement de données sources effectué.
