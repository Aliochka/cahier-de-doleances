# Coûts expérimentaux mesurés

Fichiers locaux, calcul exact, quatre threads BLAS, aucune nouvelle inférence. Médianes sur q01/q06/q25. Les temps ne sont pas une mesure du service PostgreSQL/ANN en production. L'export SQL est hors ligne.

| Réponses 2019 | Segments existants | Vecteurs bruts (Mio) | Préparation du sous-tableau (ms) | Cosinus + agrégation (ms) | Tri vectoriel complet (ms) | BM25 (ms) | Tri lexical (ms) | RSS après palier (Gio) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 | 240 | 0.94 | 1.30 | 0.02 | 0.02 | 0.07 | 0.02 | 0.06 |
| 1,000 | 1,003 | 3.92 | 2.47 | 0.02 | 0.05 | 0.07 | 0.04 | 0.07 |
| 5,000 | 5,021 | 19.61 | 3.84 | 0.11 | 0.26 | 0.24 | 0.15 | 0.10 |
| 20,000 | 20,061 | 78.36 | 13.16 | 1.95 | 1.21 | 0.69 | 0.56 | 0.22 |
| 100,000 | 100,348 | 391.98 | 66.91 | 8.71 | 7.14 | 3.87 | 2.93 | 0.87 |
| 1,000,000 | 1,003,055 | 3918.18 | 1.55 | 88.47 | 81.83 | 80.40 | 31.69 | 4.25 |

Export local : 283.80s pour 1 003 055 vecteurs existants ; tokenisation/statistiques préparées en 16.65s ; 30 requêtes vectorielles calculées en 2.68s hors tri. Cache de travail : 4.82Gio. Les fenêtres SQL de 1 000 documents sont bornées à 15 s ; les durées observées restent sous la seconde. Pas d'encodage de requête ni de chargement de modèle dans ces temps.

Les RSS sont des observations du processus après chaque palier, avec pages mappées et caches déjà chauds ; ce ne sont pas des pics mémoire indépendants par requête. Le cache lexical ne conserve que les fréquences des termes des30 requêtes, mais les longueurs et les IDF sont calculés sur tous les documents : c'est une optimisation de calcul exacte, pas un index lexical général.
