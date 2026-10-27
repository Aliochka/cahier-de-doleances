# Méthode de rapprochement

## Réutilisation et gel

Les six METS de l’étude précédente fournissent le cadre de 1 305 notices. Les 90 notices DC cibles déjà en cache ont été réutilisées, puis 73 requêtes OAI de métadonnées ont complété les champs (voir journal). Les pages `ListRecords` sont suivies avec le **jeton opaque retourné**, sans reconstruire un curseur ; un `GetRecord` ciblé complète la couverture résiduelle. 1 305 notices DC obtenues, toutes de type `griev`, titres cohérents avec METS après retrait des blancs externes. Aucune inférence depuis un HTML de portail ni récupération TEI.

La révision Stanford est `926fd3cd986a3c3d411e93d1845fff6475cb2602`. Sources locales vérifiées, aucune réécriture. Le helper `Source`, la construction des feuilles XML, l’index de pages, les scores titre/contexte et les propositions de frontières sont **réutilisés par import en lecture** depuis l’audit précédent. Aucun ancien `main()` exécuté.

Les adaptations du développement sont dans `registry_rules.py` : conservation du mot « tiers », conflit explicite entre ordres, ajout limité du début de corps pour un titre purement générique, soutien V2 seulement avec indice de titre/corps. Elles ne résolvent pas tous les titres internes. Les seuils restent 0,62 et 0,78, marge 0,10 ; score initial = 0,55 couverture titre + 0,10 contexte + 0,35 même page, avec pénalités d’ordre et de rubriques. Le contexte historique original n’est jamais modifié par cette normalisation de **comparaison**.

Les 72 cas antérieurs restent du développement. Règles, sources, paramètres, 100 identifiants et 12 zones sont figés dans `data/freeze.json` **avant ouverture des nouveaux packs**. Les règles n’ont pas été modifiées après lecture. Les corrections figurent seulement dans les annotations et localisations complémentaires.

## Décision et abstention

Le générateur conserve cinq alternatives, pas seulement la première trouvée. Une identité forte exige titre propre suffisamment couvert, score et marge concordants, sans conflit d’ordre. Les quasi-ex æquo restent ambigus ; un soutien V2 unique avec indice partiel peut proposer un résultat probable. Les pages réduisent l’espace de recherche, mais ne certifient jamais une identité. Les propositions partageant une même ancre sont signalées : 24 notices concernées, sans appariement un-à-un forcé.

Lors du repli sur V2, la marge conservée reste celle du classement initial avant repli : elle ne mesure pas l’écart du candidat substitué. Ne pas l’utiliser comme certification ni comme probabilité. Les scores et alternatives restent inspectables.

Le voisinage est conservé pour l’inspection, pas utilisé pour inventer des limites. Les entités homonymes restent à trancher, notamment Marolles et Marolles-en-Hurepoix sur la même page. La recherche de paragraphes internes exige encore des marqueurs documentaires et une longueur limitée ; des titres « Copie », « Déclaration » ou OCR trop abîmés peuvent échapper aux propositions.

## Frontières : traitement séparé

Le début proposé suit l’ancre XML ou le titre interne. La fin suit la feuille puis, dans certains cas, des sections voisines compatibles avec la pagination. Un nouveau titre littéral CAHIER peut arrêter la plage. Ce mécanisme est réutilisé tel quel avec ses limites : « SECONDE PARTIE » peut manquer, ou un CAHIER interne appartenant au dossier être pris pour une fin.

Les 1 236 plages se répartissent initialement en 988 proposées sans alerte et 248 ambiguës. **L’absence d’alerte n’est pas une preuve d’exactitude.** La fin d’Aix clergé absorbe la noblesse ; Châtellerault clergé s’arrête avant son propre cahier ; les deux parties Valenciennes ne sont pas réunies. L’identité peut être correcte dans chacun de ces cas.

Ni les annexes, ni les signatures, ni les notes ne sont supprimées. Les composants XML identifiables sont référencés ; la séparation définitive n’est pas prétendue résolue. Les colonnes intercalées en Artois ne se corrigent pas par un simple déplacement de borne.
