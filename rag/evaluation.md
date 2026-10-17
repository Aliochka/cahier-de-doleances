# Protocole d’échantillonnage et d’évaluation — RAG-006

## Périmètre et méthode

Les composants n’utilisent aucun modèle ni moteur. Les unités restent stockées
par RAG-005 dans PostgreSQL. Les manifestes d’échantillon sont des fichiers JSON
contenant identifiants, empreintes, métadonnées de sélection et partitions,
sans corps documentaire. Ils référencent des extractions **terminées** et figées,
identifiées par UUID et paramètres. Aucun nouveau schéma ni migration n’est requis.

Le cadre est l’union dédupliquée par ID d’au plus vingt extractions RAG-005.
Il est limité à 100 000 unités distinctes et 200 000 références parcourues.
Leur lecture est paginée par `RagStore`, avec transactions fermées entre lots.
Seuls les résumés nécessaires sont conservés en mémoire, jamais tous les corps.
La mémoire est O(taille maximale du cadre + taille d’un lot documentaire), pas
O(corpus complet). Un cadre trop grand provoque une erreur, sans troncature
silencieuse. Deux occurrences ayant le même texte et des IDs différents restent
présentes ; un même ID ayant deux contenus incompatibles est refusé.

**Limite structurante :** RAG-005 n’offre pas de tirage uniforme global des
millions d’unités sources. Le tirage aléatoire est donc uniforme au sens d’un
classement pseudo-aléatoire SHA256(graine, ID) **dans le cadre déclaré**. Il est
indépendant de l’ordre de lecture, sans `ORDER BY random()`, OFFSET ni parcours
source complet. Un cadre obtenu par extraction des premiers IDs ou des dernières
contributions conserve son biais de constitution. Il ne représente pas le
corpus national. Un futur tirage probabiliste global exigera un plan spécifique.

Deux sélections sont disponibles :

- `random` : les N premiers IDs classés par leur empreinte pseudo-aléatoire,
  sans quota. La graine explicite permet de répéter le tirage.
- `stratified` : sélection déterministe des strates rares d’abord, puis
  complément pseudo-aléatoire jusqu’à N. Ce jeu est volontairement enrichi et
  **n’est pas statistiquement représentatif**.

La taille acceptée est 1 à 20 000, afin de permettre les petites vérifications ;
les expériences visées utilisent 10 000 à 20 000 unités. RAG-005 reste plafonné
à 10 000 par extraction : fournir plusieurs extractions pour un cadre plus grand.
Une taille ou un quota impossible fait échouer la CLI sans fichier de sortie,
sauf choix explicite `--allow-shortfall` pour un diagnostic.

Les quotas par défaut sont de 100 unités pour chacun des questionnaires 4, 5,
7 et 10, et de 100 pour chaque strate supplémentaire, ramenés à N/8 pour les
petits essais. Les strates peuvent se chevaucher : leurs comptes ne s’additionnent
pas à la taille du jeu. `--quotas` accepte un objet JSON strate → minimum.

| Strate | Définition v1 |
|---|---|
| `form:4`, `form:5`, `form:7`, `form:10` | Questionnaire détaillé |
| `short` | Au plus 20 caractères Unicode Python |
| `long` | Plus de 2 000 caractères |
| `other` | Unité `other_text` |
| `duplicate` | Texte exactement identique dans des contributions différentes du cadre |
| `multiple_units` | Contribution ayant au moins deux réponses ouvertes dans le cadre |
| `context_candidate` | Réponse courte, candidate à une vérification humaine du besoin de contexte |

Les strates doublons et réponses multiples sélectionnent aussi une occurrence
apparentée lorsque l’espace le permet. Les occurrences ne sont ni supprimées ni
fusionnées. Le besoin de contexte ne peut pas être prouvé par une longueur : la
strate correspond à des candidats, **pas à des annotations sémantiques établies**.
Les réponses longues/courtes gardent le texte original normalisé de RAG-004.

## Reproductibilité et séparation

Le manifeste contient version de sélection et de contrat, version de corpus
fournie explicitement, extractions sources avec leurs filtres/versions/identités,
méthode, graines de sélection et de partition, quotas, seuils, date UTC, liste
sélectionnée et SHA256 de cette liste ainsi que du cadre. La date change lors
d’une nouvelle génération ; les IDs, partitions et empreintes restent identiques
à paramètres et données identiques. La version de corpus est une déclaration de
l’opérateur, pas une preuve automatique de l’immuabilité du corpus.

Les partitions documentaires utilisent les composantes connexes du **cadre
entier**, y compris les documents non sélectionnés qui servent de ponts :

1. Lien par contribution, dans son corpus : protection contre les fuites de contexte.
2. Lien par empreinte SHA256 du texte exact : protection contre les fuites de contenu.

Une composante entière est affectée au développement ou à l’évaluation par une
graine de partition indépendante (1729 par défaut), avec probabilité cible
80/20. Le regroupement peut produire une forte asymétrie, notamment avec les
réponses courtes répétées ; la taille du plus grand groupe et les tailles réelles
sont publiées, sans casser les groupes pour équilibrer artificiellement.
Il n’y a pas de détection de paraphrases ou de doublons approximatifs.

Utiliser **le même cadre et la même graine de partition** pour les sélections
aléatoire et stratifiée : elles peuvent se recouvrir, mais un document partagé
conserve sa partition. Des cadres différents peuvent changer les composantes :
ne pas mélanger leurs partitions. Geler le cadre, les requêtes et les jugements
avant de comparer des moteurs. Les futurs moteurs devront indexer/interroger
la partition correspondante ; la CLI refuse résultats et annotations hors partition.

Les requêtes possèdent leur propre partition explicite et des familles de
formulations apparentées. Le fichier initial contient 40 requêtes, dix par
domaine (fiscalité, démocratie, services publics, écologie), réparties en vingt
requêtes de développement et vingt d’évaluation. Les catégories sont recherche
thématique, proposition concrète, expression précise, vocabulaire différent,
besoin de contexte et ambiguïté. Les deux partitions couvrent les six catégories.
Une revue humaine des familles reste nécessaire pour éviter des proximités
sémantiques non capturées par les identifiants de famille.

## Jugements humains et candidats

Les annotations sont une liste JSON lisible et exportable par `write_json`,
réimportable par `load_judgments`. Chaque ligne contient :

```json
{
  "query_id": "identifiant-de-requete",
  "document_id": "identifiant-documentaire",
  "grade": 2,
  "justification": "Exemple de structure uniquement",
  "judged_at": "2026-10-17T12:00:00+02:00",
  "version": "v1",
  "evaluator": "evaluateur-local"
}
```

Cet exemple ne constitue **aucun jugement réel**. Les notes sont 0 non pertinent,
1 partiellement pertinent, 2 pertinent, 3 très pertinent. Un candidat non jugé
porte `grade: null`, ne passe pas la validation d’un jugement et doit rester
séparé du fichier de jugements validés. L’absence d’une paire requête/document
signifie non jugé, jamais zéro. Date avec fuseau et version sont obligatoires.

Plusieurs évaluateurs sont identifiables, mais pour calculer des scores une seule
note adjudicataire par paire et une seule version sont acceptées. La résolution
des désaccords demeure humaine ; aucun calcul implicite de moyenne n’est réalisé.
Les sorties ne remplacent pas un fichier existant : importer, choisir et écrire
une nouvelle version explicite plutôt qu’écraser des annotations.

`candidates` propose un ordre pseudo-aléatoire reproductible d’IDs appartenant à
la partition de chaque requête, avec les champs d’annotation laissés vides.
Ce n’est pas une sélection par pertinence et il peut y avoir beaucoup de notes
zéro. L’évaluateur consulte le document et son contexte via `RagStore` et conserve
les fichiers enrichis localement. Les futurs résultats de moteurs pourront
compléter les candidats ; aucun moteur de recherche n’est introduit ici.

## Métriques et jugements incomplets

`evaluate(results, judgments, k=10, complete=False)` reçoit une liste ordonnée
sans doublon et un dictionnaire ID → note. `aggregate` utilise les requêtes pour
les regroupements globaux, par catégorie et par partition.

- Pertinence binaire : note **au moins 2**. La note 1 n’est pas binaire positive.
- Precision@k : nombre de pertinents dans les k premiers résultats divisé par k.
  Une liste plus courte ne réduit pas le dénominateur. Si un résultat retourné
  dans le top-k n’est pas jugé, la mesure vaut `null`.
- Recall@k : nombre de pertinents retournés dans le top-k divisé par le nombre
  total de pertinents du périmètre évalué. `null` si ce nombre est nul ou si les
  jugements ne sont pas exhaustifs.
- Reciprocal rank : inverse du rang du premier pertinent dans la liste fournie
  entière, indépendamment de k. Vaut zéro si aucun résultat n’est pertinent et
  que tous les résultats sont jugés. Un non-jugé précédant le premier pertinent
  rend la mesure indéfinie. MRR est sa moyenne sur les requêtes définies.
- nDCG@k : gains `2^note - 1`, décote `log2(rang+1)`, normalisation par le classement
  idéal de tous les jugements. `null` si le gain idéal est nul, si un top-k est
  non jugé ou si les jugements ne sont pas exhaustifs.

Sans aucun jugement, toutes les métriques valent `null`. Aucun score n’est
calculé sur les vrais documents lors de cette tâche, puisqu’ils n’ont pas de
jugements humains. La CLI n’accepte `--complete` que si **chaque document de la
partition est jugé pour chaque requête**. L’exhaustivité concerne l’échantillon,
pas les millions d’unités du corpus. Ce choix conservateur évite de présenter
un rappel sur quelques documents jugés comme un rappel réel.

Les agrégats publient moyenne, nombre de requêtes définies et nombre total ; ils
ne remplacent pas les indéfinis par zéro. Pour comparer des moteurs, utiliser les
mêmes requêtes, documents, jugements, k et ensembles de requêtes définies. Une
moyenne calculée sur des sous-ensembles différents ne permet pas une comparaison
fiable. Les résultats incluent empreintes du manifeste, des requêtes, des
jugements et des classements. Le score global mêle développement et évaluation :
la mesure finale doit utiliser l’agrégat `split:evaluation`, sans régler ensuite
les paramètres sur cette partition.

Ces mesures concernent la pertinence documentaire. Elles ne mesurent ni la
fréquence des opinions ni leur représentativité dans la population française.

## Commandes

Depuis `rag/` :

```bash
uv sync --locked
mkdir -p evaluation/local
# Répéter --extraction pour constituer le cadre de 10 000 à 100 000 unités.
uv run --locked cahier-rag-eval sample --extraction UUID_1 --extraction UUID_2 --corpus-version gdn-2019-audit-2026-10-16 --size 10000 --seed 20261017 --method random --output evaluation/local/random.json
uv run --locked cahier-rag-eval sample --extraction UUID_1 --extraction UUID_2 --corpus-version gdn-2019-audit-2026-10-16 --size 10000 --seed 20261017 --method stratified --output evaluation/local/stratified.json
uv run --locked cahier-rag-eval describe --sample evaluation/local/random.json
uv run --locked cahier-rag-eval candidates --sample evaluation/local/random.json --queries evaluation/queries.json --per-query 20 --output evaluation/local/candidates.json
# Après annotation humaine et fourniture d’un classement par un moteur futur :
uv run --locked cahier-rag-eval score --sample evaluation/local/random.json --queries evaluation/queries.json --judgments evaluation/local/judgments.json --results evaluation/local/results.json --k 10 --output evaluation/local/scores.json
```

`sample` accepte `--env-file` comme les commandes existantes et reste soumis aux
contrôles réels des bases RAG-005. Les autres commandes sont hors connexion.
Le format des résultats est un objet JSON `query_id -> [document_id, ...]` ;
les rangs correspondent à l’ordre fourni. Aucune récupération ou recherche
implicite n’est exécutée. Les fichiers sont bornés à 64 Mio ; les références
inconnues, doublons et clés JSON répétées sont refusés.

Les manifestes et jugements locaux, même sans corps documentaire, contiennent
des références au corpus. Les empreintes de textes courts ne les anonymisent
pas. Les textes consultés peuvent contenir des données personnelles : pas
d’export automatique vers Git ni de service externe.

```bash
uv lock --check
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m pytest tests/unit
RAG_TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
RAG_STORAGE_TEST_DATABASE_URL=postgresql:///cahier_rag_test \
uv run --locked python -m pytest
```
