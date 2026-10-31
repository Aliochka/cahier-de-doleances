# Données de travail

- **registry/** : données du registre Persée–Stanford, avec leurs statuts et provenances historiques.
- **article-corpus/** : corpus initial et références de ses 29 cahiers ; ne pas y substituer silencieusement les corrections humaines ou une extraction globale.
- **review-exports/** : sorties existantes de l’outil, sans régénération automatique.
- **segmentation-proposals/** : comparaison des segmentations et signalements ; propositions distinctes des décisions.
- **private/document-review/** : journaux réels et sessions. Confidentiel, ignoré par Git.
- **corpus/<version>/** : convention réservée à la future extraction globale ; aucun résultat global nouveau créé ici.

Les manifestes et données ont conservé leur contenu d’origine. Certains champs désignent donc des chemins historiques. Utiliser le résolveur `1789/cahier1789_paths.py` pour les lectures par ces références, et non une réécriture des JSON.

Les liens `archives/<expérience>/data` pointent vers ces dossiers uniques pour les expériences encore utilisées par les outils. Les autres jeux de résultats historiques restent dans leur archive d’origine.
