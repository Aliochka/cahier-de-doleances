# RAG-019 — Comparaison des stratégies hybrides

Expérience locale du 19 octobre 2026. Les cinq hybrides et quatre références
individuelles ont été comparés sur les 20 requêtes de développement, avec les
mêmes candidats et paramètres figés. **H1 et H5 sont les configurations à
conserver en priorité pour le reranking**, avec le vectoriel seul comme contrôle.
Ce sont des recommandations exploratoires fondées sur deux référentiels LLM,
pas une validation humaine ou une conclusion statistique définitive.

**Aucune nouvelle annotation n'était nécessaire.** Les 2 673 couples distincts
des top 50 appartiennent déjà aux plans RAG-017/018. Les trois anciens échecs du
14B restent non jugés ; aucun modèle juge n'a été chargé et aucun cache
historique n'a été modifié.

## Configurations et gel

Toutes utilisent RRF, `k=60`, rangs à partir de 1 et 50 candidats par moteur :

| Configuration | Lexical pondéré | BM25-A | BM25-B | BGE-M3 |
|---|---:|---:|---:|---:|
| H1 historique | 1 | — | — | 1 |
| H2 | — | 1 | — | 1 |
| H3 | — | — | 1 | 1 |
| H4 triple | 1 | 1 | — | 1 |
| H5 équilibré | 1/4 | 1/4 | — | 1/2 |

Le score est `Σ poids / (60 + rang)`, sans comparaison des scores natifs.
Le gel a précédé le calcul de pertinence. Ses paramètres, empreintes de code,
corpus, requêtes, classements et index sont enregistrés dans
`evaluation/local/rag019/configuration/frozen.json` :

`68a359ab000a61ab4071468224b736c3809d23698e7c6080049a5ddb5a9cfa68`.

Les poids n'ont pas été ajustés après observation des résultats. Les BM25
conservent `k1=1,2`, `b=0,75`, leur normalisation française et leurs index RAG-018.
BGE-M3 et le lexical pondéré restent dans leurs configurations historiques.

## Architecture et garanties

L'extension est limitée à `src/cahier_rag/search/hybrid/multi/`. Elle contient
la fusion pondérée et son orchestration (`core.py`), les adaptateurs inchangés
des moteurs (`live.py`), le gel et les artefacts (`artifacts.py`), les mesures
et le rejeu (`experiments.py`), le pooling et l'évaluation (`evaluation.py`),
le rapport (`markdown.py`) et la CLI. Aucun module historique n'est modifié.

Les scores RRF sont calculés et triés en fractions exactes ; les égalités sont
départagées par identifiant. Un même document compte une fois par source, au
premier rang rencontré. Les occurrences citoyennes distinctes restent distinctes,
même si leur texte est identique. Les contenus incompatibles pour un même ID
sont refusés. Les `SearchResult`, BIGINT et provenance sont conservés.

Questionnaire, type et partition sont appliqués aux recherches sources, puis
vérifiés avant fusion. Les segments vectoriels restent regroupés selon la règle
RAG-013. Le corpus est exclusivement celui des 20 000 unités RAG-007 ; les
requêtes et recherches de l'expérience sont limitées au développement.

## Passage réel et reproductibilité

Le passage réel exécute chaque moteur **une seule fois par requête**, puis les
cinq fusions partagent ces listes. BGE-M3 est chargé une fois, avec un seul
encodage par requête. Ce passage sert à mesurer les coûts des sources ; le
rejeu suivant réutilise les rangs et scores sauvegardés, sans modèle ni PostgreSQL.

- Les préfixes des quatre sources sont identiques à ceux de RAG-018.
- Les **top 50 H1 sont identiques à RAG-014** sur les 20 requêtes.
- Le rejeu CPU reproduit exactement classements, scores et traces de fusion.
- Les sorties hybrides conservent jusqu'à 100 résultats depuis l'union des
  listes de 50 ; la profondeur source n'est pas passée à 100.
- Les neuf méthodes couvrent les 20 requêtes et retournent chacune 50 résultats
  dans la comparaison principale. Les références individuelles gardent ces
  mêmes 50 candidats ; leurs anciens top 100 restent intacts.

## Performances

Chargements et vérifications globales exclus ; sources exécutées séquentiellement.
Les coûts par configuration sont reconstitués à partir des étapes mesurées pour
chaque requête : sources concernées, contrôles et fusion. Ce ne sont pas cinq
recherches indépendantes et les médianes des composantes ne s'additionnent pas.

| Source, 50 candidats | Médiane | P95 |
|---|---:|---:|
| Lexical pondéré | 170,23 ms | 248,80 ms |
| BM25-A | 185,81 ms | 565,34 ms |
| BM25-B | 349,67 ms | 833,84 ms |
| BGE-M3, encodage compris | 98,89 ms | 101,16 ms |

| Profil | Fusion réelle médiane / P95 | Total séquentiel attribuable médian / P95 | Rejeu : fusion seule médiane |
|---|---:|---:|---:|
| H1 | 1,04 / 1,28 ms | 270,65 / 351,39 ms | 1,01 ms |
| H2 | 1,03 / 1,27 ms | 287,17 / 665,93 ms | 0,99 ms |
| H3 | 1,08 / 1,39 ms | 452,56 / 937,04 ms | 1,01 ms |
| H4 | 1,85 / 2,48 ms | 435,20 / 811,83 ms | 1,83 ms |
| H5 | 1,89 / 2,49 ms | 435,24 / 811,82 ms | 1,85 ms |

La session partagée complète — quatre sources et cinq fusions — a une médiane
de 792,86 ms par requête, P95 1 657,60 ms. Le rejeu ne mesure que la fusion sur
des candidats précalculés. Aucun de ces chiffres ne prédit les performances
de Wallace, notamment son encodage CPU. Aucun benchmark de charge concurrente.

## Recouvrement, diversité et contributions des sources

Recouvrement moyen des sources, en documents communs par requête au top 50 :
lexical/vectoriel **9,05**, BM25-A/vectoriel **11,15**, BM25-B/vectoriel **13,85**,
lexical/BM25-A **15,95**, lexical/BM25-B **16,90**, BM25-A/BM25-B **29,35**.

Dans l'union des quatre sources, 566 couples sont propres au lexical, 642 au
vectoriel, 345 à BM25-A et 283 à BM25-B. « Propre » signifie absent des top 50
des trois autres, pas absent de leurs correspondances possibles.

| Profil | Contributions distinctes top 10 / top 50 | Réponses <60 caractères top 10 / top 50 | « Autre » top 10 / top 50 |
|---|---:|---:|---:|
| H1 | 172 / 702 | 15 / 155 | 4 / 28 |
| H2 | 198 / 818 | 55 / 258 | 9 / 38 |
| H3 | 196 / 821 | 49 / 231 | 9 / 35 |
| H4 | 186 / 748 | 26 / 170 | 7 / 28 |
| H5 | 194 / 810 | 37 / 233 | 9 / 44 |

Ces effectifs sont cumulés sur 20 requêtes, soit 200 occurrences au top 10 et
1 000 au top 50. Ils décrivent des résultats, pas des opinions représentatives.
Les occurrences de réponses répétées ne sont pas supprimées.

Le rapport complet donne, pour chaque profil aux top 10 et 50, la présence,
l'exclusivité et la part de score RRF de chaque source. Deux observations :

- Dans les top 50 H4, les branches lexicales représentent ensemble **70,14 %**
  de la somme des contributions RRF, le vectoriel 29,86 %.
- Dans les top 50 H5, le vectoriel représente **68,35 %** de cette somme ; les
  deux branches lexicales 31,65 %. Il apparaît dans 821 des 1 000 occurrences,
  dont 530 lui sont exclusives au sein de H5.

Les poids d'entrée 50/50 de H5 ne garantissent donc pas un partage 50/50 dans les
résultats sélectionnés. Une seule branche lexicale de poids 1/4 ne peut pas
dépasser un candidat vectoriel présent dans les 50 avec un poids 1/2 :
`(1/4)/61 < (1/2)/110`. Les documents trouvés par les deux branches lexicales
peuvent en revanche contribuer sans être dans la liste vectorielle.
Ces effets sont structurels, sans réglage appris ; la part RRF n'est pas une
preuve de pertinence causale.

## Référentiel et annotations

La cible regroupe **2 673 couples uniques** pour les cinq hybrides et les quatre
références. Tous sont déjà présents dans les 3 254 couples cumulés RAG-017/018.
Le complément indépendant contient donc `pool.json = []`, `new_pairs = 0`
et `plan_hash = null`. Aucun nouveau jugement ou cache n'est créé.

Les deux référentiels restent séparés : **3 254 jugements valides pour le 8B**,
**3 251 pour le 14B**. Les trois sorties historiques invalides de ce dernier
restent non jugées. Les caches sont ouverts avec `mode=ro` et leurs recettes,
entrées et sorties sont vérifiées. Aucune note humaine n'est utilisée.

Au top 50, le 8B couvre 1 000/1 000 résultats de chaque méthode. Le 14B couvre
997/1 000 pour le lexical, 998/1 000 pour H1 et H4, et 1 000/1 000 pour les
autres méthodes. Les trois requêtes au pool incomplet restent exclues des
moyennes communes : `fiscalite-04`, `fiscalite-05`, `services_publics-01`.

Le mécanisme de complément non vide est disponible et testé sur des données
synthétiques : plan v2, nouveaux couples dédupliqués et cache séparé, sans
réannotation des anciens échecs. Aucun cas réel n'a nécessité son exécution.

## Pertinence sur les mêmes 17 requêtes

Seuil binaire : notes 2–3. Precision@5/10/20/50, MRR@50 et nDCG poolée sont
recalculés pour les neuf méthodes avec le même ensemble de requêtes. Les
couvertures et valeurs calculables sur les 20 requêtes sont conservées aussi.

L'IDCG est constitué du pool cumulé commun, pour chaque requête et juge, avec
gain `2**grade-1`. Il n'est pas exhaustif sur le corpus. Aucun Recall exhaustif,
aucun zéro attribué à un non-jugé, aucune copie de nDCG d'un rapport historique.
Il n'y a pas eu d'enrichissement réel ici ; les chiffres sont néanmoins
recalculés depuis les notes afin de conserver une référence explicite commune.

| Juge | Méthode | P@10 | nDCG poolée@10 | P@50 | nDCG poolée@50 | MRR@50 |
|---|---|---:|---:|---:|---:|---:|
| 8B | H1 | 0,935 | 0,634 | 0,860 | 0,729 | 0,912 |
| 8B | H2 | 0,912 | 0,572 | 0,853 | 0,690 | 1,000 |
| 8B | H3 | 0,935 | 0,576 | 0,864 | 0,688 | 1,000 |
| 8B | H4 | 0,906 | 0,577 | 0,878 | 0,720 | 0,912 |
| 8B | H5 | 0,929 | 0,618 | 0,896 | 0,731 | 0,971 |
| 8B | Lexical | 0,829 | 0,573 | 0,796 | 0,672 | 0,971 |
| 8B | BM25-A | 0,882 | 0,526 | 0,756 | 0,605 | 0,971 |
| 8B | BM25-B | 0,859 | 0,522 | 0,821 | 0,640 | 0,971 |
| 8B | Vectoriel | 0,935 | 0,621 | 0,888 | 0,719 | 1,000 |
| 14B | H1 | 0,894 | 0,720 | 0,748 | 0,679 | 0,961 |
| 14B | H2 | 0,865 | 0,652 | 0,746 | 0,637 | 0,892 |
| 14B | H3 | 0,865 | 0,648 | 0,768 | 0,646 | 0,897 |
| 14B | H4 | 0,853 | 0,652 | 0,768 | 0,667 | 0,961 |
| 14B | H5 | 0,912 | 0,712 | 0,799 | 0,688 | 0,931 |
| 14B | Lexical | 0,735 | 0,554 | 0,645 | 0,556 | 0,863 |
| 14B | BM25-A | 0,818 | 0,602 | 0,615 | 0,520 | 0,882 |
| 14B | BM25-B | 0,776 | 0,566 | 0,704 | 0,567 | 0,882 |
| 14B | Vectoriel | 0,865 | 0,705 | 0,779 | 0,673 | 1,000 |

**H1** conserve la meilleure nDCG@10 hybride selon les deux juges, avec un coût
inférieur à H3/H4/H5. **H5** obtient les meilleurs Precision@50 et nDCG@50
hybrides selon les deux juges, mais son avantage sur H1 en nDCG@50 est faible
pour le 8B. Son pool top 50 contient davantage de documents jugés pertinents,
ce qui motive son intérêt comme source de candidats pour un reranker ; cela
ne constitue pas une mesure de rappel exhaustif.

H2/H3 ne démontrent pas un avantage général sur H1. H4 est moins favorable que
H5 sur plusieurs métriques de tête et à 50, mais garde un MRR supérieur selon
le 14B : il ne faut pas transformer les seules moyennes retenues en domination
universelle. Le vectoriel seul reste compétitif, plus rapide et à MRR 1,000.

## Écarts par requête, domaine et juge

Le [rapport local complet](evaluation/local/rag019/comparison/report.md) donne
les quatre profondeurs, toutes les couvertures, les écarts par requête et les
agrégations par domaine. Son `comparison.json` conserve aussi les catégories
et les inversions de classement entre juges.

- Pour `fiscalite-01`, H5 gagne face à H1 environ 0,117 de nDCG@10 selon le 8B
  et 0,306 selon le 14B ; les gains P@10 sont 0,100 et 0,300.
- Pour `democratie-03`, H5 perd environ 0,119 et 0,111 de nDCG@10 face à H1,
  malgré une Precision@10 identique.
- Pour `ecologie-01`, le changement de MRR H5–H1 est **+0,5 pour le 8B** et
  **−0,5 pour le 14B**. Une seule note sur un premier résultat peut modifier
  fortement le diagnostic de rang réciproque.
- Sur la fiscalité des requêtes complètes, le 14B donne une nDCG@10 de 0,819
  à H5 contre 0,733 à H1 ; le 8B donne 0,724 contre 0,730. Les tendances ne
  sont donc pas uniformes entre domaines et juges.

Au total, **197 inversions strictes** entre deux profils hybrides sont présentes
sur 17 requêtes, en comptant les différentes paires, métriques et profondeurs.
Ce ne sont ni 197 requêtes indépendantes ni un test statistique. Aucun consensus
de notes n'est produit ; les deux évaluations restent séparées.

## Artefacts, commandes et validations

```text
evaluation/local/rag019/
  protected.json                Empreintes des fichiers historiques
  configuration/frozen.json     Poids, profondeur et références figés
  development/                  Sources chronométrées, neuf classements, traces, statistiques
  replay/                       Rejeu CPU des mêmes candidats, sans modèle
  complement/                   Cibles, origines et manifeste ; complément vide
  comparison/                   Métriques recalculées, rapport et exports LLM séparés
```

Depuis `rag/`, sans GPU ni PostgreSQL pour le rejeu et les rapports :

```bash
.venv/bin/python -m cahier_rag.search.hybrid.multi.cli replay \
  --experiment evaluation/local/rag019/development \
  --output evaluation/local/NOUVEAU_REJEU
.venv/bin/python -m cahier_rag.search.hybrid.multi.cli report \
  --experiment evaluation/local/rag019/development \
  --pool evaluation/local/rag019/complement \
  --output evaluation/local/NOUVEAU_RAPPORT
```

La [procédure détaillée](recherche-multi-hybride.md) documente le passage réel,
les filtres, le gel, les compléments et la distinction des latences. Les sorties
réelles restent ignorées par Git. Les dossiers de sortie doivent être nouveaux.

Validation : **465 tests réussis, 3 ignorés** dans l'environnement léger sans
PyTorch. Les 22 nouveaux tests incluent l'intégration PostgreSQL/SQLite sur des
données synthétiques, la compatibilité H1, les poids, filtres, partitions,
BIGINT, manifestes, caches préservés, compléments vides/non vides et métriques
indéfinies. Ruff, `uv lock --check` et les contrôles de diff sont conformes.
L'avertissement Starlette/httpx déjà présent reste sans changement.

Les **1 068 fichiers historiques protégés** conservent leurs empreintes,
notamment les modèles de classement, les index BM25 locaux, les requêtes,
les référentiels et annotations humaines. Aucune migration, dépendance ou
infrastructure ajoutée. Aucun backend, frontend, Wallace, corpus source,
index existant ou jugement historique modifié. Aucun commit ni push.

## Limites et recommandation RAG-020

Le développement ne comprend que 20 requêtes, dont 17 au pool entièrement
jugé. Le pooling dépend des moteurs, les deux juges partagent la famille Qwen,
les notes humaines ne valident pas ces conclusions et aucune incertitude
statistique n'est revendiquée. La corrélation des deux branches lexicales peut
renforcer des erreurs communes. La sélection des candidats pour la suite n'est
pas une validation sur les 20 requêtes réservées, qui restent intactes.

Pour RAG-020, comparer en priorité le reranking des candidats **H1 et H5**, avec
**BGE-M3 seul** comme contrôle : H1 représente le compromis de coût et de tête,
H5 un pool top 50 plus dense en documents jugés pertinents, et le vectoriel une
référence simple et rapide. Conserver les autres configurations comme ablations
disponibles, sans multiplier les réglages de poids.

Fixer le protocole du reranker et les critères principaux avant les mesures,
garder séparés les deux référentiels, contrôler humainement des accords et
désaccords et annoter tout nouveau couple hors pool. Ne pas utiliser les notes
comme entrée du reranker ni présenter une mesure sur ces mêmes requêtes de
développement comme une validation finale indépendante.
