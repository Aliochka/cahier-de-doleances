# Extraction — composants réutilisés

`segmentation.py` est le segmenteur existant déplacé depuis l’outil de vérification, **sans modification de ses règles ni de son contenu**. Il s’agit d’une bibliothèque, pas d’une commande d’extraction globale.

Il utilise les primitives documentaires V2 conservées dans `../archives/1789-extraction-v2/` et `../archives/1789-extraction-200/`. Les lecteurs Stanford et la provenance historiques sont aussi réutilisés, sans nouvelle implémentation. Le module est chargé par les outils via leur initialisation des chemins.

Les scripts anciens `extract.py`, `build.py`, etc. restent dans leurs expériences : chacun décrit et peut reproduire un protocole précis. Ne pas les considérer comme une nouvelle chaîne globale et ne pas les exécuter pendant une simple vérification de déplacement.

Les journaux humains sous `../data/private/document-review/` sont prioritaires. Les propositions de segmentation sous `../data/segmentation-proposals/` restent distinctes ; aucune proposition n’a été appliquée pendant la réorganisation.

## Extraction globale

`production.py` exécute la chaîne sur les 1 305 notices avec le registre et les journaux existants. Il réutilise les règles ci-dessus, sans les modifier. Il produit une génération immuable sous `../data/corpus/`, puis l’active seulement après contrôles.

```sh
python3 1789/extraction/production.py
python3 1789/extraction/production.py --resume
python3 1789/extraction/production.py --verify-only 1789/data/corpus/global-corpus-1-<empreinte>
```

Le bilan réel, les fichiers, les précautions de reprise et les limites documentaires sont dans [../docs/PRODUCTION.md](../docs/PRODUCTION.md). Cette commande produit des textes et des unités documentaires : elle ne calcule pas d’embeddings et ne prépare pas d’index.

`boundary_rules.py` applique les réparations documentaires déterministes avant extraction : identité explicite, divisions contenant plusieurs cahiers, résolution traçable des alertes obsolètes. `boundary_report.py` compare deux générations sans modifier leurs données. Les règles du segmenteur d’articles restent inchangées. Voir [le bilan des corrections](../docs/BOUNDARY-CORRECTIONS.md).
