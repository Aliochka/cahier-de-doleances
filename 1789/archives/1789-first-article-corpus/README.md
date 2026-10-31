# Premier corpus d’articles de 1789 et vérification locale

**L’outil est utilisable et le corpus est produit : 29 parents, 719 articles, 4 sections et 793 passages techniques. 30 dossiers examinés dans l’outil : validés humainement : 29 ; incertains : 1 ; bloqués : 0. La validation des parents ne certifie pas chaque article.**

Lancer l’outil depuis la racine du dépôt :

```sh
/usr/bin/python3 1789/tools/document-review/server.py
```

Ouvrir http://127.0.0.1:1789. [Mode d’emploi](../../tools/document-review/README.md).

## Constitution du lot

24 dossiers du pilote et six références documentaires corrigées ou complexes des audits ultérieurs. Sélection intentionnelle, pas un nouvel échantillon de validation statistique. Cinq dossiers par volume, ordres et longueurs variés, numérotations irrégulières (Lawastine, Ribaucourt, Flines), annexes/suppléments (Colmar, Mirecourt), certifications, et corrections de Gray, Châtellerault, Digne, Santeny, Châteauneuf. Aubervilliers apporte un contrôle supplémentaire de rapprochement fort. Les motifs et anciens IDs figurent dans `data/selection.json`.

Aucun nouveau détecteur. Les notices du registre restent intactes. Les références Codex établies lors de l’expérience Qwen sont réutilisées **sans lire les sorties du modèle et sans nouvelle inférence**. Elles priment sur le registre ; les références vérifiées du registre priment ensuite sur les parents hérités du pilote. Cette hiérarchie est explicite dans `reviewlib.Store.base`, et chaque export conserve la frontière automatique originale. Elle ne certifie pas l’absence de toute contradiction documentaire.

| Tome | Cahiers |
| --- | ---: |
| 1 | 5 |
| 2 | 5 |
| 3 | 4 |
| 4 | 5 |
| 5 | 5 |
| 6 | 5 |

## Résultats effectivement produits

- **719 articles : 217 A examinés dans les transcriptions, 502 B proposés.** 69.8 % restent non certifiés individuellement ; ce n’est pas un taux d’erreur mesuré.
- 4 sections B dont la portée reste proposée ; les titres initiaux du document ne sont pas assimilés à des sections autonomes.
- 793 passages C, compléments techniques du texte parent, sans prétention à une revendication historique autonome. Ils comprennent aussi titres, préambules, blancs, notes et signatures ; ils ne sont pas tous destinés à la recherche.
- Cinq anciennes références d’articles demandant un réexamen dans les diagnostics V2 restent B malgré leur antériorité. Aucun ancien identifiant n’est écrasé.
- 29 parents validés humainement dans cet export ; 1 dossier(s) non exporté(s). Les références Codex restent traçables. **La validation du parent ne valide pas automatiquement ses articles.**
- Dossiers retenus hors export : Cahier du tiers-état de Digne (Sénéchaussée de Forcalquier) (uncertain).
- Ferrières : correction humaine intégrée jusqu’aux signatures, bloc v4-b013967 ; Commerce et Justices seigneuriales sont conservés.

Le segmenteur V2 et ses rôles XML sont réutilisés. Les références d’articles examinées sont conservées séparément des propositions brutes ; les propositions qui les recouvrent ne sont pas cumulées avec elles. Le texte restant est conservé en C, et non transformé arbitrairement en articles. Aucun nouvel examen individuel de ces 719 unités n’est revendiqué.

## Contrôles et limites

[QUALITY.md](QUALITY.md) détaille les invariants et tests. Tous les caractères de chaque parent sélectionné sont couverts exactement une fois par les plages des unités. Chaque parent correspond à sa tranche Stanford exacte. Ce contrôle matériel ne garantit pas que les frontières B ou les périmètres hérités sont historiquement parfaits. **Un réexamen a notamment retrouvé une fin trop courte à Ferrières dans la référence du registre : voir le point de contrôle documenté dans QUALITY.md.** Ferrières : correction humaine intégrée jusqu’aux signatures, bloc v4-b013967 ; Commerce et Justices seigneuriales sont conservés.

L’interface a été testée à 320, 375, 768 et 1280 px, avec agrandissement du texte à 200 %, navigation clavier, sélection, enregistrement et reprise. Les essais ont exclusivement utilisé des journaux temporaires synthétiques. Le journal réel est maintenant pris en compte : **30 dossiers examinés dans l’outil : validés humainement : 29 ; incertains : 1 ; bloqués : 0. La validation des parents ne certifie pas chaque article.** L’outil a enregistré 33 événements et environ 1716 secondes d’activité de navigation déclarée ; ce compteur n’est pas une mesure indépendante du travail humain. Son empreinte est conservée dans `source-manifest.json`, sans exporter les noms et remarques du journal privé.

**Aucun changement applicatif, PostgreSQL, index ou embedding. Aucun LLM appelé, aucun corpus téléchargé, aucune correction OCR.** 583 fichiers antérieurs/sources contrôlés inchangés. Les services de test sont des serveurs de boucle locale, pas des déploiements.

## Données et reproduction

[DATA.md](DATA.md) décrit les exports, identifiants et relations. Pour régénérer :

```sh
/usr/bin/python3 1789/archives/1789-first-article-corpus/build.py
/usr/bin/python3 1789/archives/1789-first-article-corpus/verify.py
/usr/bin/python3 1789/archives/1789-first-article-corpus/report.py
```

Les corpus complets locaux `data/parents.jsonl.gz`, `units-A.jsonl.gz`, `units-B.jsonl.gz`, `units-C.jsonl.gz` et les propositions brutes sont **exclus de Git**, conformément au nettoyage des gros artefacts. Ils existent sur cette machine et sont régénérables avec les sources/références locales. Les rapports, scripts, sélection, correspondances et empreintes restent versionnables ; `data/extraction-manifest.json` conserve leurs tailles et SHA-256. Aucun lien externe de sauvegarde n’est inventé. Les journaux humains doivent être sauvegardés séparément.

`prepare.py` reproduit la sélection initiale ; ne pas le relancer pour enregistrer des décisions. Une modification du lot nécessite une nouvelle version explicitement documentée. Les anciens audits et leurs IDs restent inchangés. Les transcriptions Stanford et les métadonnées Persée gardent leurs provenances et conditions distinctes ; cet outil ne vaut pas autorisation de republication. Aucune publication sur le site n’est effectuée.

## Réponses aux dix questions

1. **Vérifier sans XML ?** Oui, panneaux de blocs, pages, titres, voisins du contexte, liens source et contexte extensible.
2. **Corriger ?** Oui, choix d’un bloc existant pour chaque extrémité ; une limite interne à un bloc reste signalée, jamais fabriquée.
3. **Conservation des décisions ?** Journal append-only, horodaté, lié aux empreintes, historique et contrôle de concurrence ; reprise après redémarrage. La validation exige une action explicite de l’utilisateur.
4. **Dossiers préparés ?** 30, cinq par volume, accessibles parmi les 1 305 notices.
5. **Articles ?** 719, dont 217 examinés antérieurement par Codex et 502 proposés.
6. **Part incertaine ?** 69.8 % des articles sont B. Les A ne sont pas des validations humaines ; sections B et passages C sont séparés.
7. **Parents intégraux ?** Oui pour les périmètres sélectionnés, avec notes, signatures et annexes présentes dans ces plages. Cela ne prouve pas la complétude historique de l’édition ni la justesse absolue du dossier.
8. **Retour au contexte ?** ID parent/version de périmètre, offsets Unicode relatifs, XPath/blocs, pages, provenance et voisins techniques disponibles.
9. **Freins à l’indexation ?** Le dossier incertain reste exclu ; les parents exportés ont leur statut explicite. B non examinés, rôle de certaines annexes et rubriques, OCR et textes de paratexte. Un essai isolé est possible en filtrant les types/statuts/`search_eligible`, sans prétendre à un corpus certifié. Aucun embedding produit ici.
10. **Étendre aux 1 305 ?** Vérifier les priorités, traiter les limites internes/composites, enregistrer les décisions, étendre explicitement le lot puis régénérer et contrôler. Garder un contrôle indépendant d’articles et de parents séparé, sauvegarder les journaux et gérer les versions ; pas de généralisation automatique.

## Dossiers et articles

| Tome | Dossier | Articles A/B | Origine |
| --- | --- | ---: | --- |
| 1 | Cahier du clergé de la sénéchaussée d'Agen | 9/61 | 1789-document-registry:verified_reference |
| 1 | Cahier de la noblesse de la sénéchaussée d'Agen | 3/63 | 1789-extraction-pilot:ap1789-pilot-d1:jt959wc5586:e3853dbbb35a07b290ab |
| 1 | Cahier du clergé du bailliage d'Alençon | 5/82 | 1789-extraction-pilot:ap1789-pilot-d1:jt959wc5586:c8caba17ed36b64403f1 |
| 1 | Cahier de la noblesse du bailliage d'Alençon | 2/10 | 1789-extraction-pilot:ap1789-pilot-d1:jt959wc5586:bcdc69723b9153e44463 |
| 1 | Cahier de Gray (Bailliage d'Amont ) | 0/32 | 1789-qwen-boundaries/data/reference-validation.jsonl |
| 2 | Cahier de la noblesse de la sénéchaussée d'Angoumois | 4/52 | 1789-document-registry:verified_reference |
| 2 | Cahier du clergé de la sénéchaussée d'Anjou | 18/62 | 1789-document-registry:verified_reference |
| 2 | Cahier de Lawastine (Bailliage de Bailleul) | 5/0 | 1789-extraction-pilot:ap1789-pilot-d1:fz023dp4399:10c1f778fd324706de33 |
| 2 | Cahier de la noblesse de la sénéchaussée du Beaujolais | 15/8 | 1789-extraction-pilot:ap1789-pilot-d1:fz023dp4399:3e6a4db201abec55cb3e |
| 2 | Cahier du clergé de la sénéchaussée de Châtellerault | 0/0 | 1789-qwen-boundaries/data/reference-development.jsonl |
| 3 | Cahier de la ville de Colmar (District de Colmar et Schlesladt) | 8/28 | 1789-document-registry:verified_reference |
| 3 | Cahier de la communauté de Terre-Franche et du comté de Ribeaucourt (Bailliage de Douai) | 11/0 | 1789-extraction-pilot:ap1789-pilot-d1:mc666yy3026:f330cd449d20585043c2 |
| 3 | Cahier de la communauté de Flines (Bailliage de Douai) | 13/0 | 1789-extraction-pilot:ap1789-pilot-d1:mc666yy3026:97af66caeb2eea3e1442 |
| 3 | Cahier de la communauté des frères mineurs de Carces (Sénéchaussée de Draguignan) | 8/0 | 1789-extraction-pilot:ap1789-pilot-d1:mc666yy3026:f9e19530b4e33ccf95c7 |
| 4 | Cahier du clergé du bailliage de Mirecourt | 5/0 | 1789-extraction-pilot:ap1789-pilot-d1:xg914wh0253:fbbba92b6bb96154d07a |
| 4 | Cahier de la noblesse du bailliage de Mirecourt | 11/14 | 1789-document-registry:verified_reference |
| 4 | Cahier d'Arnouville ou Ermenouville (Paris) | 12/0 | 1789-extraction-pilot:ap1789-pilot-d1:xg914wh0253:2d9eb8a19442dcf619d3 |
| 4 | Cahier d'Aubervilliers-les-Vertus (Paris) | 0/4 | 1789-qwen-boundaries/data/reference-validation.jsonl |
| 4 | Cahier de Ferrières-en-Brie (Paris) | 22/3 | 1789-document-registry:verified_reference |
| 5 | Cahier de Perigny en Brie (Paris) | 15/0 | 1789-extraction-pilot:ap1789-pilot-d1:xx284sn7328:0e4e17a10525b854d367 |
| 5 | Cahier de Pierrelez (Paris) | 9/0 | 1789-document-registry:verified_reference |
| 5 | Cahier de Plessis-Secqueville (Paris) | 9/0 | 1789-extraction-pilot:ap1789-pilot-d1:xx284sn7328:83dfa5bae7397bf30538 |
| 5 | Cahier de Puteaux (Paris) | 11/0 | 1789-extraction-pilot:ap1789-pilot-d1:xx284sn7328:9a570b0100acb2734ded |
| 5 | Cahier de Santeny (Paris) | 0/0 | 1789-qwen-boundaries/data/reference-validation.jsonl |
| 6 | Cahier de l'ordre de la noblesse du bailliage de Toul | 2/32 | 1789-extraction-pilot:ap1789-pilot-d1:wg983ft3682:8dab1fac50b6320bcb33 |
| 6 | Cahier du clergé de Vic (Bailliage de Toul) | 8/34 | 1789-document-registry:verified_reference |
| 6 | Cahier de la communauté d'Albertas (Sénéchaussée d'Aix) | 9/0 | 1789-extraction-pilot:ap1789-pilot-d1:wg983ft3682:c33d108ba660e47d2e75 |
| 6 | Cahier de la communauté de Beaurecueil (Sénéchaussée d'Aix) | 3/0 | 1789-extraction-pilot:ap1789-pilot-d1:wg983ft3682:f7df571f2f7d6b380e1b |
| 6 | Cahier de la communauté de Châteauneuf (Sénéchaussée d'Aix) | 0/17 | 1789-qwen-boundaries/data/reference-validation.jsonl |
