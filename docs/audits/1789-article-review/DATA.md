# Décisions, positions et exports

## Sources immuables

Le lecteur réutilise les quatre exports du premier corpus : parents et unités A/B/C gzip, issus des six XML Stanford figés. Il ne découvre pas de nouveaux cahiers et ne réexécute pas l’extracteur d’articles. Le jeu courant comprend 29 parents humainement validés ; Digne n’y figure pas.

Les textes sont reconstruits uniquement par tranches des sources `itertext()` existantes, sans normalisation, modernisation, correction OCR ni séparateur ajouté. Les positions sont des points de code Unicode semi-ouverts `[start,end)`, pas des octets ou indices UTF-16. Le navigateur convertit une sélection en positions Unicode et vérifie que la sélection correspond exactement à la source ; l’utilisateur ne calcule pas les offsets.

Les notes explicitement balisées XML restent dans le parent et les plages techniques ; elles sont exclues du texte fusionné d’un article ou passage revendicatif. Les notes éditoriales présentes dans un simple paragraphe peuvent encore exiger une décision humaine ; le logiciel ne devine pas leur nature sémantique.

## Identifiants et versions

Les unités inchangées gardent leur ID initial. Une correction de géométrie, fusion, séparation ou changement de type produit un ID `ap1789-reviewed-unit-1:…`, déterministe pour le type, les plages et la version de périmètre. Une correction du seul numéro garde l’ID et crée une nouvelle révision de décision. Les numéros déclarés par un lecteur portent `number_origin=human_attribution` ; le texte original et les propositions d’origine restent conservés.

`origin_ids` relie les fragments aux propositions initiales ; `original_proposals` les expose dans l’export. Les remplacements intermédiaires sont traçables par les images avant/après du journal. Les liens précédent/suivant suivent l’ordre matériel des unités actives (paratexte compris), sans certification de succession historique exhaustive.

La version d’une page de travail comprend l’empreinte des fichiers du corpus, le `parent_extent_id`, l’empreinte XML, les bornes courantes du parent, son statut et le dernier événement de ses frontières. Une page ancienne est refusée si cette version ou la dernière décision d’unités du cahier a changé.

Les décisions d’articles sont réappliquées seulement au même périmètre et à la même source. Un changement de source/périmètre ne migre pas automatiquement les validations. Un retour à des bornes et sources matériellement identiques reste compatible ; une simple nouvelle date de confirmation du parent n’annule pas une géométrie inchangée.

## Journal d’unités

`article-decisions.jsonl` utilise exactement les fonctions de verrouillage/lecture et la convention de chaîne SHA-256 du journal des cahiers, dans un fichier distinct. Chaque événement contient :

- `id`, `document_id`, `parent_extent_id`, `source_sha256`, `version` ;
- `action` : validate, correct, merge, split, missing, classify, number, uncertain ou undo ;
- `date`, `reviewer`, `actor_type=human`, remarque et confirmation explicite ;
- `previous_event_id` du cahier et `previous_hash` global ;
- `before` et `after` : descripteurs complets des unités concernées, plages originales/corrigées, type, numéro, origine, ancien état ;
- `affected_ids`, empreinte de la prévisualisation, version de méthode et `event_hash`.

Le texte historique n’est pas dupliqué dans chaque événement : les plages et empreintes suffisent à le reconstruire. Les opérations sont atomiques à l’échelle d’un événement sous verrou. Un groupe conserve un descripteur pour chacune de ses unités, ce qui donne les mêmes garanties matérielles qu’une série de validations individuelles. Une annulation est un nouvel événement inverse ; les événements antérieurs restent intacts. Une altération ou une ligne JSON incomplète bloque la lecture au lieu d’être ignorée.

Les noms et remarques restent dans le journal local. Le serveur est uniquement local, protégé contre les écritures d’une autre origine ; le pseudonyme est déclaratif, pas une authentification ou certification juridique.

## Types et états indépendants

| Type | Signification | Éligibilité expérimentale |
| --- | --- | --- |
| article | Article historique identifié/proposé | Possible même A/B non validé, état explicite |
| section | Subdivision historique identifiée/proposée | Possible avec statut explicite |
| claim_passage | Passage revendicatif technique classé par un lecteur | Possible, jamais présenté comme article |
| technical_passage | Texte conservé non encore qualifié | Non |
| paratext | Titres, notes, signatures ou autre paratexte classé | Non |

`source_status` conserve A/B/C pour les propositions initiales et les simples requalifications. Une nouvelle unité géométrique créée humainement porte `human_created`, avec ses origines A/B/C dans `original_proposals` ; elle n’est pas présentée comme une nouvelle proposition automatique. `review_status` distingue codex_examined, automatic_proposal, technical_unclassified, human_validated, human_corrected et uncertain. `validation_status` peut en outre devenir review_required si une ancienne validation n’est plus compatible. Un groupe comportant une anomalie ou une incertitude est refusé ; l’examen individuel et la confirmation de l’alerte restent possibles.

Une classification C ne peut pas choisir automatiquement le type article. Pour reconnaître un article oublié dans une plage C, il faut utiliser l’action missing, définir la plage et prévisualiser cette décision humaine. Les unités résiduelles ne deviennent pas des revendications par défaut.

## Exports locaux

`units.jsonl.gz` contient toutes les unités actives, y compris celles exclues de la recherche. Chaque ligne comporte identifiants, type, numéro et origine de son attribution, texte exact et SHA-256, `spans`, positions relatives au parent, pages, XPath/blocs, section, source, propositions originales, état de validation, `last_event_id` et version de parent.

- `indexing_eligible` exige un parent courant compatible et humainement validé, un type article/section/passage revendicatif et l’absence d’incertitude/invalidation. Il s’agit d’un indicateur expérimental, pas d’une publication.
- `publication_ready` est plus conservateur : examen/correction humaine de l’unité et aucune alerte restante. Il ne constitue pas une vérification juridique des droits ni une autorisation de déploiement.
- `invalidated.jsonl.gz` recense les parents incompatibles et les décisions liées à d’anciennes versions.
- `summary.json` sépare types, origines A/B/C et validations ; `manifest.json` conserve les empreintes des fichiers.
- `initial-summary.json` et `input-manifest.json` conservent l’état et la provenance initiaux ; ils ne sont pas réécrits par le bouton d’export.

Les gzip sont générés sans horodatage variable et les objets ordonnés, pour permettre une comparaison octet à octet. Les tests comparent réellement deux exports après relecture du même journal.
