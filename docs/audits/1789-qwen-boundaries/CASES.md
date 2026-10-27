# Exemples réels : corrections et erreurs

Les références et positions sont celles des sources Stanford figées. Les textes complets des blocs de ces exemples sont dans `data/gallery.jsonl`; les fenêtres exactes permettent la vérification. Aucun texte historique n’est corrigé. Les annotations sont exploratoires Codex.

## Correction complète du PV et du cahier de Châtellerault

Cahier du clergé de la sénéchaussée de Châtellerault — [notice Persée](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1692), tome 2, pages[686, 690]. [XML Stanford figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/fz023dp4399/fz023dp4399.xml) ; [numérisation](https://purl.stanford.edu/fz023dp4399).

Référence : `v2-b018316 → v2-b018412 (established)`. ModèleC : `v2-b018316 → v2-b018412`. Exactitude : **True**. Diagnostic de référence : Châtellerault clergé: PV introductif et cahier, signatures avant noblesse absente.

Sortie Qwen (JSON mis en forme ; réponse brute conservée dans les données) :

```json
{
  "decision": "propose",
  "start_id": "v2-b018316",
  "end_id": "v2-b018412",
  "signatures": [
    "v2-b018412"
  ],
  "annexes": [
    {
      "start_id": "v2-b018413",
      "end_id": "v2-b018417",
      "relation": "excluded"
    }
  ],
  "other_documents": [
    "v2-b018308",
    "v2-b018309",
    "v2-b018310",
    "v2-b018311",
    "v2-b018312"
  ],
  "uncertain": false,
  "reason": "Le document commence par le titre 'SÉNÉCHAUSSÉE DE CHATELLERAÏÏLT.' et se termine par la signature des commissaires. Les autres blocs sont soit des cahiers voisins, soit des annexes ou notes éditoriales distinctes, donc excluses ou non liés"
}
```

`v2-b018316` — `/TEI.2/text/body/div1/div2[48]/div3[1]/head[1]`, p.686, source[4657864:4657878]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> PROCÈS-VERBAL

`v2-b018412` — `/TEI.2/text/body/div1/div2[48]/div3[1]/p[90]`, p.690, source[4689964:4690477]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Fait et arrêté en l'église des Frères Mineurs conventuels, par nous, commissaires nommés, pour être présenté, lu et approuvé à l'assemblée de l'ordre du clergé, renvoyée au 30 du courant, ce 28 mars 1789, et ont signé Palouzier, prieur, curé de Seuillé; Joyeux, curé de Saint-Jean ; Gàu-vain, curé de Bone'uil-Matours; Rolland, chanoine; F. A. Delugens, Deswallons, ancien custode et ex définiteur des Frères Mineurs conventuels ; signé aussi Louis-François Motant, secrétaire.

`v2-b018413` — `/TEI.2/text/body/div1/div2[48]/div3[2]/head[1]`, p.690, source[4690498:4690505]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> CAHIER

`v2-b018417` — `/TEI.2/text/body/div1/div2[48]/div3[3]/head[2]`, p.690, source[4690875:4690959]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Des plaintes et réclamations du tiers-état de la sénéchaussée de Châtellerault (1).

## Correction complète de la fin de Digne

Cahier du tiers-état de Digne (Sénéchaussée de Forcalquier) — [notice Persée](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1944), tome 3, pages[348, 356]. [XML Stanford figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/mc666yy3026/mc666yy3026.xml) ; [numérisation](https://purl.stanford.edu/mc666yy3026).

Référence : `v3-b009162 → v3-b009417 (established)`. ModèleC : `v3-b009162 → v3-b009417`. Exactitude : **True**. Diagnostic de référence : Digne tiers: signature Trabue avant doléances locales séparées.

Sortie Qwen (JSON mis en forme ; réponse brute conservée dans les données) :

```json
{
  "decision": "propose",
  "start_id": "v3-b009162",
  "end_id": "v3-b009417",
  "signatures": [
    "v3-b009417"
  ],
  "annexes": [],
  "other_documents": [
    "v3-b009155",
    "v3-b009156",
    "v3-b009157",
    "v3-b009158",
    "v3-b009159"
  ],
  "uncertain": false,
  "reason": "Le document commence par le titre 'CAHIER' et contient les articles et signatures liés au tiers-état de Digne. Les autres blocs sont des parties annexes ou liées au même dossier, mais ne forment pas un document distinct. La fin est marquée"
}
```

`v3-b009162` — `/TEI.2/text/body/div1/div2[27]/div3[7]/head`, p.348, source[3167497:3167504]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> CAHIER

`v3-b009417` — `/TEI.2/text/body/div1/div2[27]/div3[7]/p[246]`, p.356, source[3239863:3240296]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Lu et arrêté, dans l'assemblée de l'ordre du tiers-état, le 6 avril 1789; et ont signé MM. les président, les commissaires et le secrétaire : Pressai, L.-G., président; de Roihas; Simon; Ëourret; Michel Salvator; Rougon; Guaud; Tho- mas; Arnauld Faudon; Bayle; Trabue, greffier. Signé à l'original, collationné : Trabue.

## Réussite autonome à Exmes, sans gain sur A

Cahier du bailliage d'Exmes (Baillage d'Alençon) — [notice Persée](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_1_1_1544), tome 1, pages[726, 729]. [XML Stanford figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/jt959wc5586/jt959wc5586.xml) ; [numérisation](https://purl.stanford.edu/jt959wc5586).

Référence : `v1-b016123 → v1-b016171 (established)`. ModèleB : `v1-b016123 → v1-b016171`. Exactitude : **True**. Diagnostic de référence : Exmes: titre propre et expédition greffier du21mars, avant Verneuil.

Sortie Qwen (JSON mis en forme ; réponse brute conservée dans les données) :

```json
{
  "decision": "propose",
  "start_id": "v1-b016123",
  "end_id": "v1-b016171",
  "signatures": [
    "v1-b016121",
    "v1-b016122"
  ],
  "annexes": [],
  "other_documents": [
    "v1-b016172",
    "v1-b016173",
    "v1-b016174",
    "v1-b016175",
    "v1-b016177"
  ],
  "uncertain": false,
  "reason": "Le document commence par le titre 'CAHIER' et se termine par la signature des députés. Les autres documents mentionnés sont des cahiers voisins et ne font pas partie du même dossier de notice Persée, donc ils sont exclus de la sélection du塊"
}
```

`v1-b016123` — `/TEI.2/text/body/div1/div2[9]/div3[6]/head[1]`, p.726, source[5591878:5591884]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> CAHIER

`v1-b016171` — `/TEI.2/text/body/div1/div2[9]/div3[6]/p[44]`, p.729, source[5611034:5611359]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> La présente expédition délivrée conforme à l'original par nous, greffier au bailliage d'Exmes, ledit original signé au juge et de tous les députés présents à la lecture d'icelui, à Exmes, ce vingt et un mars mil sept cent quatre-vingt-neuf.

## Dégradation nouvelle à Gray : absorption de la fin du dossier précédent

Cahier de Gray (Bailliage d'Amont ) — [notice Persée](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_1_1_1554), tome 1, pages[777, 782]. [XML Stanford figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/jt959wc5586/jt959wc5586.xml) ; [numérisation](https://purl.stanford.edu/jt959wc5586).

Référence : `v1-b017319 → v1-b017460 (established)`. ModèleC : `v1-b017304 → v1-b017460`. Exactitude : **False**. Diagnostic de référence : Gray: titre en paragraphe, liste de signatures et collation Vivant clôturant le tome.

Sortie Qwen (JSON mis en forme ; réponse brute conservée dans les données) :

```json
{
  "decision": "propose",
  "start_id": "v1-b017304",
  "end_id": "v1-b017460",
  "signatures": [
    "v1-b017308",
    "v1-b017318",
    "v1-b017450",
    "v1-b017455",
    "v1-b017460"
  ],
  "annexes": [
    {
      "start_id": "v1-b017319",
      "end_id": "v1-b017454",
      "relation": "included"
    }
  ],
  "other_documents": [
    "v1-b017311"
  ],
  "uncertain": false,
  "reason": "Le document commence par les articles 63 à 65, puis la signature des députés, et se termine par les signatures des députés du tiers-état et la certification du greffier. Les annexes incluent le cahier général des demandes et remontrances, y"
}
```

`v1-b017319` — `/TEI.2/text/body/div1/div2[10]/div3[3]/p[85]`, p.777, source[6055434:6056124]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Cahier général des demandes ét remontrances des villes, bourgs et communautés du bailliage de Gray, pour être représenté à rassemblée générale du tiers-état du bailliage d'Amont, ledit cahier arrêté à l'assemblée secondaire dudit bailliage tenue en la ville de Gray, le 20 mars 1789 et jours suivants, en vertu des; lettres de convoca- tion de Sa Majesté du 20 février dernier et des règlements y annexés duait jour 20 février et 24 janvier précédent pour la députation aux Etats généraux (1).

`v1-b017460` — `/TEI.2/text/body/div1/div2[10]/div3[3]/p[220]`, p.782, source[6096749:6096970]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Çoilationnè par le soussigné, commis au greffe civil dq bailliage de Qray, et trouvé conforme à la minute déposée audit greffe 4P Gray, ce avril 1789. Signé vivant.

`v1-b017304` — `/TEI.2/text/body/div1/div2[10]/div3[3]/p[71]`, p.776, source[6040708:6040824]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Art. 63. L'abolition de la peine du banniss- ement et sa conversion en une autre peine.

`v1-b017454` — `/TEI.2/text/body/div1/div2[10]/div3[3]/p[215]`, p.781, source[6089978:6091022]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> testations contre le résultat du conseil du roi, du 27 décembre dernier, et qui ont été déposées au greffe du Parlement, au mois de janvier dernier, et renouvelées le 10 mars présent mois, à moins que lesdits membres du clergé et de la noblesse pro- testant ne détractent solennellement, à l'ouverture de ladite assemblée des trois états, leurs dites protestations ; qu'au cas qu'ils y persistent, lesdits députés proposeront contre eux et soutiendront les moins de droit (sic) qui s'élèvent pour les

## Amélioration partielle, certification de noblesse Amont omise

Cahier de la noblesse du bailliage d'Amont — [notice Persée](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_1_1_1551), tome 1, pages[763, 768]. [XML Stanford figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/jt959wc5586/jt959wc5586.xml) ; [numérisation](https://purl.stanford.edu/jt959wc5586).

Référence : `v1-b017018 → v1-b017125 (established)`. ModèleC : `v1-b017018 → v1-b017122`. Exactitude : **False**. Diagnostic de référence : Amont noblesse: cahier et suite du PV de nominations, certification Fleury avant cahier général tiers.

Sortie Qwen (JSON mis en forme ; réponse brute conservée dans les données) :

```json
{
  "decision": "propose",
  "start_id": "v1-b017018",
  "end_id": "v1-b017122",
  "signatures": [
    "v1-b017122"
  ],
  "annexes": [],
  "other_documents": [
    "v1-b017126",
    "v1-b017127",
    "v1-b017128",
    "v1-b017129",
    "v1-b017130"
  ],
  "uncertain": false,
  "reason": "Le document commence par le titre 'CAHIER DE DOLÉANCES DONNÉES PAR LA NOBLESSE DU BAILLIAGE D'AMONT' et se termine par les signatures des députés et la certification du lieutenant particulier. Les annexes sont incluses comme des parties liè"
}
```

`v1-b017018` — `/TEI.2/text/body/div1/div2[10]/div3[2]/head[1]`, p.763, source[5919992:5919999]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> CAHIER

`v1-b017125` — `/TEI.2/text/body/div1/div2[10]/div3[2]/p[100]`, p.768, source[5970058:5970083]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Signé Jacques de Fleury.

`v1-b017122` — `/TEI.2/text/body/div1/div2[10]/div3[2]/p[97]`, p.768, source[5967750:5969129]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Tous messieurs ayant déclaré qu'ils n'avaient plus aucunes propositions à faire relativement aux objets pour lesquels ils ont été convoqués, monsieur le président a été chargé de rendre compte aux ministres, au nom de la chambre, de ce qui s'est passé dans les assemblées tenues par la noblesse du bailliage d'Amont, en confor- mité des ordres de Sa Majesté ; ensuite a adressé un discours à l'assemblée, et le présent procès- verbal a été clos, terminé, conclu et arrêté et signé de monsieur le prés

## Brives : bornes exactes mais annexe Turenne attribuée à tort

Cahier du tiers-état de la sénéchaussée de Brives (Province du Bas-Limousin) — [notice Persée](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1991), tome 3, pages[542, 544]. [XML Stanford figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/mc666yy3026/mc666yy3026.xml) ; [numérisation](https://purl.stanford.edu/mc666yy3026).

Référence : `v3-b014699 → v3-b014769 (established)`. ModèleC : `v3-b014699 → v3-b014769`. Exactitude : **True**. Diagnostic de référence : Tiers Brives: cahier signé; mémoire Turenne explicitement annexé mais possédant sa propre notice, donc conservé lié et séparé.

Sortie Qwen (JSON mis en forme ; réponse brute conservée dans les données) :

```json
{
  "decision": "propose",
  "start_id": "v3-b014699",
  "end_id": "v3-b014769",
  "signatures": [
    "v3-b014697",
    "v3-b014698",
    "v3-b014768",
    "v3-b014769"
  ],
  "annexes": [
    {
      "start_id": "v3-b014770",
      "end_id": "v3-b014781",
      "relation": "included"
    }
  ],
  "other_documents": [
    "v3-b014772",
    "v3-b014773",
    "v3-b014774",
    "v3-b014775",
    "v3-b014776"
  ],
  "uncertain": false,
  "reason": "Le document commence par le titre 'CAHIER' et se termine par les signatures des députés. Le mémoire est inclus comme annexe, conformément à l'indication du cahier. Les autres documents sont liés à des notices distinctes ou à des notes édite"
}
```

`v3-b014699` — `/TEI.2/text/body/div1/div2[39]/div3[4]/head[1]`, p.542, source[4908204:4908211]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> CAHIER

`v3-b014769` — `/TEI.2/text/body/div1/div2[39]/div3[4]/p[67]`, p.544, source[4926906:4927605]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> MM. Malès, Malepeyre, Lavardç, Bâche-lerie, Violbans, Toulzac, Latour, Dés Roches, Marbot, Laplace, Daval, Sclafer, Lasserre, Rama-des, Cerout, Cirejol, Peyredieu, Laroche,.Monl-brial, Martial, Soulié, Labrunie, Lavergne, Vignes, Salvagnac, Bénies, Berty, Lafon, Serajal, Dupont, Montel, notaire ; Montel, Gherières, Verdier, Bas-til, Bordes, Peyral, Ducnamp, Lescure, Duchas-seing, Chadirac, Reijal, Faurie, Borie, Dulmet, la Gironie, Bonneval, Algay, Chauvac, d'Aines, Peyral Delsue, etc., etc., et

`v3-b014770` — `/TEI.2/text/body/div1/div2[39]/div3[5]/head[1]`, p.544, source[4927672:4927680]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> MÉMOIRE

`v3-b014782` — `/TEI.2/text/body/div1/div2[39]/div3[5]/p[9]`, p.545, source[4934820:4934851]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Coté et paraphé à chaque page.

`v3-b014781` — `/TEI.2/text/body/div1/div2[39]/div3[5]/p[8]`, p.545, source[4933238:4934795]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Signé Bories, avocat, corédacteur par commissariat; Bedoch fils, corédacteur par commissariat; Marbos ; Reyjal Latour; Chevière ; Roche ; Malès; Roche ; Dulmet; Vignes de Salvagnac; Sireg-jol ; Lacoste ; Dupré de Testut; Duchassaing, commissaire ; Touteiar; Guérin; Reyjal; Lacoste de Sarevmondië; Dérdenat; Delavigerïe; Delrieux; .Sclafér,; Cerout ; Monmaur : Boulles; Duroux ; Deserere,: Delpuech ; Glavai ; Lenière ; Blooch ; Robert : Duchamp, notaire royal ; Verdier ; Gha-dirac; Charagen ; Labru

## Fin proche mais titre du cahier Châteauneuf-le-Rouge absorbé

Cahier de la communauté de Châteauneuf (Sénéchaussée d'Aix) — [notice Persée](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2579), tome 6, pages[285, 287]. [XML Stanford figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/wg983ft3682/wg983ft3682.xml) ; [numérisation](https://purl.stanford.edu/wg983ft3682).

Référence : `v6-b008080 → v6-b008117 (established)`. ModèleC : `v6-b008080 → v6-b008118`. Exactitude : **False**. Diagnostic de référence : Châteauneuf: cahier et procès-verbal de nomination/remise des députés, avant Châteauneuf-le-Rouge distinct.

Sortie Qwen (JSON mis en forme ; réponse brute conservée dans les données) :

```json
{
  "decision": "propose",
  "start_id": "v6-b008080",
  "end_id": "v6-b008118",
  "signatures": [
    "v6-b008079",
    "v6-b008115",
    "v6-b008134",
    "v6-b008135"
  ],
  "annexes": [
    {
      "start_id": "v6-b008080",
      "end_id": "v6-b008118",
      "relation": "included"
    }
  ],
  "other_documents": [
    "v6-b008119",
    "v6-b008136"
  ],
  "uncertain": false,
  "reason": "Le document commence par le titre 'CAHIER' suivi des doléances de la communauté de Châteauneuf, et se termine par la signature des députés et le cahier de la communauté de Châteauneuf-le-Rouge, incluant les annexes liées à la même notice. A"
}
```

`v6-b008080` — `/TEI.2/text/body/div1/div2[17]/div3[24]/head`, p.285, source[2564284:2564291]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> CAHIER

`v6-b008117` — `/TEI.2/text/body/div1/div2[17]/div3[25]/p[9]`, p.287, source[2575435:2576469]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Et, de leur part, lesdits députés se sont présent tement chargés du cahier de doléances dè ladite communauté, et ont promis de le porter à ladite assemblée, et de se conformer à tout ce qui est prescrit;et ordonné par lesdites lettres du Roi, règlement y annexé, et ordonnance susdatée ; desquelles nominations de députés, remise de cahier, pouvoir et déclaration, nous avons a tous les susdits comparants donné acte ; et avons signé avec ceux desdits habitants qui savent signer, et avec lesdits dép

`v6-b008118` — `/TEI.2/text/body/div1/div2[17]/div3[26]/head`, p.287, source[2576536:2576543]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> CAHIER

## Santeny : A vide, Qwen localise le texte mais décale ses titres de borne

Cahier de Santeny (Paris) — [notice Persée](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2405), tome 5, pages[107, 109]. [XML Stanford figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xx284sn7328/xx284sn7328.xml) ; [numérisation](https://purl.stanford.edu/xx284sn7328).

Référence : `v5-b002758 → v5-b002787 (established)`. ModèleC : `v5-b002759 → v5-b002788`. Exactitude : **False**. Diagnostic de référence : Santeny: titre CAHIER dans un p, clôture signée avant Sarcelles; borne exacte présente malgré proposition automatique située ailleurs.

Sortie Qwen (JSON mis en forme ; réponse brute conservée dans les données) :

```json
{
  "decision": "propose",
  "start_id": "v5-b002759",
  "end_id": "v5-b002788",
  "signatures": [
    "v5-b002754",
    "v5-b002787"
  ],
  "annexes": [
    {
      "start_id": "v5-b002759",
      "end_id": "v5-b002788",
      "relation": "included"
    }
  ],
  "other_documents": [
    "v5-b002789"
  ],
  "uncertain": false,
  "reason": "Le cahier de Santeny commence par le titre 'Des très-humbles et très-respectüeuses remontrances que la paroisse de Santeny...' et se termine par le titre 'CAHIER' suivi de la mention de la paroisse de Sarcelles, qui est un cahier distinct."
}
```

`v5-b002758` — `/TEI.2/text/body/div1/div2[1]/div3[76]/p[1]`, p.107, source[979487:979493]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> CAHIER

`v5-b002787` — `/TEI.2/text/body/div1/div2[1]/div3[76]/p[29]`, p.109, source[992883:993290]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Et ont signé : Buret, syndic;. Lhéry, avocat; H. Jacquemin; Lesson; Gheveun de la Chapelle, seigneur du fief des Lions ; Jean Guyot; Formé ; Cheradame; Lubin; L. Guérin; Thérôze; Gunter; Magrimaux; Buisson; Guérin; Jean Jacquemin, Hubier; Jacquemin; Pierre Lepagnol, et Martin Piilier, greffier.

`v5-b002759` — `/TEI.2/text/body/div1/div2[1]/div3[76]/p[2]`, p.107, source[979518:979782]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Des très-humbles et très-respectüeuses remontrances que la paroisse de Santeny, près Brie-Comte-Robert, a Vhonneur de faire aux Etats généraux qui doivent être tenus à Versailles le 27 avril présent mois (1).

`v5-b002788` — `/TEI.2/text/body/div1/div2[1]/div3[77]/head`, p.109, source[993357:993363]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> CAHIER

## Clergé Paris : fin réparée mais début fusionné avec deux autres paroisses

Cahier du clergé (Paris) — [notice Persée](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2489), tome 5, pages[230, 235]. [XML Stanford figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xx284sn7328/xx284sn7328.xml) ; [numérisation](https://purl.stanford.edu/xx284sn7328).

Référence : `v5-b006015 → v5-b006144 (established)`. ModèleC : `v5-b005969 → v5-b006144`. Exactitude : **False**. Diagnostic de référence : Clergé Paris hors murs: cahier avec arrêté du6mai et trois secrétaires, avant noblesse.

Sortie Qwen (JSON mis en forme ; réponse brute conservée dans les données) :

```json
{
  "decision": "propose",
  "start_id": "v5-b005969",
  "end_id": "v5-b006144",
  "signatures": [
    "v5-b005968",
    "v5-b005998",
    "v5-b006014",
    "v5-b006142",
    "v5-b006143",
    "v5-b006144"
  ],
  "annexes": [],
  "other_documents": [
    "v5-b005967",
    "v5-b006000",
    "v5-b006015",
    "v5-b006145"
  ],
  "uncertain": false,
  "reason": "Le document commence par le titre 'CAHIER' et les articles du clergé de Paris, se terminant par les signatures des députés. Les autres documents sont distincts et ne font pas partie du même cahier de la notice Persée"
}
```

`v5-b006015` — `/TEI.2/text/body/div1/div2[1]/div3[158]/head`, p.230, source[2116327:2116333]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> CAHIER

`v5-b006144` — `/TEI.2/text/body/div1/div2[1]/div3[158]/p[126]`, p.235, source[2158309:2158451]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Royon, chapelain de l’ordre de Saint-Lazare et professeur de philosophie au collège de Louis-le-Grand, secrétaire.

`v5-b005969` — `/TEI.2/text/body/div1/div2[1]/div3[156]/head`, p.229, source[2107408:2107414]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> CAHIER

## Artois : des colonnes intercalées demandent une abstention, pas une plage certifiée

Cahier du clergé de la province d'Artois — [notice Persée](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1578), tome 2, pages[78, 79]. [XML Stanford figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/fz023dp4399/fz023dp4399.xml) ; [numérisation](https://purl.stanford.edu/fz023dp4399).

Référence : `None → None (uncertain_source)`. ModèleC : `v2-b001693 → v2-b001775`. Exactitude : ** None**. Diagnostic de référence : Artois clergé/noblesse: colonnes intercalées dans des p; aucune plage contiguë fidèle pour un seul cahier. Abstention attendue.

Sortie Qwen (JSON mis en forme ; réponse brute conservée dans les données) :

```json
{
  "decision": "propose",
  "start_id": "v2-b001693",
  "end_id": "v2-b001775",
  "signatures": [
    "v2-b001765",
    "v2-b001766",
    "v2-b001767",
    "v2-b001768",
    "v2-b001769",
    "v2-b001770",
    "v2-b001771",
    "v2-b001773"
  ],
  "annexes": [],
  "other_documents": [
    "v2-b001686",
    "v2-b001687",
    "v2-b001688",
    "v2-b001689",
    "v2-b001690"
  ],
  "uncertain": false,
  "reason": "Le document commence par le titre 'PROVINCE D'ARTOIS' et se termine par les signatures des curés et l'approbation de l'évêque, correspondant à la notice Persée donnée. Les autres blocs sont des parties antérieures ou liées à d'autres cahier"
}
```

`v2-b001693` — `/TEI.2/text/body/div1/div2[6]/head`, p.78, source[527295:527313]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> PROVINCE D'ARTOIS

`v2-b001775` — `/TEI.2/text/body/div1/div2[6]/div3[1]/p[78]`, p.79, source[536147:536198]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> 1 pelle, réel ou sur les consommations , direct ou

## Eguilles : périmètre du mémoire Goullin à distinguer du seul corps du cahier

Cahier de la communauté d'Eguilles (Sénéchaussée d'Aix) — [notice Persée](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2581), tome 6, pages[288, 289]. [XML Stanford figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/wg983ft3682/wg983ft3682.xml) ; [numérisation](https://purl.stanford.edu/wg983ft3682).

Référence : `v6-b008136 → v6-b008180 (established)`. ModèleC : `v6-b008136 → v6-b008169`. Exactitude : **False**. Diagnostic de référence : Eguilles: cahier avec mémoire Goullin explicitement joint (article25), sans notice METS distincte retrouvée; choix de dossier explicite, à confirmer indépendamment.

Sortie Qwen (JSON mis en forme ; réponse brute conservée dans les données) :

```json
{
  "decision": "propose",
  "start_id": "v6-b008136",
  "end_id": "v6-b008169",
  "signatures": [
    "v6-b008134",
    "v6-b008135",
    "v6-b008167",
    "v6-b008169"
  ],
  "annexes": [
    {
      "start_id": "v6-b008170",
      "end_id": "v6-b008180",
      "relation": "included"
    }
  ],
  "other_documents": [
    "v6-b008182",
    "v6-b008183",
    "v6-b008184",
    "v6-b008185",
    "v6-b008186"
  ],
  "uncertain": false,
  "reason": "Le cahier d'Eguilles commence par le titre 'CAHIER' suivi des articles et se termine par la signature de la liste des députés. Le mémoire de Goullin est inclus comme pièce annexe. Les autres blocs appartiennent à un cahier voisin ou à des c"
}
```

`v6-b008136` — `/TEI.2/text/body/div1/div2[17]/div3[27]/head`, p.288, source[2583735:2583742]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> CAHIER

`v6-b008180` — `/TEI.2/text/body/div1/div2[17]/div3[28]/p[9]`, p.289, source[2598739:2598787]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> Signé Goullin, maître en chirurgie, à Eguilles.

`v6-b008169` — `/TEI.2/text/body/div1/div2[17]/div3[27]/p[32]`, p.289, source[2592496:2592591]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> laud ; A. Guillaume ; G. Guilton; Armieux, et Saint-Etienne, greffier.

`v6-b008170` — `/TEI.2/text/body/div1/div2[17]/div3[28]/head[1]`, p.289, source[2592658:2592666]. Extrait d’affichage (blancs compactés, 500 premiers caractères maximum ; texte exact complet dans JSONL) :

> MÉMOIRE
