# Échecs, ambiguïtés et décisions du pilote

Les exemples renvoient aux sources figées par les XPath du registre. Les textes complets des divergences automatiques sont dans [boundary-errors.json](data/boundary-errors.json), et le suivi de toutes les propositions dans [proposal-review.json](data/proposal-review.json). Les observations sur images et leurs empreintes sont dans [scan-checks.json](data/scan-checks.json).

## 1. Beaurecueil : deux cahiers dans un `div3`

Volume VI, `div2[17]/div3[14]`. `p[9]` porte « D0LÉANCE ET PLAINTES », puis `p[10]` « De la communauté de Belèodène (1). ». Les `p[11]–p[15]` et leurs signatures ne sont plus Beaurecueil.

**Automatique :** l’étendue du parent englobe toute la division. **Source observée :** le [scan de la page 262](https://stacks.stanford.edu/image/iiif/wg983ft3682%2Fwg983ft3682_00_0266/full/1800,/0/default.jpg) montre la signature Roché, un filet, puis Belcodène. **Décision :** terminer Beaurecueil après `p[8]` ; annoter sa signature à partir de « Signé Roché » dans ce même paragraphe.

Autre difficulté dans ce cahier : `p[5]` contient trois demandes `1°`, `2°`, `3°` au milieu d’une présentation en prose. Les explications des `p[6]–p[8]` prolongent le troisième ensemble avant la signature. Une première lecture succincte avait annoté cette fenêtre sans articles ; la lecture complète et le scan ont corrigé le référentiel, comme le précise le journal. Cette correction n’est pas une erreur imputée au segmenteur.

**Piste :** repérer les titres internes et formules de changement de communauté, puis contrôler les parents suspects. Ne pas se contenter de compter les divisions.

## 2. Anjou : chapitres frères et articles mêlés

Volume II, `div2[2]/div3[1..3]`. Les chapitres II et III sont des continuations, pas deux nouveaux cahiers. La règle de regroupement restitue le parent sur trois divisions et les sections distinctes.

Dans le premier chapitre, `p[17]` commence le `15°`. Le texte se poursuit dans `p[18]` après la note de bas de page et le changement de colonne ; le même `p[18]` contient ensuite `16°`, `17°`, `18°`. La [page contrôlée](data/scan-checks.json) montre ces numéros distincts à droite.

**Automatique :** les marqueurs permettent ici la bonne reconstruction ; **contrôle :** une référence de quatre unités sur deux paragraphes a été ajoutée. **Limite :** il serait faux de généraliser « un paragraphe = un article » ou de prendre le début d’une nouvelle colonne pour une frontière.

## 3. Agen clergé : `arf. 9,` n’est pas reconnu

Volume I, `div2[6]/div3[1]/p[20..23]`. Le segmenteur fusionne l’article 8 avec `p[22]–p[23]` car « arf. 9, » n’est pas un marqueur `Art.` reconnu. Les limites ont été séparées dans la référence A.

Le contrôle image du premier audit indiquait que **l’édition imprimée porte également ARF. 9** : ne pas appeler automatiquement cette forme une erreur OCR. Le texte littéral est conservé. Le numéro n’est pas « réparé » dans les données.

**Piste :** règle distincte d’alerte pour une étiquette isolée entre deux numéros concordants, avec origine explicitement éditoriale ou OCR ; ne pas remplacer globalement `arf` par `art`.

## 4. Montigny : numéros illisibles et ponctuation parasite

Volume III, `div2[22]/div3[23]`. Les débuts `z8`, `36`, `B®`, `Il®` sont mal reconnus. Le [scan de la première page](data/scan-checks.json) permet de lire les articles imprimés 1°, 2°, 3°, mais seul le début a été collationné visuellement ; les frontières suivantes sont contrôlées dans le XML.

**Automatique :** des unités sont fusionnées, notamment les premiers articles ; la virgule de « ,5® » est laissée à la fin de l’unité précédente par le repérage de marqueur. **Référence :** onze unités dans la fenêtre, avec conservation exacte des caractères du TEI. Les jetons non reconnus gardent `historical_number: null`.

**Piste :** signaler les ruptures de numérotation et reconnaître des positions de marqueur en début de paragraphe, avec gestion explicite de la ponctuation préfixe. Une suite de chiffres attendue ne suffit pas à restaurer un numéro disparu.

## 5. Alençon noblesse : une fin et un début dans le même paragraphe

Volume I, `div2[9]/div3[2]/p[10]`. La citation « Lex consensu populi fit. et constitutione régis. » termine l’article 2, avant le marqueur `Art. 3.` dans le même paragraphe. La séparation est confirmée sur le scan de la page imprimée 711.

**Automatique :** ce cas est correctement découpé dans la fenêtre retenue, car le préfixe du paragraphe prolonge l’unité précédente. **Précaution :** la fin de l’article 3 et la transition vers le texte suivant ne sont pas certifiées ; la référence s’arrête avant son début. Une lecture des seuls premiers caractères de chaque `p` n’aurait pas suffi.

## 6. Alençon clergé : `2°-` et rubrique « Religion. »

Volume I, `div2[9]/div3[1]/p[5..10]`. Le tiret après `2°` ne satisfait pas la condition de caractère suivant du marqueur ordinal ; les articles 1 et 2 sont fusionnés. La rubrique « Religion. », balisée en `p`, est absorbée dans la fin de la dernière unité de la série préliminaire.

**Décision :** frontières explicites dans la fenêtre de référence ; rubriques séparées dans les rôles documentaires. **Piste :** améliorer les séparateurs acceptés après un ordinal et détecter les petites rubriques sans assimiler tout paragraphe court à un titre. Les autres rubriques et reprises sont conservées, sans certification individuelle de tous leurs articles.

## 7. Angoumois : une charte dans un article, puis un autre titre

Volume II, `div2[1]/div3[2]/p[5..20]`. L’article 4 contient « Charte nationale. » et une suite de propositions, puis `p[20]` « Administration. » annonce le groupe suivant.

**Automatique :** l’article 4 absorbe ce dernier titre. **Décision :** conserver toute la charte dans l’article, mais arrêter le corps après `p[19]`. L’ancien extrait expérimental incluait `p[20]` ; le nouveau périmètre est documenté sans modifier cet ancien fichier. La charte n’est pas découpée en revendications fabriquées.

**Piste :** associer les rubriques à leur structure documentaire, en distinguant un sous-titre interne d’un titre du groupe suivant. Une simple règle « arrêter à chaque titre » serait erronée ici.

## 8. Ribaucourt : dernier marqueur dégradé et mandat absorbé

Volume III, `div2[22]/div3[9]/p[12..15]`. Le dernier marqueur est transcrit « i lfl » ; le texte parle du « onzième chef ». L’automatique l’absorbe avec l’unité précédente et poursuit jusqu’au mandat `p[14]`.

**Décision :** onze frontières de la fenêtre contrôlées ; mandat et clôture séparés. **Limite :** le texte et l’étiquette OCR restent littéraux, sans compléter automatiquement le numéro. **Piste :** déclencher une alerte sur une fin de série suivie d’un mandat, et valider la frontière plutôt que réécrire le texte.

## 9. Mirecourt : préfixes, pièces jointes et absence de numéro

Volume IV, `div2[1]/div3[2..4]`. Deux articles figurent dans `p[2]` du corps principal ; l’article 4 traverse deux paragraphes et pages. Ces cas sont extraits puis vérifiés. Le préfixe `-11°` provoque un décalage de frontière : le tiret est associé à l’unité précédente dans la proposition automatique.

Les demandes provinciales et le « TRAVAIL » justificatif sont des pièces jointes du même dossier dans ce pilote. Le travail déclare explicitement servir « à l’appui des cahiers de la noblesse ». Il n’est pas compté comme un parent supplémentaire.

**Incertitude conservée :** le `p[2]` des demandes provinciales n’a pas de marqueur. Le parallélisme suggère une unité distincte, mais cette fenêtre reste B et hors des scores. La méthode ne lui invente pas de `2°`. **Piste :** vérifier la mise en page des annexes et leurs relations, en conservant leur statut documentaire et leur date propre.

## 10. Ferrières : cinq divisions et hiérarchie d’un article introductif

Volume IV, `div2[18]/div3[145..149]`. Le premier `div3` est le préambule ; suivent Constitution, Agriculture, Commerce et Justices seigneuriales. Le scan de la page 545 confirme le titre Ferrières puis Constitution comme section interne. Le regroupement automatique est conforme au parent retenu.

La numérotation reprend dans chaque section. Une virgule précédant `Art. 14.` décale une frontière automatique. Surtout, l’article 15 de Constitution annonce « les articles suivants » : les sections thématiques peuvent être comprises comme une hiérarchie subordonnée. **Cet article introductif reste B** ; les 24 autres unités du parent sont vérifiées à leurs niveaux documentaires.

**Piste :** représenter une relation de portée entre divisions et unités introductives sans aplatir ou dupliquer leur texte. Un résultat documentaire n’a pas à être une revendication atomique.

## 11. Toul noblesse : rubriques et demandes sans numéro

Volume VI, `div2[1]/div3[2]`. « Dette nationale consolidée. » et « Visite des titres des créanciers… » sont des paragraphes courts avant les articles 2 et 3. L’automatique les associe à la fin des articles précédents.

De nombreuses autres rubriques sont suivies de demandes sans numéro. Leur rattachement à un article ou leur autonomie n’est pas toujours clair. Un en-tête courant imprimé est également transcrit en `p[26]`, au milieu de l’article 6.

**Décision :** séparer les intitulés et l’en-tête par des rôles explicites, mais ne certifier que les articles 1 et 2 dans ce pilote. Les autres propositions restent B ; des zones sans numéro restent C. **Piste :** faire annoter la hiérarchie de ce document avant d’élargir une règle générique sur les petites rubriques. Les décisions saisies hors fenêtre facilitent la lecture, elles ne valent pas certification de toutes les unités.

## 12. Clôtures, signatures et notes

- **Pierrelez, volume V, `div3[9]` :** le dernier article est automatiquement prolongé par « Ce fut fait… » et les signatures ; la référence sépare `p[10]` de `p[11..12]`. Une liste limitée de formules de clôture ne couvre pas toutes les variantes.
- **Guérande, volume IV, `div2[9]/div3[3]/p[38]` :** la signature commence dans le paragraphe du dernier article, puis continue dans `p[39]`. Les minutes électorales et votes qui suivent ne sont pas de nouveaux articles. Seuls les premiers articles ont le statut A ; le dernier ensemble attend une certification documentaire.
- **Périgny et Plessis, volume V :** une note éditoriale est insérée dans un article et dans un mot coupé (`ga- … belles`, `en- … fièrement`). Elle est séparée via `text_spans`, mais aucune césure ou coquille n’est corrigée. Ces unités sont contrôlées dans le XML, sans collation intégrale sur image.

## 13. Prose, suppléments et documents absents

**Agen tiers et Lourmarin :** conserver les textes complets et leurs paragraphes n’autorise pas à déclarer autant d’articles. Les plages de corps non segmentées restent C. La rubrique Constitution d’Agen tiers pourra éventuellement fournir une unité de section après un contrôle spécifique ; aucune segmentation sémantique n’est réalisée.

**Colmar :** `Art.` sans numéro précède une sous-liste 1°–4° ; la numérotation d’article manquante n’est pas restaurée, la sous-liste reste dans le même article. Le supplément et les actes notariés sont conservés séparément du corps de mars. Le premier audit avait déjà établi que la date structurée du 27 avril était une collation. Une date balisée ne suffit donc pas à déterminer la date du cahier.

**Albret :** un titre « CAHIER » est suivi de l’annonce qu’il n’a pu être retrouvé. Le véto de notice empêche de fabriquer un parent plein et des revendications. **Vic noblesse :** l’intitulé « Extrait » entraîne l’exclusion de l’échantillon de cahiers intégraux, sans nier l’intérêt historique du document.
