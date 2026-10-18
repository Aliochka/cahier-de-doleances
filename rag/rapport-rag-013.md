# RAG-013 — Première recherche vectorielle locale

## Résultat

Le corpus expérimental est effectivement indexé dans PostgreSQL local :
**20 000 unités originales, 20 067 représentations B et vecteurs BGE-M3**.
La recherche cosinus exacte est fonctionnelle. Les classements des seules
20 requêtes de développement ont été exportés et reproduits à l'identique.
Aucune requête réservée ni annotation humaine n'a été utilisée.

## 1. Segmentation et préparation

Le nouveau module `vector/preparation.py` reprend le format B de RAG-011,
question et fragment de réponse séparés par des libellés explicites. Il mesure
le texte complet avec le tokenizer BGE-M3, y compris les tokens spéciaux.
Le budget choisi avant toute recherche est 1024 tokens, avec chevauchement
configuré de 128 tokens et préférence pour les frontières de phrases/paragraphes.
Les segments conservent leurs offsets Unicode dans le texte original.
Aucune troncature ni réécriture linguistique n'est appliquée.

Résultats réels :

| Indicateur | Valeur |
|---|---:|
| Unités originales | 20 000 |
| Représentations / vecteurs | 20 067 |
| Unités segmentées | 33 |
| Maximum de segments par unité | 18 |
| Tokens cumulés, contexte et chevauchements compris | 1 548 983 |
| Maximum de tokens par représentation | 1024 |
| Unités développement / évaluation | 17 612 / 2 388 |
| Segments développement / évaluation | 17 667 / 2 400 |

Les unités réservées sont indexées conformément au corpus commun ; leurs
requêtes d'évaluation ne sont jamais exécutées. Aucun parent extérieur n'est
ajouté à B. A et D restent disponibles pour des expériences ultérieures ; C
pourra réutiliser les vecteurs B. `TextUnit` et les contrats RAG-011 sont inchangés.
La représentation nouvelle possède une version explicite `token-B:v1`.

## 2. Modèle et configuration

- Modèle : `BAAI/bge-m3`, sortie dense, licence MIT.
- Révision : `5617a9f61b028005a4858fdac845db406aefb181`, identique à RAG-012.
- Tokenizer et poids : snapshot local validé par SHA-256, réseau désactivé.
- Pooling CLS ; aucun préfixe supplémentaire pour documents ou requêtes.
- Calcul bfloat16 sur RTX 5090, normalisation L2, stockage float32 / 1024 dimensions.
- Lots GPU de 8 représentations, lots de reprise de 25 unités.

La matrice float32 brute occupe **82 194 432 octets**, environ 78,4 Mio.
Aucune nouvelle dépendance Python n'est nécessaire : les paramètres vectoriels
sont validés puis liés à un cast SQL `public.vector(1024)`. Le stockage et les
imports de recherche ne forcent ni numpy, ni torch, ni un adaptateur psycopg global.
Le moteur utilise les dépendances optionnelles déjà verrouillées de RAG-012.

## 3. PostgreSQL et migrations

L'installation système initialement absente a été faite par l'utilisateur.
L'utilisateur a ensuite activé l'extension avec son rôle administrateur dans
`cahier_rag` et `cahier_rag_test`. L'extension disponible est **pgvector 0.8.7**,
sur PostgreSQL 17. Elle n'est pas installée dans `cahier_doleances_local`
(vérification en lecture seule : zéro extension `vector`).

La migration indépendante `rag_0003` ajoute :

- `rag.vector_spaces` : recette et manifeste JSONB, empreinte du corpus,
  volumes attendus, checkpoint transactionnel et état de complétude.
- `rag.vector_representations` : identifiant stable, référence au document,
  empreintes, partition, positions, représentation préparée, vecteur et SHA-256
  des octets float32.
- Contraintes de références, d'unicité, de positions et de norme ; index B-tree
  pour l'espace, les documents et les partitions.

Aucun HNSW ni IVFFlat. La recherche utilise l'opérateur cosinus exact `<=>`.
Le contrôle d'identité physique RAG-005 précède toute migration/écriture.
La migration refuse une extension absente ou incompatible ; aucune installation
système n'est exécutée par le code. Le downgrade conserve l'extension partagée.
La migration aller-retour a été testée sur la destination de test vide uniquement.

Stockage mesuré : **155 246 592 octets**, environ **148,1 Mio**, tables, TOAST et
index vectoriels relationnels compris. Le schéma source n'est pas modifié.

## 4. Indexation, interruption et reprise

La préparation produit un JSONL et son manifeste en mémoire bornée. Les lectures
PostgreSQL sont fermées avant traitement. L'encodage produit des lots `.f32`
locaux et des métadonnées atomiques vérifiant identifiants et empreintes.
Les versions des bibliothèques et paramètres sont conservés dans
`encoded/parameters.json`, les ressources mesurées dans `encoded/report.json`.

Un premier lot réel de **25 unités** a été encodé, puis la génération relancée.
Elle a réutilisé ce lot et complété les 20 000 unités. L'import PostgreSQL a
également été arrêté après 25 unités, puis repris jusqu'à complétude.
L'encodage et l'import sont séparés afin de ne pas recalculer les vecteurs déjà
validés lorsqu'une migration ou une écriture est interrompue.

Chaque lot PostgreSQL insère ses représentations et met à jour le checkpoint
dans **une seule transaction**. Un retry identique est idempotent ; une empreinte
différente déclenche un conflit sans écrasement. Les tests simulent une panne
avant checkpoint et comparent les empreintes d'une reprise et d'un parcours
sans interruption. Le corpus réel n'a pas été dupliqué pour cette comparaison.

Espace final :

```text
d8535ec2e25212b669fee8977e766ac1e308d6dd935792730ba08a73f4f7960b
```

Empreinte ordonnée des identifiants de représentations et des vecteurs :

```text
6481f5b998e0e26856a8a495e657daf6616c128d3cb4734a8d1b832ed3a4a812
```

## 5. Recherche et performances

`VectorEngine` vérifie explicitement l'encodeur et l'index avant chargement.
La recherche agrège les segments par le **meilleur score cosinus**, puis limite
les unités et départage les égalités par identifiant documentaire, collation C.
Les filtres de questionnaire, type et partition s'appliquent avant agrégation.
Les résultats réutilisent le contrat lexical `SearchResult`, avec le `TextUnit`
complet et ses identifiants sérialisés sans perte de précision.

Un contrôle supplémentaire refuse une disparition de segments même si un état
`complete` subsiste après modification administrative externe. Les tests ont
révélé ce cas et le contrôle de volumes a été ajouté avant chaque recherche.

| Mesure locale | Observation |
|---|---:|
| Génération GPU après reprise des 25 premiers vecteurs | 58,21 s |
| Débit global, incluant validation/cache | environ 344 représentations/s |
| Pic mémoire GPU allouée par PyTorch | 1 371 702 272 octets, environ 1,28 Gio |
| Pic RSS du processus de génération | 4 234 006 528 octets, environ 3,94 Gio |
| Import des 19 975 unités restantes et vérification complète | 39,52 s |
| Requêtes de développement avec résultats | 20 / 20 |
| Résultats par requête | 10 |
| Latence finale médiane, encodage + contrôles + SQL | 96,41 ms |
| Latence finale P95, rang le plus proche sur 20 mesures | 102,10 ms |
| Encodage des requêtes, médiane | 10,66 ms |
| SQL et contrôles, médiane | 85,67 ms |

Le premier encodage de requête est plus lent ; il est inclus dans les mesures.
Les chargements du modèle et la vérification initiale complète de l'index sont
hors latence par requête. Le pic GPU est la mémoire allouée par PyTorch,
pas la totalité de la mémoire réservée par le pilote.
Le temps de préparation du premier JSONL n'a pas été instrumenté séparément.
Ces mesures sont celles du PC local, pas de Wallace ni d'une charge concurrente.

Les 200 résultats comprennent **198 contributions distinctes par requête en
somme** (9 ou 10 contributions pour 10 unités), sans compter plusieurs segments
d'une même réponse. Cette somme n'est pas un nombre de contributions uniques
sur l'ensemble des requêtes.
Trois parcours de développement ont produit **les mêmes 20 classements et les
mêmes 200 scores**, y compris après ajout du contrôle de volumes. La mesure
finale retient le parcours avec ce contrôle actif ; les précédents sont gardés.
Aucun Precision, Recall, MRR ou nDCG n'a été calculé sans jugements humains.

## 6. Commandes et artefacts

Voir [les commandes complètes](recherche-vectorielle.md). Depuis `rag/` :

```bash
.cache/embeddings-venv/bin/python -m cahier_rag.vector.cli status
.cache/embeddings-venv/bin/python -m cahier_rag.vector.cli verify
.cache/embeddings-venv/bin/python -m cahier_rag.vector.cli search 'Comment financer les services publics ?'
```

Les deux variables RAG doivent être définies explicitement. Pour refaire une
préparation ou un export, choisir un nouveau dossier avec `--directory` ou
`--output` ; les commandes refusent l'écrasement.

Artefacts privés ignorés par Git sous `rag/evaluation/local/rag013/` :

- `bge-B/manifest.json`, `representations.jsonl` : recette et textes préparés.
- `bge-B/encoded/` : lots float32, empreintes d'entrées, paramètres et rapport GPU.
- `bge-B/index-report.json` : résultat de l'import repris.
- `development/`, `development-replay/`, `development-final/` : classements,
  scores et mesures. **Utiliser `development-final/rankings.json`** pour RAG-006.
- `statistics.json`, `validation.json` : statistiques et contrôle de reproduction,
  avec empreintes de l'implémentation finale.

Aucun de ces fichiers privés n'est ajouté à Git. La session d'annotation et ses
jugements n'ont été ni ouverts ni modifiés. Les 40 requêtes et les manifestes
RAG-007 à RAG-012 restent inchangés. Les seuls changements de projet existant
sont le point d'entrée Python, l'attente de révision/tables dans le test de
migration et la documentation RAG. Le verrou n'a pas besoin de changer, car
aucune dépendance n'est ajoutée.

## 7. Tests et intégrité

- Suite complète dans l'environnement courant d'annotation : **362 réussis,
  3 ignorés**, ces derniers requérant torch absent de cet environnement.
- Les trois tests optionnels de pooling ont été exécutés séparément dans
  l'environnement embeddings : **3 réussis**.
- **8 tests PostgreSQL vectoriels** : stockage, idempotence, conflits, rollback
  avant checkpoint, reprise, recherche exacte, filtres/partitions, égalités,
  agrégation de segments, BIGINT/provenance, corruption, migration aller-retour.
- **25 tests unitaires nouveaux** : segmentation, textes, offsets, empreintes,
  cache, erreurs et isolation, sans GPU ni PostgreSQL.
- Ruff conforme ; `uv lock --check --offline` conforme ; `git diff --check` conforme.
- Vérification intégrale réelle effectuée avec l'environnement sans torch :
  20 000 unités et 20 067 vecteurs conformes, empreinte finale identique.

Un avertissement Starlette/httpx préexistant demeure dans le test d'annotation ;
il n'est pas lié à la recherche vectorielle.

## 8. Limites et suite

Le budget de 1024 tokens est une recette expérimentale, pas un optimum mesuré.
Les fenêtres de texte peuvent couper une phrase sans frontière disponible.
Le chevauchement est demandé en tokens, ses frontières étant retranscrites en
caractères et revérifiées après contextualisation. Les vecteurs BGE-M3 ne sont
pas encore comparés en pertinence aux baselines lexicales.

La première recherche exacte retourne ses voisins même pour une requête peu
pertinente : aucun seuil de score n'a été réglé. La présence de 10 résultats
ne démontre donc pas leur qualité. Les textes courts et « Autre » sont inclus,
mais leur qualité sémantique reste à évaluer humainement.

L'index initial exige la recette bfloat16 correspondante pour les requêtes ;
une variante CPU float32 nécessitera une compatibilité explicitement validée.
La CLI sait choisir CPU, mais cela ne constitue pas une recette compatible
implicite avec cet index GPU. Aucun service public n'est intégré.

L'intégrité complète est contrôlée au chargement ; les volumes et les documents
retournés sont revérifiés par recherche. Des modifications administratives
concurrentes ne constituent pas un mode d'exploitation pris en charge.
La recherche exacte et ses contrôles devront être remesurés avant d'augmenter
le corpus ou la concurrence. Aucune simulation de panne électrique matérielle
n'a été réalisée ; les tests portent sur interruptions de processus, erreurs
et transactions annulées.

Pour la recherche hybride, conserver cet espace et les baselines gelés,
utiliser les identifiants originaux comme clé commune de fusion, puis régler
une fusion uniquement sur le développement après disponibilité de jugements
humains. Aucun poids hybride, reranker, index approximatif ni seuil n'est
introduit dans cette tâche.
