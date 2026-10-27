# Pilote documentaire de 30 cahiers de 1789

Étude locale réalisée le 26 octobre 2026. Source : [Stanford, révision figée 926fd3c](https://github.com/StanfordUniversityLibraries/ap_tei/tree/926fd3cd986a3c3d411e93d1845fff6475cb2602). Méthode `pilot-1.0.0`.

**Les 30 parents sont produits. Les règles retrouvent les frontières attendues de 29 parents sur 30, à partir de débuts présélectionnés. Beaurecueil nécessite une correction documentaire : son `div3` contient aussi Belcodène.** Cela ne mesure pas le rappel de la découverte des cahiers dans six volumes entiers.

Le corpus livré contient **759 candidats articles/unités numérotées : 269 A vérifiés dans le XML, 490 B non certifiés individuellement**. Il conserve aussi **187 plages C sans segmentation d’article certifiée**, en plus des textes parents intégraux. Ces plages techniques ne sont pas 187 revendications. Aucun embedding ni segment vectoriel n’est produit.

La revue a été effectuée par Codex, avec cinq contrôles visuels de pages imprimées. **Ce n’est pas une validation humaine indépendante par un historien.** « A » signifie que les frontières ont été examinées dans la source XML ; cela ne certifie ni chaque caractère de l’OCR ni la fidélité au manuscrit de 1789.

## Livrables et accès

| Livrable | Fichier |
|---|---|
| Registre des 30 cahiers, raisons du choix et résultats | [REGISTER.md](REGISTER.md), [registre JSON](data/register.json) |
| Décisions documentaires et fenêtres de référence | [decisions.json](decisions.json), [référence calculée](data/reference.json) |
| Textes complets et structure | [documents.jsonl](data/documents.jsonl), [textes et fragments XML par parent](data/parents/) |
| Unités A et B, positions et navigation | [units.jsonl](data/units.jsonl) |
| Texte retenu sans inventer d’articles | [retained-unsegmented.jsonl](data/retained-unsegmented.jsonl) |
| Résultats automatiques avant décisions | [automatic-predictions.jsonl](data/automatic-predictions.jsonl) |
| Évaluation chiffrée, par fenêtre et par cahier | [EVALUATION.md](EVALUATION.md), [evaluation.json](data/evaluation.json), [summary.json](data/summary.json) |
| Erreurs et limites concrètes | [PROBLEMS.md](PROBLEMS.md), [erreurs avec textes exacts](data/boundary-errors.json) |
| Contrôles, cas négatifs, reproductibilité | [checks.json](data/checks.json), [negative-results.json](data/negative-results.json), [reproducibility.json](data/reproducibility.json) |
| Schéma, commandes et conventions de fidélité | [DATA.md](DATA.md) |

## 1. Réutilisation des audits précédents

Les rapports [Stanford et multicorpus](../1789-multicorpus/README.md) et [comparaison des sources](../1789-sources-comparison/README.md), leurs sélections, extractions et contrôles ont été réutilisés. Les 50 fichiers de ces dossiers sont comparés à leurs empreintes au début de cette mission ; ils sont inchangés.

Les caches XML temporaires précédents n’existaient plus. Seuls les six volumes nécessaires ont été téléchargés à la révision imposée, puis vérifiés avec les SHA-256 du premier inventaire. Les sources de travail restent dans `/tmp/cahier-1789-extraction-pilot/sources/`, hors application. Aucun autre volume XML n’est téléchargé.

Les sept correspondances Persée déjà vérifiées et la notice de Ferrières servent de contrôles bibliographiques secondaires. Aucune nouvelle collecte Persée n’est réalisée. En particulier, le regroupement Mirecourt est cohérent avec la notice déjà étudiée couvrant les pages 1–6, et Ferrières avec une notice unique. **Le traitement se reproduit sans accès à Persée.** Les textes du pilote proviennent exclusivement de Stanford.

Les sept anciens parents sont conservés dans la sélection. Le nouveau dossier Mirecourt comprend désormais les demandes provinciales et le mémoire justificatif qui suivent son corps principal : sa nouvelle étendue exige un nouvel identifiant technique. [La table de correspondance](data/legacy-crosswalk.json) retrouve les 28 anciens passages ; 27 ont la même étendue source après retrait des blancs de bordure. Pour l’article 4 d’Angoumois, le titre « Administration. » est séparé du corps de l’article. Les anciens fichiers ne sont pas corrigés.

## 2. Échantillon raisonné

Répartition : **5 / 5 / 5 / 6 / 4 / 5** cahiers dans les volumes I à VI. Les ordres explicitement attribués sont : **7 clergé, 6 noblesse, 6 tiers état** ; **11 sans attribution explicite retenue**. « Habitants » n’est pas automatiquement transformé en tiers état. Un territoire ou un lieu de réunion n’est pas automatiquement une commune moderne.

Les 23 ajouts et les sept cas hérités sont distingués dans le registre. Le choix recherche des contrastes : corps courts et longs, plusieurs régions, trois ordres, articles `Art.` et ordinaux, sous-listes, reprises de numéros, OCR difficile, signatures intégrées et divisions multiples. Anjou, Mirecourt et Ferrières imposent des regroupements ; Beaurecueil impose une frontière intérieure. Agen tiers et Lourmarin offrent des cas sans numérotation exploitable retenue.

**Cet ensemble n’est pas statistiquement représentatif.** Plusieurs cas difficiles sont sélectionnés précisément parce que les audits les avaient repérés. Aucun taux de ce pilote ne doit être appliqué aux centaines ou milliers de cahiers potentiels.

Six cas négatifs sont examinés à part : notice du cahier absent d’Albret, continuation Anjou II, demandes annexes de Mirecourt, mémoire des commissaires, extrait de Vic noblesse et section Constitution de Ferrières. Ils ne sont jamais ajoutés aux 30 parents. Belcodène est un autre vrai cahier, exclu de Beaurecueil et hors de cette sélection ; ce n’est pas un document historiquement inexistant. Aucun doublon historique n’est affirmé ou supprimé sur la base de ces 30 documents.

## 3. Frontières et reconstruction documentaire

### Proposition automatique

L’identification examine les titres et les premiers paragraphes, pas seulement le nom de la balise. Des formules explicites repèrent des débuts possibles ; des vétos excluent les extraits et annonces de cahiers introuvables. Une règle de continuation regroupe les divisions sœurs titrées `CHAPITRE`, `CONSTITUTION`, `AGRICULTURE`, `COMMERCE`, `JUSTICES`, `DEMANDES PARTICULIÈRES` ou `TRAVAIL`, sans franchir un nouveau document reconnu.

Ces règles permettent de grouper les trois chapitres d’Anjou, les trois pièces du dossier Mirecourt et les cinq divisions de Ferrières. Une convention naïve « un `div3` = un parent » donnerait 26 étendues conformes ici ; les regroupements donnent 29. Ce résultat reste conditionnel aux 30 débuts sélectionnés et à ce jeu de développement : la classification exhaustive de tous les débuts possibles n’a pas été évaluée.

### Référence documentaire

Pour les 30 cahiers, les titres initiaux, la clôture, les paragraphes finaux et les documents voisins ont été examinés. Les décisions sont explicites dans `decisions.json`, avec des plages inclusives de paragraphes, une division et un rôle documentaire. Elles distinguent préambule, corps, rubrique, supplément, mémoire, réserves, mandat, clôture, signatures, certification et éléments éditoriaux.

Beaurecueil s’arrête après `p[8]`. Ses `p[9]–p[15]` appartiennent à Belcodène, dont le titre a été balisé comme un simple paragraphe. La signature de Beaurecueil se trouve dans `p[8]`, après le corps. Le scan de la page 262 confirme le filet et le changement de titre. Le fichier parent n’inclut pas Belcodène.

Le texte parent correspond exactement à une plage du texte XML décodé, avec les notes, signatures et éléments éditoriaux conservés et repérés. Pour les groupes de divisions, les blancs originaux entre divisions sont conservés. Les fragments XML livrés sont des sérialisations de contrôle entourées d’une racine technique ; les SHA-256 des fichiers Stanford restent la référence binaire.

« Complet » signifie ici **complet dans le périmètre de l’édition transcrite que nous avons délimité**, pas « transcription intégrale garantie du manuscrit original de 1789 ». Aucune recherche archivistique d’un feuillet absent n’a été menée. Les incertitudes concernant les annexes et la hiérarchie interne restent signalées même quand les frontières du parent sont établies dans le TEI.

## 4. Extraction des unités documentaires

Le segmenteur combine l’ordre XML, les marqueurs explicites `Article`, `Art.`, les formes ponctuées et les ordinaux. Il n’emploie aucun modèle linguistique pour découper le texte.

- Un article peut réunir plusieurs paragraphes, et traverser une page ou une note.
- Plusieurs marqueurs au sein d’un même paragraphe peuvent produire plusieurs articles.
- Après un début `Art.`, les listes `1°`, `2°` internes restent dans l’article. Colmar constitue un contrôle concret de cette priorité.
- Une nouvelle rubrique ou division peut terminer une unité ; la numérotation peut reprendre dans une autre section. La section est conservée avec un identifiant.
- Un marqueur OCR illisible ne reçoit pas automatiquement un numéro « réparé ». Une proposition incertaine reste B ; une frontière expressément revue peut produire A sans restaurer le chiffre absent.
- Une absence de marqueur n’autorise pas à convertir chaque paragraphe en revendication. Les plages non segmentées restent dans leur parent, avec C.

Les décisions de structure sont appliquées séparément, puis les seuls intervalles de référence A contrôlés remplacent les propositions qui les recouvrent. **Les unités hors de ces fenêtres restent B**, même quand elles semblent régulières. L’annexe provinciale de Mirecourt comporte une fenêtre de référence B ; elle n’alimente pas les mesures A.

Les unités sont documentaires, pas des revendications sémantiques atomiques : la charte incluse dans l’article 4 d’Angoumois demeure un seul article. Le mémoire justificatif et le supplément de Colmar sont identifiés comme pièces jointes ; leurs propositions ne sont pas assimilées à des articles du corps initial.

## 5. Évaluation effectivement réalisée

La référence comporte **37 fenêtres A intégralement annotées**, y compris des fenêtres sans articles, et **une fenêtre B exclue des scores**. Elle ne se limite pas à sélectionner des sorties jugées réussies : elle comporte aussi des articles manqués, des fusions et des fins incorrectes. Les annotations sont lisibles sans consulter les prédictions. La première annotation succincte de Beaurecueil a été rectifiée après lecture complète et contrôle du scan : les trois demandes insérées dans sa prose sont conservées. Le [journal de revue](review-log.json) documente cette révision et les compléments ultérieurs.

Il s’agit d’un **jeu de développement revu par le même agent**, et non d’un test aveugle ou d’une annotation indépendante par deux spécialistes. La comparaison mesure la conformité à ces frontières documentaires, pas un CER/WER ni une précision sur tout Stanford.

Avant décisions documentaires et remplacement par la référence, les fenêtres contiennent **262 propositions pour 269 unités de référence**. **244 propositions ont simultanément le bon début et la bonne fin**, soit une précision de **93,1 %** et un rappel de **90,7 %** sur ces fenêtres. Les frontières seules ont une précision de **98,9 % au début** et **96,2 % à la fin**. Une frontière correcte peut être associée à la mauvaise autre frontière dans une fusion : la mesure par unité est donc essentielle.

Après revue, **269 unités ont le statut A, soit 35,4 % des 759 candidats livrés**. Elles couvrent **18,9 % du texte de tous les parents**, mesuré sur les caractères non blancs, titres, notes et signatures inclus dans le dénominateur. Cette couverture basse reflète le contrôle partiel des longs cahiers ; elle n’est pas un taux de texte automatiquement extractible.

Le corps numéroté a été contrôlé en entier pour **13 cahiers**. Les **15 autres cahiers possédant des articles** sont contrôlés par fenêtres ; les deux cahiers sans articles retenus restent consultables intégralement. Les 490 B ne sont pas présentés comme validés.

Cinq images Stanford ont été téléchargées et examinées : Beaurecueil/Belcodène, Montigny, Ferrières, Anjou et Alençon noblesse. Les observations, zones vérifiées, limites, URL et empreintes sont dans [scan-checks.json](data/scan-checks.json). Les contrôles des anciens audits sont réutilisés comme observations antérieures, pas comptés comme cinq nouvelles inspections. La numérisation n’a pas été collationnée pour chaque article des 30 cahiers.

## 6. Provenance et retour au contexte

Chaque unité comporte le corpus, le parent, l’ordre, un identifiant et une ancre reproductibles, le texte, les références XML, les positions globales et relatives au parent, les pages, le lien au volume numérisé, les versions et les empreintes source/méthode. Les notes retirées du texte de l’article restent dans le parent et dans les annotations. Les numéros illisibles restent nuls ou littéraux, jamais reconstruits silencieusement.

Les champs `previous_unit_id` et `next_unit_id` permettent d’aller au contexte et aux voisins sans nouvelle extraction. Les statuts des voisins restent à respecter : un voisin B est une proposition, pas un article définitivement validé. [Trois exemples complets](data/navigation-examples.json) montrent notamment l’article 4 de Mirecourt sur deux paragraphes et deux pages, et l’article 15 de Périgny avec une note interne séparée. Aucune route future n’est imposée.

## 7. Coût et contrôles

Le traitement automatique des six volumes, positions et écritures du corpus prend environ **deux secondes** dans cet environnement après téléchargement ; les durées exactes de l’exécution sont dans `evaluation.json`. Le débit observé ne permet pas d’estimer le coût documentaire humain.

Les décisions saisies représentent **une correction de frontière de parent, 185 affectations de rôles/plages documentaires, et 269 unités A contrôlées**. Elles modifient le rôle de 344 paragraphes. Le registre de suivi classe les 750 propositions initiales : 244 inchangées et A, 427 inchangées et B, 72 avec frontières modifiées, 7 exclues comme articles autonomes. Ces sept propositions restent présentes comme citation dans le préambule d’Agen noblesse.

**Aucun temps de validation humaine n’a été mesuré ; aucun historien n’est intervenu.** La mise au point initiale des règles et la revue Codex ont eu lieu dans la même session. Leur durée ne doit pas être convertie en minutes par cahier ou extrapolée à un opérateur humain. Le prochain lot devra chronométrer séparément préparation, validation, correction et arbitrage.

Les contrôles vérifient la reconstruction des 30 parents, les plages exactes, les notes séparées, les empreintes, le bon parent, l’ordre, les voisins, les identifiants, les doublons d’intervalles et la conformité des A à la référence. Sept erreurs injectées sont détectées, les six cas négatifs sont exclus des parents autonomes, et les 50 fichiers des anciens audits restent inchangés. La reproduction de deux exécutions vérifie l’identité des fichiers de corpus ; les horodatages et durées sont exclus de cette comparaison.

## 8. Faisabilité et généralisation

| Catégorie | Observation dans ce pilote | Conséquence |
|---|---|---|
| Articles numérotés réguliers | Annet, Pierrelez, Plessis, Albertas ; 13 corps numérotés entièrement contrôlés | Conserver les règles, puis évaluer sur des cahiers nouveaux avant validation par lot |
| Continuités typographiques | Anjou 15–18, Mirecourt 4, Flines 1, notes en ligne | XML + marqueurs suffisent souvent, avec maintien des positions et des notes |
| Regroupements de divisions | Anjou, Ferrières, dossier Mirecourt | Règles de continuation utiles, mais vocabulaires de titres encore limités |
| OCR des marqueurs | Montigny, Ribaucourt, `arf. 9` d’Agen | Validation ou règle supplémentaire sur l’image ; pas de réparation silencieuse |
| Rubriques dans des `p` | Toul, Angoumois, Alençon | Risque d’absorber un titre ou de tronquer une unité ; rôles documentaires nécessaires |
| Plusieurs parents dans une division | Beaurecueil/Belcodène | Chercher les changements de titre internes ; validation prioritaire des parents suspects |
| Prose libre, portée hiérarchique incertaine | Agen tiers, Lourmarin, Ferrières Constitution 15 | Garder le parent ; étudier une unité de section explicite, sans découpage sémantique |
| Pièces jointes et certifications | Colmar, Mirecourt, réserves et minutes de Guérande | Conserver les rôles et les dates propres, ne pas tout indexer comme paroles du corps initial |

Une partie substantielle des formes rencontrées paraît traitable par ces règles ; **sa part dans le corpus complet reste inconnue**. Les six volumes n’ont pas fait l’objet d’un nouvel inventaire validé exhaustivement. La disponibilité de textes ou d’un catalogue documentaire ne suffit pas à certifier toutes les unités.

Les risques de passage à l’échelle sont d’abord documentaires : autres titres de continuation, documents imbriqués dans des paragraphes, numéros perdus, tableaux et colonnes mélangés, limites des annexes, doublons d’édition et lacunes historiques. Les performances de ces six petits fichiers ne constituent pas un benchmark pour un service de recherche. Aucun changement applicatif n’est nécessaire pour continuer l’étude.

## 9. Droits et périmètre préservé

Les [deux audits antérieurs](../1789-sources-comparison/README.md) distinguent domaine public historique, édition, transcription, balisage, métadonnées et images. Les réserves signalées y restent applicables : **l’étude locale ne constitue pas une autorisation de republication de toutes les ressources associées**. Aucune licence générale ne se déduit d’un dépôt public ou d’un lien IIIF. Les images restent dans le cache isolé ; seules leurs références et empreintes sont livrées. La clarification Persée en cours n’est pas nécessaire à ce pilote autonome.

Aucun fichier applicatif, route, modèle, configuration de production, migration, donnée PostgreSQL, index ou moteur de recherche n’a été modifié. Aucun service n’a été déployé, aucun organisme contacté, aucun texte publié sur le site et aucun embedding généré.

## 10. Réponses explicites et prochaines étapes

**Q1 — Parents automatiques fiables ?** 29/30 étendues automatiques concordent avec les frontières revues dans le TEI, à partir de débuts présélectionnés. Ce n’est pas 96,7 % de rappel d’identification sur Stanford. Les 30 parents sont livrés après correction de Beaurecueil.

**Q2 — Intervention humaine ?** Une correction de frontière de parent est nécessaire dans ce lot. Tous les parents ont été contrôlés par Codex, et 185 décisions de structure ont été saisies. Les 490 unités B attendent une validation complémentaire. Aucun taux de recours à un humain en production n’est établi et aucune validation humaine externe n’a eu lieu.

**Q3 — Articles aux limites vérifiées ?** 269/759 candidats livrés, soit 35,4 %, portent A. Sur les fenêtres contrôlées, 244/262 propositions automatiques sont exactement reconstituées avant correction ; 25/269 unités de référence ne le sont pas. Les 490 autres candidats ne sont pas réputés exacts.

**Q4 — Obstacles principaux ?** Marqueurs OCR illisibles, titres/notes/signatures en paragraphes ordinaires, plusieurs articles dans un paragraphe, sous-listes, changements de section et frontières de parents à l’intérieur d’une division.

**Q5 — Lien article/cahier ?** Oui pour chaque unité livrée : parent, XPath, plages sources et relatives, pages, ancre et voisins. La justesse documentaire des B reste distincte de cette traçabilité technique, vérifiée pour tous.

**Q6 — Fidélité au TEI ?** Oui dans le modèle explicite de texte XML décodé : aucune réécriture, modernisation, normalisation Unicode ou correction OCR ; blancs de bordure hors unité et séparation des notes documentés par les plages. Le texte intégral du parent est strictement conservé. Ce n’est pas une garantie de transcription du manuscrit original.

**Q7 — Extension des règles ?** Plausible pour les mêmes familles de mise en page et numérotation, non mesurée sur l’ensemble des volumes. L’algorithme reste trop dépendant des conventions observées pour autoriser une validation automatique générale.

**Q8 — Cas spécifiques ?** Cahiers composites, annexes/suppléments, rubriques en `p`, numéros perdus, prose non numérotée, tableaux à colonnes, extraits et publications répétées. Les modèles de corpus futurs ne sont pas modifiés par ce pilote.

**Q9 — Travail manuel réel ?** Les interventions documentaires Codex sont dénombrées ci-dessus et dans les fichiers ; le temps d’un validateur humain n’est pas mesuré. Impossible d’en déduire honnêtement un budget horaire pour des milliers de cahiers.

**Q10 — Prochaine étape ?** Faire évaluer un lot nouveau et gelé avant toute intégration : annotation indépendante et chronométrée, contrôle des parents, puis comparaison aveugle des unités. Conserver ce lot-ci comme jeu de développement.

Ordre recommandé, **sans commencer ces travaux pendant cette mission** :

1. Faire relire les frontières des 30 parents et les ambiguïtés documentaires signalées, puis un sous-ensemble des A par une personne compétente ; arbitrer surtout les annexes et rubriques de Toul/Ferrières.
2. Constituer un cadre de sondage à partir de l’inventaire précédent, incluant les titres suspects et documents non reconnus. Tirer un lot distinct réparti entre les six volumes ; publier la méthode de tirage. Pour estimer une fréquence globale avec une marge d’environ ±10 points à 95 % sous hypothèses d’un tirage aléatoire simple, un ordre de grandeur de 100 parents est raisonnable ; ajuster au plan, à la population et à la stratification. Cette indication ne prédit aucun taux de réussite.
3. Annoter intégralement parents et articles de ce lot sans consulter les sorties, avec double lecture d’une partie et journal des durées. Mesurer découverte des parents, frontières, regroupements, unités complètes et couverture du texte, en comptant les échecs et exclusions.
4. Améliorer les règles de titres internes, clôtures et marqueurs OCR sur le jeu de développement, puis geler la version avant le test indépendant. Aucun numéro absent ne doit être restitué sans trace.
5. Décider ensuite d’une extraction plus large par lots révisables. N’envisager intégration, republication et expériences d’embeddings qu’après ces contrôles et les clarifications de droits pertinentes.

Le pilote démontre une chaîne de conservation et de retour au contexte opérationnelle, avec un premier sous-corpus A utilisable pour des essais locaux. Il ne justifie pas encore une extraction générale sans contrôle documentaire.
