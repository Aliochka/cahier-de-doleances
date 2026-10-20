# RAG-026 — Recherche hybride sur le corpus complet local

## Résultat

**Le corpus complet est extrait, vectorisé, vérifié et interrogeable.**
`evaluation/local/rag026/phase.json` et `completion.json` indiquent `complete`.
La recherche H1 associe le lexical pondéré à BGE-M3 par RRF `k=60`, dans un
espace dédié. L'interface conserve RAG-007 par défaut et propose explicitement
RAG-026. Aucun changement du générateur, du reranker, du site public ou de Wallace.

Deux limites dominent : **le lexical peut prendre une vingtaine de secondes**,
et **HNSW perd des voisins par rapport à l'exact**. Une recherche fonctionnelle
ne signifie donc ni faible latence pour toute requête, ni pertinence validée.

## Inventaire réel et manifeste

Audit PostgreSQL 17.11 en lecture seule, mêmes règles que `GdnReader`/`TextUnit`
v1 ; contrôle préalable des JSON et des relations question–questionnaire–contribution.

| Mesure | Nombre |
|---|---:|
| Contributions sources | 1 589 285 |
| Lignes de réponses sources | 15 792 750 |
| Réponses ouvertes exploitables | 5 004 470 |
| Unités « Autre » exploitables | 167 886 |
| **Unités définitives** | **5 172 356** |
| **Segments vectoriels définitifs** | **5 187 190** |
| Unités < 60 caractères | 1 688 267 |
| Unités > 2 000 caractères | 30 843 |
| Unités > 4 000 caractères | 8 533 |
| Contributions avec unité exploitable | 551 000 |
| Contributions avec plusieurs unités | 490 678 |

31 éléments « Autre » blancs sont exclus conformément à `str.strip()` ; aucune
réponse courte n'est retirée. Les textes normalisés restent exacts, séparés du
contexte, des titres et de la provenance. Aucun `raw_json` ou profil d'auteur extrait.

| Questionnaire | Réponses ouvertes | « Autre » |
|---|---:|---:|
| 4 — Services publics | 852 920 | 0 |
| 5 — Démocratie | 2 132 401 | 0 |
| 7 — Fiscalité | 945 925 | 91 686 |
| 10 — Écologie | 1 073 224 | 76 200 |

Les sept questionnaires ont été examinés ; les trois questionnaires rapides ne
fournissent pas d'unité textuelle exploitable selon le contrat. Les comptages
retrouvent les volumes ouverts/Autre de l'audit initial, sans confondre les
15,79 millions de lignes avec autant de documents.

716 347 occurrences répétées sont estimées par MD5, avec 98 377 groupes touchant
plusieurs contributions ; cette statistique comporte une limite théorique de
collision, sans comparaison exhaustive des corps. **Aucune occurrence supprimée.**
Les noms, versions et sources des questionnaires, ainsi que les disponibilités
des métadonnées, sont conservés dans `metadata.json`. Les identifiants restent
BIGINT en base et entiers Python ; les exports documentaires utilisent les chaînes
prévues par `TextUnit`.

Manifeste préalable : `audit.json`, sélection
`39fcc82862b72cda1844dcdbfccc8fb9d24c012a92b654808fe9539a1d627817`.
Le manifeste opérationnel et le curseur sont dans `rag_full.spaces` ; la chaîne
finale des documents est
`bf1bac7a6c9af63c1cb5d465cd4611310f77e7923b75ce5d9fc105afedbcf4d3`.
`integrity.json` atteste les nombres, les empreintes et l'état vérifié.

## Architecture et séparation

Nouveau package `cahier_rag.fullcorpus` : audit, adaptateur de lecture, persistance,
pipeline, recherche, expériences, orchestration CLI et adaptateur personnel.

Migrations RAG `rag_0004` à `rag_0006` : schéma `rag_full`, tables `spaces`,
`documents`, `segments`, partitions `pilot100k`/`full`, clés B-tree, GIN français
et HNSW cosinus. Les tables historiques `rag.*` ne sont pas étendues ou réindexées.
Les identités physiques des bases sont contrôlées par `DatabaseGuard` avant écriture.
La base source n'est jamais une destination de migration.

Les limites historiques de 20 000 unités et les plafonds des extractions RAG-005
restent en place. Le nouveau parcours complet exige un inventaire et un précontrôle
compatibles, puis un pilote vérifié ; il ne desserre pas ces protections anciennes.
Les transactions sources se ferment avant les écritures RAG. Documents/curseur,
puis segments/checkpoint vectoriel, sont persistés atomiquement. Une reprise saute
les unités vectorielles déjà terminées, avec verrous de progression.

Le pilote porte sur 100 000 unités/100 258 segments, répartis par hachage de
contribution avec graine 26, puis plafonnés dans l'ordre des réponses. Il ne
constitue pas un échantillon statistiquement représentatif. Les partitions
RAG-007 restent des métadonnées pour ses documents ; les nouvelles unités n'ont
pas reçu artificiellement une partition expérimentale.

## Recette vectorielle et recherche

BGE-M3 dense, révision `5617a9f61b028005a4858fdac845db406aefb181`, snapshot
`fe2f29e9b4699cfeb8ee4d9524c1e99df203cb4f144dbe4b463e28e65e3d1f6d`.
Inférence BF16 sur RTX 5090, sortie normalisée L2, stockage float32/1 024 dimensions.
Représentation B, segmentation RAG-013 à 1 024 tokens incluant question et libellés,
chevauchement de 128 tokens. Positions et références de chaque fragment conservées.
Le chemin rapide des réponses courtes produit les mêmes représentations ; les
lots sont triés par longueur pour réduire le padding et remis en correspondance
par identifiant. Pas de conservation globale des embeddings en RAM.

Le lexical conserve les poids et la préparation française de RAG-009, réponse
seule. Population et fréquences sont calculées sur le nouveau périmètre ; ce
changement de corpus modifie naturellement les classements. RRF ne compare pas
les scores bruts, profondeur 50, départage documentaire stable.

L'exact calcule les distances de tous les segments, sélectionne les meilleurs
segments puis agrège par maximum cosinus au niveau de l'unité. La fenêtre augmente
si elle ne contient pas encore assez d'unités distinctes. Cela évite l'agrégation
initiale de cinq millions d'unités sans changer le classement exact ; les six
classements exacts du pilote ont été reproduits à l'identique après cette adaptation.

HNSW utilise `vector_cosine_ops`, `m=16`, `ef_construction=64`, valeurs initiales
recommandées par la [documentation pgvector](https://github.com/pgvector/pgvector#hnsw).
La version réelle 0.8.7 accepte les vecteurs 1 024 dimensions ; aucune conversion
halfvec n'est nécessaire. `ef_search` a été mesuré à 40/100/200/400, puis à des
valeurs supérieures lors du pilote. La configuration H1 ANN actuelle utilise 400,
avec balayage itératif strict et partitions physiques séparées. L'approximation
est explicite ; l'exact reste accessible. Les filtres sont liés en SQL.

## Ressources et durées

Précontrôles `preflight-initial.json` et `preflight-measured.json` : environ
1,42 To libres sur le NVMe du projet et du cluster PostgreSQL, plus de 120 Go de
RAM disponibles, 63 Gio de mémoire partagée. Enveloppe prudente : 303 Go libres,
comprenant stockage, temporaire et réserve. Projection float32 brute avec marge
sur les segments : 21,61 Go ; alternative float16 brute : 10,80 Go, non utilisée.
La projection GPU prudente depuis le pilote était de 4 h 26.

| Phase réellement mesurée | Durée |
|---|---:|
| Extraction complète | 842,66 s — 14 min |
| Génération/import des embeddings | 9 971,93 s — 2 h 46 |
| Vérification finale réussie | 808,80 s — 13 min 29 |
| Construction HNSW complète | 1 086,96 s — 18 min 7 |

Débit complet embedding + préparation + écriture : **519 unités/s**, meilleur
que le pilote avec entretien HNSW incrémental (~325/s). Pic alloué GPU : **1,98 Go** ;
pic RSS du processus d'encodage : **4,48 Go**. Il ne s'agit pas du pic RAM global
du serveur PostgreSQL. La construction complète utilise un budget de maintenance
local de 40 Gio et deux workers, avec contrôle de RAM préalable ; aucune
configuration d'instance modifiée. Sa transaction est bornée à deux heures.
Une interruption oblige à reconstruire HNSW ; documents et vecteurs restent repris.

| Relation | Octets, index inclus sauf indication |
|---|---:|
| `documents_full` | 11 145 658 368 |
| `segments_full` | 70 545 850 368 |
| HNSW seul, **déjà inclus dans la ligne précédente** | 38 692 986 880 |
| **Ensemble documents + segments** | **81 691 508 736 — 81,69 Go / 76,08 Gio** |

Les durées d'inférence GPU et d'import vectoriel ne sont pas isolées dans la
mesure complète : le débit annoncé est celui du pipeline. Les temps d'encodage
à vide, les attentes entre reprises et les premières tentatives échouées ne sont
pas à additionner naïvement aux compteurs de reprise de `completion.json` : ceux-ci
contiennent de petits temps de passage pour les étapes déjà terminées. Les vraies
durées initiales restent dans les journaux, manifestes et diagnostics.

## Recherches exploratoires et approximation

Six questions libres communes, thématiques et expressions, ont été encodées une
fois puis réutilisées pour les mesures. Aucune requête réservée ni jugement utilisé.
Mesures séquentielles, cache progressivement chaud, sans concurrence simulée.
P95 empirique de six observations : ici le maximum, pas une estimation robuste.

| Composant | Médiane | P95 observée |
|---|---:|---:|
| Vectoriel exact | 5,51 s | 5,64 s |
| Lexical pondéré | 4,27 s | 20,21 s |
| ANN, `ef_search=400` | 14 ms | 35 ms |

La fusion prend environ 0,44 à 0,61 ms. La chaîne H1 ANN varie entre **0,88 et
20,18 s**, hors encodage des requêtes ; le lexical domine. Les temps ANN isolés
et ceux dans H1 diffèrent avec le cache et l'ordre des mesures. Aucun de ces
nombres ne mesure la latence totale avec reranking et génération.

Le recouvrement documentaire top 50 ANN/exact à `ef_search=400` est respectivement
**86 %, 72 %, 98 %, 88 %, 84 %, 96 %** sur ces six questions. Les réglages plus
faibles perdent davantage de voisins. C'est une mesure technique de voisins,
pas un rappel exhaustif des contributions pertinentes ; les égalités et répétitions
peuvent également influencer les identités retenues. **ANN n'est pas validé comme
équivalent à l'exact et mérite un travail supplémentaire.**

Les top 50 hybrides contiennent 49–50 contributions distinctes, 1–25 réponses
courtes et 1–20 répétitions textuelles selon la question. Aucun « Autre » n'apparaît
dans ces six top 50 ; cela n'est pas un filtre d'exclusion et ne décrit pas leur
rappel général. Recouvrement lexical/vectoriel : 0–2 candidats sur ces exemples.

Comparaison aux mêmes questions sur RAG-007, sans toucher aux résultats historiques :
49–50 des 50 réponses hybrides du corpus complet sont extérieures aux 20 000 unités.
Le recouvrement top 50 avec l'ancien corpus va de zéro à une unité. Le changement
de périmètre est donc majeur. Aucune comparaison de nDCG sur des pools différents
ni conclusion automatique sur une amélioration de pertinence.

Détails : `full-search.json`, `comparison-rag007-full.json`, `ann-plans.json`.
L'analyse est descriptive, sur six requêtes ; elle ne remplace pas une campagne
complète des vingt requêtes de développement ou une inspection sémantique annotée.

## Incidents, correction et intégrité

La première vérification a refusé un vecteur. Le réencodage de son lot d'origine
(256 unités) a reproduit exactement le SHA-256 attendu : cinq coordonnées avaient
subi un double arrondi décimal float64 → texte → float32 différent de l'arrondi
float32 utilisé pour l'empreinte. Écarts d'un ULP, sans changement documentaire.

Le vecteur a été restauré aux octets attendus, **sans remplacer son empreinte**,
après preuve cryptographique et contrôle transactionnel. Les écritures arrondissent
désormais en float32 avant le transport décimal, sous forme de chaîne préservant
également les zéros signés. La vérification utilise `vector_send` binaire.
Les preuves, différences et tentatives initiales restent dans `diagnostics/` et
`full-run.log`. La vérification intégrale suivante a réussi.

Le premier benchmark exact dépassait 30 s ; l'adaptation SQL décrite plus haut
ramène la mesure à ~5,5 s et conserve les classements exacts vérifiés du pilote.
Ces deux incidents ne sont pas effacés des journaux.

**2 294 fichiers historiques vérifiés inchangés**. Les comptes, empreintes
concaténées des documents et vecteurs historiques PostgreSQL correspondent au
relevé préalable : 42 380 unités stockées historiquement, 20 000 membres lexicaux,
20 067 vecteurs. Ce chiffre de 42 380 constaté dans la base, supérieur au cadre
RAG-007 de 42 318, n'est pas utilisé comme périmètre du nouvel index. Les sélections
RAG-007 et les sessions/jugements humains restent inchangés.

## Commandes et interface personnelle

Depuis `rag/`, connexions explicites :

```bash
export RAG_SOURCE_DATABASE_URL=postgresql:///cahier_doleances_local
export RAG_DATABASE_URL=postgresql:///cahier_rag
.venv/bin/python -m cahier_rag.fullcorpus.cli status --space full
.cache/embeddings-venv/bin/python -m cahier_rag.fullcorpus.cli search \
  --space full --query 'Comment améliorer les transports ruraux ?' --ann
.cache/judges-venv/bin/python -m cahier_rag.personal.cli serve --corpus rag026 --ann
```

L'option ANN est explicite ; sans elle la recherche vectorielle est exacte.
Sans `--corpus rag026`, l'interface garde les 20 000 unités. Les nouveaux caches
personnels sont séparés sous `evaluation/local/rag026/personal/`. Écoute loopback,
contrôles d'origine existants et modèle/reranker inchangés. L'adaptateur complet
vérifie l'état validé et ne charge en RAM que les métadonnées des candidats.
Le parcours intégral génération/interface sur RAG-026 n'a pas fait l'objet d'un
nouveau test GPU de bout en bout ; sa sélection, son affichage de périmètre et
les garde-fous sont testés. Le moteur hybride complet est effectivement exécuté.

Pour une reprise après interruption, consulter [corpus-complet.md](corpus-complet.md).
Les sources/poids/artefacts restent locaux et ignorés par Git. Aucun nouveau modèle,
paquet lourd ou service n'est ajouté. Aucun commit ni push.

## Validations et recommandations

**574 tests réussis, 3 ignorés** (PyTorch optionnel absent de l'environnement léger).
Intégrations PostgreSQL sur bases `_test`, tests de transport avec cas d'arrondi et
zéro signé, atomicité et reprise, provenance, BIGINT, filtres, segmentation et
isolation. Ruff conforme, `uv lock --check` conforme, dépendances du backend intactes.
Vérification réelle des cinq millions de documents et vecteurs, état HNSW
`indisvalid=true`/`indisready=true`, et recherches complètes exécutées.

Pour poursuivre : mesurer et réduire le coût du lexical sans modifier sa formule
à l'aveugle ; étendre les mesures ANN/exact et examiner les ex æquo avant de choisir
une recette ANN plus exigeante ; mesurer la concurrence séparément ; tester le
parcours personnel de bout en bout. Ne pas lancer de campagne LLM massive sur
ces résultats sans un protocole distinct.

Pour Wallace, **ne rien transposer tel quel** : ~82 Go supplémentaires, une chaîne
GPU locale et un lexical parfois à 20 s ne constituent pas une cible de production.
Il faudra mesurer RAM/disque/CPU réels de Wallace, encodage de requêtes CPU,
qualité ANN et architecture de service avant toute décision de déploiement.
