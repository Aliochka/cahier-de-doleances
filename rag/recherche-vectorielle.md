# RAG-013 — Recherche vectorielle locale exacte

Le périmètre reste le manifeste RAG-007 : **20 000 unités**, empreinte
`d0173a371df7fc5d6b5d8ca393ea3f230349140b1cfb92a1ec4a2280200033cc`.
Les unités du cadre qui n'y figurent pas ne sont ni vectorisées ni recherchées.
Les artefacts, classements et sessions RAG-007 à RAG-012 restent inchangés.

## Représentation et modèle

La représentation B reprend les libellés RAG-011 :

```text
Question :
[question originale]

Réponse :
[fragment original de réponse]
```

Les titres restent des métadonnées. Aucun contexte externe n'est ajouté.
C réutilisera ces textes et vecteurs ; A et D ne sont pas indexées ici.
Le nouveau contrat `token-B:v1` conserve les offsets Unicode `[start,end[` dans
la réponse, l'indice du segment, le document source et son empreinte, la
contribution, le questionnaire, le type et la partition. L'identifiant dépend
du document, de son empreinte, du corpus, de la configuration et des offsets.
L'empreinte du contenu inclut toutes les métadonnées et le texte préparé.
Le contrat `TextUnit` et les artefacts RAG-011 ne sont pas modifiés.

BGE-M3 dense utilise la révision RAG-012
`5617a9f61b028005a4858fdac845db406aefb181`, pooling CLS, aucun préfixe
supplémentaire, normalisation L2, stockage **float32 / 1024 dimensions**.
Le calcul GPU utilise bfloat16, puis conversion et normalisation avant stockage.
Le snapshot local vérifie les empreintes des poids et du tokenizer ; le réseau
est désactivé par l'adaptateur. Aucun téléchargement n'est nécessaire.

Le budget initial est **1024 tokens**, chevauchement demandé **128 tokens**.
Ces paramètres sont techniques et ne sont pas réglés sur des annotations.
Le comptage couvre question, libellés et tokens spéciaux avec le vrai tokenizer.
La segmentation cherche une frontière de phrase/paragraphe lorsqu'elle tient
dans le budget, puis valide exactement chaque texte final. Les offsets du
tokenizer déterminent le chevauchement ; la retokenization aux frontières peut
faire varier légèrement sa longueur effective. Une question trop longue ou un
chevauchement empêchant la progression provoque une erreur. Aucun texte n'est
tronqué. Le budget est configurable jusqu'à 8192, il n'est pas une taille finale
retenue pour toutes les expériences.

## Modules et stockage

- `vector/preparation.py` : segmentation et artefact JSONL + manifeste.
- `vector/cache.py` : lots binaires float32 locaux, vérification des entrées et
  sorties, reprise de génération GPU sans PostgreSQL.
- `vector/store.py` : persistance, intégrité et recherche exacte pgvector.
- `vector/pipeline.py` : checkpoint par lots d'unités originales.
- `vector/engine.py` : interface de recherche et contrôle de l'encodeur.
- `vector/cli.py` : commandes locales, export de développement uniquement.

La migration `rag_0003` ajoute `rag.vector_spaces` et
`rag.vector_representations`. Le premier conserve le manifeste versionné, les
volumes attendus, les compteurs/checkpoint et l'état `building`/`complete`.
Le second lie chaque représentation au `TextUnit`, stocke la provenance de
segmentation et le texte préparé en JSONB, les empreintes et `vector(1024)`.
Les clés étrangères, unicités et contraintes de norme protègent la structure.
Seuls des index B-tree sont créés : aucun HNSW ni IVFFlat.

Les migrations passent par le contrôle d'identité physique RAG-005, refusent
la base source et vérifient la disponibilité et les fonctions de pgvector.
L'installation du paquet système et la première activation de l'extension
requièrent l'administrateur. **Ne jamais activer l'extension dans la base source.**
L'extension n'est pas supprimée lors du downgrade, car elle peut être partagée.
Une migration échouée est annulée en transaction.

## Reprise et intégrité

Les documents sont parcourus dans l'ordre explicite de leurs identifiants.
La préparation lit 25 unités à la fois ; chaque lecture PostgreSQL est fermée
avant la tokenization. Son fichier final et son manifeste ne deviennent
valides qu'une fois terminés ; une préparation interrompue se relance dans un
nouveau dossier.

L'encodage traite par défaut 25 unités par lot de reprise et 8 représentations
par lot GPU. Il garde au plus 2048 représentations en mémoire et refuse les
unités dépassant 1000 segments. Les fichiers `encoded/NNNNN.f32` sont écrits
par remplacement atomique ; leurs métadonnées JSON sont écrites en dernier.
Les SHA-256 des entrées et des octets float32 empêchent une reprise différente.
Les paramètres de génération, versions des bibliothèques et matériel sont
conservés localement. Une erreur GPU n'avance pas le lot ; les lots déjà
validés sont réutilisés. Conserver les mêmes tailles de lots pour une reprise
bit à bit de la génération. Pour un OOM, choisir explicitement un nouvel essai
avec une configuration documentée ; aucun repli CPU n'est silencieux.

L'import valide les documents stockés et les vecteurs, puis écrit **toutes les
représentations du lot et le checkpoint dans une transaction unique**.
Une répétition identique est sans effet ; une empreinte différente est un
conflit sans écrasement. Le cache local survit à un rollback PostgreSQL.
Deux importateurs concurrents sont sérialisés par verrou et checkpoint.
L'état `complete` est attribué seulement après contrôle de tous les documents,
segments et empreintes. Un index incomplet est refusé par la recherche.

`verify` ne charge pas le modèle : il recalcule les empreintes float32 et celles
des documents, vérifie leurs références au manifeste, les partitions, les
positions, l'absence de trous et les textes préparés. Il parcourt les vecteurs
avec un curseur serveur, sans charger toute la matrice en RAM. La CLI charge le
tokenizer uniquement pour préparer/encoder et le modèle uniquement pour encoder
ou rechercher. Les imports du stockage ne requièrent ni torch ni numpy.

## Recherche et partitions

Le score est `1 - distance_cosinus`. Pour plusieurs segments d'une même unité,
le score de l'unité est le maximum de leurs similarités. La requête groupe donc
les segments **avant** la limite, puis départage par identifiant documentaire
avec la collation `C`. Chaque réponse apparaît une fois ; plusieurs réponses
d'une même contribution restent plusieurs unités, et la diversité des
contributions est mesurée séparément.

La recherche est exacte et utilise les seuls vecteurs de l'espace lié au
manifeste. Les filtres questionnaire, type et partition sont appliqués avant
l'agrégation. Le moteur vérifie modèle, révision, snapshot, dimension et recette.
Les identifiants BIGINT restent des `int` Python et deviennent des chaînes dans
les résultats JSON. Les résultats réutilisent `SearchResult` du moteur lexical.

La CLI recherche exclusivement dans `development`. La commande `development`
exécute seulement les 20 requêtes de cette partition. Aucune commande de cette
version n'exécute le jeu de requêtes réservé. Les classements exportés sont des
objets `query_id -> [document_id,...]` compatibles RAG-006 ; les scores et temps
sont séparés. Ils ne constituent pas des jugements ni des scores de pertinence.

## Commandes

Depuis `rag/`, avec les deux variables RAG définies explicitement :

```bash
export RAG_SOURCE_DATABASE_URL=postgresql:///cahier_doleances_local
export RAG_DATABASE_URL=postgresql:///cahier_rag

# Environnement optionnel embeddings ; ne pas synchroniser la session d'annotation.
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv sync --locked --extra embeddings

# Après disponibilité et activation administrateur de pgvector dans la seule base RAG :
uv run --no-sync cahier-rag schema-upgrade

# Utilisable directement dans l'environnement GPU séparé existant :
.cache/embeddings-venv/bin/python -m cahier_rag.vector.cli prepare --budget 1024 --overlap 128
.cache/embeddings-venv/bin/python -m cahier_rag.vector.cli encode
.cache/embeddings-venv/bin/python -m cahier_rag.vector.cli index --stop-after 25
.cache/embeddings-venv/bin/python -m cahier_rag.vector.cli resume
.cache/embeddings-venv/bin/python -m cahier_rag.vector.cli verify
.cache/embeddings-venv/bin/python -m cahier_rag.vector.cli status
.cache/embeddings-venv/bin/python -m cahier_rag.vector.cli search 'Comment améliorer les services publics ?' --limit 10
.cache/embeddings-venv/bin/python -m cahier_rag.vector.cli development --output evaluation/local/rag013/development
```

Les options globales (`--directory`, `--models`, `--env-file`, `--sample`,
`--device`, `--precision`) précèdent la sous-commande. Le défaut de sortie est
`evaluation/local/rag013/bge-B`. Une préparation et un export exigent un dossier
inexistant, afin de ne pas écraser une expérience. `encode` peut être effectué
avant disponibilité de pgvector ; `index`/`resume` réutilisent ses lots validés.
Le point d'entrée installé est aussi `cahier-rag-vector` après synchronisation
ou réinstallation du projet. `python -m` fonctionne sans toucher l'environnement
d'annotation actif.

```bash
uv run --locked --no-sync pytest tests/unit
RAG_TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
RAG_STORAGE_TEST_DATABASE_URL=postgresql:///cahier_rag_test \
uv run --locked --no-sync pytest tests/integration
uv run --locked --no-sync ruff check .
uv lock --check
```

Les deux bases d'intégration sont distinctes et suffixées `_test`. L'extension
vector doit être disponible et activée par l'administrateur dans la destination
de test. Aucun test d'écriture ne cible le corpus réel.

## Limites

Le corpus doit être figé pendant préparation/indexation ; aucune synchronisation
continue n'est prévue. Les verrous et transactions protègent les écritures RAG,
pas des modifications administratives externes. Le cache JSONL contient des
textes réels : il reste sous `evaluation/local/`, ignoré par Git, comme les
vecteurs et classements. Aucun contenu citoyen n'est journalisé par le pipeline.
La commande interactive `search` affiche volontairement le texte demandé ; ne
pas rediriger sa sortie vers un fichier partagé. Aucun texte n'est envoyé hors
de la machine. Les manifestes stockent les empreintes, jamais les URL secrètes.

La recherche exacte est une première référence ; ses coûts augmentent avec la
taille du corpus et les segments. Aucun choix d'hybridation ou de pondération
n'est encore fait, et aucun jugement RAG-010 n'est lu.
