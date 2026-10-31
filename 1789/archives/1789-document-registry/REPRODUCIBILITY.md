# Reproduction, provenance et droits

## Sources et isolement

Les sources Stanford sont les six XML déjà présents dans `../../sources/stanford/926fd3cd986a3c3d411e93d1845fff6475cb2602/`. La révision et les six empreintes figurent dans `data/freeze.json`. Les helpers antérieurs sont chargés par chemin et utilisés en lecture ; les commandes `main()` des anciens audits ne sont jamais exécutées. `prior-audits-sha256.json` contrôle 493 fichiers antérieurs ; le contrôle final est dans `data/checks.json`.

L’expérience utilise Python 3.10.12 et lxml 4.8.0 locaux. Aucun paquet nouveau installé. Les données sources XML restent ignorées par Git. Les métadonnées brutes de réseau sont également en cache ignoré ; les champs normalisés nécessaires à la reproduction, y compris les déclarations de droits et les références OAI, sont conservés dans les fichiers comprimés. Les empreintes des réponses et les requêtes sont dans `data/access-log.json`. Les originaux METS réutilisés sont identifiés par leurs SHA et XPath dans `catalogue.jsonl.gz`.

## Fichiers et commandes

Les JSONL volumineux sont fournis en gzip, sans perte. `archive_manifest.json` associe empreintes comprimées et décomprimées. Le registre référence des plages, pas une nouvelle copie de tous les textes. Aucun TEI Persée dans les livrables.

Depuis la racine du dépôt :

```sh
/usr/bin/python3 1789/archives/1789-document-registry/materialize.py
/usr/bin/python3 1789/archives/1789-document-registry/build.py
/usr/bin/python3 1789/archives/1789-document-registry/evaluate_zones.py
/usr/bin/python3 1789/archives/1789-document-registry/finalize.py
/usr/bin/python3 1789/archives/1789-document-registry/audit_checks.py
```

Ces commandes utilisent les snapshots locaux et n’appellent pas de base. `collect.py` sert seulement à documenter et, si nécessaire, reproduire la collecte publique ; il n’est pas requis pour relire le registre. `prepare_review.py` a servi une fois à figer l’échantillon : **ne pas le relancer sur les annotations**. Il refuse d’écraser la sélection existante. Ne pas changer la graine ni remplacer les échecs.

`review_pack.py`, `brief_review.py`, `zone_pack.py` et `inspect_abstentions.py` permettent de revoir les emplacements ; ils n’attribuent pas de validation. `review_decisions.json` et `review_targets.json` sont les décisions explicites de lecture ; `annotations.jsonl` en est la projection, avec références et portée. `evaluate_zones.py` contient une référence de lecture écrite, distincte du détecteur. Les références positives de frontières se rapportent aux extrémités du TEI, sans garantie historique/OCR.

Le gel protège les octets des règles et échantillons ; trois fichiers gelés conservent leur ordre d’import initial (exception Ruff I001 uniquement). Aucun changement de règles après lecture. Les durées de calcul sont mesurées, les durées humaines ne le sont pas. Le SHA de l’automatique doit rester identique lors d’un second calcul ; seule la durée du résumé peut changer.

## Collecte complémentaire

[Documentation OAI Persée](https://www.persee.fr/entrepot-oai), [Identify](https://oai.persee.fr/oai?verb=Identify), ensemble `persee:serie-arcpa:doc`, `metadataPrefix=oai_dc`. Requêtes séquentielles avec pause de 1,2 s et délai de 30 s, pas de collecte des textes ni de contournement. 90 notices cibles réutilisées ; 73 requêtes supplémentaires enregistrées ; 1 305 notices obtenues. Jetons opaques suivis avec `verb=ListRecords&resumptionToken=...`, sans réenvoyer les autres paramètres. Le collecteur est borné et s’arrête sur erreur ; le journal conserve statuts HTTP, erreurs OAI et empreintes. L’année dans les identifiants n’est pas une date de rédaction.

## Conditions de réutilisation distinctes

**Métadonnées Persée.** Attribution : Persée — UAR 3602, ENS de Lyon/CNRS, notices des Archives parlementaires, liens documentaires dans chaque ligne. Identify annonce les métadonnées sous **CC BY-SA 3.0**. Les notices contiennent aussi une déclaration **CC BY-NC-SA 3.0 concernant les contenus**, et un avertissement générique. Ne pas appliquer ce dernier indistinctement aux métadonnées, ni transformer l’accès public en autorisation universelle. Les [CGU](https://www.persee.fr/cgu) distinguent services, jeux et contenus ; pour une republication publique pérenne du registre dérivé, confirmer avec Persée l’articulation et les obligations de licence/attribution. Les champs de droits originaux sont conservés. Aucun contact nouveau envoyé. La présente étude locale ne prétend pas accorder de droits sur les textes ou images Persée.

**Transcriptions Stanford.** [Dépôt à la révision figée](https://github.com/StanfordUniversityLibraries/ap_tei/tree/926fd3cd986a3c3d411e93d1845fff6475cb2602). Les audits précédents distinguent textes historiques/édition, TEI, métadonnées et images ; ils n’ont pas trouvé de fichier LICENSE autonome ni de `availability` explicite pour les six TEI. Le domaine public historique et la mention de volumes ne constituent pas une licence séparée de tous les enrichissements. Garder provenance et attribution ; clarifier les conditions avant republication massive. Images et plateformes ont leurs propres conditions. Cette mission ne republie aucun texte historique sur le site et ne redistribue pas d’images.
