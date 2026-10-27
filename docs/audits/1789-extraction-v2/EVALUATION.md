# Évaluation V1/V2

## Protocole effectivement suivi

1. Enregistrement de [24 candidats et 12 zones](validation-plan.json) avant finalisation des règles. Exclusion conservatrice des divisions des 30 parents du pilote, des 170 candidats sélectionnés en V1, des anciennes fenêtres négatives et de Pecqueuse.
2. Finalisation sur le développement seulement puis [gel des règles](rules-freeze.json).
3. Lecture des packs **sources seuls**, sans classements V2 nouveaux. Chaque zone comprend deux divisions feuilles consécutives complètes, soit 24 divisions sources, y compris listes nominatives et règlements sans cahier. Les 12 zones ont été lues intégralement. Pour les candidats séparés : titre, ouverture, courtes rubriques, clôture et contexte voisin, **pas collation intégrale de tous les longs corps**.
4. Création de [références déclaratives](annotate_reference.py), puis [gel des références](reference-freeze.json), avant prédictions nouvelles.
5. Comparaison aux hypothèses V1 archivées sur l’ensemble des six volumes, puis aux prédictions V2 gelées. Les seuils et règles n’ont pas été ajustés sur les erreurs nouvelles.

Un défaut de nouveauté a été découvert pendant la lecture source : Albret absent appartenait déjà aux cas négatifs du premier pilote. Il est conservé comme témoin connu et **exclu des performances nouvelles**. Une réserve déterministe supplémentaire est enregistrée dans [novelty-amendment.json](novelty-amendment.json). Aucun autre candidat nouveau éligible du même cadre ne restait au volume I : réserve prise au volume II, par empreinte et sans prédiction. Au total : **25 candidats enregistrés, dont 24 réellement nouveaux**, répartis sur les six volumes (3, 5, 4, 4, 4, 4). Les douze zones n’ont pas changé. L’enregistrement initial est conservé, pas réécrit.

La sélection par empreinte est indépendante des prédictions, mais stratifiée à partir d’indices lexicaux bruts, de la longueur et du volume : **pas un échantillon représentatif de tous les cahiers**. Les strates ont un repli quand elles sont vides; les étiquettes `strong_long` ne garantissent donc pas un long texte au volume I. Les candidats connus ne servent pas à annoncer la généralisation.

La référence est établie par Codex : séparation procédurale du développement, **pas validation humaine indépendante, ni test aveugle indépendant**. Pas de nouvelle vérification des fac-similés : les résultats portent sur la transcription XML et son organisation, pas sur l’exactitude de l’OCR par rapport à l’imprimé.

## Découverte

| Périmètre | Version | VP | FP | Manqués | Précision locale | Rappel local |
|---|---|---:|---:|---:|---:|---:|
| 24 candidats nouveaux, autonomes | V1 | 15 | 1 | 0 | 93,8 % | 100,0 % |
| 24 candidats nouveaux, autonomes | V2 | 14 | 0 | 1 | 100,0 % | 93,3 % |
| 24 candidats nouveaux, autonomes + associés | V1 | 16 | 0 | 2 | 100,0 % | 88,9 % |
| 24 candidats nouveaux, autonomes + associés | V2 | 16 | 0 | 2 | 100,0 % | 88,9 % |
| 12 zones continues, autonomes | V1 | 12 | 0 | 1 | 100,0 % | 92,3 % |
| 12 zones continues, autonomes | V2 | 12 | 0 | 1 | 100,0 % | 92,3 % |
| 12 zones continues, autonomes + associés | V1 | 12 | 0 | 3 | 100,0 % | 80,0 % |
| 12 zones continues, autonomes + associés | V2 | 12 | 0 | 3 | 100,0 % | 80,0 % |


Dans les 24 candidats, la référence comporte 15 cahiers autonomes, 3 pièces associées et 6 cas négatifs/parties. La V1 ne distingue pas les pièces associées : Grasse était un faux autonome. La V2 évite cet autonome abusif mais classe Courtiches comme associé, perdant un vrai autonome. Le gain de précision est donc **conditionnel à ce petit lot et accompagné d’une baisse de rappel strict**. Dans le périmètre inclusif, aucun gain net n’est démontré.

Les zones continues contiennent 13 débuts de cahiers autonomes et 2 débuts de pièces associées. Cinq zones n’ont aucun nouveau début (dont une continuation de cahier). Les deux versions trouvent 12/13 autonomes et 12/15 documents inclusifs, sans faux positif dans ces zones. Ce rappel est **exhaustif pour les débuts recensés dans ces seules zones**, jamais un rappel global des six volumes. Les instructions des Minimes et les deux pièces de La Rochelle restent manquées.

Pour les 12 autonomes retrouvés dans les zones, **12 débuts et 12 fins sont exacts dans les deux versions**; aucune fusion ou troncature parentale supplémentaire n’y est observée. Cela n’inclut pas les parents manqués et ne démontre aucun gain sur les fins. Les fins des longs candidats séparés ne sont pas certifiées et ne figurent pas dans ce dénominateur. Les sous-classes `associated/part/out_of_scope` ont des erreurs même lorsque la décision binaire d’admission est correcte.

## Articles sur les documents nouveaux

79 unités de référence ont été délimitées par lecture du XML, sur treize parents des zones continues. Les fenêtres couvrent débuts ordinaux, marqueurs corrompus, articles sur plusieurs `p`, plusieurs articles dans un `p`, changement de page, note et clôture. Elles sont choisies pour varier les structures, pas pour mesurer un taux représentatif de tous les articles.

| Version | Références | Bornes toutes deux exactes | Débuts exacts | Fins exactes | Couverture du texte revu par unités exactes |
|---|---:|---:|---:|---:|---:|
| V1 | 79 | 68 (86,1 %) | 73 | 73 | 86,9 % |
| V2 | 79 | 69 (87,3 %) | 74 | 72 | 87,2 % |


Cette comparaison utilise les **mêmes parents de référence** pour isoler le segmenteur : c’est une mesure conditionnelle, **pas la performance de bout en bout du détecteur**. Les instructions des Minimes sont segmentées dans ce contrôle alors que le détecteur n’en admet pas le parent. Le fichier [article-boundary-comparison.jsonl](data/article-boundary-comparison.jsonl) permet de retrouver chaque décision et chaque prédiction.

La V2 gagne les articles 13 et 14 des Enfants Rouges par affectation du tiret au bon article, mais **perd l’article 2 de Grigny** : « Cela fait bien du tort pour la deuxième coupe. » est pris pour une rubrique et détaché de l’article. Bilan net : +1 unité exacte, avec une vraie régression nouvelle. Les neuf écarts de développement résiduels ne sont pas ces dix erreurs nouvelles : ce sont des périmètres distincts.

Parmi les dix références non exactes V2 : 5 débuts manquent; 7 ont au moins une prédiction débordante et 2 une prédiction tronquée. Ces catégories se recouvrent et leur somme n’est pas un nombre d’articles. Le fichier conserve les recouvrements, plutôt qu’une attribution forcée à une cause unique. Les faux débuts en dehors des fenêtres ne sont pas tous annotés : **aucune précision globale des propositions d’articles n’est annoncée**.

## Difficultés concrètes

| Cas | Structure source observée | Résultat / cause |
|---|---|---|
| Grigny, IV `div2[18]/div3[175]/p[5–6]` | Article 2 suivi de « Cela fait… » | V1 exact, V2 tronqué : règle nominale trop permissive |
| Saint-Nom, V `div2[1]/div3[68]/p[7]` | `Ar . 6.` | Marqueur non reconnu; fusion avec art5 |
| Sainte-Aulde, V `div2[1]/div3[54]/p[17]` | `Ar.t. 12.` | Marqueur non reconnu; art12 manqué |
| Minimes, VI `div2[52]/div3[5]/p[14]` | `Ant, 17.` | Marqueur OCR non reconnu |
| Avesnes régulier, II `div2[12]/div3[2]/p[4–5]` | Le paragraphe suivant réclame la pragmatique sanction, sans numéro visible | Fusion de deux propositions documentaires; la référence ne rétablit aucun chiffre manquant |
| Enfants Rouges, VI `div2[52]/div3[4]/p[36]` | Clôture OCR `Glos et arrêté` | Clôture absorbée par art40 |
| Saint-Ouen, V `div2[1]/div3[69]/p[2]` | `Arl. 1er.` | Début manqué |
| Avesnes séculier, II `div2[12]/div3[1]/p[10–13]` | Art9 interrompu par une note, son fragment `Archives de l Empire.` dans un `p` | Bornes exactes ne garantissent pas la pureté du texte de lecture |
| Saint-Prix et Saint-Nom | Notes éditoriales à l’intérieur de paragraphes ordinaires | Fidélité au TEI conservée, séparation éditoriale non certifiée |

La qualification de p5 d’Avesnes comme proposition séparée est appuyée par son contenu distinct mais sa numérotation manque. Elle reste une difficulté documentaire, pas la preuve d’un article « 5 » historiquement certifié.

## Après référence et effort observé

Les 79 références initiales ont été examinées; une réserve documentaire explicite abaisse ensuite à 78 le nombre exporté en A, sans modifier la référence gelée ni les résultats primaires : voir [reference-review-notes.jsonl](data/reference-review-notes.jsonl). La fin de l’article4 d’Avesnes régulier reste incertaine car p5 n’a pas de marqueur; on ne fabrique donc pas un article5. La sensibilité sur les 78 références sans cette réserve donne V1 68/78 et V2 69/78. Sur la référence initiale, **69/79** correspondent aux propositions V2 initiales. Les 10 autres (dont une limite ensuite réservée) ne sont pas silencieusement remplacées dans les prédictions. L’export de référence, avec 78 A et une réserve maintenue en contexte, représente les décisions revues, pas une amélioration automatique après correction. A signifie « bornes examinées dans le TEI par Codex », pas preuve historique indépendante ni transcription débarrassée de ses notes/OCR.

Journal : [review-log.jsonl](data/review-log.jsonl). 19 écarts anciens examinés individuellement; 25 candidats source dont un connu exclu; 12 zones complètes; 79 unités revues (ces périmètres se recouvrent). 0 intervention humaine indépendante; **temps humain de validation non mesuré**. Aucune durée humaine n’est déduite des temps de calcul. La génération/comparaison nouvelle a pris 2.29 s sur cet environnement; le balayage global 5.37 s. Ce sont des mesures locales de calcul, pas le coût documentaire récurrent. Les dates des gels ne sont pas des chronomètres de lecture.

Les fautes constatées après gel deviennent des pistes V3, sans réécriture de l’expérience V2. Aucun intervalle de confiance, précision globale ou projection de productivité humaine n’est justifié par ce lot.
