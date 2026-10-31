# Bilan humain et contrôle qualité des articles de 1789

## Conclusion

**Passer à une vérification ciblée accompagnée d’un échantillonnage est raisonnable ; considérer immédiatement les articles sans alerte comme fiables ne l’est pas.** Le journal confirme les dix cahiers, les 108 acceptations sans correction du lot tiré au sort, mais montre aussi des fusions importantes sans alerte directe.

Le présent travail analyse les données existantes. Il ne développe pas de nouveau segmenteur, ne modifie aucune décision, ne lance aucune extraction, aucun modèle de langage, aucun embedding ni accès PostgreSQL.

## Mesures vérifiées

| Mesure | Résultat |
|---|---:|
| Cahiers avec décisions d’articles | 10 |
| Articles actuels validés ou corrigés humainement | **333** |
| Articles conservés sans changement | **308** |
| Articles actuels corrigés ou créés | **25** |
| Propositions initiales modifiées | 14 |
| Articles ajoutés | 11 |
| Validations individuelles enregistrées | 317 opérations |
| Validations groupées enregistrées | **0** |
| Incidents après regroupement des opérations complémentaires | 15 |
| Fusions étayées dans le texte | **9** |
| Séparations incorrectes enregistrées | 0 |
| Articles encore incertains dans ces dix dossiers | 0 |

Les 317 validations touchent 312 identifiants distincts ; certaines ont été répétées ou suivies d’une correction. Le total humain actuel résulte du rejeu de l’historique, pas d’une addition des clics. Les décisions de frontières parentales ne sont pas comptées parmi les validations d’articles.

### Deux groupes à ne pas confondre

- **Cinq premiers, orientés développement/difficultés :** 214 propositions initiales, 225 articles actuels, 200 sans changement, 25 corrigés/créés. Ce n’est pas un échantillon représentatif.
- **Cinq tirés au sort :** 108 propositions, **108 acceptées sans correction enregistrée**, environ 15 minutes déclarées. Le tirage portait sur 24 cahiers aux parents déjà validés ; 80 des 108 articles proviennent d’Anjou. Ce résultat ne démontre pas un taux d’erreur nul dans la collection.

Le bilan détaillé par cahier et la distinction entre corrections, ajouts, validations répétées et incertitudes résolues figurent dans [HUMAN-REVIEW.md](HUMAN-REVIEW.md).

## Ce que les corrections révèlent

Les 27 opérations de modification sont regroupées en **15 incidents** : neuf fusions, un petit déplacement de frontière, une rubrique absorbée, un numéro seul et trois autres cas documentaires. Dix incidents sont graves et étayés : neuf fusions et une omission d’article. Le cas d’un numéro 2 absent du TEI à Mirecourt reste une interprétation humaine de subdivision, conservée comme telle.

Les neuf fusions établies concernent la reconnaissance de marqueurs numériques ou de leur contexte OCR. Mais l’article 6 du clergé d’Agen était pris pour une rubrique ; des titres et une prose de mandat ont aussi été absorbés. **Un numéro manquant n’est donc ni l’unique cause, ni une preuve suffisante d’erreur.** Voir [ERRORS.md](ERRORS.md).

## Ce que les alertes permettent réellement

Sur les dix incidents graves connus :

- ancienne alerte directe : **2/10** ;
- alerte directe avec l’extension automatique : **7/10** ;
- proposition de marqueur, y compris dans C : **8/10** ;
- file élargie aux voisins + marqueurs C : **10/10 rétrospectivement**, principalement sur des cas de développement.

Ce dernier chiffre **n’est pas un rappel indépendant**. Il justifie de tester la lecture en contexte, pas de déclarer le problème résolu. Les deux fusions sans alerte directe sont `A:rt. 32.` à Vic et `4°\\Que…` à Mirecourt. Une note Codex existe pour Vic ; elle n’est pas comptée comme détection automatique.

Le saut 14° → 16° à Anjou a produit une alerte mais aucune correction : une rupture peut être légitime dans le texte disponible. Voir [DETECTION.md](DETECTION.md).

## Proposition opérationnelle

1. Conserver les **333 articles humains** comme références prioritaires et comme premier lot possible pour une expérience locale après contrôle d’intégrité.
2. Sur les **19 cahiers restants**, les contrôles actuels signalent 40 des 397 articles. Avec leurs voisins immédiats, la file concerne **69 articles**, sans les valider automatiquement.
3. Calibrer le tri sur un tirage distinct de **100 parmi les 328 autres articles**, avec des fenêtres de texte parent/C pour rechercher les articles totalement manqués. Les dix cahiers déjà examinés sont exclus de cette validation.
4. Après calibration satisfaisante, vérifier les cas suspects et leur contexte, puis maintenir un contrôle reproductible d’environ **10 % des autres unités**, à ajuster selon les résultats.
5. Étendre par petits lots de **20 à 30 nouveaux parents établis**, en conservant les documents associés, les incertitudes et toutes les versions. Ne pas traiter les 1 305 notices comme autant de cahiers autonomes certifiés.

Les catégories proposées sont : candidat à faible risque, à vérifier, bloqué/incertain. L’absence d’alerte n’est qu’un critère de prétri ; les notes, rubriques, omissions et frontières parentales doivent aussi être contrôlées. [QUALITY-STRATEGY.md](QUALITY-STRATEGY.md) détaille la chaîne et la distinction expérimentation/publication ; [SAMPLING.md](SAMPLING.md) fixe un protocole et des seuils **proposés, non mesurés**.

## Effort humain

Deux déclarations servent uniquement d’hypothèses : environ 15 min/108 articles sans correction et 30 min/82 articles actuels des trois dossiers difficiles. Elles correspondent à environ 8,3 et 22 secondes par article, sans prétention de cadence stable.

À titre conditionnel, vérifier systématiquement 5 000 articles représenterait environ **12 à 31 heures**, hors parents. Avec 25 % dans une file ciblée et 10 % des autres contrôlés, le scénario donne environ **8,5 heures**, toujours hors parents et contrôles fixes. La fraction de 25 % est une hypothèse : elle n’est pas mesurée pour les six volumes. Voir [WORKLOAD.md](WORKLOAD.md).

## Réponses aux dix questions

1. **Combien validés humainement ?** 333 articles actuels, en incluant les corrections humaines ; pas 346 événements ni 29 décisions parentales.
2. **Combien corrigés ?** 14 propositions initiales modifiées et 11 créations, soit 25 articles actuels corrigés/créés ; 27 opérations regroupées en 15 incidents, de gravités différentes.
3. **Erreurs récurrentes ?** Fusions par marqueurs OCR dégradés, puis confusions de rôle/prose et quelques décalages.
4. **Principalement les numéros ?** Oui pour les neuf fusions établies ; non pour tous les autres incidents. Un saut ou une reprise ne prouve pas une erreur.
5. **Quelle proportion signalée ?** 2/10 incidents graves avec les anciennes alertes directes, 7/10 avec les alertes automatiques directes actuelles ; couverture rétrospective, pas rappel indépendant.
6. **Catégorie peu anormale identifiable ?** Un réservoir de 357 articles non signalés parmi les 397 restants existe ; 328 restent hors de la file élargie de contexte. Leur faible risque doit encore être évalué.
7. **Risques silencieux ?** Marqueurs hors motifs connus, article totalement absent de la liste, rôle éditorial erroné, interprétation de prose et périmètre parental incorrect.
8. **Quel volume humain ?** D’abord un calibrage limité, puis ciblage et échantillonnage. Les scénarios chiffrés sont conditionnels et séparent parents/articles.
9. **Organisation des nouveaux cahiers ?** Petits lots, parents établis, règles et données figées, anomalies en contexte, échantillon indépendant et arrêt en cas de défaut grave silencieux.
10. **Avant une indexation plus large ?** Intégrité parfaite, décisions humaines préservées, parents compatibles, cas non résolus exclus, calibration distincte satisfaisante, statuts explicites et première montée en charge locale plafonnée. Une publication demande une validation supplémentaire sur de nouveaux parents.

## Reproduction et protection des données

```sh
python3 1789/archives/1789-human-review-quality/analyze.py
python3 1789/archives/1789-human-review-quality/check.py
```

Utilise Python/lxml déjà disponibles et les utilitaires existants. Les journaux Articles et Cahiers sont figés dans `.local/`, ignoré par Git. Une réexécution réutilise ces instantanés ; elle ne modifie pas la période analysée pour inclure silencieusement de nouvelles décisions.

`annotations.json` contient la classification des 27 modifications, avec leurs identifiants d’événements mais sans noms de lecteurs ni remarques privées. `data/cahiers.json`, `errors.json`, `detection.json`, `summary.json` et `strategy-plan.json` conservent les mesures et hypothèses. Le fichier détaillé `data/triage.json` reste local et reproductible ; ses catégories sont des prétris non certifiés, sans effet sur l’interface.

`data/provenance.json` et `checks.json` donnent empreintes, versions et contrôles. Les contrôles de chaîne, couverture, unicité du rattachement des modifications, cohérence des totaux et préservation des sources/journaux ont été exécutés. Aucun bilan de validation indépendante ni gain de temps de validation groupée n’a été inventé.
