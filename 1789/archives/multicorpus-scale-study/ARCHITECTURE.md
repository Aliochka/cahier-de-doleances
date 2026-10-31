# Conséquences pour le futur moteur

L'étude ne démontre pas qu'une récupération par corpus soit nécessaire pour obtenir de bonnes premières pages. Elle démontre que la faible profondeur globale peut rendre indisponibles des passages historiques jugés pertinents, et qu'enrichir les candidats ne résout pas automatiquement leur classement. Les options ci-dessous sont des propositions, aucune intégration n'a été réalisée.

| Option | Bénéfices | Limites et risques | Coût et nouveaux corpus |
|---|---|---|---|
| A — Recherche globale simple | Scores et statistiques communs, simplicité, aucune règle par époque ; bonnes premières pages contemporaines observées ; la gabelle reste première | Top 50 peu couvrant pour les témoins ; hausse uniforme jusqu'à 1 000 sans gain final au million ; sensibilité au lexical et au déséquilibre des populations | Un mécanisme par branche, ajout d'un corpus sans nouvelle logique de quotas ; performances ANN et statistiques globales à valider |
| B — Récupération par corpus, classement commun | Couverture des témoins presque complète même à faible L ; récupération spécialisée possible pour des structures documentaires différentes | Pas de gain démontré du top 10 ; davantage de candidats à L égal ; rangs locaux non comparables, omissions de contemporains possibles ; notre oracle de rang global n'est pas acquis dans une fédération réelle | Récupérations et orchestration croissent avec le nombre de corpus ; nécessité de scores communs ou d'un reclassement réellement comparable ; intégration plus complexe |
| C — Référence globale avec budget de récupération ajusté et contrôle du classement | Réutilise le moteur et garde le classement global ; permet des expériences bornées sur le rappel, puis sur les faux positifs | Un seuil plus haut ne suffit pas ; aucun déclencheur de profondeur adaptative n'est validé ici ; un reclassement supplémentaire reste une hypothèse à tester | Peut rester proche du chemin existant ; coût à mesurer sur les véritables index, sans exception liée à 1789 |

## Ce que montre la variante distribuée

Nous prenons L candidats dans chaque corpus et chaque branche, puis appliquons RRF avec les **rangs dans la population complète**. Un premier résultat historique ayant le rang global 10 000 reçoit `1/(60+10000)`, jamais `1/61`. Les contributions ne sont attribuées que dans les branches où le passage est effectivement candidat. Il n'y a pas de quota de sortie.

Cette expérience est volontairement plus prudente qu'une fusion de classements de corpus indépendants. Elle reste un contrôle de couverture qui connaît les rangs globaux grâce au calcul exact. Dans un système distribué, obtenir ces rangs peut nécessiter de compter ou récupérer beaucoup de documents ; reclasser seulement le pool avec des rangs compressés ne reproduit pas la présente méthode. Une autre option serait un score commun de pertinence applicable à tous les candidats, mais aucun nouveau modèle ni normalisation n'a été testé ici.

Les 57 témoins du top 100 distribué 50 au million ne prouvent pas une meilleure liste que les 18 de globale 50 : les pools diffèrent en taille et omettent des contemporains potentiellement mieux classés. Avec L=100, la distribuée reste à 270 témoins candidats mais retombe à 18 dans le top 100. Le budget augmente donc la concurrence au sein du pool. **La couverture doit être mesurée avant le classement ; la pertinence doit être mesurée après.**

Les fusions elles-mêmes restent peu coûteuses en mémoire sur cette machine : environ 0,49 ms pour globale 50 et 0,57 ms pour distribuée 50, jusqu'à 8,12 ms pour distribuée 1 000. Ces chiffres excluent l'obtention des rangs et toute inférence. Ils ne suffisent pas à estimer le coût d'une architecture multi-index.

## Recommandation à ce stade

Conserver la recherche globale comme référence et le principe d'une liste unique. Ne pas ajouter de bonus historique, de quotas de sortie ni de fusion naïve de premiers rangs par corpus. Ne pas généraliser L=1 000 à partir d'un gain de couverture qui ne se transforme pas en meilleures premières pages.

Garder la récupération distribuée comme variante de validation, pour les corpus de tailles et de structures différentes. Son adoption demanderait une amélioration démontrée à budget voisin et une méthode réalisable de classement commun. Une exception dédiée aux seuls cahiers de 1789 rendrait l'extension à d'autres consultations inutilement fragile.

L'option C représente le chemin d'étude le moins intrusif : mesurer séparément les défauts des candidats et ceux du classement du moteur existant, puis tester une modification à la fois. Elle ne constitue pas un paramétrage prêt à déployer.

## Mission complémentaire limitée, non commencée

1. Figer de nouvelles requêtes de validation, sans ajuster leurs formulations aux classements, et un petit ensemble de passages témoins vérifiés indépendamment. Inclure les difficultés historiques et des sujets uniquement contemporains.
2. Reprendre le million local existant et deux autres tirages indépendants, sans nouvel encodage massif. Distinguer variation de sélection et effet de taille ; garder une comparaison conditionnelle qui inclut les 240 réponses de référence.
3. Dans un espace expérimental séparé, comparer le BM25 actuel de l'audit à la recette lexicale PostgreSQL publique. Tester les candidats de l'ANN locale contre le classement exact, en lecture seule et avec charge bornée. La perte d'ANN doit être isolée de la concurrence sémantique et de la troncature RRF.
4. Comparer des budgets totaux proches pour globale et distribuée. Si une variante de classement commun est proposée, fixer sa règle avant les nouveaux jugements ; ne pas remplacer implicitement les rangs globaux par des rangs locaux.
5. Faire juger en aveugle, par des lecteurs indépendants, un pool de concurrents contemporains, de témoins conservés et de témoins relégués. Mesurer accord entre juges, pertinence des premières pages et rappel sur témoins séparément. Ne pas prétendre à un rappel exhaustif.
6. Mesurer mémoire, latence et concurrence des véritables chemins techniques hors production. Décider ensuite si une profondeur différente ou une récupération distribuée justifie sa complexité.

Cette prochaine expérience testerait le mécanisme applicatif réel, au lieu d'extrapoler directement les résultats de fichiers en mémoire. Aucune de ces opérations n'a été lancée dans cette mission.
