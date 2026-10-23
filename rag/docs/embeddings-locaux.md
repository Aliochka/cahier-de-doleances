# RAG-012 — Embeddings locaux interchangeables

Le package `cahier_rag.embeddings` encode documents et requêtes localement, avec
un chargement explicite. Les modules lexicaux, la préparation documentaire et
l’annotation continuent de fonctionner sans PyTorch, Transformers ou NumPy.
Aucun moteur de recherche vectorielle, index ou schéma PostgreSQL n’est créé.

## Modèles configurés et sources officielles

| Clé CLI | Dépôt officiel | Paramètres approximatifs | Dimension utilisée | Fenêtre retenue | Licence annoncée |
|---|---|---:|---:|---:|---|
| `e5-small` | `intfloat/multilingual-e5-small` | 118 M | 384 | 512 tokens | MIT |
| `bge-m3` | `BAAI/bge-m3` | 568 M | 1024 | 8192 tokens | MIT |
| `qwen3-0.6b` | `Qwen/Qwen3-Embedding-0.6B` | 596 M | 1024 | 32768 tokens | Apache-2.0 |

Révisions immuables du registre :

- E5 : `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- BGE : `5617a9f61b028005a4858fdac845db406aefb181`.
- Qwen : `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`.

Les trois familles couvrent le français et la recherche asymétrique. E5-small
permet d’étudier un compromis de taille pour le CPU ; BGE-M3 fournit une référence
encodeur multilingue à contexte plus long ; Qwen apporte un modèle instructionnel
récent. Seule la sortie dense de BGE-M3 est utilisée. Qwen conserve sa dimension
complète ; sa réduction dimensionnelle n’est pas expérimentée ici.

Les résultats publiés sur MTEB/MIRACL motivent cette sélection, sans prédire
la pertinence sur notre corpus et sans assimiler E5-small à E5-large-instruct.
Les licences MIT/Apache sont permissives sous leurs conditions de conservation
des mentions et notices. Références : [fiche E5](https://huggingface.co/intfloat/multilingual-e5-small),
[rapport E5](https://arxiv.org/abs/2402.05672),
[fiche BGE-M3](https://huggingface.co/BAAI/bge-m3),
[publication M3](https://arxiv.org/abs/2402.03216),
[fiche Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B),
[publication Qwen](https://arxiv.org/abs/2506.05176).

## Installation isolée avec uv

Pendant l’annotation, **ne pas synchroniser l’environnement `rag/.venv/`** pour
y ajouter ou retirer des dépendances. Utiliser le second environnement ignoré :

```bash
cd rag
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv \
  uv sync --locked --extra embeddings --dev
```

L’option `embeddings` verrouille PyTorch 2.10.0, Transformers 4.57.6,
huggingface-hub 0.36.0, NumPy 2.2.6 et psutil 7.2.2. Sur Linux x86_64,
PyTorch provient de l’index officiel **CUDA 12.8**, explicitement limité à cette
dépendance optionnelle. Les autres paquets proviennent de l’index Python normal.
CUDA 12.8/PyTorch récent prennent en charge Blackwell ; aucun toolkit CUDA
système, pilote ou service n’est installé par ce projet.
Voir [la documentation PyTorch](https://pytorch.org/blog/pytorch-2-7/).

Les dépendances d’exécution existantes restent aux mêmes versions. L’index GPU
et le verrou appartiennent au seul sous-projet RAG. Le backend public et son
verrou ne changent pas. Cet environnement CUDA peut aussi exécuter des calculs
CPU ; un éventuel déploiement CPU utilisera plus tard des roues CPU appropriées.

### Commandes locales

Toutes les commandes suivantes utilisent ce second environnement, sans
resynchronisation implicite :

```bash
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli list
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli show qwen3-0.6b
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli download e5-small
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli download bge-m3
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli download qwen3-0.6b
```

Le point d’entrée `cahier-rag-embed` est également déclaré. Les poids restent
sous `rag/models/<clé>/<révision>/`, ignorés par Git. Les fichiers sont limités
aux poids, tokenizer, configurations et notices ; aucun code distant n’est chargé.
Le snapshot conserve les SHA-256 des fichiers et la révision exacte. Un
snapshot déjà complet est vérifié et réutilisé. Une interruption de téléchargement
peut être reprise par la même commande.

**`download` est la seule commande réseau du moteur.** Elle télécharge uniquement
les fichiers officiels des modèles. Le chargement et l’inférence utilisent les
snapshots locaux avec `local_files_only=True`, `trust_remote_code=False` et les
modes hors ligne de Hugging Face/Transformers. BGE fournit des poids PyTorch `.bin`,
chargés avec `weights_only=True` ; les deux autres utilisent Safetensors.
Aucun texte citoyen ni requête n’est transmis à un service externe.

## Recettes d’encodage et limites

| Modèle | Documents | Requêtes | Pooling |
|---|---|---|---|
| E5 | Préfixe `passage: ` | Préfixe `query: `, y compris en français | Moyenne masquée |
| BGE-M3 | Aucun préfixe | Aucun préfixe | Premier token CLS |
| Qwen | Aucune instruction | Instruction de recherche officielle en anglais, puis la requête | Dernier token, padding gauche |

Aucun modèle génératif n’est invoqué : `AutoModel` fournit les états cachés,
puis le pooling extrait le vecteur. Aucune reformulation des requêtes n’intervient.
Le pooling est conforme aux configurations officielles des trois modèles.
Les vecteurs sont normalisés L2 par le moteur et stockés en **float32 little-endian**.
Les calculs du modèle utilisent bfloat16 sur GPU et float32 sur CPU dans nos essais.

Le tokenizer compte le texte effectivement envoyé au modèle, préfixes,
instructions et tokens spéciaux compris. La limite prend le minimum de la
fenêtre connue du registre et de la configuration du modèle. Le tokenizer Qwen
annonce 131072, mais la configuration du modèle est **32768** ; cette dernière
limite prévaut. Les 8194 positions internes de BGE ne sont pas une autorisation
de dépasser sa fenêtre documentée de 8192 tokens.

Tout dépassement est refusé par `InputTooLong` **avant** l’encodage du lot.
L’erreur conserve identifiants et longueurs, sans reproduire le contenu dans
son message. `counts()` permet de signaler les dépassements ; `require_fits()`
les refuse explicitement, même sans charger les poids du modèle. Aucun texte
n’est tronqué, aucun repli GPU → CPU n’est effectué automatiquement.

### Interface Python

```python
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingInput
from cahier_rag.embeddings.transformers_backend import TransformersBackend

backend = TransformersBackend(
    MODELS["e5-small"], "models", device="cpu", precision="float32", threads=4
)
engine = EmbeddingEngine(backend, normalize=True)
try:
    engine.load()
    inputs = [EmbeddingInput("exemple", "Une réponse synthétique.", "source-synthétique")]
    for batch in engine.encode_documents(inputs, batch_size=8):
        use(batch.identifiers, batch.vectors)  # votre traitement
    query_batches = list(
        engine.encode_queries(
            [EmbeddingInput("requête", "Comment simplifier les démarches ?", "requête-synthétique")]
        )
    )
    dimension = engine.dimension
finally:
    engine.close()
```

`Backend` est un protocole interchangeable. Le cœur vérifie dimensions, valeurs
finies, normes, unicité et ordre des identifiants. Les dépendances lourdes ne sont
importées que lors du chargement explicite du tokenizer ou du modèle réel.
La CLI borne cette première expérience à 512 cibles primaires de développement,
2048 représentations et des lots de 1 à 64 ; il n’y a pas de commande d’indexation.

## Corpus commun et plan de comparaison

Les répertoires de référence sont `evaluation/local/rag011/final-trial-A`,
`final-trial-B`, `final-trial-C` et `final-trial-D`, issus des mêmes 512 unités.
Le chargeur vérifie leurs manifestes, références, empreintes et partitions contre
le périmètre exact RAG-007. Aucun jugement humain ou requête RAG-006 n’est utilisé.

```bash
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli tokens e5-small \
  evaluation/local/rag011/final-trial-D
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli plan \
  --output evaluation/local/rag012/mon-plan.json
```

Le plan conserve les comptages par modèle et stratégie, les dépassements
identifiés, les empreintes, les paramètres de préparation et la liste ordonnée
des représentations communes. Cette liste est l’**intersection des entrées qui
respectent toutes les fenêtres** : aucun modèle n’est comparé sur un ensemble
plus facile que les autres dans une même stratégie. Les tokenizers produisent
des unités différentes ; les tokens/s ne sont pas une mesure universelle entre
modèles.

C est vérifié contre B : mêmes paramètres hors stratégie, mêmes unités primaires
et mêmes textes dans le même ordre. Le plan conserve les alias **ID C → ID B**
pour les représentations encodées et le nombre d’exclusions communes. Il n’y a
aucun recalcul pour C. Les matrices restent associées aux identifiants préparés,
eux-mêmes reliés aux `TextUnit` et aux segments sources.

## Benchmarks GPU et CPU

```bash
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli benchmark e5-small \
  --plan evaluation/local/rag012/mon-plan.json --device cuda --precision bfloat16 \
  --batch-sizes 8 32 --threads 4 --output evaluation/local/rag012/mon-gpu-e5

UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli benchmark e5-small \
  --plan evaluation/local/rag012/mon-plan.json --device cpu --queries-only \
  --precision float32 --threads 4 --output evaluation/local/rag012/mon-cpu-e5

UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  python -m cahier_rag.embeddings.cli inspect evaluation/local/rag012/mon-gpu-e5
```

Répéter avec `bge-m3` et `qwen3-0.6b`. Une sortie doit être un nouveau dossier
sous `evaluation/local/rag012/`. Aucun artefact existant n’est remplacé. En cas
d’échec, l’absence de manifeste signale un résultat incomplet ; recommencer dans
un nouveau dossier après correction.

Le benchmark mesure le chargement complet local (vérification des poids incluse),
les débits sur A/B/D pour les tailles de lots choisies, puis les latences de huit
requêtes françaises **synthétiques**, deux passages à chaud. Synchronisation CUDA
avant et après les mesures ; le débit inclut comptage, tokenization, inférence,
pooling, normalisation, transfert CPU et écriture locale des vecteurs. Il ne
mesure pas un noyau GPU isolé. Un chauffage synthétique précède les mesures.

Les normes et valeurs finies sont contrôlées pour chaque vecteur. La stabilité
compare les huit premiers vecteurs documentaires entre tailles de lots et les
huit vecteurs de requêtes entre passages : tolérance absolue 0,005 en GPU/bfloat16,
0,001 en CPU/float32, avec cosinus au moins 0,999. Ce n’est pas une promesse
universelle d’identité binaire entre matériels ou tailles de lots.

Les cas synthétiques explorent synonymes, polysémie, réponse courte contextualisée
et vocabulaire différent. Ils enregistrent des classements illustratifs, sans
produire de score de pertinence sur le Grand Débat ni choisir un modèle définitif.

### Artefacts et mesures

- Matrices `.f32` accompagnées de JSON ordonnés : identifiants, empreintes d’entrée,
  tokens et dimension. Aucune conversion de BIGINT par un flottant.
- Manifeste : modèle/révision, tokenizer, paramètres préparatoires, précision,
  normalisation, instructions, tailles de lots, threads, matériel, bibliothèques,
  empreintes des données, des matrices et du code, mesures et stabilité.
- `inspect` vérifie manifeste, matrices, associations des identifiants, valeurs
  finies et normes des vecteurs stockés, sans charger de modèle.
- VRAM : pics **alloués et réservés par PyTorch**, hors mémoire du bureau et des
  autres applications, avec leurs limites de mesure.
- RAM : RSS du processus échantillonné toutes les 20 ms, chargement inclus ;
  des pics plus courts peuvent être manqués.
- Stockage estimé : `nombre de vecteurs × dimension × 4`, hors modèle, métadonnées,
  réplication de segments et futur index.

Les matrices, modèles, caches et environnements sont ignorés par Git. Le motif
`/embeddings/` est ancré à la racine RAG afin de conserver les artefacts ignorés
tout en permettant de versionner `src/cahier_rag/embeddings/`.

## Tests et indépendance

```bash
# Environnement normal de l’annotation, sans synchronisation :
uv run --locked --no-sync pytest
uv run --locked --no-sync ruff check .
uv lock --check

# Tests supplémentaires des recettes de pooling, avec l’option installée :
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv run --locked --no-sync \
  pytest tests/unit/test_embeddings.py tests/unit/test_embedding_plan.py
```

Les tests simulés et d’intégrité n’ont pas besoin de GPU ni de modèle. Les trois
tests de pooling utilisant des tenseurs CPU sont ignorés si PyTorch est absent.
Les protections d’isolation interdisent les imports lourds depuis le cœur même
lorsque les bibliothèques sont installées dans un environnement optionnel.
L’environnement de l’annotation, sa session, les 400 candidats, les 40 requêtes,
les jugements et les configurations gelées n’ont pas à être modifiés.

Pour les latences, P50/P95 utilisent le rang `ceil(p × nombre de mesures)`.
Sur les 16 mesures de requêtes, P95 correspond donc au maximum observé ; ces
petits échantillons ne caractérisent pas une charge de production.

Un futur index doit utiliser **le même modèle, la même révision, les mêmes
recettes de pooling/préfixes et la même dimension** pour les documents et les
requêtes. Les requêtes CPU E5 ne peuvent pas interroger un index BGE ou Qwen.
Une dimension identique ne rend pas deux espaces vectoriels compatibles. Le
changement CPU/GPU et de précision peut produire de petits écarts numériques,
à mesurer séparément de la pertinence.
