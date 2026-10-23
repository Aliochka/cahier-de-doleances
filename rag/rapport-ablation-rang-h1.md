# Ablation de pertinence de ts_rank_cd dans H1

Expérience locale du 23 octobre 2026. Aucune modification de H1 en production, aucun modèle ni juge relancé et aucun benchmark de performance.

**Résultat : `ts_rank_cd` ne gagne pas en pertinence lexicale moyenne sur ce jeu, mais H1 original conserve la meilleure nDCG@10 hybride selon les deux juges.** Son avantage hybride est faible face à `ts_rank`, plus marqué face à la suppression du rang pour le juge 14B. Cette expérience ne suffit donc pas à justifier sa suppression de H1.

## Protocole et parité

- Corpus expérimental RAG-007 : 20 000 unités ; mêmes 20 requêtes de développement. Aucune recherche sur les requêtes réservées.
- Même représentation lexicale réponse seule, préparation française, partition de développement, admissibilité, DF/IDF et départage `document_id COLLATE "C"`.
- Original : `0,5 × couverture IDF + 0,3 × couverture des termes + 0,2 × ts_rank_cd(v,q,32)`.
- Sans rang : `0,5 × couverture IDF + 0,3 × couverture des termes` ; aucune renormalisation et aucun appel à une fonction de rang.
- Avec `ts_rank` : remplacement de la seule fonction, normalisation 32 et poids 0,2 conservés.
- Hybride : mêmes top50 BGE-M3 archivés de RAG-019 ; RRF `k=60`, rangs à partir de 1, poids égaux, 50 candidats par branche et départage par identifiant.
- Jugements historiques RAG-017/018, protocole `relevance-fr-v2`, notes de Qwen3-8B et Qwen3-14B conservées séparément ; pertinent = note 2 ou 3.
- nDCG : gain `2**grade−1`, idéal du pool historique fixe de 3 254 couples par juge. Aucun recalcul de l’idéal à partir du seul top10, aucun non-jugé remplacé par zéro.

**Contrôle réussi sur les 20 requêtes : les top50 lexicaux originaux reproduisent exactement les identifiants et scores RAG-019 ; les top50 hybrides reproduisent exactement H1 RAG-019.** Les ensembles de candidats admissibles des trois variantes sont identiques pour chaque requête. Les classements ont été enregistrés avant lecture des notes.

## Comparaison principale : mêmes 17 requêtes pour toutes les colonnes

Exclusions dues aux trois sorties historiques invalides du 14B : `fiscalite-04`, `fiscalite-05`, `services_publics-01`. Les trois variantes sont comparées sur les mêmes requêtes pour P@10 et nDCG@10, et pour les deux juges.

| Recherche | Variante | P@10 · 8B | nDCG@10 · 8B | P@10 · 14B | nDCG@10 · 14B |
|---|---|---:|---:|---:|---:|
| lexical | original | 0.8294 | 0.5733 | 0.7353 | 0.5537 |
| lexical | sans-rang | 0.8647 | 0.5981 | 0.7588 | 0.5824 |
| lexical | ts-rank | 0.8529 | 0.5837 | 0.7529 | 0.5915 |
| hybrid | original | 0.9353 | 0.6336 | 0.8941 | 0.7203 |
| hybrid | sans-rang | 0.9294 | 0.6315 | 0.8882 | 0.6945 |
| hybrid | ts-rank | 0.9294 | 0.6309 | 0.8824 | 0.7135 |

Écarts de nDCG@10 par rapport à l’original et nombre de requêtes gagnantes / égales / perdantes (seuil numérique 1e-12) :

| Recherche | Variante | Δ 8B | Gains / égalités / pertes · 8B | Δ 14B | Gains / égalités / pertes · 14B |
|---|---|---:|---|---:|---|
| lexical | sans-rang | +0.0248 | 11 / 1 / 5 | +0.0287 | 12 / 0 / 5 |
| lexical | ts-rank | +0.0104 | 11 / 3 / 3 | +0.0378 | 13 / 1 / 3 |
| hybrid | sans-rang | -0.0021 | 3 / 7 / 7 | -0.0259 | 3 / 5 / 9 |
| hybrid | ts-rank | -0.0027 | 5 / 8 / 4 | -0.0069 | 2 / 8 / 7 |

La meilleure moyenne du lexical seul ne garantit pas une meilleure fusion : RRF dépend des rangs et des documents communs aux deux branches. Le changement de liste lexicale peut améliorer sa précision propre tout en réduisant sa complémentarité avec BGE-M3. C’est une explication possible du contraste observé, pas une preuve causale.

## Couverture des jugements

Les référentiels contiennent 3 254 notes valides pour le 8B et 3 251 pour le 14B. Tous les documents des top10 principaux des variantes appartiennent au pool historique ; les seules notes manquantes au top10 sont des échecs historiques du 14B. Le pool reste complet sur les mêmes 17 requêtes pour la nDCG.

| Recherche | Variante | Top10 jugés · 8B /200 | Top10 jugés · 14B /200 |
|---|---|---:|---:|
| lexical | original | 200 | 198 |
| lexical | sans-rang | 200 | 198 |
| lexical | ts-rank | 200 | 198 |
| hybrid | original | 200 | 200 |
| hybrid | sans-rang | 200 | 200 |
| hybrid | ts-rank | 200 | 200 |

Les top50 principaux font entrer **22 nouveaux couples non jugés**, tous après le rang 10. Le scénario d’inversion des ex æquo porte le complément éventuel à 45 couples distincts. Aucun juge n’a été relancé : cette couverture suffit pour les P@10/nDCG@10 publiés sur le pool historique, mais pas pour une comparaison complète à 50 ni pour une nDCG sur un pool enrichi. Les métriques de tête ne prouvent donc pas l’équivalence des candidats avant reranking.

## Effet des ex æquo

Groupes comptés sur tous les candidats admissibles, avec égalité exacte du score PostgreSQL retourné ; le comptage ne s’arrête pas au top50.

| Variante | Scores distincts moyens top10 | Requêtes avec groupe coupé à 10 /20 | À 50 /20 | Taille maximale du groupe à la frontière 10 | IDs top10 lexical remplacés en inversant les égalités /200 | IDs top10 hybride remplacés /200 |
|---|---:|---:|---:|---:|---:|---:|
| original | 8.90 | 7 | 11 | 6 | 10 | 4 |
| sans-rang | 4.45 | 13 | 16 | 35 | 59 | 19 |
| ts-rank | 8.95 | 6 | 7 | 10 | 10 | 2 |

L’inversion des identifiants à score égal conserve les scores, mais modifie potentiellement l’admission au top50 et les rangs RRF. Le départage historique reste celui de toutes les mesures principales. Le tableau suivant indique la variation moyenne de nDCG@10 du scénario inversé par rapport au départage historique, sur les mêmes 17 requêtes, toutes évaluables aussi dans ce scénario :

| Recherche | Variante | Δ nDCG@10 · 8B | Δ nDCG@10 · 14B |
|---|---|---:|---:|
| lexical | original | +0.0003 | -0.0101 |
| lexical | sans-rang | -0.0075 | -0.0019 |
| lexical | ts-rank | -0.0102 | -0.0194 |
| hybrid | original | -0.0010 | +0.0019 |
| hybrid | sans-rang | -0.0215 | +0.0009 |
| hybrid | ts-rank | -0.0115 | -0.0013 |

Sans rang, 59 des 200 identifiants des top10 lexicaux changent sous ce seul départage, contre 10 pour chaque formule avec rang. Les écarts par requête sont parfois plus grands que les écarts moyens entre recettes. L’inversion n’est ni un tirage aléatoire, ni une borne exhaustive, ni une proposition de nouveau départage. Elle montre que la composante de rang sert aussi à distinguer des documents de couverture identique.

## Écarts de nDCG@10 par requête

Δ = variante − original. Les trois requêtes à pool incomplet restent indéfinies (—). Les P@10, leurs écarts et les valeurs absolues pour les 20 requêtes figurent dans le [rapport local complet](evaluation/local/rank-ablation-20261023/report.md).

| Recherche | Requête | Sans rang · Δ8B | Sans rang · Δ14B | ts_rank · Δ8B | ts_rank · Δ14B |
|---|---|---:|---:|---:|---:|
| lexical | democratie-01 | -0.0135 | -0.0737 | +0.0329 | +0.0075 |
| lexical | democratie-02 | +0.0050 | -0.0088 | -0.0465 | -0.0851 |
| lexical | democratie-03 | +0.1204 | +0.1606 | +0.0540 | +0.0466 |
| lexical | democratie-04 | +0.0100 | -0.0079 | +0.0052 | -0.0109 |
| lexical | democratie-05 | -0.0366 | -0.0318 | -0.0225 | -0.0196 |
| lexical | ecologie-01 | +0.0389 | +0.0187 | -0.1028 | +0.0532 |
| lexical | ecologie-02 | +0.1837 | +0.0136 | +0.0614 | +0.0482 |
| lexical | ecologie-03 | +0.1638 | +0.1119 | +0.0562 | +0.2541 |
| lexical | ecologie-04 | +0.0577 | +0.0647 | +0.0188 | +0.0257 |
| lexical | ecologie-06 | +0.0000 | +0.0020 | +0.0000 | +0.0067 |
| lexical | fiscalite-01 | -0.0351 | -0.0575 | +0.0039 | +0.0039 |
| lexical | fiscalite-02 | +0.0634 | +0.0806 | +0.0507 | +0.1307 |
| lexical | fiscalite-03 | -0.0301 | +0.0189 | +0.0000 | +0.0000 |
| lexical | fiscalite-04 | +0.0304 | — | +0.0316 | — |
| lexical | fiscalite-05 | -0.0575 | — | -0.1066 | — |
| lexical | services_publics-01 | +0.0574 | — | -0.0055 | — |
| lexical | services_publics-02 | +0.0273 | +0.0273 | +0.0273 | +0.0636 |
| lexical | services_publics-03 | -0.1887 | +0.1168 | +0.0000 | +0.0843 |
| lexical | services_publics-04 | +0.0382 | +0.0365 | +0.0360 | +0.0326 |
| lexical | services_publics-06 | +0.0163 | +0.0153 | +0.0018 | +0.0008 |
| hybrid | democratie-01 | +0.0011 | -0.0533 | +0.0011 | -0.0533 |
| hybrid | democratie-02 | +0.0000 | +0.0010 | -0.1108 | -0.0241 |
| hybrid | democratie-03 | -0.0043 | -0.0466 | +0.0000 | +0.0000 |
| hybrid | democratie-04 | +0.0000 | -0.0076 | +0.0000 | -0.0076 |
| hybrid | democratie-05 | -0.0030 | +0.0000 | +0.0055 | +0.0000 |
| hybrid | ecologie-01 | -0.0039 | +0.0129 | +0.0032 | -0.0022 |
| hybrid | ecologie-02 | +0.0000 | -0.0671 | +0.0000 | -0.0022 |
| hybrid | ecologie-03 | +0.0000 | -0.0332 | +0.0000 | +0.0000 |
| hybrid | ecologie-04 | -0.0328 | -0.1297 | +0.0629 | +0.0000 |
| hybrid | ecologie-06 | +0.0186 | +0.0000 | +0.0000 | +0.0000 |
| hybrid | fiscalite-01 | +0.0000 | +0.0000 | -0.0019 | +0.0551 |
| hybrid | fiscalite-02 | -0.0120 | -0.0483 | -0.0120 | -0.0120 |
| hybrid | fiscalite-03 | +0.0000 | +0.0441 | +0.0000 | +0.0000 |
| hybrid | fiscalite-04 | +0.0000 | — | +0.0034 | — |
| hybrid | fiscalite-05 | +0.0000 | — | -0.0503 | — |
| hybrid | services_publics-01 | -0.0521 | — | -0.0521 | — |
| hybrid | services_publics-02 | -0.0314 | -0.0397 | -0.0314 | +0.0051 |
| hybrid | services_publics-03 | -0.0058 | +0.0000 | +0.0000 | +0.0000 |
| hybrid | services_publics-04 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| hybrid | services_publics-06 | +0.0379 | -0.0726 | +0.0379 | -0.0755 |

## Interprétation et décision

- **Lexical seul : aucun gain moyen démontré pour `ts_rank_cd`.** Sans rang, nDCG@10 gagne +0,0248 / +0,0287 (8B / 14B) ; avec `ts_rank`, +0,0104 / +0,0378. Les deux alternatives améliorent aussi P@10 sur les 17 mêmes requêtes.
- **H1 hybride : avantage descriptif à l’original.** Sans rang, nDCG@10 perd −0,0021 / −0,0259 ; avec `ts_rank`, −0,0027 / −0,0069. La suppression du rang est donc presque neutre pour le 8B mais moins favorable pour le 14B. Les deux juges restent séparés, sans note de consensus.
- **Les ex æquo comptent.** La suppression augmente nettement la dépendance aux identifiants arbitraires et peut affecter à la fois le top10 lexical et les candidats de la fusion.

**Conserver provisoirement `ts_rank_cd` dans H1 hybride est cohérent avec ces résultats. En revanche, ils ne montrent pas qu’il est indispensable, ni que son gain justifie un coût donné : aucun coût n’a été mesuré dans cette expérience.** `ts_rank` est une alternative de pertinence proche dans l’hybride, avec moins de groupes coupés à 50 sur ce jeu ; une décision de remplacement demanderait une validation indépendante et, ultérieurement, une mesure de coût distincte.

Limites : 20 requêtes de développement dont 17 au pool complet, corpus expérimental et non corpus complet, pool construit avec les moteurs historiques, deux juges de la même famille, absence de validation humaine indépendante et aucune inférence de significativité. L’absence de nouveaux non-jugés dans les top10 ne supprime pas le biais du pool.

## Artefacts et reproduction

- [Rapport détaillé : P@10, nDCG@10, écarts par requête et ex æquo](evaluation/local/rank-ablation-20261023/report.md).
- [Résultats structurés et scénario de départage inversé](evaluation/local/rank-ablation-20261023/comparison.json).
- [Classements top50](evaluation/local/rank-ablation-20261023/runs.json), [tous les scores candidats](evaluation/local/rank-ablation-20261023/candidates.json), [SQL et paramètres](evaluation/local/rank-ablation-20261023/sql.json), [couples non jugés](evaluation/local/rank-ablation-20261023/unjudged.json).
- [Protocole et empreintes](evaluation/local/rank-ablation-20261023/protocol.json). Les fichiers historiques protégés ont conservé leurs empreintes. Le script exactement exécuté est archivé dans `executed-script.py` ; le script versionné ne diffère ensuite que par le formatage et le remplacement de deux lambdas d’affichage par des fonctions.

Depuis la racine, dans un nouveau répertoire, sans GPU :

```sh
RAG_SOURCE_DATABASE_URL=postgresql:///cahier_doleances_local \
RAG_DATABASE_URL=postgresql:///cahier_rag \
  .cache/search-cpu-venv/bin/python rag/scripts/evaluate_rank_ablation.py \
  --output rag/evaluation/local/NOUVELLE_ABLATION
```

Cette commande refait uniquement la récupération lexicale pour les trois recettes et réutilise les vecteurs et jugements archivés. Elle ne chronomètre aucune étape. Les résultats locaux restent ignorés par Git ; ce rapport et le script sont versionnables.

Validation : 3 tests ciblés réussis (parité RRF avec la fusion historique, traitement strict d’un top10 non jugé et exclusion des moyennes appariées, groupes d’ex æquo au-delà de la coupure 50), plus les contrôles réels de parité des 20 classements et les empreintes des artefacts.
