# Registre documentaire expérimental des Archives parlementaires, tomes I–VI

Étude locale du 27 octobre 2026. **Le registre des 1 305 entrées `griev` est construit. La stratégie C est utile pour l’inventaire, mais les frontières ne permettent pas encore une extraction systématique sans contrôle.** Ni l’application, ni PostgreSQL, ni les index n’ont été modifiés. Aucun article ni embedding nouveau n’a été produit. Aucun texte intégral Persée téléchargé.

## Résultats

| Objet | Résultat |
| --- | --- |
| Notices METS rapprochées des notices OAI | 1 305 / 1 305 ; six tomes ; aucune divergence titre/type entre ces deux descriptions |
| Identités automatiques | 964 fortes ; 182 probables ; 75 ambiguës ; 32 non retrouvées ; 52 hors périmètre retenu |
| Nature documentaire automatique | 1 227 cahiers autonomes probables ; 20 documents associés ; 4 PV ; 2 extraits ; 46 listes ; 1 autre document ; 5 notices d’absence |
| Frontières automatiques | 1 236 plages : 988 proposées sans alerte propre, 248 ambiguës ; 69 notices sans plage |
| Contrôle inédit | 100 notices : 69 identités compatibles, 3 fausses propositions, 1 identité incertaine ; 19 abstentions récupérables, 1 abstention non résolue, 1 exclusion erronée, 6 listes sans identité exhaustive examinée |
| Frontières nouvellement contrôlées | 52 conformes / 67 tranchées (77,6 %) ; 15 incorrectes ; 4 autres incertaines ; 29 non évaluées |
| Références de frontières conservées | 78 : 26 héritées + 52 nouveaux contrôles Codex ; aucune validation humaine indépendante |
| Complément Stanford | 92 hypothèses V2 admises sans ancre primaire équivalente Persée ; 55 hypothèses V2 incertaines conservées séparément |
| File de contrôle des notices | 189 hautes, 295 intermédiaires, 821 à contrôler par échantillonnage |

Ces nombres décrivent des **hypothèses**, pas 1 227 cahiers historiquement certifiés. Les 100 cas surreprésentent les difficultés. Le résultat de 77,6 % ne mesure ni tous les documents ni la complétude de leur corps. Quatre frontières supplémentaires incertaines donnent seulement 52 conformes sur 71 examinées, sans assimiler les incertitudes à des réussites. Aucun taux global n’est extrapolé.

## Livrables

- [REGISTRY.md](REGISTRY.md) : schéma, statuts, identifiants et utilisation des plages.
- [ALIGNMENT.md](ALIGNMENT.md) : règles réutilisées, gel et exemples.
- [EVALUATION.md](EVALUATION.md) : référence exploratoire, erreurs et zones indépendantes du catalogue.
- [REVIEW.md](REVIEW.md) : contrôles classés et liste nominative.
- [COVERAGE.md](COVERAGE.md) : couverture et désaccords entre inventaires.
- [REPRODUCIBILITY.md](REPRODUCIBILITY.md) : scripts, empreintes, commandes et droits.
- `data/registry.jsonl.gz` : registre enrichi complet ; `data/registry-automatic.jsonl.gz` : prédictions inchangées.
- `data/annotations.jsonl`, `data/zone-annotations.jsonl` : décisions de lecture, séparées du calcul.

## Réponses aux dix questions

1. **Cahiers autonomes probables :** 1 227 selon la classification automatique ; leur autonomie reste à contrôler. Le titre seul ne permet pas de trancher tous les dossiers composites.
2. **Associés / hors périmètre :** 20 associés + 4 PV + 2 extraits, conservés ; 46 listes + 1 autre + 5 absences classés hors périmètre de recherche. Les contrôles montrent notamment que Turenne doit rester comme annexe et que l’absence du clergé de Chaumont ne vaut pas absence de sa noblesse. Les prédictions originales restent visibles.
3. **Rapprochements forts :** 964, non automatiquement vérifiés.
4. **Ambigus ou introuvables :** 75 + 32. Sur les 20 abstentions nouvelles contrôlées, 19 ont été localisées par une recherche documentaire complémentaire, sans changer l’algorithme. La vingtième reste non résolue, sans preuve d’absence du texte.
5. **Frontières proposées :** 1 236 ; 69 notices sans plage. Une plage peut être trop courte, trop longue ou viser un voisin.
6. **Exactitude contrôlée :** 52/67 frontières tranchées ; 4 incertaines. Contrôle des extrémités dans le TEI par Codex, sans collation intégrale ni validation humaine indépendante.
7. **Documents manquants :** 92 propositions V2 sans équivalent d’ancre, à examiner ; ce ne sont pas 92 omissions avérées de Persée. Les pouvoirs du clergé de Saintonge et le mémoire Goullin sont présents dans Stanford mais non identifiés comme unités dans le registre automatique. Voir les limites de catalogue/dossier dans COVERAGE.
8. **Vérification restante :** 189 notices prioritaires + 295 intermédiaires, puis contrôle stratifié des 821 autres ; ajouter le complément Stanford et les cas incertains. 1 227 notices n’ont aucune référence de frontières contrôlées. Aucun temps humain mesuré et aucune estimation en heures défendable.
9. **Obstacles à l’extraction des articles :** dossiers mêlés dans une division, pièces précédant/suivant le corps, titres internes manqués, homonymes sur une page, OCR et colonnes intercalées. Aucune segmentation massive d’articles n’a été lancée.
10. **Méthode recommandée :** conserver C pour le registre, corriger d’abord les parents prioritaires par décisions versionnées, séparer cahier et pièces liées, faire valider un lot stratifié par un lecteur indépendant, puis autoriser l’extraction des seuls parents dont le périmètre est établi. Garder des abstentions pour les autres. Le registre est exploitable comme outil documentaire, pas comme corpus intégral certifié.
