# Galerie des erreurs et ambiguïtés

Les exemples nouveaux renvoient aux identifiants de [sélection](data/selection.jsonl), aux [décisions source](data/reference-documents.jsonl) et aux [prédictions initiales](data/automatic-units.jsonl). Aucun exemple de développement ci-dessous n'est présenté comme validation nouvelle.

## 1. Faux cahiers hors 1789 — volume I

`candidate-a8987424bbb5cb9fa345`, `div2[1]/div3[14]/p[57]` : « Cahier de la noblesse. » est un titre interne du récit **« ÉTATS GÉNÉRAUX DE 1483, SOUS CHARLES VIII »**. Le passage résume les demandes de la noblesse ; ce n'est pas une transcription de 1789. Le tiers état sous Charles IX en 1560 produit la même erreur (`candidate-b289035431c04956dabe`).

Le repérage lexical trouve réellement ces titres, mais manque leur période et leur genre englobant. Les deux cas appartiennent au lot gelé ; cinq autres résumés explicitement datés de 1483/1560 ont été rejetés ensuite par contrôle de leurs titres, sans changer les règles. Ils restent dans le registre et les textes C de quarantaine.

## 2. Cahier annoncé mais absent — Béziers et Soissons

Volume II, `div2[24]/div3[3]`, `candidate-5f5cd4b2ef58f7dece46` : l'ouverture porte bien « CAHIER », mais `p[2]` annonce « Ce cahier manque aux Archives de l'Empire ». Aucun corps revendicatif n'est transcrit.

Volume V, `div2[30]/div3[3]`, `candidate-e2ed8e80bf9d0e527ede` : la note précise que les cahiers de Soissons ne se trouvent pas aux Archives. Le veto d'absence reconnaissait d'autres formulations du développement ; il échoue ici. Les deux fiches sont mises en quarantaine, jamais complétées avec des revendications inventées.

## 3. Sections transformées en faux parents — Montargis et Claye

Volume IV, Montargis clergé, `div2[2]/div3[1]/p[39]`, `candidate-8615aa6715be49c318a9` : « Doléances pour le clergé » est une section du chapitre V du cahier commencé en tête de division. La détection d'un titre interne est trop permissive : elle propose un parent tronqué et autonome.

Même volume, `div2[18]/div3[90]/p[228]`, `candidate-cd771995c951b0c35db8` : « PLAINTES LOCALES » appartient au cahier de Claye, commencé au `p[199]`. Le bourg est nommé dans le corps, mais ce n'est pas un nouveau cahier. Les textes sont conservés en quarantaine ; les règles ne sont pas ajustées sur ces exemples après évaluation.

## 4. Plusieurs documents fusionnés — médecins d'Arles

Volume II, `div2[4]/div3[3]`, `candidate-506a682f65ae1e814a3a`. Les doléances des médecins commencent `p[81]` et s'achèvent par leurs signatures `p[92]`. Le `p[93]` ouvre les doléances des procureurs. L'hypothèse automatique continue trop loin dans le dossier professionnel, jusqu'à d'autres pièces.

La correction est explicite : parent limité à `p[81]–p[92]`, nouvel identifiant et correspondance dans `crosswalk.json`. La prédiction longue d'origine reste archivée. Le statut retenu est celui d'un **sous-document revendicatif annexé au dossier d'Arles**, pas d'un cahier territorial équivalent à tous les autres.

Ce document fournit aussi un cas positif de granularité : `p[84]` réunit les articles 2 et 3, le troisième continue en `p[85]` ; `p[88]` réunit 6 et 7, et `p[89]` prolonge 7. Ces sept premières unités sont correctement reconstituées dans la fenêtre revue.

## 5. Vrais cahiers manqués hors des hypothèses admises

Le contrôle des fenêtres non couvertes et des débuts englobants établit notamment :

| Document | Source | Cause observée |
|---|---|---|
| Armagnac / Isle-Jourdain | II, `div2[5]/div3[4]` | Titre dégradé `REMONTRÂCES`, plusieurs intitulés ; classification incertaine au lieu d'admission |
| Mandats du tiers de Dijon | III, `div2[19]/div3[1]` | Vrai corps d'instructions numérotées sous le titre « MANDATS », sans hypothèse de parent |
| Saint-Pierre-le-Moutier | V, `div2[22]/div3[2]` | « CAHIER » en `p[1]`, intitulé en `p[2]`, sans `head` ; le chemin de détection initial manque ce cas |
| Bouvignies, doléances dans un procès-verbal | III, `div2[22]/div3[13]` | Exclusion globale du procès-verbal alors qu'il contient des doléances numérotées |

Ces cas ne sont pas ajoutés artificiellement aux 170 tirés pour remplacer les échecs. Le mémoire des notaires de Vitry-le-François reste un cas de genre ambigu, sans classement forcé en cahier autonome.

## 6. Articles manqués à cause du marqueur OCR

La Rochelle tiers, III, `div2[35]/div3[6]/p[2]` : le marqueur `ArtIer.` n'a pas de séparation entre `Art` et `Ier`. La règle avec frontière de mot ne le retrouve pas. Vernouillet, V, `div2[1]/div3[120]/p[8]` : `Àri. er.` échappe également au motif.

Les deux unités sont dans la référence créée avant prédiction ; elles sont donc réellement comptées comme manquées. Le texte littéral est conservé lors de leur ajout au fichier A. Les numéros non lisibles comme chiffres ne sont pas restaurés silencieusement.

Dans les 48 unités nouvelles de référence, aucune fusion ou scission supplémentaire n'est observée. **Aucune précision sur les articles non revus n'en découle**, et aucune troncature d'article supplémentaire n'est inventée pour compléter une catégorie de galerie.

## 7. Fusions et rubriques absorbées : régressions de développement

La nouvelle exécution sur les anciens parents, conservée dans [development-article-regression.json](data/development-article-regression.json), retrouve encore des erreurs connues :

- **Montigny**, III, `div2[22]/div3[23]/p[1..3]` : marqueurs illisibles et sous-numérotation conduisent à une unité fusionnée. Ces limites ne deviennent pas A par une restauration implicite des chiffres.
- **Toul noblesse**, VI, `div2[1]/div3[2]/p[10..12]` : « Dette nationale consolidée. » est absorbé à la fin de l'article précédent.
- **Alençon clergé**, I, `div2[9]/div3[1]/p[9..10]` : la rubrique « Religion. » est absorbée par le `5°` précédent.

Il s'agit de prédictions de développement, pas de nouvelles erreurs certifiées dans les 153 parents non revus. Les anciennes corrections et unités sont conservées dans le corpus final, sans remplacement par ces prédictions brutes.

## 8. Notes, signatures et texte non numéroté

Les `note` XML sont séparées du texte des unités par `text_spans`, mais restent intégralement dans le parent et C. Les signatures en début de paragraphe ont un rôle dédié ; une signature au milieu d'un paragraphe est une hypothèse annotée séparément. Arles `p[92]` illustre le risque d'assimiler les mots « Signé Vigne… » au corps documentaire.

La séparation de tous les en-têtes, notes transcrites en prose ou signatures des milliers de B n'est pas certifiée. Les rubriques absorbées du développement montrent pourquoi une simple extraction de `p` ne suffit pas.

Rognac, VI, `div2[17]/div3[81]`, possède un cahier en prose, daté et signé, mais pas de numérotation d'articles retenue. Sa fenêtre est évaluée avec zéro article attendu : son texte demeure dans C et le parent, sans découpage sémantique arbitraire.

## 9. Régressions réussies, sans généralisation abusive

Pecqueuse conserve ses 38 articles et réunit les deux paragraphes de l'article 37. Vernouillet s'arrête avant le `p[318]`, titre de Verrières, bien que les deux cahiers soient dans une même division. Le regroupement des deux divisions de La Rochelle conserve les demandes de l'île de Ré et les signatures, avec une portée d'annexe explicite.

Ces réussites montrent l'intérêt des règles de continuité et du contexte ; elles n'annulent pas les faux positifs et les cahiers manqués ci-dessus.
