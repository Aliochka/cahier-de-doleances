# Contrôle de qualité et limites

Les nombres courants sont dans `data/quality.json`. Il faut distinguer la fidélité matérielle, la délimitation du parent et la segmentation de ses unités.

## Fidélité matérielle

`verify.py` relit les sources locales et vérifie indépendamment de la construction :

- le texte intégral et l’empreinte de chaque parent, dans la bonne source et la bonne plage ;
- les bornes de chaque unité à l’intérieur du bon parent et de sa version ;
- la reconstruction exacte du texte à partir des plages source puis des positions relatives dans le parent ;
- les identifiants uniques, les références XML et les liens entre blocs et XPath ;
- l’absence de recouvrement accidentel ou de caractère perdu : les plages A/B/C partitionnent le parent entier, notes et blancs compris ;
- l’ordre des unités et les liens précédent/suivant ;
- les correspondances avec les anciens textes d’articles ;
- les empreintes des exports et des 583 fichiers antérieurs/sources figés avant ce travail.

Les corrections manuelles ne remplacent jamais un XML ou une notice. Les tests d’intégration introduisent six corruptions contrôlées : texte remplacé, parent inexistant, mauvais offset relatif, unité débordante, ID dupliqué, passage technique retiré. Les six sont détectées.

## Outil et décisions

Huit tests Python vérifient l’acceptation, une correction exacte, l’incertitude, la limite interne à un bloc, le blocage, les identifiants inventés, les limites inversées, les sauts de page inadmissibles, la confirmation explicite, les sources périmées, les conflits de modification, la chaîne du journal et les protections de boucle locale.

Trois tests de corpus vérifient le lot entier, les corruptions ci-dessus et la propagation d’une décision humaine **synthétique** incertaine vers l’extraction : 29 parents restent exportés, le trentième est retenu dans `withheld.json`. Deux exécutions sur ce même journal temporaire produisent des fichiers identiques octet pour octet. L’export réel conserve maintenant 29 parents validés ; les décisions synthétiques ne sont jamais importées dans son journal.

Playwright/Chromium existants ont vérifié 320, 375, 768 et 1280 px, l’élargissement des contextes, les textes à 200 %, l’absence de défilement horizontal, la navigation clavier, l’enregistrement, la correction et la reprise après rechargement. Les 30 dossiers ont également été ouverts par l’API avec leurs deux contextes. Les résultats navigateur sont conservés dans `data/browser-checks.json`. Une inspection visuelle locale a été effectuée ; aucune capture n’est nécessaire au fonctionnement ou ajoutée au dépôt.

Commandes :

```sh
/usr/bin/python3 docs/tools/1789-document-review/test_review.py
/usr/bin/python3 docs/audits/1789-first-article-corpus/test_corpus.py
/usr/bin/python3 docs/audits/1789-first-article-corpus/verify.py
.venv/bin/ruff check docs/tools/1789-document-review docs/audits/1789-first-article-corpus
.venv/bin/ruff format --check docs/tools/1789-document-review docs/audits/1789-first-article-corpus
node --check docs/tools/1789-document-review/static/app.js
```

Ces tests ciblent exclusivement l’outil expérimental. Aucun test applicatif ni calcul GPU n’est requis : le frontend public, les routes, les bases et les index ne sont pas modifiés.

## Ce que ces résultats ne prouvent pas

La couverture textuelle exacte ne prouve pas la bonne frontière historique de chaque parent. Les périmètres sont des références exploratoires héritées, avec des choix de dossier documentés, notamment les suppléments de Colmar et les pièces de Mirecourt. Ils restent à vérifier dans l’outil. Le modèle n’est plus sollicité ; ses propositions n’interviennent pas dans ces limites.

Les 502 articles B du corpus courant ne sont pas déclarés exacts. Le segmenteur existant peut manquer un marqueur OCR, fusionner une rubrique ou se tromper de portée après une reprise de numérotation. Les compléments C empêchent la perte des caractères mais ne réparent pas automatiquement la structure. Les cinq références anciennes demandant réexamen sont explicitement abaissées à B.

Les 217 A du corpus courant ont des frontières contrôlées dans le TEI par Codex lors d’expériences antérieures, pas une transcription intégralement collationnée ni une validation humaine indépendante. La proportion de B mesure la part restant à examiner, pas la précision de l’extracteur. Les 30 dossiers sont intentionnellement sélectionnés ; aucun taux global sur les 1 305 notices n’est déduit.

À la livraison initiale, aucune vérification humaine réelle n’avait encore eu lieu. La première session utilisateur a désormais examiné les 30 dossiers : 29 validations de parents et une incertitude conservée pour Digne. Le corpus courant exclut Digne ; les articles ne deviennent pas humainement validés du seul fait de cette session.

## Point de contrôle retrouvé pendant l’utilisation : Ferrières

La référence héritée du registre pour `arcpa_0000-0000_1879_num_4_1_2175` finit à 5032843, après « AGRICULTURE. ». Le pilote avait conservé le périmètre plus long, jusqu’à 5034067. Une nouvelle lecture des divisions XML 148–149 confirme « COMMERCE. », puis « JUSTICES SEIGNEURI ALES. » et la clôture/signatures du 14 avril à Ferrières, avant le cahier de Férolles (division 150). Le dernier bloc à conserver est `v4-b013967`, `/TEI.2/text/body/div1/div2[18]/div3[149]/p[3]`.

C’est une contradiction de références documentaires, pas une erreur OCR ni quatre problèmes distincts : le même indicateur était répété dans deux listes. L’interface déduplique et traduit désormais les alertes et affiche ce point de contrôle spécifique. Les données originales et les décisions humaines ne sont pas réécrites. L’export initial fondé sur la référence courte était tronqué. La correction humaine est désormais enregistrée jusqu’au bloc `v4-b013967` et intégrée au corpus régénéré : Commerce, Justices seigneuriales et la clôture sont rétablis. Ne pas considérer cet export initial comme intégralement certifié ; les contrôles de fidélité aux plages ne prouvent pas la bonne portée de ces plages.

## Bilan de la première session humaine

Les 30 dossiers sont examinés : 29 parents validés et Digne laissé incertain à propos des doléances locales qui suivent. Les 33 événements restent dans le journal privé ; ils ne représentent pas 33 documents. Les dernières décisions comptent 57 extrémités acceptées, deux corrigées et une incertaine. Le navigateur a enregistré environ 1 716 secondes d’activité estimée ; ce n’est ni le temps des scripts ni un chronométrage indépendant.

Le corpus passe de 816 à 719 articles : retrait provisoire des 101 candidats de Digne, rétablissement de quatre articles à Ferrières. Les autres nombres d’articles par parent restent identiques. Les 217 unités A actuelles reprennent toujours des contrôles Codex antérieurs ; 502 articles restent B. Aucune validation humaine individuelle des articles n’est déduite de la validation des parents.

Une copie privée du journal et de l’export précédent a été conservée sous `.local/`, hors Git, avant régénération. L’empreinte du journal utilisé figure dans le nouveau manifeste source. Le journal actif n’a pas été modifié par les scripts ni les tests.
