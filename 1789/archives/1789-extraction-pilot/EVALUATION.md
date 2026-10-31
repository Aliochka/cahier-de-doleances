# Évaluation documentaire et technique

Générée depuis les résultats calculés. Référence XML revue par Codex ; cinq contrôles visuels partiels, aucune validation humaine indépendante. Les scores concernent des fenêtres de développement choisies intentionnellement, pas un échantillon représentatif ni un test aveugle.

## Frontières des parents

Sur 30 débuts présélectionnés, 29 étendues automatiques concordent avec la référence XML ; 1 nécessite une correction (Beaurecueil). Après décision, 0 frontière de parent reste non résolue dans le périmètre TEI retenu. La complétude historique des manuscrits n’est pas mesurée.

La simple prise du premier `div3` donnerait 26 étendues conformes. Trois regroupements sont nécessaires (Anjou, Mirecourt, Ferrières), et un cahier doit être coupé à l’intérieur d’une division. Le rappel de découverte des cahiers dans six volumes entiers n’est pas connu.

## Avant corrections : unités et frontières

37 fenêtres A entièrement annotées pour leur périmètre d’articles, 269 unités de référence ; une fenêtre B exclue. Les fenêtres sans articles sont conservées, les erreurs et unités manquées sont comptées. 262 propositions automatiques commencent dans ces fenêtres. Leurs fins peuvent dépasser le périmètre contrôlé, ce qui ne les rend pas exactes.

| Mesure | Corrects | Faux positifs | Manqués | Précision | Rappel |
|---|---:|---:|---:|---:|---:|
| Débuts (offset exact) | 259 | 3 | 10 | 98,9 % | 96,3 % |
| Fins (offset exact) | 252 | 10 | 17 | 96,2 % | 93,7 % |
| Unités (couple début/fin exact) | 244 | 18 | 25 | 93,1 % | 90,7 % |

Calcul : précision = corrects / propositions ; rappel = corrects / référence. Les débuts et fins sont comparés comme ensembles d’offsets. Une fusion peut avoir un début et une fin chacun présents dans la référence, mais associés à deux articles différents ; seule la mesure par couple vérifie alors la bonne unité. Les décalages de ponctuation sont comptés comme erreurs strictes, même quand le contenu lexical est proche.

Les prédictions brutes ne bénéficient ni des affectations déclaratives de paragraphes ni du remplacement par les plages de référence. Les règles ont néanmoins été développées sur ces documents : ce résultat n’est pas une estimation indépendante de généralisation. Les modifications du référentiel sont documentées dans `review-log.json`.

## Après revue : statut du corpus

759 candidats : **269 A (35,4 %)**, **490 B**, et **187 plages C non assimilées à des articles**. Les 30 textes parents sont conservés.

Couverture A : 60695 caractères non blancs sur 320547 dans tous les parents, soit **18,9 %**. Le dénominateur inclut titres, notes, signatures, annexes et préambules ; il ne représente pas seulement les revendications. L’indentation XML ne pèse pas dans cette mesure.

Le corps numéroté est entièrement vérifié pour 13 cahiers : lawastine-tiers, ribaucourt, flines, carces-mineurs, annet-marne, ermenonville, mirecourt-clerge, pierrelez-habitants, perigny-brie, plessis-secqueville, puteaux, albertas, beaurecueil. Les autres corps numérotés ne sont vérifiés que par fenêtres. Agen tiers et Lourmarin n’ont aucun article retenu ; leur prose reste accessible dans les parents et les plages C.

La correspondance de chaque A avec la référence est contrôlée automatiquement. Afficher 100 % après remplacement par cette référence serait tautologique ; aucun nouveau taux indépendant après correction n’est annoncé.

## Résultats par cahier

| Cahier | Candidats bruts | Après revue | A vérifiés | B non certifiés | Frontière parent |
|---|---:|---:|---:|---:|---|
| agen-clerge | 69 | 70 | 9 | 61 | conforme |
| agen-noblesse | 66 | 59 | 3 | 56 | conforme |
| agen-tiers | 0 | 0 | 0 | 0 | conforme |
| alencon-clerge | 85 | 86 | 5 | 81 | conforme |
| alencon-noblesse | 12 | 12 | 2 | 10 | conforme |
| angoumois-noblesse | 56 | 56 | 5 | 51 | conforme |
| anjou-clerge | 80 | 80 | 18 | 62 | conforme |
| annonay-clerge | 31 | 31 | 13 | 18 | conforme |
| beaujolais-noblesse | 23 | 32 | 15 | 17 | conforme |
| lawastine-tiers | 5 | 5 | 5 | 0 | conforme |
| colmar-ville | 36 | 36 | 8 | 28 | conforme |
| ribaucourt | 10 | 11 | 11 | 0 | conforme |
| flines | 13 | 13 | 13 | 0 | conforme |
| carces-mineurs | 8 | 8 | 8 | 0 | conforme |
| montigny-ostrevent | 15 | 19 | 11 | 8 | conforme |
| mirecourt-noblesse | 25 | 25 | 13 | 12 | conforme |
| guerande-tiers | 27 | 27 | 8 | 19 | conforme |
| ferrieres | 25 | 25 | 24 | 1 | conforme |
| annet-marne | 15 | 15 | 15 | 0 | conforme |
| ermenonville | 12 | 12 | 12 | 0 | conforme |
| mirecourt-clerge | 5 | 5 | 5 | 0 | conforme |
| pierrelez-habitants | 9 | 9 | 9 | 0 | conforme |
| perigny-brie | 15 | 15 | 15 | 0 | conforme |
| plessis-secqueville | 9 | 9 | 9 | 0 | conforme |
| puteaux | 11 | 11 | 11 | 0 | conforme |
| vic-clerge | 42 | 42 | 8 | 34 | conforme |
| toul-noblesse | 34 | 34 | 2 | 32 | conforme |
| albertas | 9 | 9 | 9 | 0 | conforme |
| beaurecueil | 3 | 3 | 3 | 0 | corrigée |
| lourmarin | 0 | 0 | 0 | 0 | conforme |

## Suivi des propositions et exclusions

Sur 750 propositions initiales :

- `unchanged_verified_A` : 244.
- `boundary_changed` : 72.
- `unchanged_unverified_B` : 427.
- `excluded_by_structure_review` : 7.

Les 7 exclusions d’articles autonomes correspondent à la citation du conseil royal dans le préambule d’Agen noblesse, conservée dans le texte parent. Les 72 frontières modifiées ne désignent pas 72 articles désormais certifiés : une modification de rôle documentaire peut également affecter une proposition restant B. Les passages ajoutés ou scindés sont traçables dans les objets de référence et les relations du registre de revue.

Six cas négatifs distincts sont exclus comme parents autonomes. Ils ne sont pas ajoutés au dénominateur des 30. La liste des erreurs exactes et leurs textes est conservée dans `data/boundary-errors.json` ; l’analyse des causes se trouve dans `PROBLEMS.md`.

## Effort observé et durées

- Correction de frontière parent : 1.
- Décisions déclaratives de rôles/plages documentaires : 185, modifiant le rôle de 344 paragraphes.
- Unités A contrôlées dans les fenêtres : 269.
- Parsing et calcul des positions pour les six XML : 1.166 s.
- Extraction et écritures du corpus, parsing compris : 1.716 s ; CPU 1.716 s.
- Exécution mesurée : `2026-10-26T10:26:45.586997+00:00`.
- Téléchargement, revue documentaire et temps humain : hors de cette durée automatique. Aucun temps humain de validation mesuré, aucun historien intervenu.

La mise au point initiale et la revue du lot n’ont pas été chronométrées séparément. Les nombres de décisions ne peuvent donc pas être convertis en heures par cahier ou en coût de traitement général. Prévoir un journal opérateur sur un prochain lot indépendant, avec tâches et durées distinctes.

## Portée des contrôles

La reconstruction des textes, les empreintes, les intervalles, les références XML, les parents, les notes séparées, l’ordre et les voisins passent les contrôles. Sept fautes injectées sont détectées. Les 50 fichiers des anciens audits sont inchangés. La reproductibilité des données est vérifiée sur deux exécutions, hors durées et horodatages. Ces garanties techniques n’équivalent pas à la validation documentaire des B.

Les cinq contrôles image sont ponctuels, sans mesure exhaustive de CER/WER. Le taux de cahiers manquants, le nombre total d’articles réels dans les 30 parents et la fréquence des difficultés sur tout Stanford ne sont pas établis. Aucune extrapolation de précision ou de temps humain n’est justifiée.
