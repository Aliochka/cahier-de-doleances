# Charge humaine — scénarios conditionnels

## Ce qui est connu

- Environ **15 minutes pour 108 articles** dans les cinq cahiers tirés au sort, sans correction enregistrée.
- Environ **30 minutes pour Terre-Franche, Vic et la noblesse de Mirecourt**, soit 82 articles actuels (78 propositions initiales), avec cinq incidents de nature différente.
- Aucune durée active n’est enregistrée dans les événements Articles. Les dates des clics indiquent une fenêtre chronologique, pas la lecture avant le premier clic, les pauses ou le travail de correction.
- Le journal Cahiers contient 33 événements avec un cumul instrumental de 1 716 secondes environ. Ce compteur d’activité d’interface n’est pas un chronométrage humain certifié, ne porte pas sur les articles et ne permet pas de projeter le coût de contrôle des 1 305 notices.

Les cadences utilisées ci-dessous sont donc **des hypothèses de planification tirées de deux déclarations approximatives** : 8,3 s/article pour le lot sans correction et 22,0 s/article pour les trois dossiers difficiles. Le coût des corrections est inclus dans le second ratio. Le coût varie fortement par cahier, longueur, qualité OCR et interface.

## Vérification systématique

| Articles | Hypothèse 8,3 s/article | Hypothèse 22,0 s/article |
|---:|---:|---:|
| 1 000 | 2.3 h | 6.1 h |
| 5 000 | 11.6 h | 30.5 h |
| 10 000 | 23.1 h | 61.0 h |

Ce sont des scénarios de lecture d’articles, **hors sécurisation des parents**, qualifications C, contrôles indépendants et préparation des lots. Ce ne sont pas des prévisions certaines. Aucun effectif d’articles n’est déduit mécaniquement des 1 305 notices.

## Ciblage seul, puis ciblage + échantillonnage

Formules, pour N articles et une fraction f à vérifier (file **après extension au contexte**, pas seulement les alertes) :

- Ciblage seul : `N × f × 22 secondes`. Les erreurs silencieuses ne sont alors pas mesurées : stratégie déconseillée seule.
- Ciblage + échantillonnage de fraction q des autres : `N × f × 22 + N × (1 − f) × q × 8,3 secondes`.
- Ces formules omettent les coûts fixes et supposent que les cadences observées restent applicables.

Exemple **5 000 articles**, q = 10 % ; f est une hypothèse, pas un taux mesuré sur le corpus complet :

| Part dans la file ciblée | Ciblage seul | Avec 10 % des autres |
|---:|---:|---:|
| 10% | 3.0 h | 4.1 h |
| 25% | 7.6 h | 8.5 h |
| 50% | 15.2 h | 15.8 h |

La file de 40 alertes sur 397 articles restants couvre 69 articles en incluant les voisins, soit 17,4 % du cadre actuel. Cela ne permet pas d’annoncer une fraction ciblée de 17,4 % sur les futurs corpus.

## Application limitée aux 19 cahiers restants

- Régime permanent proposé après calibration : lecture des 69 articles de contexte (sans validation fictive des voisins), puis environ 33 articles tirés parmi les 328 autres. Selon les deux cadences, une hypothèse de charge se situe autour de **24 à 30 minutes**, hors parents et cas C.
- Calibration initiale : 69 articles de contexte + 100 non-alertés distincts + 20 fenêtres parentales. La seule partie articles représenterait environ **40 minutes** sous les hypothèses choisies ; le temps des fenêtres et des éventuels désaccords n’est pas connu. Ce calibrage n’est pas à répéter intégralement sur chaque petit lot.

Ces ordres de grandeur servent à organiser une session, pas à imposer une durée à l’utilisateur. Le temps devra être déclaré ou mesuré au cours de la future campagne, avec séparation entre lecture, correction, vérification du parent et qualification des passages. Des validations par groupe peuvent réduire les clics, mais leur gain de temps **n’a pas été mesuré** ici : toutes les validations observées étaient individuelles.

## Coût des parents

Aucun taux fiable par cahier nouveau n’est disponible. Les frontières constituent une tâche séparée, particulièrement coûteuse pour les documents composites, pages partagées et annexes. Prévoir un poste de charge distinct et mesurer le prochain lot de parents. Ne pas multiplier 3 minutes par 1 305 pour annoncer le coût d’intégration.
