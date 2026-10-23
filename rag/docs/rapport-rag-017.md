# RAG-017 — Campagnes automatiques et comparaison des moteurs

Exécution locale du 18 octobre 2026. Les deux campagnes ont parcouru les
**2 500 couples** ; **4 997 jugements sont valides sur 5 000** après reprise.
Trois sorties du 14B restent invalides : le critère de couverture intégrale
des top 50 par les deux juges n'est donc pas entièrement atteint.
Les notes humaines et les expériences historiques sont préservées.

## Pool et reproductibilité

Le pool est limité aux 20 requêtes de développement et aux unités de développement
du manifeste RAG-007. Il contient 2 500 couples uniques, 1 829 unités distinctes
et 1 387 contributions. Une même unité peut être jugée pour plusieurs requêtes,
sans réutiliser sa pertinence d'une requête à l'autre.

L'union obligatoire comportait 1 931 couples : les top 50 gelés des trois moteurs,
les deux pools de 400 et les 101 compléments RAG-016. Le déficit minimal était
de 69 couples. Une récupération supplémentaire à profondeur 100 a permis
d'ajouter 569 couples pour atteindre exactement 2 500, sans sélectionner de
documents arbitraires. Les préfixes lexicaux/vectoriels 1–50 ont été vérifiés
identiques aux classements historiques. Les nouveaux résultats hybrides ne
servent pas à cet enrichissement.

Les ajouts parcourent les rangs 51–100, puis les requêtes triées par identifiant,
puis les moteurs lexical et vectoriel. Toutes les origines sont conservées.
Les effectifs par origine se recouvrent : 1 819 couples des top 50, 400 RAG-010,
400 RAG-014, 101 RAG-016 et 768 présents dans les profondeurs supplémentaires.
Le pool compte entre 109 et 138 couples par requête.

Manifeste : `evaluation/local/rag017/pool/manifest.json`.
Empreinte du plan :
`035030a5688defe26eb52fdd1dbde3d5360f3c93e195a99bed9a572d57ee521e`.
Les entrées, origines, modèles, recettes, tentatives et rapports restent locaux,
ignorés par Git. Le protocole et les résultats v1 ne sont pas remplacés.

## Protocole et modèles

`relevance-fr-v2` note l'adéquation à l'intention de 0 à 3. La précision attendue
dépend de la demande ; la longueur n'est pas récompensée. Les trois exemples
du ticket sont inclus. Le prompt ne reçoit que requête, réponse, question et
titre : aucun moteur, rang, score, autre jugement ou commentaire humain.

| Modèle | Révision officielle conservée |
|---|---|
| Qwen3-8B | `b968826d9c46dd6066d109eabc6255188de91218` |
| Qwen3-14B | `40c069824f4251a91eefaf281ebe4c544efd3e18` |

Recette inchangée de RAG-016 : NF4 double, calcul bfloat16, attention SDPA,
lots de 2, graine 42, génération gloutonne, thinking désactivé, sortie maximale
192 tokens et entrée maximale 24 576 tokens. Les deux précontrôles tokenizers
ont réussi sur toutes les entrées ; maximum constaté : **16 630 tokens**.
Aucune entrée n'a été tronquée. Inférence entièrement hors ligne, modèles
exécutés successivement sur RTX 5090.

## Exécution et intégrité

| Mesure | Qwen3-8B | Qwen3-14B |
|---|---:|---:|
| Premier passage | 2 499 valides, 1 invalide | 2 496 valides, 4 invalides |
| Après reprise des seuls échecs | **2 500 valides** | **2 497 valides, 3 invalides** |
| Temps cumulé, reprises et chargements inclus | 2 265,08 s | 3 797,42 s |
| Tentatives générées, reprises incluses | 2 501 | 2 504 |
| Débit cumulé, tentatives/s | 1,104 | 0,659 |
| Pic VRAM allouée PyTorch | 14,37 Gio | 19,41 Gio |
| Pic mémoire résidente du processus | 5,03 Gio | 6,02 Gio |
| Tokens d'entrée, reprises incluses | 2 493 709 | 2 500 150 |
| Tokens de sortie hors EOS | 136 051 | 216 247 |

Les durées cumulées représentent environ **1 h 41 min** de campagnes,
hors préparation et précontrôles. La VRAM mesurée est l'allocation PyTorch,
pas toute la mémoire réservée par le pilote. Les temps des seuls passages de
reprise ne sont pas présentés comme le débit de la campagne complète.

Les trois sorties invalides du 14B ont une justification de 573, 514 ou 508
caractères, au-delà du contrat de 500. Elles restent sans note exploitable ;
aucune réparation, troncature ou récupération partielle de note n'est appliquée.
Les tentatives originales et reprises sont conservées dans le cache transactionnel.

| Requête | Réponse source | Moteurs concernés dans leur top 50 |
|---|---|---|
| `fiscalite-04` | `21906` | lexical rang 6, hybride rang 11 |
| `fiscalite-05` | `4611645` | lexical rang 35 |
| `services_publics-01` | `22141` | lexical rang 7, hybride rang 23 |

Couverture 14B au top 50 : lexical **997/1 000**, vectoriel **1 000/1 000**,
hybride **998/1 000**. Le 8B couvre les 1 000 résultats de chaque moteur.
Tous les identifiants, hash de contenus et requêtes, recettes, statuts et
références de corpus sont vérifiés lors de la génération du rapport.

## Métriques et résultats

Pertinence binaire : notes 2–3. Precision conserve le dénominateur k ; MRR est
calculé sur le classement fourni, limité au top 50. Un document non jugé n'est
jamais noté zéro. Les métriques dont des rangs nécessaires sont inconnus
restent indéfinies. Aucun Recall exhaustif n'est calculé.

Pour nDCG, gain `2**grade-1`, décote logarithmique et idéal constitué de toutes
les notes du pool de la requête pour ce juge. Cette **nDCG poolée** exige ici
un pool entièrement jugé pour la requête ; ce n'est pas un idéal exhaustif
sur les 20 000 unités. Les trois requêtes incomplètes du 14B sont exclues de
ses nDCG, même lorsque son top k est entièrement jugé.

Pour comparer sur le même périmètre, le tableau ci-dessous utilise les **17
requêtes intégralement jugées par les deux modèles**. Les résultats sur toutes
les requêtes calculables, aux seuils 5, 10, 20 et 50, restent dans le rapport
local avec leurs effectifs et couvertures explicites.

| Juge | Moteur | P@10 | nDCG poolée@10 | P@50 | nDCG poolée@50 | MRR@50 |
|---|---|---:|---:|---:|---:|---:|
| 8B | Lexical | 0,829 | 0,577 | 0,796 | 0,684 | 0,971 |
| 8B | Vectoriel | 0,935 | 0,626 | 0,888 | 0,734 | 1,000 |
| 8B | Hybride | 0,935 | 0,638 | 0,860 | 0,743 | 0,912 |
| 14B | Lexical | 0,735 | 0,554 | 0,645 | 0,568 | 0,863 |
| 14B | Vectoriel | 0,865 | 0,705 | 0,779 | 0,688 | 1,000 |
| 14B | Hybride | 0,894 | 0,720 | 0,748 | 0,694 | 0,961 |

Les deux juges donnent un signal favorable au vectoriel et à l'hybride face au
lexical. L'hybride obtient la nDCG poolée moyenne la plus élevée à ces deux
seuils ; le vectoriel obtient la plus forte précision à 50 et le meilleur MRR.
Ce constat ne désigne pas un moteur gagnant définitif : le sous-ensemble commun
est lui-même affecté par les échecs, le pool dépend des moteurs et les labels
sont automatiques. Aucun moteur n'a été réglé à partir de ces résultats.

Les distributions par moteur, requête, domaine et catégorie, les métriques aux
quatre seuils et les requêtes non calculables figurent dans `comparison.json`
et `report.md`. Les exports par modèle portent `judgment_origin: llm` et
`human_reference: false` dans leurs enveloppes ; les listes de jugements sont
compatibles RAG-006, les références et rapports conservateurs avec RAG-015.

## Accords et désaccords

Comparaison sur les **2 497 couples valides communs** :

- Accord exact : **62,68 %** ; à ±1 point : **89,19 %**.
- Accord binaire : **82,54 %** ; kappa pondéré linéaire : **0,5655**.
- **270** écarts d'au moins deux points et **436** divergences binaires.
- **470** couples à examiner : désaccords binaires ou importants, incertitudes,
  ou sorties invalides ; ces catégories se recouvrent.

| Juge | Note 0 | Note 1 | Note 2 | Note 3 | Incertains |
|---|---:|---:|---:|---:|---:|
| 8B | 492 | 51 | 1 644 | 313 | 22 |
| 14B | 699 | 210 | 930 | 658 | 15 |

Le 8B concentre ses notes sur 2 ; le 14B répartit davantage entre 0, 1 et 3.
Cette différence est observée, sans lui attribuer une meilleure fidélité humaine.
La matrice de confusion complète est publiée dans le rapport local.

Seize requêtes présentent au moins une inversion stricte entre deux moteurs
selon le juge, sur une métrique ou un seuil. Les 67 inversions détaillées
ne sont pas 67 requêtes indépendantes. Elles concernent notamment
`democratie-01`, `ecologie-01`, `fiscalite-02` et `services_publics-03`.
Exemples de désaccords importants, sans reproduire de texte citoyen :
`democratie-01` / réponse `1020379`, `democratie-02` / réponse `1062016`
(notes 8B/14B : 2/0). Leurs références complètes et justifications sont dans
`comparison-verified/review.json`. Aucun consensus n'est calculé.

## Modules, commandes et validations

`judges/protocols.py` versionne la grille. `judges/campaign.py` constitue le pool,
contrôle les tokenizers et orchestre les campagnes. `judges/evaluation.py` vérifie
les références, calcule les métriques et exports ; `judges/markdown.py` produit
le rapport lisible. Les primitives RAG-016 restent utilisées pour les modèles,
le cache et les lots. Aucun ajout de dépendance ni modification de verrou.

Procédure détaillée : [evaluation-llm-v2.md](evaluation-llm-v2.md).
Depuis `rag/`, pour produire un **nouveau** rapport sans inférence :

```bash
.venv/bin/python -m cahier_rag.judges.campaign report \
  --output evaluation/local/rag017/nouveau-rapport
```

Rapport de référence local :
[evaluation/local/rag017/comparison-verified/report.md](evaluation/local/rag017/comparison-verified/report.md).
Manifestes et états : `evaluation/local/rag017/pool/` ; cache et tentatives :
`evaluation/local/rag017/cache.sqlite3` ; exports séparés :
`evaluation/local/rag017/comparison-verified/qwen3-{8b,14b}/`.

Validation : **433 tests réussis, 3 ignorés** car PyTorch est absent de
l'environnement léger ; intégrations PostgreSQL activées avec les bases de
test dédiées. Ruff et `uv lock --check` conformes. Les validations réelles
tokenizers et GPU ont utilisé l'environnement optionnel des juges.
Les 32 empreintes historiques contrôlées sont inchangées, dont la session
humaine ; le texte du prompt v1 est identique à celui versionné avant RAG-017.
Les rapports sont reproductibles sans nouvelle inférence. Les adaptations
restent dans `rag/` ; aucune écriture source, migration, modification d'index,
intervention sur Wallace, commit ou push.

## Recommandations RAG-018

1. Geler ces deux références séparément ; conserver les trois sorties invalides
   visibles. Une future recette imposant une sortie structurée devra être
   versionnée et validée, sans réparation silencieuse des résultats actuels.
2. Comparer un reranker sur le même pool de candidats, notamment les candidats
   hybrides, en gardant les références lexicales et vectorielles. Ne jamais
   fournir les jugements au reranker ni entraîner sur ces labels puis annoncer
   une évaluation indépendante sur les mêmes couples.
3. Publier les métriques selon chacun des deux juges et sur un même ensemble
   de requêtes calculables. Vérifier aussi la précision et le MRR : le gain
   de nDCG de l'hybride ne garantit pas une meilleure première réponse.
4. Contrôler humainement un échantillon des désaccords **et** des accords.
   Les deux Qwen partagent une famille et peuvent partager des biais ; aucun
   jugement humain v2 indépendant n'a été utilisé ici. Préserver les 20
   requêtes réservées pour une future validation, sans les lancer maintenant.
