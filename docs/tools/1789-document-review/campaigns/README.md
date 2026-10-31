# Campagne 1 — cinq cahiers supplémentaires

Tirage figé le 31 octobre 2026, à partir des **29 cahiers aux frontières validées humainement**. Les cinq cahiers possédant déjà des événements dans le journal réel des articles ont été exclus, même si leur relecture comporte des incertitudes. Il reste **24 cahiers admissibles**.

Méthode : `random.Random(17892019).sample(sorted(identifiants_admissibles), 5)` en Python, sans remise. Le tirage reçoit uniquement les identifiants : ni nombre d’articles, ni anomalie, ni difficulté présumée. Aucun remplacement effectué.

| Ordre tiré | Cahier | Tome | Articles proposés au tirage | Identifiant Persée |
|---:|---|---:|---:|---|
| 1 | Clergé de la sénéchaussée d’Anjou | II | 80 | `arcpa_0000-0000_1879_num_2_1_1563` |
| 2 | Pierrelez (Paris) | V | 9 | `arcpa_0000-0000_1879_num_5_1_2339` |
| 3 | Lawastine (bailliage de Bailleul) | II | 5 | `arcpa_0000-0000_1879_num_2_1_1612` |
| 4 | Clergé du bailliage de Mirecourt | IV | 5 | `arcpa_0000-0000_1879_num_4_1_1744` |
| 5 | Plessis-Secqueville (Paris) | V | 9 | `arcpa_0000-0000_1879_num_5_1_2348` |

**108 articles proposés au départ**, sans décision humaine sur ces cinq dossiers à la date du tirage. Les A restent des limites examinées antérieurement par Codex, pas des validations humaines. Le cahier du clergé de Mirecourt est distinct de celui de la noblesse déjà examiné.

## Où les ouvrir

Relancer le serveur habituel puis recharger la page :

```sh
python3 docs/tools/1789-document-review/server.py
```

Ouvrir `http://127.0.0.1:1789`, cliquer sur **Articles**, puis utiliser les cinq boutons sous **« Campagne : cinq cahiers tirés au sort »**. Le menu Cahier habituel reste également disponible. Chaque accès affiche le titre, le nombre de propositions au tirage et le statut de vérification courant. Les boutons chargent le document sans créer de décision.

Les propositions d’origine et le segmenteur ne sont pas modifiés. Le panneau de comparaison préexistant conserve sa fonction : ses avertissements sont des hypothèses, pas des corrections confirmées. Examiner le texte avant toute décision.

## Pour préparer le bilan ultérieur

Utiliser les commandes habituelles de validation, séparation, fusion, correction ou incertitude. Dans la remarque d’une correction, préciser si possible : **fusion d’articles**, **séparation à tort**, **petit décalage de frontière**, ou **autre erreur**. Cette indication évite de déduire mécaniquement la gravité de la seule opération enregistrée. Un écart de ponctuation n’est pas assimilé à un article entier manquant ou absorbé.

À la fin, communiquer le temps consacré à ce lot, globalement ou par cahier. Aucun chronométrage humain n’est inventé. Les environ 30 minutes déjà signalées pour Terre-Franche, Vic et la noblesse de Mirecourt concernent le lot précédent.

Le bilan n’est **pas réalisé maintenant**. Il comparera les unités initiales et les décisions postérieures au point de départ enregistré (238 événements), en tenant compte des annulations et du statut final. Les validations groupées sont comptées par article, pas par clic. Les corrections n’étant pas toujours diagnostiquables automatiquement, leur type et leur gravité devront être contrôlés dans le contexte.

## Provenance et reprise

`five-cahiers.json` conserve la graine, la version Python, les 29 parents, les cinq exclusions, les 24 admissibles, les cinq identifiants tirés et les empreintes des données initiales. `draw_five.py` reproduit le tirage mais refuse de remplacer le fichier figé : ne pas supprimer celui-ci pour retirer un cas difficile.

Une copie privée du journal initial et des unités initiales sélectionnées est conservée sous `../.local/campaigns/five-cahiers-01/`, ignorée par Git. Les décisions ultérieures restent dans le journal habituel, jamais dans les fichiers sources. Aucun événement de test n’est ajouté au journal réel.

Ce petit lot oriente les prochaines décisions ; il ne permettra pas d’estimer fiablement la qualité des 1 305 notices. Aucun bilan, aucune extraction, aucun embedding ou accès PostgreSQL n’est réalisé pendant cette préparation.
