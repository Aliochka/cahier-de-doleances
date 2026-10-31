# Corpus historique de 1789

Espace unique de travail pour les cahiers de doléances : sources, registre, corpus expérimental, extraction, vérification humaine et expériences antérieures. L’extraction globale est produite : **1 305 notices traitées, 1 244 textes, 38 553 articles**, dont 333 validés/corrigés humainement. Voir [les corrections de frontières](docs/BOUNDARY-CORRECTIONS.md) et [le bilan initial de production](docs/PRODUCTION.md) pour les statuts, limites et commandes.

```text
1789/
├── README.md
├── docs/                         # fonctionnement, conservation et données locales
├── sources/
│   ├── stanford/<révision>/      # six XML originaux figés, locaux
│   └── persee/                  # caches des métadonnées déjà collectées
├── data/
│   ├── registry/                # registre des 1 305 notices et rapprochements
│   ├── corpus/                  # générations globales et sélection current.json
│   ├── article-corpus/          # référence initiale : 29 parents, 719 articles
│   ├── review-exports/          # exports de l’outil, avec statuts explicites
│   ├── segmentation-proposals/ # comparaisons et propositions, séparées des décisions
│   └── private/document-review/ # journaux humains et sessions, jamais dans Git
├── extraction/
│   ├── production.py           # extraction globale, reprise et contrôles
│   └── segmentation.py         # segmenteur existant, inchangé
├── tools/document-review/       # interface locale, tests et campagnes
├── review.py                    # lanceur de cette interface
├── archives/                    # quinze audits, leurs scripts et résultats historiques
├── migration/                   # correspondances de chemins et contrôles de déplacement
└── cahier1789_paths.py           # lecture compatible des références historiques figées
```

## Démarrer la vérification

Depuis la racine du dépôt :

```sh
python3 1789/review.py
```

Ouvrir **http://127.0.0.1:1789**. Pour arrêter : Ctrl-C. Le serveur reste strictement lié à `127.0.0.1`. Le serveur sélectionne la génération globale active. Les modes Cahiers/Articles, l’historique et les campagnes sont conservés ; les filtres permettent de parcourir les six volumes. En cas de serveur démarré avant le déplacement, l’arrêter puis le relancer avec cette commande avant de recharger le navigateur.

Les instructions détaillées sont dans [tools/document-review/README.md](tools/document-review/README.md). La campagne de cinq cahiers reste dans [tools/document-review/campaigns/](tools/document-review/campaigns/README.md).

## Ce qui sert au travail actuel

- `data/corpus/current.json` : sélection de la génération globale ; ses textes, unités et inventaire complet sont décrits dans [docs/PRODUCTION.md](docs/PRODUCTION.md).
- `data/registry/registry.jsonl.gz` : 1 305 notices ; ne pas les assimiler à autant de cahiers autonomes certifiés.
- `data/article-corpus/parents.jsonl.gz` et `units-A/B/C.jsonl.gz` : corpus initial conservé, sans réécriture par les décisions ultérieures.
- `data/private/document-review/decisions.jsonl` : décisions des frontières parentales.
- `data/private/document-review/article-decisions.jsonl` : décisions sur les articles, séparées des propositions initiales. À la migration : 346 événements et 333 articles validés ou corrigés humainement.
- `data/review-exports/` : exports existants ; ils ne sont pas implicitement régénérés lors du lancement.
- `data/segmentation-proposals/` : propositions OCR et signalements documentaires, jamais substitués silencieusement aux validations.
- `extraction/segmentation.py` : module existant, pas une commande d’extraction globale. Il réutilise les primitives historiques V2 et le lecteur Stanford ; ces dépendances sont conservées dans les archives.

Le corpus global utilise des générations versionnées sous `data/corpus/`, sans écraser `article-corpus/` ni les journaux. Les 29 parents initiaux et leurs identifiants sont conservés pour reprendre les décisions humaines.

## Archives et conclusions

[archives/README.md](archives/README.md) indexe les travaux précédents. Les deux conclusions opérationnelles récentes sont :

- [Bilan des validations humaines et stratégie de contrôle](archives/1789-human-review-quality/README.md).
- [Amélioration conservatrice du segmenteur](archives/1789-article-segmentation-improvement/README.md).

Les anciens scripts sont des moyens de reproduction d’une expérience précise, pas une chaîne globale à exécuter en série. Certains lancent des calculs, des téléchargements ou des extractions : **ne pas lancer leurs `main()` pour simplement tester l’installation**.

Les dossiers d’archives qui utilisaient `data/` ou un cache Persée disposent de liens symboliques internes vers les données uniques sous `1789/data/` et `1789/sources/`. Ces liens conservent la lecture relative des expériences sans dupliquer les textes. Aucun ancien répertoire applicatif n’est maintenu dans `docs/audits/` ou `docs/tools/`.

## Provenance, confidentialité et vérification

Les textes, données, identifiants, offsets, décisions et manifestes historiques ont été déplacés **sans modifier leurs octets**. Les chemins anciens inscrits dans les JSON ou journaux sont des références de provenance : ils ne sont pas réécrits. [cahier1789_paths.py](cahier1789_paths.py) les résout à l’aide de [migration/paths.json](migration/paths.json).

Les différences de code/documentation dues au déplacement sont inventoriées séparément. Une ancienne empreinte n’est acceptée pour un fichier adapté que si son empreinte antérieure et son empreinte actuelle figurent dans la correspondance autorisée ; aucune exception ne permet de modifier un texte ou un journal.

Les sources, journaux, caches et gros résultats restent exclus de Git. Un clone seul ne suffit pas à restaurer le corpus local. Voir [docs/LOCAL_DATA.md](docs/LOCAL_DATA.md) et [docs/WORKFLOW.md](docs/WORKFLOW.md) pour les données et sauvegardes à préserver. Les modèles partagés et les ressources 2019 restent dans `rag/` : ils ne sont pas spécifiques au corpus de 1789 et n’ont pas été déplacés.

Contrôle de la migration, sans extraction :

```sh
python3 1789/migration/verify.py
python3 1789/archives/1789-human-review-quality/check.py --read-only
python3 -m unittest discover -s 1789/tools/document-review -p 'test_*.py'
```

Le contrôle complet de déplacement nécessite l’inventaire local privé conservé sous `migration/.local/`. Son résultat lisible est dans [migration/verification.json](migration/verification.json).
