# Blancs techniques des passages C

Sur les six volumes, **35 716 passages C exclusivement blancs** sont désormais classés automatiquement comme **paratexte technique exclu de la recherche**.

| Tome | Passages concernés |
|---|---:|
| I | 965 |
| II | 7 595 |
| III | 6 435 |
| IV | 7 091 |
| V | 8 048 |
| VI | 5 582 |
| **Total** | **35 716** |

Le comptage utilise la génération `global-corpus-4-b643646266f1` et les décisions humaines actuelles (399 événements d’articles au moment du calcul). Les 42 349 C restants dans cet état comprennent ces blancs : **6 633 autres C** restent distincts. Les différences avec les effectifs du bilan de génération proviennent des décisions humaines intervenues depuis son instantané.

## Règle et conservation

La règle `unicode-whitespace-1` teste le texte exact avec `str.isspace()` : chaîne non vide et exclusivement composée de caractères blancs Unicode, notamment espaces insécables, espaces fines, tabulations et sauts de ligne. Aucun nettoyage ou remplacement n’est appliqué. Une ponctuation, un chiffre ou une seule lettre empêche ce classement. Les caractères de largeur nulle U+200B et le BOM U+FEFF ne sont pas considérés comme blancs par cette règle. Les versions Python et Unicode sont enregistrées dans le bilan.

Seuls les C de statut `technical_unclassified` sont éligibles. Les classifications humaines explicites, validations et décisions d’incertitude sont prioritaires. Seize unités concernées ont une origine humaine : ce sont des restes techniques produits par des opérations d’ajout/correction, pas des passages classés ou laissés incertains explicitement. Leurs identifiants, positions et événements d’origine restent conservés.

La classification s’applique à la lecture de l’interface et à l’export. Elle ne réécrit pas la génération brute ni les journaux. Chaque unité conserve son identifiant, son texte exact, ses plages sources et parentales, sa pagination et sa provenance. Les sorties distinguent `original_type: technical_passage`, `type: paratext`, `automatic_classification`, `validation_status: automatic_technical_paratext` et `human_validated: false`. Le classement automatique n’est jamais enregistré comme une décision humaine.

Un manifeste structuré de toutes les classifications a été effectivement produit sous `data/technical-paratext/whitespace-<empreinte>/`, avec une sélection dans `data/technical-paratext/current.json`. Il conserve aussi l’éventuel événement antérieur et les empreintes du texte et des entrées. Il est ignoré par Git. Le [bilan agrégé](whitespace-summary.json) est versionnable. La règle reste dynamique dans l’interface : une décision humaine ultérieure est prioritaire sur cet instantané.

## Interface

Les blancs classés ne sont pas affichés par défaut, même lorsque « Afficher les passages techniques et le paratexte » est activé. La case séparée **Afficher aussi les blancs techniques classés automatiquement** permet de les consulter. Le cahier complet les conserve toujours. Les cartes automatiques n’ont ni sélection ni bouton de validation rapide ; leur contexte reste accessible.

Les exports distinguent ces unités des C restant à classer. Le compteur `technical_passages_to_classify` et le statut « À classer » les excluent. Le compteur humain ne les inclut pas. Les effectifs totaux des unités et leurs positions restent inchangés.

## Contrôles et reproduction

- **62 tests Python réussis**, dont les caractères Unicode, les contre-exemples courts/ponctués, la conservation exacte du texte et des plages, l’absence d’événement humain et la priorité aux décisions humaines.
- Test navigateur réussi : masquage par défaut, indépendance des deux cases, visibilité des C non blancs, absence de sélection/validation des blancs, aucun POST et aucun enregistrement humain.
- Régression navigateur réussie : liens et navigation dans le lot de 24 fenêtres, filtres et comparaisons avant/après, clavier et affichage jusqu’à 320 pixels et texte à 200 %.
- Contrôle de partition exacte de tous les parents et empreintes inchangées des sources, générations et journaux lors du traitement. Aucun découpage, texte source ou autre classification n’a été modifié.

```sh
python3 1789/extraction/classify_whitespace.py
python3 1789/review.py
```

Redémarrer le serveur déjà ouvert et recharger le navigateur pour utiliser le nouvel affichage. Le script de classification est reproductible, ne relance aucune extraction et ne calcule aucun embedding.
