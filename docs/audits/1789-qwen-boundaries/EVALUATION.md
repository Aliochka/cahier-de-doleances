# Résultats mesurés

## Validation, 36 cas

| Méthode | Bornes exactes /36 | Débuts faux | Fins fausses | Corrige A | Dégrade A correct | Invalide |
| --- | --- | --- | --- | --- | --- | --- |
| A | 31 | 2 | 5 | — | — | 0 |
| B | 4 | 22 | 21 | 0 | 26 | 1 |
| C | 30 | 3 | 4 | 0 | 1 | 0 |

| Diagnostic | A | B | C |
| --- | --- | --- | --- |
| Débuts incorrects | 2 | 22 | 3 |
| Fins incorrectes | 5 | 21 | 4 |
| Plages tronquées | 2 | 15 | 2 |
| Plages trop larges | 3 | 21 | 5 |
| Titre d’un voisin absorbé | 2 | 10 | 4 |
| Annexe mal attribuée (cas référencés) | 0 | 1 | 1 |
| Sorties invalides | 0 | 1 | 0 |
| Abstentions | 0 | 0 | 0 |
| Incertitude déclarée | 0 | 0 | 0 |
| Signature hors des propres bornes | 0 | 15 | 25 |

Les compteurs ne sont pas additifs : une plage peut être tronquée d’un côté et trop large de l’autre. « Titre d’un voisin absorbé » exige un titre documentaire visible hors de la référence ; une marge géographique seule n’est pas assimilée à la fusion d’un cahier complet. L’unique plage A sans bloc textuel est Santeny : 25 caractères blancs, données exactes dans `empty-baseline-case.json`. Ce défaut du générateur ne devient pas une abstention artificielle.

Le compteur de titres visibles n’est pas un décompte exhaustif des fusions : à Gray, l’en-tête du dossier précédent est hors fenêtre, mais sa fin est absorbée, ce que confirme la lecture des signatures et du titre propre de Gray.

A 31/36 (86,1%), B 4/36 (11,1%), C 30/36 (83,3%). B dégrade 26 des 31 références A correctes et donne une sortie inutilisable supplémentaire ; C en dégrade 1, sans corriger entièrement une erreur A. Le critère **corrections complètes > dégradations nouvelles** échoue sur validation pour les deux variantes.

C conserve exactement les deux bornes A dans 31/36 cas. Ses cinq changements n’apportent aucune paire exacte supplémentaire : Gray devient trop large ; Amont noblesse reste trop court ; Santeny est presque localisé mais les deux titres de frontière sont décalés ; clergé Paris finit au bon endroit mais absorbe Wissous/Saint-Witz ; Châteauneuf inclut encore le titre du suivant. Le cas chapitre Paris/Saint-Paul conserve l’erreur A. Ne pas confondre cette fidélité à A avec une vérification réussie.

Sur les 3 cas de référence non unique/insuffisante de développement, aucune abstention structurée. C signale une seule incertitude sur un autre cas, Uzent, mais propose tout de même une plage trop large. Aucun signal d’incertitude sur validation malgré 6 propositions C inexactes et 31 propositions B inexactes. La confiance déclarée n’est pas calibrée ici.

Les contrôles de signatures sont purement positionnels : 25 réponses C ont au moins un ID de signature extérieur à leurs propres limites, 15 pour B. Ce n’est pas une mesure exhaustive de précision des rôles, mais une contradiction vérifiable avec le contrat demandé. Les annexes n’ont des références de rôle explicites que sur quelques contrôles (notamment Eguilles/Goullin inclus, Brives/Turenne et Uzerche/annexe exclus) ; aucun taux global de qualité des annexes n’est extrapolé.

## Développement

| Méthode | Exactes /21 tranchables | Corrige une erreur A | Dégrade un contrôle A conforme | Réponses invalides |
| --- | --- | --- | --- | --- |
| A | 6 | — | — | 0 |
| B | 1 | 1 | 6 | 1 |
| C | 8 | 2 | 0 | 1 |

C corrige complètement Châtellerault clergé et Digne tiers ; B ne corrige complètement qu’un cas. Sur les 15 erreurs initialement documentées, 13 ont ici une référence complète tranchée ; Castelnaudary et Riez restent explicitement limités. Le dénominateur conservateur 15 n’implique pas une vérité de référence exacte créée pour ces deux cas. Artois constitue un contrôle supplémentaire de source intercalée. Les références sont dans `reference-development.jsonl`, avec diagnostics et statuts.

Ce lot est volontairement difficile et connu : son gain net C +2 ne constitue pas une validation. Le nouveau lot donne C −1. Les paramètres n’ont pas été retouchés pour transformer ce résultat.

## Tous les documents ou seulement les suspects ?

Indicateur non appris : alerte structurelle A existante ou extrémité A non représentable dans la fenêtre. Sur les 36 nouveaux cas :

| Sous-lot | Effectif | A exact | B exact | C exact |
| --- | --- | --- | --- | --- |
| suspect | 5 | 1 | 0 | 1 |
| no_structural_alert | 31 | 30 | 4 | 29 |

Sur les 5 suspects, aucune amélioration d’exactitude ; sur les 31 sans alerte, C perd une paire. Ce petit sous-lot ne valide donc pas non plus une application automatique aux seuls suspects. Une aide de lecture peut être proposée à un documentaliste, mais n’est pas une décision fiable. Les alertes déterministes de plage vide, prochain titre et signatures extérieures doivent précéder tout recours LLM.

## Temps et mémoire

| Mesure validation | B | C |
| --- | --- | --- |
| Appels | 36 | 36 |
| Entrée min–max tokens | 4780–11252 | 4904–11369 |
| Temps cumulé (s) | 275.01 | 265.85 |
| Médiane (s) | 7.32 | 7.36 |
| p95 (s) | 10.77 | 8.9 |
| Pic alloué PyTorch (GiB) | 12.55 | 12.58 |
| Pic réservé PyTorch (GiB) | 13.08 | 13.08 |

Les temps incluent génération, construction éventuelle de grammaire et analyse de la réponse, hors chargement du modèle et contrôle préalable des poids. Première requête plus coûteuse ; reprise des quatre premiers essais contraints incluse dans les 24 cas de développement, pas comptée deux fois. Quatre essais non contraints sont archivés séparément. Paramètres de génération identiques pour B/C, lots de 1, aucun dépassement de contexte, aucun OOM, aucun repli vers un autre modèle.

Une extrapolation purement arithmétique de la médiane C donne ≈ 2,67 h pour 1 305 fenêtres similaires, sans validation humaine, assemblage ni variation de longueur. Ce n’est pas une mesure de débit sur les 1 305 notices ni une recommandation de lancement.

## Limites et interprétation

- Un seul modèle/quantification/prompt final et mode non-thinking ; pas de comparaison BF16 intégral, autre backend ou raisonnement activé. Les IDs et la lecture des longs contextes peuvent être une cause importante des échecs.
- Fenêtres de pages extrêmes : milieu explicitement omis, voisins et notices parfois mal paginés. Sur développement, une véritable extrémité nécessaire n’est pas visible et une portée Riez est incertaine. Ce n’est pas une preuve d’incapacité sémantique générale.
- Contrôle Codex, avant sorties Qwen de validation, mais sans lecteur humain indépendant, sans collation complète des corps ni nouveaux scans. 36 notices stratifiées, parfois voisines : pas d’estimation statistique globale.
- Exactitude stricte des deux ID : certains échecs sont un seul titre ou une certification omise ; d’autres fusionnent réellement plusieurs documents. Les deux sont montrés dans CASES. Un gain partiel n’autorise pas l’écriture de la nouvelle plage.
- La grammaire améliore la validité du format ; elle ne corrige ni l’ordre des IDs ni leur attribution documentaire. Le plafond de 240 caractères peut fermer une justification en milieu de mot ; les réponses brutes permettent de le voir. Aucune justification n’est utilisée comme preuve de justesse.

**Décision : ne pas remplacer les frontières A par ces propositions, ni lancer un contrôle LLM massif.** Une éventuelle prochaine campagne limitée devrait changer explicitement la représentation des deux limites et comparer le mode de raisonnement sur de nouvelles références indépendantes. Elle n’a pas été commencée.
