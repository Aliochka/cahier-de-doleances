# Métadonnées publiques Persée

## Accès observé le 27 octobre 2026

Les deux points d’entrée fournis ont répondu HTTP200 en XML OAI via le client Python. L’outil de lecture web ne savait pas ouvrir ces URL XML; cet échec de client n’était pas une indisponibilité du serveur. Aucune restriction n’a été contournée.

- [Ensemble collection](https://oai.persee.fr/oai?verb=ListRecords&metadataPrefix=oai_dc&set=persee:serie-arcpa).
- [Ensemble documents](https://oai.persee.fr/oai?verb=ListRecords&metadataPrefix=oai_dc&set=persee:serie-arcpa:doc).
- [Identify](https://oai.persee.fr/oai?verb=Identify).
- [Documentation de moisson](https://www.persee.fr/entrepot-oai).

Le premier ensemble **n’est pas limité aux volumes** : sa première page contient la série puis19 notices de volumes. Les six tomes recherchés y figurent. Le second contient des documents de plusieurs tomes, y compris le tomeVII et ses tables. Les résultats ne sont ni des cahiers tous valides, ni un ordre de pagination historique fiable.

Le service livre20 notices par lot observé. `Identify` annonce une granularité UTC à la seconde et une gestion des suppressions `transient`; une collecte ultérieure devrait conserver les datestamps et distinguer notices supprimées, absentes et non parcourues. Les réponses `oai_dc` observées incluent aussi des extensions `dcterms` : elles ont été conservées, sans prétendre à une validation XSD complète. Un jeton a été suivi dans chaque ensemble : `verb=ListRecords&resumptionToken=...`, sans ajouter `set` ou `metadataPrefix`. Les secondes pages ont20 notices, un curseur20, aucun identifiant commun avec la première page et un autre jeton non vide. Arrêt volontaire après cette vérification : **la fin des listes et la durée de vie des jetons n’ont pas été testées**. Les jetons sont utilisés tels que reçus, sans décodage/reconstruction de leur état. Voir [pagination-check.json](data/pagination-check.json) et la [spécification OAI-PMH](https://www.openarchives.org/OAI/openarchivesprotocol.html#FlowControl).

## Collecte bornée

Deux pages de chaque ensemble, `Identify`, `robots.txt`, six `GetRecord persee_mets` de volumes et les DC des 72 notices sélectionnées; quatre DC ont été repris des lots déjà obtenus. **80 requêtes HTTP journalisées, 1,584,974 octets**, environ1,6 Mo; toutes HTTP200. Un seul appel à la fois, cache, pause entre appels, arrêt sur erreur HTTP, sans relance en boucle. Les documentations ont aussi été consultées via l’outil web.

Les six METS sont des **métadonnées de tables des matières**, pas des textes TEI. Ils fournissent les titres, types, positions relatives et liens de notices. Leurs liens vers d’autres ressources n’ont pas été suivis automatiquement. Aucune transcription, image, PDF ou page de texte historique Persée téléchargée. Les réponses complètes restent dans `.cache/`, ignoré par Git; les 72 notices normalisées sont conservées avec leur attribution.

`robots.txt` interdit l’indexation web générale. Nous avons limité les appels à l’API OAI explicitement communiquée par le producteur et documentée pour la moisson, sans exploration de pages du portail. Cette lecture du périmètre est explicitée ici; elle ne vaut pas autorisation générale de crawler les autres services.

## Champs effectivement présents dans le lot

| Information | Champ / provenance | Limite |
|---|---|---|
| Identifiant OAI | `header/identifier`, `oai:persee:article/...` | Identifiant de notice, pas d’article numéroté du cahier |
| Identifiant documentaire | suffixe `arcpa_..._num_...` | Distinct de l’identifiant technique Stanford |
| Titre | `dc:title` | Intitulé éditorial de catalogue, pas nécessairement titre imprimé littéral |
| Volume | `dcterms:isPartOf` et identifiant structuré du volume | Pas déduit artificiellement du titre; références croisées contrôlées |
| Pages | `dc:coverage`, `pp. x-y` / `p. x` | Pages imprimées, aucune borne intra-page |
| Nombre de pages | `dcterms:extent` | Pas nombre de pages manuscrites du cahier original |
| Date | `dc:date=1879` pour les 72 notices | **Année d’édition**, pas date de rédaction en1789 |
| Mise à jour | OAI `datestamp` | Date de notice, pas révision du texte OCR |
| Type | `dc:type` / METS `TYPE` | `griev` est une catégorie large, pas certificat de cahier autonome |
| URL | `dc:identifier`, HTTPS du portail | Aucun offset textuel Stanford |
| Bibliographie | `dcterms:bibliographicCitation`, `dc:description` | Référence d’édition à conserver comme telle |
| Langue / diffuseur / droits | `dc:language`, `dc:publisher`, `dc:rights`, `dcterms:accessRights` | Déclarations de portées différentes, ne pas réduire à « libre » |
| Localité, ordre, territoire | Titres et ancêtres METS | Pas de champs systématiques de commune normalisée, d’ordre ou de date historique dans les DC observés |

Les 72 notices ont un titre et une plage de pages, et les identifiants structurés les rattachent aux six tomes. **Aucune notice réellement dépourvue de ces trois informations n’a été rencontrée dans ce lot** : le comportement sur ces manques reste à tester; on ne simule pas un résultat observé. Les dates historiques et les limites intra-page sont en revanche absentes comme champs structurés dédiés.

## Couverture de catalogue, pas décompte historique

| Tome | `griev` du METS |
|---|---:|
| 1 | 24 |
| 2 | 181 |
| 3 | 223 |
| 4 | 347 |
| 5 | 298 |
| 6 | 232 |


Total 1 305 entrées `griev`. Dans les 72 notices testées :58 `griev`,7 `article`,4 `table`,1 `index`,1 `edito`,1 `liminaire`. Les listes de nobles du Poitou et d’Autun sont elles-mêmes `griev`; le procès-verbal du Béarn est également dans cette catégorie. Les entités `theme` organisent les territoires et n’ont pas été tirées comme documents individuels. Un identifiant et un type ne prouvent ni présence intégrale du cahier, ni absence de pièces associées.

## Réutilisation : déclarations observées

[Identify](https://oai.persee.fr/oai?verb=Identify) annonce les **métadonnées sous CC BY-SA 3.0**. Les notices portent aussi une déclaration concernant les **contenus sous CC BY-NC-SA 3.0**, plus un texte générique de droits. Ces périmètres doivent rester distincts. Les [CGU](https://www.persee.fr/cgu), notamment§5 et§12.2.1, décrivent l’usage non commercial des services/jeux de données et l’attribution à Persée avec origine et lien. La [documentation OAI](https://www.persee.fr/entrepot-oai) distingue métadonnées publiques et contenu réservé à des utilisateurs identifiés.

Le registre attribue ses notices à **Persée — UAR 3602, ENS de Lyon/CNRS**, conserve les déclarations et leurs URL. Pour une reprise publique pérenne, confirmer le périmètre applicable au jeu dérivé, l’articulation des déclarations et les obligations de licence; aucune autorisation de republication des textes ou images n’est déduite de cet accès. Aucun contact envoyé pendant cette étude.
