# Balayage des six volumes et décision

**Ne pas lancer encore une extraction systématique en considérant ses parents comme fiables.** Le balayage expérimental des six volumes a été réalisé et archivé; il révèle des problèmes bloquants pour une extraction systématique de contenu retenu. Continuer un inventaire non certifié reste possible, mais n’apporte pas la garantie documentaire recherchée.

## Diff global réel

La V1 recensait 4 448 signaux, dont 1 278 hypothèses admises. La V2 classe 1 954 ancres : 1 197 autonomes, 43 associées, 174 parties, 121 hors périmètre, 55 incertaines et 364 replis `mention`. **Les deux inventaires n’ont pas le même cadre** : V2 classe toutes les divisions feuilles et certains titres internes, V1 conservait aussi de nombreuses mentions courantes. 1 954 contre 4 448 ne mesure ni précision ni rappel.

| Volume | V1 admis | V2 autonomes | V2 associés |
|---|---:|---:|---:|
| 1 | 31 | 20 | 0 |
| 2 | 187 | 171 | 12 |
| 3 | 212 | 184 | 12 |
| 4 | 356 | 348 | 4 |
| 5 | 299 | 292 | 6 |
| 6 | 193 | 182 | 9 |


Sur les 1 278 ancres précédemment admises : 1 166 deviennent autonomes, 13 associées, 40 parties, 31 hors périmètre, 25 incertaines, 1 repli `mention`; 2 ne sont plus proposées. Il y a 61 nouvelles ancres admises par rapport à la V1. Aucun de ces ajouts n’est automatiquement validé.

1 276 identifiants d’ancres communs sont conservés; 58 intervalles associés à une ancienne ancre changent. Six pièces admises sont rattachées à un autre dossier : **1 234 hypothèses non rattachées**, contre 1 240 admissions en comptant ces six pièces. Ce ne sont pas 1 234 cahiers certifiés.

Les [diffs complets](data/v1-v2-document-diff.jsonl), [classifications](data/v2-document-predictions.jsonl) et [anomalies](data/global-anomalies.jsonl) sont conservés. 26 alertes : 24 racines scindées et 2 admissions très courtes, dont l’intitulé collectif du dossier d’Arles. Une alerte demande un contrôle; elle n’est pas une erreur certifiée en elle-même.

## Changements suspects effectivement examinés

- **Grasse**, III, `div2[24]/div3[3]/p[50]` : « DEMANDES ET DOLÉANCES / Du clergé de Grasse et de Vence, auxquelles les curés… n’ont pas souscrit », suivi de deux demandes et de signatures. Disparition d’une pièce réellement distincte : manque de reconnaissance de cette formule.
- **Montargis**, IV, `div2[2]/div3[1]/p[54]`, « :Doléances pour te peuple. » : disparition d’une rubrique auparavant surinterprétée, cohérente avec le diagnostic de développement. La perte d’une ancre n’est donc pas toujours un document manqué.
- **Anjou clergé** : régression de classification et de rattachement des chapitres II–III. **Mirecourt noblesse** : confusion entre corps nobiliaire et corps professionnel.
- Sur les trente anciens parents, **28 intervalles V2 sont strictement identiques**. Pour Beaurecueil, les 26 caractères supplémentaires sont uniquement du blanc de mise en forme : pas une nouvelle pièce absorbée. Pour Anjou clergé, la différence est documentaire et grave. Égalité d’intervalle et bonne classe sont deux contrôles différents.

Ces contrôles globaux sont exploratoires, effectués après l’évaluation; ils ne sont pas ajoutés au dénominateur du test nouveau.

## Ce qui peut être conservé

Provenance, empreintes, intervalles Unicode et XPath; parents complets; classement séparé des pièces associées; exclusion des absences explicites et des récits hors 1789; mécanisme de référence figée; priorité aux marqueurs documentaires plutôt qu’à une segmentation sémantique. Pecqueuse confirme le traitement multi-paragraphe sans équivalence article=`p`.

## Prochaine itération prioritaire, sans la commencer ici

1. **V3 sur les cas désormais de développement** : reconnaître « Demandes et doléances »; restreindre les motifs professionnels; distinguer liste/mention/hors périmètre; préserver les continuations. Ajouter aux contrôles de parents Anjou, Mirecourt, Courtiches, Grasse et Minimes.
2. Retirer ou fortement contraindre la détection nominale des rubriques qui tronque Grigny; traiter explicitement clôtures et marqueurs OCR raisonnablement déterministes. Ne pas rétablir automatiquement les chiffres illisibles de Montigny.
3. Geler V3 puis sélectionner un nouveau lot **encore inédit**, avec zones continues et contrôle de notes/signatures. Ne pas recycler le lot V2 comme preuve de généralisation V3.
4. Faire relire une partie de la référence et des fac-similés par un lecteur indépendant, chronométrer son travail. Puis envisager un lot d’extraction plus grand **avec quarantaine**, jamais une publication automatique.

Les cahiers sans titre canonique, les dossiers composites, PV, pouvoirs, suppléments, numérotations OCR dégradées, notes en paragraphes ordinaires et changements de sections restent soumis à contrôle. Aucune estimation de milliers de documents fiables ou de journées humaines n’est fondée à ce stade.
