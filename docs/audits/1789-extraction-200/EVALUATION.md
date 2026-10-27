# Évaluation : périmètres et dénominateurs

Les règles de classification et segmentation sont gelées avant la lecture des nouveaux résultats d'articles. Les références source sont gelées ensuite, avant leur comparaison avec les prédictions. Les annotations sont réalisées par Codex, séparément du développement, **sans indépendance humaine ni aveuglement complet**. Les hypothèses de parents sont connues et leurs débuts/fins sont confirmés ou infirmés par lecture ; il ne s'agit pas d'une référence historienne construite ex nihilo.

## Découverte des parents

| Périmètre | Résultat | Portée |
|---|---:|---|
| Inventaire de tout I–VI | 1 278 hypothèses de documents | Compte automatique, pas vérités documentaires |
| Nouveaux candidats tirés | 170 | Tirage déterministe de diversité, non représentatif |
| Candidats du lot de validation | 12 | Deux par volume, courts et difficiles/longs |
| Retenus comme cahiers/sous-documents | 6 | Arles médecins, La Rochelle, Thionville, Vernouillet, Rognac, Vic |
| Faux parents | 6 | Deux résumés anciens, deux notices d'absence, deux sections internes |
| Précision dans ce lot | 6/12 = 50 % | Pas d'intervalle national ni extrapolation |
| Frontières correctes parmi les retenus | 5/6 | Comparaison des intervalles non blancs ; les intervalles bruts restent conservés |
| Frontière à corriger | 1 | Arles médecins : exclure les documents professionnels suivants |

La détection d'une section de Montargis ou de Claye n'est pas comptée comme un cahier autonome correctement découvert, même si ses phrases sont des doléances réelles. Le défaut est l'association au parent et l'autonomie documentaire.

Un contrôle supplémentaire après la référence rejette cinq autres résumés du volume I, explicitement situés en 1483 ou 1560 dans leur titre source. Ces décisions améliorent l'état livré mais ne changent ni les règles ni les scores ci-dessus. Au total, onze fiches sont en quarantaine.

## Zones non couvertes

Douze fenêtres sont tirées par hachage parmi des paragraphes hors de toute hypothèse admise, deux par volume. Elles comprennent jusqu'à six paragraphes chacune, soit 68 paragraphes lus entièrement. Les titres et premières lignes des parents englobants ont été consultés pour interpréter les zones.

- Trois cahiers formels manqués sont identifiés par ce contrôle et leur contexte : Armagnac/Isle-Jourdain, les Mandats du tiers de Dijon et Saint-Pierre-le-Moutier.
- Une fenêtre appartient aux doléances de Bouvignies, incorporées dans un procès-verbal écarté globalement.
- Un mémoire professionnel de Vitry-le-François reste ambigu comme cahier autonome.
- Sept fenêtres concernent récits, traités, procès-verbaux ou listes sans nouveau cahier identifié dans le contrôle.

Les ouvertures des quatre pièces revendicatives sont en dehors des courtes fenêtres et ont été examinées en complément. **Il ne s'agit pas d'un recensement exhaustif de zones continues comprenant tous leurs débuts : aucun rappel global ni pseudo-rappel 6/(6+4) n'est publié.** La sélection conditionnelle à la non-détection recherche précisément des erreurs, et n'est pas un sondage uniforme du volume.

## Articles avant correction

La référence couvre 48 unités complètes dans sept fenêtres des six vrais documents. Rognac fournit une fenêtre entière de prose sans unité numérotée certifiée ; La Rochelle fournit deux fenêtres. Les grands corps ne sont pas intégralement annotés.

| Mesure conditionnelle | Corrects | Proposés | Attendus |
|---|---:|---:|---:|
| Débuts exacts | 46 | 46 | 48 |
| Fins exactes | 46 | 46 | 48 |
| Couples début/fin exacts | **46** | **46** | **48** |

Précision des unités : 46/46 ; rappel : 46/48 = 95,83 %. Deux articles entiers sont manqués, sans début reconnu : `ArtIer.` à La Rochelle et `Àri. er.` à Vernouillet. Aucune fusion ou scission supplémentaire n'est observée dans ces fenêtres. Cela n'en établit pas l'absence dans les milliers d'autres propositions.

Onze propositions apparaissent dans les fenêtres des six faux parents : elles sont comptées séparément comme erreurs du pipeline documentaire, et exclues de cette mesure conditionnelle de segmentation. Leur présence n'est pas masquée. Le détail de chaque fenêtre et erreur est dans [evaluation.json](data/evaluation.json) et [article-errors.json](data/article-errors.json).

Après revue, les deux articles manqués sont ajoutés et les 48 limites de référence sont utilisées comme unités A. La conformité après substitution est contrôlée, mais **n'est pas présentée comme une nouvelle précision indépendante**.

## Corpus final et couverture

Les 317 A comprennent 269 anciens et 48 nouveaux. Sur 6 189 A/B finaux, cela représente 5,12 %. Les nouveaux A ne représentent que 48/5 430 = 0,88 % des nouvelles unités. Les 5 872 B restent non certifiés, et les 812 C ne sont pas autant d'articles.

Les A couvrent 72 446 caractères non blancs sur 4 406 144 dans les 189 parents hors quarantaine, soit 1,64 %. Le dénominateur inclut titres, signatures, notes, préambules, annexes et prose non numérotée. Ce n'est pas un taux de paroles citoyennes extractibles.

## Développement et limites

La régression des 30 anciens parents et de Pecqueuse est séparée. Les nouvelles règles correspondent à 250/269 unités dans les 37 anciennes fenêtres ; cette mesure sert à détecter les régressions, pas à estimer la généralisation. Les 759 unités antérieures sont conservées telles quelles dans le corpus final, y compris leurs décisions documentaires : la nouvelle prédiction brute ne remplace pas silencieusement leurs A.

Les strates de longueur et structure, la petite taille du lot, l'examen partiel des articles et le jugement du même agent limitent fortement l'interprétation. Aucun temps humain n'est mesuré. Aucune nouvelle collation exhaustive sur image ni au manuscrit ne fonde les A ; la référence porte sur le TEI figé.
