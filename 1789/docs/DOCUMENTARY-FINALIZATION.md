# Finalisation documentaire — lot structurel borné

La génération **`global-corpus-3-d0df8e19ee01`** a été réellement produite et activée localement. Les générations précédentes sont conservées.

Le traitement est limité aux **16 chevauchements et 23 notices manquantes** demandés, avec correction de leurs voisins lorsqu’ils absorbaient ces textes. Il applique **48 décisions documentaires explicites** : **25 parents existants corrigés et 23 parents récupérés**. Il ne modifie ni les règles du segmenteur d’articles, ni les XML, ni les métadonnées originales, ni les journaux humains. Les examens de source ci-dessous sont réalisés par Codex ; **ils ne valent pas validation humaine indépendante**.

## Résultat

| Indicateur | Génération 2 | Génération 3 |
|---|---:|---:|
| Notices conservées | 1 305 | 1 305 |
| Textes parents | 1 244 | 1 267 |
| Cahiers autonomes probables extraits | 1 202 | 1 224 |
| Cahiers probables sans texte | 23 | 0 |
| Frontières humaines préservées | 29 | 29 |
| Frontières automatiques sans alerte documentaire | 932 | 981 |
| Frontières suspectes | 282 | 256 |
| Périmètre humain laissé incertain | 1 | 1 |
| Notices sans texte, toutes catégories | 61 | 38 |
| Paires de chevauchements | 16 | 2 |
| Groupes de plages d’unités identiques | 73 | 0 |
| Articles proposés ou humains | 38 553 | 39 072 |
| Articles humains conservés | 333 | 333 |

Les **23 textes recherchés sont présents dans Stanford**. Aucun n’a été fabriqué ou déclaré absent pour contourner un échec. Saint-Germain-des-Prés est reclassé en **procès-verbal contenant des pouvoirs et instructions**, sans changement de son intitulé Persée : il reste 1 224 cahiers autonomes probables au total, tous extraits. Les 38 autres notices sans texte comprennent les **quatre annonces d’absence inchangées** et **34 documents associés, listes ou procès-verbaux hors du lot demandé**.

Zéro groupe d’unités exactement identiques ne signifie pas zéro texte partagé : les **deux chevauchements documentaires persistants restent signalés**. Les 256 alertes techniques restantes ne sont pas présentées comme autant d’erreurs établies et ne donnent pas lieu à une nouvelle campagne générale. Le présent parcours propose seulement les trois blocages ciblés ci-dessous et le lot aléatoire de 12.

## A — Les 16 chevauchements, un par un

Les pages sont celles des notices Persée. Les ouvertures, clôtures, certifications et divisions XML ont été comparées sur les deux côtés. Les locateurs et courts témoins des corrections sont dans `extraction/documentary-finalization.json` ; le dossier local `data/corpus-comparisons/finalization/scope-cases.json` conserve les références d’ouverture/clôture des **deux** documents pour chaque paire, y compris celles laissées inchangées.

| Cas | Documents et pages | Résultat | Diagnostic et action |
|---:|---|---|---|
| 1 | [Cahier du tiers-état de la ville d'Arles](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1572) (t. 2, 57–61) / [Cahiers de quelques corps et communautés de la ville d'Arles](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1573) (t. 2, 61–63) | Corrigé | Clôture/collation du tiers avant les doléances des corps. Pièces liées mais documents distincts ; fin du tiers corrigée. |
| 2 | [Cahier du Bassigny (tiers-état) du Bailliage de Bar-le-Duc](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1614) (t. 2, 198–201) / [Cahier de la noblesse du baillage de Briey (Bailliage de Bar-le-Duc)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1615) (t. 2, 201–204) | Corrigé | Titre Pouvoirs et instructions de la noblesse de Briey après la clôture de Bassigny ; fin de Bassigny corrigée. |
| 3 | [Cahier du tiers-état du baillage de Pont-à-Mousson (Bailliage de Bar-le-Duc)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1622) (t. 2, 230–234) / [Cahier de la noblesse du baillage de Saint-Mihiel (Bailliage de Bar-le-Duc)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1623) (t. 2, 234–244) | Corrigé | Pouvoirs de Saint-Mihiel puis cahier continué dans la division suivante ; fin de Pont-à-Mousson et fin de Saint-Mihiel corrigées. |
| 4 | [Cahier des hôteliers, cuisiniers, etc. de Bordeaux (Sénéchaussée de Bordeaux)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1672) (t. 2, 406–407) / [Cahier des corporations de Bordeaux (Sénéchaussée de Bordeaux)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1673) (t. 2, 407–414) | Corrigé | Signatures des hôteliers avant les demandes des autres corporations. Fin des hôteliers corrigée ; dossier des corporations prolongé jusqu’à la clôture collective de Guyenne. |
| 5 | [Cahier du clergé de Digne (Sénéchaussée de Forcalquier)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_1941) (t. 3, 336–339) / [Cahier du clergé de Riez (Sénéchaussée de Forcalquier)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_1942) (t. 3, 339–346) | Incertain, conservé | Le cahier de Digne contient des doléances des chapitres de Digne et Riez réunis puis une rubrique propre au chapitre de Riez. L’intitulé catalogue « clergé de Riez » ne permet pas de certifier quelle portée retenir. Relation documentaire réelle, identité/périmètre de la notice encore incertains. |
| 6 | [Cahier de la communauté de Revel (Sénéchaussée de Forcalquier)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_1953) (t. 3, 379–379) / [Cahier des communautés de Tournoux et Gleisolles (Sénéchaussée de Forcalquier)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_1955) (t. 3, 379–380) | Corrigé | Certification de Revel avant le titre OCR Tournouqo et Crlpi§Qllea ; fin de Revel corrigée. |
| 7 | [Cahier de la communauté de Revel (Sénéchaussée de Forcalquier)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_1953) (t. 3, 379–379) / [Cahier de la communauté de Fours (Sénéchaussée de Forcalquier)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_1956) (t. 3, 380–381) | Corrigé | La même fin trop large de Revel absorbait également Fours ; correction identique, sans couper ni modifier Fours. |
| 8 | [Cahier du tiers-état de la sénéchaussée de La Rochelle](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_1976) (t. 3, 479–485) / [Cahier de l'île de Ré (Sénéchaussée de La Rochelle)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_1977) (t. 3, 485–486) | Corrigé | Fin du cahier général de La Rochelle avant la division Demandes particulières de l’île de Ré ; pièce associée conservée sous sa notice, sans fusion. |
| 9 | [Cahier du tiers-état de la sénéchaussée de Pamiers](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_1787) (t. 4, 281–285) / [Cahier de la commune d'Uzent-en-Foix (Sénéchaussée de Pamiers)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_1788) (t. 4, 285–285) | Corrigé | Signatures et collation du cahier général de Pamiers avant le Plan à la suite du cahier d’Uzent. Le périmètre humain d’Uzent est conservé ; seule la fin automatique de Pamiers change. |
| 10 | [Cahier de Lessart (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_2237) (t. 4, 643–643) / [Cahier de Létang-la-Ville (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_2238) (t. 4, 643–644) | Corrigé | Lessart et VEta»g-la-Ville sont deux divisions successives ; réattribution de Létang à sa propre division, avec certification finale. |
| 11 | [Cahier d'Ormoy près Lieusaint-en-Brie (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_2320) (t. 4, 778–778) / [Cahier d'Ormoy-Villabé (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_2321) (t. 4, 778–779) | Corrigé | Ormoy près Lieusaint puis Ormoy-Villabé sont deux titres et deux clôtures ; réattribution d’Ormoy-Villabé. |
| 12 | [Cahier de messire Carré, propriétaire du fief du Pin (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2340) (t. 5, 21–22) / [Cahier du Pin (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2341) (t. 5, 22–24) | Corrigé | Messire Carré possède un cahier individuel, suivi de celui des habitants du Pin (« fin » dans le titre OCR) ; réattribution du Pin. |
| 13 | [Cahier de Villecresne (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2461) (t. 5, 194–194) / [Cahier de Ville-du-Bois (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2460) (t. 5, 194–196) | Corrigé | Villecresnes et Villedubois ont des titres et clôtures distincts ; réattribution de Ville-du-Bois. |
| 14 | [Liste des comparants du clergé de la province de Poitou](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2820) (t. 5, 388–389) / [Cahier du clergé de la province de Poitou](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2821) (t. 5, 389–394) | Corrigé | La LISTE précède le CAHIER du clergé du Poitou. Retour de la liste à sa propre division, sans la classer comme cahier. |
| 15 | [Cahier de la communauté de Châteauneuf (Sénéchaussée d'Aix)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_6_1_2579) (t. 6, 285–287) / [Cahier de la communauté de Châteauneuf-le-Rouge (Sénéchaussée d'Aix)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_6_1_2580) (t. 6, 287–288) | Incertain, conservé | La frontière humaine de Châteauneuf englobe la délibération de Châteauneuf-le-Rouge. Elle reste intacte ; le vrai cahier de Châteauneuf-le-Rouge est récupéré en aval. Arbitrage humain nécessaire sur le parent validé. |
| 16 | [Cahier de la communauté de Tholonet (Sénéchaussée d'Aix)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_6_1_2656) (t. 6, 427–427) / [Cahier de la communauté de Tretz (Sénéchaussée d'Aix)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_6_1_2657) (t. 6, 427–429) | Corrigé | Tholànet et frets sont deux divisions successives ; identité de Trets étayée par la clôture, les signatures et le voisinage ; réattribution à sa propre division. |

**14 paires corrigées, 2 conservées comme incertaines.** Les relations avec des pièces associées ne sont pas supprimées : les corps d’Arles, les demandes des corporations, les pouvoirs de Saint-Mihiel et le plan d’Uzent restent identifiables, avec leur structure propre. Les attributions manifestement erronées entre voisins ont été corrigées ; aucune notice n’a été fusionnée ou supprimée.

Pour Châteauneuf-le-Rouge, la division de délibération était retrouvée mais **le véritable cahier de la division suivante manquait au parent**. Le périmètre de cette notice a été prolongé ; le débordement du parent précédent, validé humainement, reste intact et signalé.

## B — Les 23 cahiers probables sans texte

Tous ont une ouverture et une plage retrouvées. Les identités sont établies par lecture des titres, du corps, du contexte de voisinage et des clôtures ; aucun remplacement OCR n’est effectué. Lorsque le titre est dégradé, le texte et la graphie du catalogue restent distincts.

| Notice | Statut | Source et difficulté résolue |
|---|---|---|
| [Cahier des trois ordres du Bassigny-Barrois (Bailliage de Bar-le-Duc )](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1613) — t. 2, p. 196–198 | Récupéré | Remontrances des trois ordres du Bassigny après la certification du tiers de Bar-le-Duc ; titre interne p[83], requête terminale p[105]. Début : `/TEI.2/text/body/div1/div2[15]/div3[1]/p[83]`. |
| [Cahier du tiers-état du bailliage de Châlon-sur-Saône](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1738) — t. 2, p. 608–613 | Récupéré | Remontrances du tiers après la signature de la noblesse ; poursuite dans la division des doléances particulières, puis signatures et collation Bottex. Les deux divisions forment le dossier, sans absorber le clergé du Charolais. Début : `/TEI.2/text/body/div1/div2[43]/div3[3]/p[22]`. |
| [Cahier de la noblesse du bailliage de Chaumont en Bassigny](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1716) — t. 2, p. 724–726 | Récupéré | Pétitions de la noblesse après la signature du clergé régulier ; clôture et signatures des nobles avant le titre du tiers. Début : `/TEI.2/text/body/div1/div2[50]/div3[2]/p[5]`. |
| [Cahier du tiers-état du district de Colmar et Schlesladt](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_1800) — t. 3, p. 9–12 | Récupéré | Rédaction du tiers de Colmar et Schlestadt après les signatures des nobles ; certification du 31 mars et signature Klein. Début : `/TEI.2/text/body/div1/div2[1]/div3[2]/p[33]`. |
| [Cahier de la paroisse de Saint-Jean-des-Agneaux (Bailliage de Coutances)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_1812) — t. 3, p. 62–66 | Récupéré | Griefs de Saint-Jean-des-Agneaux après les signatures du document précédent ; certification des commissaires du 4 mars. Conserver le paratexte final dans le parent. Début : `/TEI.2/text/body/div1/div2[6]/div3[4]/p[88]`. |
| [Cahier de la communauté de Landas (Bailliage de Douai)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_1887) — t. 3, p. 210–214 | Récupéré | Titre RÉDACTION fortement dégradé, mais Landas est explicite dans le premier paragraphe ; clôture du 24 mars et signatures avant Beuvry. Début : `/TEI.2/text/body/div1/div2[22]/div3[17]/head[1]`. |
| [Cahier de la communauté de Lauzet (Sénéchaussée de Forcalquier)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_1952) — t. 3, p. 379–379 | Récupéré | Titre BOLEA.NCES PARTICULIÈRES du Lauzet, entre la certification de Chatelard et le titre de Revel ; signature GU-rault. Début : `/TEI.2/text/body/div1/div2[27]/div3[9]/p[241]`. |
| [Cahier de la noblesse du bailliage de Mâcon](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_2016) — t. 3, p. 623–628 | Récupéré | Copie du mandat de la noblesse du Mâconnais après la certification Greuze du clergé ; instructions et réclamations locales, signatures et articles annexés du même ordre. Début : `/TEI.2/text/body/div1/div2[45]/div3[1]/p[47]`. |
| [Cahier des vicaires des Trois-Evêchés (Bailliage de Metz)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_2056) — t. 3, p. 785–790 | Récupéré | Humbles doléances du corps des vicaires après la signature Mathey et Embry du clergé de Sarrebourg ; texte jusqu’à la fin de division, sans titre voisin. Début : `/TEI.2/text/body/div1/div2[54]/div3[9]/p[25]`. |
| [Cahier de Fourqueux (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_2186) — t. 4, p. 566–567 | Récupéré | Titre Des plaintes de Fourqueux après la signature Leflamand de Joyeuval du cahier de Fosses ; signatures des habitants de Fourqueux à p[138]. Début : `/TEI.2/text/body/div1/div2[18]/div3[159]/p[117]`. |
| [Cahier de Gif-près-Chevreuse (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_2198) — t. 4, p. 580–582 | Récupéré | Titre GAHIER dans un paragraphe ; Gif-pi ès-Chevreuse dans le suivant ; signatures Legrand et paraphé Gautier avant le cahier suivant. Début : `/TEI.2/text/body/div1/div2[18]/div3[169]/p[60]`. |
| [Cahier de Marielle (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_2272) — t. 4, p. 695–695 | Récupéré | La notice Marielle correspond à la paroisse de Meriel dans le texte. Position entre Mennecy et Méry, pagination et clôture concordantes ; graphie de source conservée. Début : `/TEI.2/text/body/div1/div2[18]/div3[238]/head[1]`. |
| [Cahier de Messy (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_2278) — t. 4, p. 702–703 | Récupéré | Nom collé deMessy dans le titre ; division propre, articles et clôture avant le titre du document suivant. Début : `/TEI.2/text/body/div1/div2[18]/div3[244]/head[1]`. |
| [Cahier de la noblesse du 1er département de Paris intra muros](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2788) — t. 5, p. 275–277 | Récupéré | Premier département écrit en toutes lettres dans le titre ; liste des rédacteurs, instructions et clôture du dossier avant le département suivant. Début : `/TEI.2/text/body/div1/div2[2]/div3[6]/head`. |
| [Cahier de l'assemblée partielle de l'église de Saint-Germain-des-Prés (Paris intra muros)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2797) — t. 5, p. 304–308 | Récupéré, procès-verbal composite | La source est un procès-verbal de Saint-Germain-des-Prés avec pouvoirs et instructions intégrés, non un cahier autonome ; même pagination 304–308 et signatures finales. Notice et titre Persée conservés. Début : `/TEI.2/text/body/div1/div2[2]/div3[16]/head`. |
| [Cahier du tiers-état de la sénéchaussée de Riom](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2856) — t. 5, p. 568–574 | Récupéré | Dossier de Riom : discours de Malouet suivi de la division INSTRUCTIONS, signatures et certification finales ; les deux divisions sont conservées séparément dans la structure. Début : `/TEI.2/text/body/div1/div2[17]/div3[3]/head`. |
| [Cahier de la noblesse de la sénéchaussée de Saintes](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2883) — t. 5, p. 665–669 | Récupéré | Titre Pouvoirs de la noblesse de Saintonge, dans la sénéchaussée de Saintes ; instructions et dernière injonction au député terminent la division. Début : `/TEI.2/text/body/div1/div2[24]/div3[3]/head`. |
| [Cahier de la noblesse du bailliage de Verdun](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_6_1_2530) — t. 6, p. 130–133 | Récupéré | Vœu de la noblesse de Verdun après la certification Georgia du clergé ; signatures puis réclamations réservées avant la notice d’absence du tiers. Début : `/TEI.2/text/body/div1/div2[9]/div3[1]/p[137]`. |
| [Cahier de la communauté de Belcodène (Sénéchaussée d'Aix)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_6_1_2569) — t. 6, p. 262–262 | Récupéré | D0LÉANCE ET PLAINTES de Belèodène à l’intérieur de la division de Beaurecueil ; signatures Velin et note éditoriale finales. Ne pas corriger ces graphies. Début : `/TEI.2/text/body/div1/div2[17]/div3[14]/p[9]`. |
| [Cahier de la communauté de Carri et le Rouet (Sénéchaussée d'Aix)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_6_1_2576) — t. 6, p. 279–281 | Récupéré | Titre Gurri et Rouât dégradé ; identité étayée par le contexte, les répétitions du nom et les deux exemplaires du cahier, signatures avant Cassis. Début : `/TEI.2/text/body/div1/div2[17]/div3[21]/head[1]`. |
| [Cahier de la communauté de Lauris (Sénéchaussée d'Aix)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_6_1_2594) — t. 6, p. 316–320 | Récupéré | Laurisptenu fusionné dans le titre, conseil du 25 mars et clôture avant Lourmarin ; nom original jamais corrigé. Début : `/TEI.2/text/body/div1/div2[17]/div3[42]/head[1]`. |
| [Cahier de la communauté de Naux (Sénéchaussée d'Aix)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_6_1_2615) — t. 6, p. 362–365 | Récupéré | Titre NaufC] dégradé ; les Naux sont nommés dans le corps aux offsets 3285010 et 3291581 ; clôture et signatures Castinel avant Ollières. Début : `/TEI.2/text/body/div1/div2[17]/div3[63]/head`. |
| [Doléances des habitants du mont Jura (Baillage d'Aval)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_6_1_2770) — t. 6, p. 737–744 | Récupéré | Très humbles doléances des habitants du M(LNT-JURA sous Bailliage d’Aval ; période 737–744, fin de division avant Province du Bas-Limousin. Début : `/TEI.2/text/body/div1/div2[59]/div3/head`. |

Les textes du Bassigny-Barrois, du tiers de Colmar, de Saint-Jean-des-Agneaux, du Lauzet, de la noblesse de Mâcon, des vicaires, de Fourqueux, de Gif et de la noblesse de Verdun étaient en partie attribués à leurs voisins. Leurs titres internes suivent des signatures ou certifications distinctes : les voisins sont arrêtés à leur propre clôture. Les textes de Riom et de Châlon-sur-Saône traversent plusieurs divisions ; leurs subdivisions, signatures, notes et compléments sont conservés.

Des différences comme **Marielle / Meriel**, **Gurri et Rouât / Carri et le Rouet**, **NaufC] / Naux** ou **frets / Tretz** sont documentées par les témoins, le corps et le voisinage ; les graphies historiques et erreurs de transcription ne sont jamais remplacées. Les données restent des propositions documentaires examinées dans le TEI, pas des textes collationnés intégralement aux images.

## C — Trois blocages, cinq notices à ouvrir

[Ouvrir uniquement les blocages ciblés](http://127.0.0.1:1789/?finalization_blockers=1).

1. **Digne/Riez (1941–1942)** : le dossier contient les chapitres réunis, puis les doléances particulières. Il faut décider de la portée exacte de la notice de Riez ; aucune coupe arbitraire du cahier commun.
2. **Châteauneuf / Châteauneuf-le-Rouge (2579–2580)** : arbitrer la fin humaine du premier parent, qui englobe la délibération suivante. La frontière humaine et ses références restent inchangées.
3. **Digne (1944)** : le périmètre laissé incertain par l’utilisateur reste à arbitrer. Il est distinct du cahier du clergé visé au premier point.

Les autres rapprochements plausibles ou alertes de contrôle restent dans l’inventaire technique. Cette liste n’est pas une nouvelle demande de vérification de centaines de dossiers. Les cas non résolus ne doivent pas être déclarés certifiés lors de la future exploitation.

## D — Les 12 cahiers pour ton contrôle

Redémarrer le serveur existant puis ouvrir le lot :

```sh
python3 1789/review.py
```

[Ouvrir les 12 cahiers tirés au sort](http://127.0.0.1:1789/?boundary_sample=1). Les boutons figurent aussi dans **Cahiers → Contrôle des frontières : 12 cahiers tirés au sort**. Le filtre « Seulement les 12 cahiers du tirage » et les boutons suivant/précédent respectent l’ordre figé. Chaque dossier se vérifie et s’enregistre avec le formulaire habituel ; aucune ouverture de page ne valide une frontière.

| Ordre | Volume | Cahier | Pages |
|---:|---:|---|---|
| 1 | 1 | [Cahier de la noblesse du bailliage d'Amiens](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_1_1_1548) | 739–744 |
| 2 | 1 | [Cahier de la noblesse de Nérac (Sénéchaussée d'Albret)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_1_1_1537) | 701–704 |
| 3 | 2 | [Cahier du tiers-état de la sénéchaussée de Clermont-Ferrand](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1699) | 769–774 |
| 4 | 2 | [Cahier du tiers-état du district de Belfort](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1642) | 315–318 |
| 5 | 3 | [Cahier de la noblesse de la sénéchaussée de Marseille](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_2032) | 700–701 |
| 6 | 3 | [Cahier du tiers-état du bailliage de Thionville (Bailliage de Metz)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_3_1_2053) | 776–780 |
| 7 | 4 | [Cahier de Morsang-sur-Orge (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_2300) | 739–741 |
| 8 | 4 | [Cahier de Cuisy (Paris)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_2147) | 482–483 |
| 9 | 5 | [Cahier du clergé de la province du Perche](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2803) | 319–322 |
| 10 | 5 | [Cahier de la noblesse de Bouzonville (Bailliage de Sarreguemines)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2896) | 701–703 |
| 11 | 6 | [Cahier du tiers-état de Vic (Bailliage de Toul)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_6_1_2499) | 20–22 |
| 12 | 6 | [Cahier de la communauté de la Roquette (Sénéchaussée d'Aix)](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_6_1_2602) | 334–335 |

Méthode figée : `random.Random(17891789)`, volumes 1 à 6 dans cet ordre, puis `sample(sorted(identifiants_admissibles), 2)` sans remise. Le tirage utilise uniquement les identifiants, sans nombre d’articles, difficulté, longueur ou anomalie présumée. **Aucun remplacement**. La population exclut les frontières humaines, les contrôles/références de source enregistrés et les dossiers de finalisation examinés ici. Elle contient 827 candidats répartis par volume : **4, 95, 124, 273, 209, 122**.

Il s’agit d’une revue humaine distincte, **pas d’un échantillon entièrement inédit pour Codex ni d’une validation statistique globale**. Certaines notices, comme Nérac ou Marseille, ont déjà bénéficié de corrections automatiques dans les travaux précédents ; elles restent dans le tirage, sans remplacement opportuniste. Les exclusions reposent sur les contrôles effectivement enregistrés, pas sur une connaissance exhaustive de toutes les lectures anciennes.

`tools/document-review/campaigns/twelve-boundaries.json` conserve la graine, les paramètres, les empreintes des populations et les 12 identifiants. Le fichier parents de la génération au tirage est **identique octet pour octet** à celui de la génération active ; une correction du seul champ de provenance de classification n’a changé aucune frontière ni aucun choix. Les règles de frontière sont restées inchangées après le tirage. Les examens humains restent entièrement à faire.

```sh
python3 1789/tools/document-review/campaigns/draw_boundaries.py --verify
```

La reproduction relit le journal figé de la génération, afin de rester possible après tes validations futures. Les décisions nouvelles restent dans le journal habituel, jamais dans le tirage. Le script refuse de remplacer le lot enregistré.

## Reproduction et conservation

```sh
python3 1789/extraction/production.py --verify-only 1789/data/corpus/global-corpus-3-d0df8e19ee01
# Seulement si les entrées ont évolué : produire une autre génération, sans écraser l’actuelle.
python3 1789/extraction/production.py
```

Les 48 décisions sont un jeu documentaire borné, vérifié contre les empreintes Stanford, les XPath, les positions et les témoins exacts. Une décision humaine nouvelle prime : elle ne peut pas être remplacée par ces corrections. Une discordance avec la version attendue est signalée, pas contournée.

Les générations, sources, comparaisons détaillées et journaux privés restent locaux et ignorés par Git. Le code, les décisions documentaires référencées, ce bilan et le tirage sans données privées sont versionnables. Les anciennes archives sont inchangées. Aucune écriture PostgreSQL, modification publique, indexation, embedding, correction OCR ou inférence LLM.

**Après le contrôle humain des 12 cahiers, la prochaine étape est le contrôle qualité des articles.** Les trois blocages restent identifiés à part ; cette livraison ne déclenche pas une nouvelle optimisation générale des frontières.

## Vérifications exécutées

- **51 tests Python réussis** : régressions existantes, ouvertures de Fourqueux et Verdun sans la certification du voisin, séparation Lauzet/Revel, classement du procès-verbal et priorité d’une décision humaine postérieure au jeu de corrections et conservation de la nature documentaire lors d’une reconstruction.
- Contrôle intégral de la génération active avec `--verify-only` : textes, XPath/plages, couverture des parents et des sources, identifiants, rattachements et décisions humaines conformes.
- Comparaison avec la génération 2 : aucun ancien parent ou notice perdu, métadonnées conservées, **29 périmètres humains et 333 articles humains inchangés**, journaux réels identiques octet pour octet et aucune nouvelle paire de chevauchement.
- Le tirage des 12 est reproductible ; les données parents de référence et actives sont identiques. Aucun texte du lot n’a reçu ici de jugement documentaire ni de validation humaine.
- Navigateur sur journaux temporaires : 12 dossiers/deux par volume, cinq notices bloquantes, accès direct, navigation dans l’ordre figé, clavier, 320/375/768/1280 px et texte à 200 %, aucune écriture lors de la consultation ni erreur JavaScript. Le parcours de validation/reconstruction d’articles existant reste fonctionnel sur une copie privée temporaire.
- Ruff, syntaxe JavaScript et `git diff --check` conformes. Les XML, le registre, le segmenteur et les anciens audits sont inchangés.

Les résultats agrégés figurent dans [finalization-checks.json](finalization-checks.json). Les journaux de test et preuves détaillées restent locaux, séparés des journaux humains réels.
