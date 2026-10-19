# RAG-018 — BM25 et comparaison lexicale

Expérience lancée le 18 octobre 2026, rapport finalisé le 19 octobre.
**Deux index BM25 de 20 000 unités sont construits et vérifiés.** Les 754 nouveaux
couples ont été annotés par chacun des deux juges, avec **1 508 sorties valides,
aucun échec**. Les trois sorties invalides historiques du 14B restent inchangées.

BM25-A améliore Precision@10 face au lexical pondéré selon les deux juges, mais
ne domine pas toutes les métriques. Les conclusions sur la nDCG divergent entre
juges. Aucun remplacement du lexical public ni réglage des paramètres n'est
effectué ; le vectoriel reste une référence forte sur cette expérience.

## Implémentation et paramètres

La baseline utilise un index inversé **SQLite sur disque**, piloté par Python,
avec la formule BM25 explicite et l'IDF positive lissée :

```text
IDF = ln(1 + (N - df + 0,5) / (df + 0,5))
score = Σ IDF × tf × (k1+1) / (tf + k1 × (1-b + b × dl/avgdl))
k1 = 1,2 ; b = 0,75
```

Les fréquences exactes, longueurs et fréquences documentaires sont conservées,
sans utiliser `ts_rank_cd`. La normalisation française réutilise `ts_debug` et
`pg_catalog.french` : stopwords et racinisation PostgreSQL, sans conversion des
documents en `tsvector` et ses plafonds de positions/fréquences. Les comptes
préservent toutes les occurrences, notamment dans les réponses très longues.
La préparation des requêtes reprend la liste générique figée de RAG-009.

BM25-A indexe la réponse seule ; BM25-B ajoute la question une fois, sans boost.
L'IDF réduit le poids des termes de question partagés par beaucoup de documents.
Cela n'élimine pas tout biais contextuel. Textes, questions et provenance restent
séparés dans les unités sources et leur restitution.

Les statistiques N/df/avgdl sont propres à chaque partition. Les filtres par
questionnaire et type portent sur les candidats, sans recalculer ces statistiques.
Les paramètres et empreintes des modules de classement/tokenisation sont figés
dans `evaluation/local/rag018/frozen-bm25.json` ; ils sont restés inchangés
pendant et après annotation. Aucun réglage sur les jugements.

La bibliothèque Python `rank_bm25` a été examinée, mais son stockage en mémoire
et ses tableaux de scores couvrant le corpus ne conviennent pas directement
à l'évolution souhaitée. Une implémentation à postings PostgreSQL serait
possible, avec migrations et mesures supplémentaires. Une extension spécialisée
comme `pg_search` pourrait devenir pertinente à grande échelle, sans justifier
ici une installation supplémentaire. La solution locale retenue ne requiert
aucune dépendance nouvelle, GPU ou service pour la recherche BM25.
La comparaison des solutions, les sources officielles et les limites sont dans
[recherche-bm25.md](recherche-bm25.md).

## Indexation et intégrité

Le périmètre correspond exactement au manifeste RAG-007 : **20 000 unités**,
dont 17 612 de développement et 2 388 réservées. Seules les 20 requêtes de
développement ont été exécutées. Aucun document du cadre des 42 318 unités
n'a été ajouté aux index.

| Mesure | BM25-A | BM25-B |
|---|---:|---:|
| Documents | 20 000 | 20 000 |
| Postings distincts document-terme | 302 780 | 496 043 |
| Lexèmes, développement | 301 988 | 495 038 |
| Lexèmes, partition réservée | 55 571 | 81 364 |
| Taille du fichier d'index | 83,65 Mio | 116,65 Mio |
| Reconstruction complète indépendante | 19,23 s | 23,14 s |
| Pic RSS du processus de reconstruction | 123,7 Mio | 160,7 Mio |

Les pics RSS sont cumulatifs depuis le début du même processus, qui construit
A puis B, et comprennent Python, les métadonnées et les caches. Ils ne mesurent
pas la mémoire du serveur PostgreSQL. Les tailles comprennent les copies JSON
auditables et les suites de lexèmes, pas uniquement les postings.

La première construction a été interrompue volontairement après 50 documents,
puis reprise. Une deuxième construction indépendante produit les **mêmes
empreintes logiques** :

- A : `6323fed918fc25e0027f8f96235fbdf731bdbedc74e2874f743b35bc609cd13f`.
- B : `71aa0ccb1c86a23ccc2597f0e109194e63f59b3aa0379a202859a3489ec5e485`.

Les lots sont atomiques ; l'index incomplet n'est pas recherchable. Les membres,
contenus, partitions, longueurs, comptes de termes et statistiques sont vérifiés.
Les recherches retournent les `SearchResult` existants avec provenance et
BIGINT sans conversion flottante. Aucun schéma PostgreSQL n'a été créé ou modifié.

## Mesures techniques

Chaque moteur a exécuté les 20 requêtes à profondeur 100. Les classements
lexicaux/vectoriels rejoués sont identiques aux références disponibles de
RAG-017, sans changer leurs paramètres ni index. Le coût vectoriel comprend
l'encodage des requêtes par le modèle déjà chargé ; les chargements initiaux
et vérifications complètes des index ne font pas partie des latences par requête.

| Moteur | Couverture | Médiane top 100 | P95 top 100 | Contributions distinctes dans les top 50 | Réponses <60 caractères /1 000 | « Autre » /1 000 |
|---|---:|---:|---:|---:|---:|---:|
| Lexical pondéré | 20/20 | 179,89 ms | 250,89 ms | 579 | 24 | 16 |
| BM25-A | 20/20 | 194,42 ms | 583,80 ms | 807 | 283 | 34 |
| BM25-B | 20/20 | 357,82 ms | 817,27 ms | 822 | 199 | 32 |
| Vectoriel BGE-M3 | 20/20 | 101,16 ms | 107,12 ms | 814 | 272 | 44 |

Les statistiques documentaires portent sur les top 50, les latences sur le
retour de 100 résultats : il ne s'agit pas de mesures séparées de latence à 50.
BM25 retrouve davantage de réponses courtes que le lexical pondéré, mais cela
ne constitue pas une preuve de pertinence. Ces mesures sur une seule machine,
en exécution séquentielle, ne sont pas un benchmark de charge.

Recouvrement moyen, en documents communs par requête :

| Paire de moteurs | Top 50 | Top 100 |
|---|---:|---:|
| BM25-A / BM25-B | 29,35 | 59,90 |
| BM25-A / lexical | 15,95 | 38,95 |
| BM25-B / lexical | 16,90 | 38,80 |
| BM25-A / vectoriel | 11,15 | 26,25 |
| BM25-B / vectoriel | 13,85 | 31,20 |
| Lexical / vectoriel | 9,05 | 21,40 |

BM25 apporte donc des candidats différents ; leur simple nouveauté ne permet
pas de conclure à un meilleur futur hybride.

## Réutilisation des jugements et complément

L'union des top 50 de A et B contient **1 413 couples uniques**. Parmi eux,
**659 couples ont déjà une note valide de chacun des juges RAG-017** : ils sont
réutilisés sans inférence. Les **754 nouveaux couples** sont dédupliqués et
annotés dans une campagne indépendante.

Le référentiel commun d'évaluation contient l'union des 2 500 anciens couples
et des 754 nouveaux : **3 254 couples par juge**, dont 3 254 valides pour le
8B et 3 251 pour le 14B. Aucune note consensuelle ni modification des notes
humaines. Les caches historiques sont ouverts en lecture seule.

Le complément garde les mêmes modèles, révisions, paramètres et prompt
`relevance-fr-v2`, avec des empreintes de recette identiques à RAG-017.
Les précontrôles des deux tokenizers ont réussi : maximum **746 tokens**.
Chaque modèle reçoit uniquement requête, réponse, question et titre ; aucun
moteur, rang, autre jugement ou commentaire humain.

| Complément | 8B | 14B |
|---|---:|---:|
| Nouveaux couples et sorties valides | 754 | 754 |
| Sorties invalides | 0 | 0 |
| Temps, chargement inclus | 515,74 s | 908,52 s |
| Débit | 1,462 couple/s | 0,830 couple/s |
| Pic VRAM allouée PyTorch | 7,05 Gio | 9,86 Gio |

Les modèles ont tourné successivement, entièrement hors ligne. Les trois
sorties historiques invalides du 14B ne concernent pas les top 50 BM25, mais
affectent la référence poolée et certains résultats du lexical. Elles restent
non jugées, sans réparation ou nouvelle annotation.

Les top 50 BM25-A, BM25-B et vectoriels sont tous jugés pour les deux modèles
(1 000/1 000 chacun). Le lexical est couvert à 1 000/1 000 pour le 8B et
997/1 000 pour le 14B. Au top 10 lexical, cette dernière couverture est 198/200.

## Pertinence : même périmètre de comparaison

La comparaison principale utilise les **17 requêtes intégralement jugées par
les deux modèles**, identiques pour les quatre moteurs. Sont exclues
`fiscalite-04`, `fiscalite-05` et `services_publics-01`. Les couvertures de toutes
les requêtes et les métriques calculables restent exportées, sans zéro implicite.

Le seuil binaire est 2–3 ; MRR est limité au classement top 50. La nDCG utilise
le gain `2**grade-1` et un idéal fondé sur **le pool enrichi commun** de chaque
requête, pour chaque juge. Cet idéal n'est pas exhaustif sur le corpus.
L'enrichissement change l'IDCG : les nDCG ci-dessous ne se comparent pas
directement aux anciennes valeurs publiées dans RAG-017. Aucun rappel exhaustif.

| Juge | Moteur | P@5 | P@10 | P@20 | P@50 | nDCG poolée@10 | nDCG poolée@50 | MRR@50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 8B | Lexical | 0,824 | 0,829 | 0,844 | 0,796 | 0,573 | 0,672 | 0,971 |
| 8B | BM25-A | 0,918 | 0,882 | 0,838 | 0,756 | 0,526 | 0,605 | 0,971 |
| 8B | BM25-B | 0,894 | 0,859 | 0,847 | 0,821 | 0,522 | 0,640 | 0,971 |
| 8B | Vectoriel | 0,965 | 0,935 | 0,929 | 0,888 | 0,621 | 0,719 | 1,000 |
| 14B | Lexical | 0,682 | 0,735 | 0,729 | 0,645 | 0,554 | 0,556 | 0,863 |
| 14B | BM25-A | 0,812 | 0,818 | 0,759 | 0,615 | 0,602 | 0,520 | 0,882 |
| 14B | BM25-B | 0,824 | 0,776 | 0,759 | 0,704 | 0,566 | 0,567 | 0,882 |
| 14B | Vectoriel | 0,894 | 0,865 | 0,847 | 0,779 | 0,705 | 0,673 | 1,000 |

Les nDCG aux quatre seuils, les différences par requête et les résultats par
thématique sont dans le [rapport local complet](evaluation/local/rag018/comparison/report.md)
et son `comparison.json`. Exemples d'hétérogénéité, sur les mêmes requêtes :

- En démocratie, P@10 BM25-A vaut 0,860 contre 0,800 pour le lexical selon le
  8B ; 0,740 contre 0,700 selon le 14B.
- En écologie, BM25-A vaut 0,840 contre 0,780 selon le 8B ; 0,800 contre 0,720
  selon le 14B. Le contexte B n'améliore pas uniformément cette différence.
- Pour `democratie-04`, BM25-B perd 0,400 point de P@10 par rapport au lexical
  selon le 8B. Pour `ecologie-02`, il gagne 0,200. Les moyennes ne suffisent
  donc pas à définir une politique de contextualisation générale.

Les deux juges constatent une amélioration moyenne de P@10 de BM25-A face au
lexical : environ +0,053 et +0,082. En revanche, le 8B lui donne une nDCG@10
plus basse et le 14B plus haute. BM25-B est moins précis à 10 que A, mais
plus précis à 50, selon les deux juges. Ces arbitrages restent exploratoires,
avec des juges de même famille et aucune nouvelle validation humaine.

## Artefacts et commandes

```text
evaluation/local/rag018/
  frozen-bm25.json               Paramètres et empreintes du classement
  protected.json                Empreintes des fichiers historiques
  bm25-{A,B}.sqlite3             Index locaux et documents restituables
  bm25-{A,B}-build.json          Première construction et reprise
  repro-index/                  Reconstruction indépendante, RSS et empreintes
  baselines100/                 Rejeu des moteurs gelés, nouveaux fichiers
  development/                  Runs top 100 et statistiques des quatre moteurs
  complement/pool/              Plan, origines, précontrôles et résultats LLM
  complement/cache.sqlite3      Cache indépendant et tentatives atomiques
  comparison/                   Rapport et exports séparés par juge
```

Depuis `rag/` :

```bash
uv run --locked --no-sync python -m cahier_rag.search.bm25.cli verify
uv run --locked --no-sync python -m cahier_rag.search.bm25.cli search \
  'transports ruraux' --variant A --limit 10
uv run --locked --no-sync python -m cahier_rag.search.bm25.cli report \
  --experiment evaluation/local/rag018/development \
  --plan evaluation/local/rag018/complement/pool \
  --output evaluation/local/NOUVEAU_RAPPORT
```

La [procédure complète](recherche-bm25.md) décrit installation, reprise,
filtres, préparation et annotation. Les dossiers d'export doivent être nouveaux.
Les fichiers contenant des textes et jugements réels restent ignorés par Git.

## Validations et limites

- **443 tests réussis**, trois tests ignorés car PyTorch est absent de
  l'environnement léger. Les intégrations PostgreSQL dédiées ont été exécutées.
- Ruff et `uv lock --check` conformes ; aucune dépendance ou verrou modifié.
- Reconstruction logique identique, reprise contrôlée, ordre déterministe,
  statistiques et provenance vérifiés ; JSON BIGINT et doublons préservés.
- Contrats de jugements, cache indépendant, réutilisation en lecture seule et
  métriques avec non-jugés couverts par les tests.
- Les **1 020 fichiers historiques protégés**, dont annotations humaines,
  requêtes, moteurs et artefacts gelés, conservent leurs empreintes.

Les latences de cette implémentation SQL locale ne valident pas une utilisation
publique à plusieurs millions de réponses. Les requêtes à nombreux termes
fréquents doivent agréger et trier de nombreux postings ; aucun algorithme
d'élagage WAND/block-max n'est implémenté. La duplication des JSON et suites de
lexèmes favorise l'audit, avec un coût disque explicite. Le serveur de
tokenisation est configuré et sondé, sans empreinte exhaustive de ses fichiers
de dictionnaires.

Le pooling dépend des moteurs et les 17 requêtes complètes excluent trois cas
avec échecs historiques. Les jugements automatiques ne remplacent pas une
référence humaine indépendante. Aucun corpus source, moteur historique,
backend, frontend, Wallace ou annotation humaine modifié. Aucun commit ou push.

## Recommandation pour RAG-019

Conserver le lexical pondéré comme référence et comparer **une fusion RRF
BM25-A + BGE-M3** à l'hybride historique, sur le développement, avec paramètres
fixés à l'avance. A est le premier candidat raisonnable : meilleure précision
dans les premiers résultats selon les deux juges et coût inférieur à B.
Garder BM25-B comme variante secondaire, son gain à 50 justifiant une ablation
documentée plutôt qu'un remplacement immédiat.

Mesurer la complémentarité effective dans la fusion : BM25 seul ne permet pas
de prédire l'amélioration hybride. Réutiliser les deux références séparées,
annoter les nouveaux couples nécessaires et contrôler humainement un échantillon
des désaccords et accords. Préserver les 20 requêtes réservées. Une optimisation
technique du stockage ou un essai de moteur spécialisé devra rester distinct
d'un réglage de pertinence sur ces labels.
