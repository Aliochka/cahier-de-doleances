# Pertinence des textes réellement relus

Dix requêtes fixées avant le nouveau classement : fiscalité, équité, dépenses, justice, responsabilité, expression et quatre contre-exemples. 445 couples relus ou réutilisés : 215 jugements antérieurs inchangés, 230 nouveaux jugements exploratoires Codex. Aucune indépendance historique/statistique. Toute configuration incomplètement jugée reste sans moyenne exacte.

| Réponses 2019 | Méthode | Stratégie | L | Note@10 /3 | Utiles /100 | Hors sujet /100 |
|---:|---|---|---:|---:|---:|---:|
| 240 | lexical | global | — | 1.06 | 31 | 41 |
| 240 | vector | global | — | 1.56 | 46 | 19 |
| 240 | hybrid | global | 50 | 1.42 | 42 | 25 |
| 240 | hybrid | distributed_global_ranks | 50 | 1.42 | 43 | 25 |
| 240 | hybrid | global | 1000 | 1.41 | 44 | 27 |
| 240 | hybrid | distributed_global_ranks | 1000 | 1.41 | 44 | 27 |
| 1,000,000 | lexical | global | — | 2.06 | 70 | 16 |
| 1,000,000 | vector | global | — | 2.57 | 81 | 0 |
| 1,000,000 | hybrid | global | 50 | 2.49 | 84 | 8 |
| 1,000,000 | hybrid | distributed_global_ranks | 50 | 2.49 | 84 | 8 |
| 1,000,000 | hybrid | global | 1000 | 2.48 | 81 | 5 |
| 1,000,000 | hybrid | distributed_global_ranks | 1000 | 2.48 | 81 | 5 |

## Quatre contre-exemples

| Réponses 2019 | Méthode | Stratégie | L | Note@10 /3 | Résultats historiques /40 | Utiles /40 |
|---:|---|---|---:|---:|---:|---:|
| 240 | lexical | global | — | 0.300 | 23 | 2 |
| 240 | vector | global | — | 0.575 | 8 | 1 |
| 240 | hybrid | global | 50 | 0.500 | 9 | 2 |
| 240 | hybrid | distributed_global_ranks | 50 | 0.500 | 10 | 2 |
| 1,000,000 | lexical | global | — | 1.300 | 0 | 18 |
| 1,000,000 | vector | global | — | 2.225 | 0 | 25 |
| 1,000,000 | hybrid | global | 50 | 2.150 | 0 | 28 |
| 1,000,000 | hybrid | distributed_global_ranks | 50 | 2.150 | 0 | 28 |

Les tableaux ne valent pas pour les 20 autres requêtes au million. Les notes 0 et 1 sont distinguées ; une proximité superficielle n'est pas un résultat utile. [Notes, textes justificatifs et origines](data/qualitative-judgments.json).
