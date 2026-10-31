# Extraction — composants réutilisés

`segmentation.py` est le segmenteur existant déplacé depuis l’outil de vérification, **sans modification de ses règles ni de son contenu**. Il s’agit d’une bibliothèque, pas d’une commande d’extraction globale.

Il utilise les primitives documentaires V2 conservées dans `../archives/1789-extraction-v2/` et `../archives/1789-extraction-200/`. Les lecteurs Stanford et la provenance historiques sont aussi réutilisés, sans nouvelle implémentation. Le module est chargé par les outils via leur initialisation des chemins.

Les scripts anciens `extract.py`, `build.py`, etc. restent dans leurs expériences : chacun décrit et peut reproduire un protocole précis. Ne pas les considérer comme une nouvelle chaîne globale et ne pas les exécuter pendant une simple vérification de déplacement.

Les journaux humains sous `../data/private/document-review/` sont prioritaires. Les propositions de segmentation sous `../data/segmentation-proposals/` restent distinctes ; aucune proposition n’a été appliquée pendant la réorganisation.
