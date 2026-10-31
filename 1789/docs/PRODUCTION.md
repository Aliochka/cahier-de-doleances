# Corpus global de travail — 1789

L’extraction des **1 305 notices** a été exécutée sur les six XML Stanford figés à la révision `926fd3cd986a3c3d411e93d1845fff6475cb2602`. Elle produit **1 237 textes parents**, dont **1 201 cahiers autonomes probables**, et **38 186 articles**. Les **29 validations humaines de parents et les 333 articles humains** ont été conservés et comparés aux décisions originales, sans écrire dans leurs journaux.

Les autres résultats restent des propositions documentaires. Ce corpus n’a été ni publié ni indexé. Aucun embedding, OCR, modèle ou accès PostgreSQL n’a été utilisé.

## Résultat de production

| Indicateur | Nombre |
|---|---:|
| Notices examinées | 1 305 |
| Cahiers autonomes probables du registre | 1 225 |
| Textes extraits, toutes catégories | 1 237 |
| Dont cahiers autonomes probables extraits | 1 201 |
| Frontières validées humainement | 29 |
| Frontières automatiques sans alerte documentaire détectée | 805 |
| Frontières automatiques suspectes | 402 |
| Périmètre incertain conservé provisoirement | 1 |
| Notices sans texte extrait | 68 |
| Articles historiques après reprise des décisions | 38 186 |
| Articles validés/corrigés humainement | 333 |
| Autres articles proposés | 37 853 |
| Articles avec au moins une anomalie de segmentation | 4 698 |
| Sections proposées | 1 311 |
| Passages techniques conservés | 41 322 |
| Chevauchements entre propositions documentaires | 46 paires |
| Plages identiques présentes sous plusieurs parents | 377 groupes |

Les 68 notices comprennent **4 annonces de cahier absent**, sans création de faux texte, et **64 notices sans plage utilisable**. Les 402 périmètres suspects et le périmètre incertain sont isolés dans le fichier des documents provisoires ; leurs textes ne sont pas présentés comme établis. L’absence d’alerte sur les 805 autres ne certifie pas leurs frontières.

La catégorie documentaire privilégie les 100 contrôles déjà présents dans `document_kind_reference`. Cinq rectifications antérieures changent la ventilation par rapport aux 1 227 cahiers probables du classement automatique initial. Les deux classements et leur origine restent dans l’inventaire : **1 225 cahiers probables, 21 documents associés, 7 procès-verbaux, 46 listes, 4 notices d’absence et 2 extraits**. Aucune relation d’annexe n’est certifiée par une simple inclusion de plages.

### Par volume

| Volume | Notices | Textes (dont cahiers probables) | Parents humains | Auto sans alerte | Suspects | Incertains | Sans texte | Articles | Articles humains | Articles avec anomalie |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 24 | 24 (24) | 5 | 12 | 7 | 0 | 0 | 1146 | 143 | 175 |
| 2 | 181 | 176 (171) | 5 | 101 | 70 | 0 | 5 | 8187 | 85 | 1440 |
| 3 | 223 | 214 (198) | 4 | 124 | 85 | 1 | 9 | 7060 | 11 | 1193 |
| 4 | 347 | 342 (342) | 5 | 255 | 82 | 0 | 5 | 7706 | 33 | 701 |
| 5 | 298 | 287 (285) | 5 | 184 | 98 | 0 | 11 | 8293 | 18 | 480 |
| 6 | 232 | 194 (181) | 5 | 129 | 60 | 0 | 38 | 5794 | 43 | 709 |

Les parents représentent **30 556 018 caractères Unicode / 31 353 097 octets UTF-8**, blancs originaux inclus, et non dédupliqués entre parents concurrents. Les **10 091 317 caractères hors de leur union** sont conservés dans `unassigned-source.jsonl.gz` avec positions et références ; ils comprennent notamment les textes des volumes qui ne sont pas des cahiers. Les articles, sections et C couvrent exactement chaque parent, sans abandon des blancs ou paratextes.

## Où sont les données ?

`1789/data/corpus/current.json` désigne la génération complète active. Le serveur la choisit au démarrage ; il faut le redémarrer après activation d’une autre génération. Les générations sont immuables et conservées dans `1789/data/corpus/global-corpus-1-<empreinte>/`.

| Fichier de génération | Usage |
|---|---|
| `inventory.jsonl.gz` | Les 1 305 notices, classifications d’origine et retenue, état d’extraction, correspondances et anomalies |
| `parents.jsonl.gz` | Textes intégraux exacts, métadonnées, divisions, blocs, notes, sections, propositions initiales et versions |
| `units.jsonl.gz` | Unités actuelles après reprise des décisions, texte exact, références et statuts explicites |
| `units-A/B/C.jsonl.gz` | Propositions de base séparées, nécessaires à la reprise du journal ; A signifie examen Codex, pas validation humaine |
| `automatic-proposals.jsonl.gz` | Sortie brute du meilleur segmenteur existant, distincte des unités retenues |
| `provisional-documents.jsonl.gz` | Références des parents suspects ou incertains |
| `review-queue.jsonl.gz` | Problèmes triés : documents non résolus, périmètres, segmentation, notices d’absence informatives |
| `document-overlaps.jsonl.gz`, `duplicate-source-spans.jsonl.gz` | Chevauchements et doublons de plages conservés explicitement, sans suppression arbitraire |
| `unassigned-source.jsonl.gz` | Complément exact des parents dans chaque texte source |
| `inputs.json`, `complete.json`, `summary.json` | Empreintes des entrées, sorties complètes contrôlées et bilan |
| `checkpoints/` | Points de reprise par volume |
| `.private/` | Instantanés privés des deux journaux utilisés, exclus de Git |

Les offsets sont des intervalles **[début, fin exclue)** en caractères Unicode dans le texte décodé par le lecteur XML existant, jamais des offsets d’octets dans le fichier XML brut. Les XPath et références de blocs permettent de revenir au XML ; `parent_spans` situe chaque plage dans le parent. Les notes retirées du texte d’un article demeurent dans le parent et dans son complément C. La succession conservée est l’ordre source, pas une certification historique des voisins.

L’identifiant parent reste celui du registre ; ses `legacy_parent_ids` gardent les références antérieures. Une unité nouvelle dépend de la version du parent, du type et des plages sources, **pas seulement de son rang ou numéro**. Les anciens identifiants des 29 parents initiaux restent conservés.

## Priorité aux décisions humaines

Les 29 parents initiaux conservent leur base d’unités et ses identifiants afin de rejouer exactement les décisions humaines, y compris les séparations et fusions. Les nouvelles propositions OCR y sont enregistrées séparément, consultables dans la comparaison existante ; elles ne remplacent pas les articles en cours de vérification. Les autres parents cohérents utilisent le meilleur segmenteur OCR existant. Les parents incertains, identités ambiguës ou documents inadéquats conservent leur texte en sections/C sans fabrication d’articles certifiés.

Le producteur contrôle chaque article humain contre le résultat des événements originaux. Une incompatibilité avec un nouveau parent bloque l’activation plutôt que d’ignorer la décision. Les règles de segmentation et les anciens audits sont inchangés. Les 333 unités humaines ne valident ni les autres articles de leur cahier, ni les nouvelles propositions.

## Contrôler et corriger dans l’interface

```sh
python3 1789/review.py
```

Ouvrir **http://127.0.0.1:1789**. Le mode **Cahiers** affiche les 1 305 notices ; le lot initial reste disponible en option. Rechercher un titre ou identifiant, choisir un volume, filtrer le statut ou les priorités. Le mode **Articles** parcourt les textes extraits, avec filtres de volume, statut des frontières et documents à revoir. Les notices sans texte disposent d’un accès à leurs frontières.

Pour une nouvelle notice : vérifier/corriger les limites dans **Cahiers**, enregistrer la validation explicite, puis utiliser **Reconstruire** pour appliquer ce périmètre à ce seul document. Les blocs peuvent être recherchés dans le volume. L’interface affiche ensuite les articles et le texte complet ; les validations et corrections d’articles fonctionnent comme auparavant. Aucun affichage ou clic de navigation ne crée une validation.

La reconstruction est un événement système distinct, avec artefact immuable et journal chaîné sous `data/private/document-review/corpus-overrides/`. Elle ne crée pas de validation humaine d’article. Elle exige une validation humaine du parent et n’écrase pas les textes sources. Le journal humain reste append-only.

**Limite volontaire :** si un parent possède déjà des décisions d’articles et que ses frontières ont changé, la reconstruction refuse de réattribuer automatiquement ces décisions. Le dossier doit être réconcilié explicitement ; restaurer l’ancien périmètre permet de retrouver l’état compatible. Si les frontières sont compatibles, ses unités humaines sont conservées. Un parent composite non représentable par une plage continue doit rester incertain.

Les corrections courantes apparaissent dans l’interface et dans son export. Les fichiers immuables de production représentent l’état à la génération : après de nouvelles décisions, utiliser l’export de l’outil ou régénérer, sans écraser une ancienne version. Les indicateurs de génération affichés ne sont pas des compteurs de validations en temps réel.

## Reproduire et vérifier

Depuis la racine, avec Python 3.10+ et `lxml` disponibles :

```sh
python3 1789/extraction/production.py
```

La commande vérifie les empreintes, traite chaque volume avec points de reprise, conserve les erreurs par notice et poursuit quand c’est sûr. Une génération n’est activée qu’après contrôle complet et vérification que les entrées n’ont pas changé pendant le traitement. Une génération identique déjà terminée n’est pas réécrite : utiliser alors `--verify-only` ou choisir un autre répertoire de sortie. Pour reprendre un calcul interrompu avec les mêmes entrées : ajouter `--resume`. Pour produire sans changer la sélection active : ajouter `--no-activate`. `--output CHEMIN` permet un répertoire de résultats explicite ; conserver les générations sous `1789/data/corpus/` pour l’activation.

```sh
python3 1789/extraction/production.py --verify-only 1789/data/corpus/global-corpus-1-<empreinte>
python3 -m unittest discover -s 1789/tools/document-review -p 'test_*.py'
```

Le contrôle seul vérifie les sommes des sorties, les textes exacts, les positions, la couverture, l’unicité, les relations parent/notice/volume et le rejeu humain. Après de nouvelles décisions il peut signaler que la matérialisation est ancienne : il faut alors exporter/régénérer, pas réécrire les journaux. Le calcul observé ici dure environ **44 secondes**, hors contrôle navigateur ; ce n’est pas du temps de validation humaine.

## Problèmes à traiter dans l’ordre

1. Les **64 notices sans plage exploitable**, les identités contradictoires et les frontières qui mélangent des voisins. Ne pas chercher à résoudre les 4 annonces d’absence en créant des cahiers.
2. Les **402 parents suspects et le parent incertain**, en particulier les **46 chevauchements**. Les **377 groupes de plages identiques** restent signalés : ils peuvent provenir de notices parentes concurrentes ou de pièces partagées et ne sont pas dédupliqués sans décision documentaire.
3. Les **4 698 articles signalés** : fusion possible, séquence irrégulière, numéro répété ou texte dépassant 12 000 caractères. Une rupture de numérotation seule n’est pas une erreur démontrée ; aucune renumérotation/comblement automatique.
4. Les sections et C pouvant contenir de la prose revendicative ; leur classement doit être explicite. Les C ne sont pas des articles historiques.
5. Contrôle par échantillonnage des propositions sans alerte, conformément à la stratégie humaine existante. L’absence d’alerte n’est pas une validation.

## Conservation

Les sources, corpus, points de reprise, instantanés et journaux restent **locaux et ignorés par Git**. Sauvegarder ensemble `1789/sources/`, `1789/data/` et les journaux privés, en conservant leur confidentialité. Le dépôt versionne le producteur, l’outil, les tests et ce bilan ; il ne republie pas les textes intégraux. Un clone seul ne suffit pas à restaurer les données ou les validations.

## Vérifications exécutées

- Contrôle intégral du corpus actif avec `--verify-only` : empreintes des sorties, textes/plages sources, couverture, relations et préservation des 333 articles humains conformes.
- Les 19 entrées protégées sont inchangées ; les deux journaux réels sont identiques aux instantanés avant production, et les règles ainsi que les archives n’ont aucune modification.
- **39 tests Python réussis**, dont la reconstruction versionnée, la reprise et le refus de transférer des validations sur un parent incompatible ; Ruff, syntaxe JavaScript et `git diff --check` conformes.
- Navigateur Chromium sur journaux temporaires : 1 305 notices, filtres/recherche, volumes, notices non résolues, recherche de blocs, validation du parent puis reconstruction de Pecqueuse (38 articles), validation d’article et rechargement.
- Scénario navigateur existant : groupes, corrections et export structurés, conservation du mode Cahiers. Clavier, largeurs 320/375/768/1280 et texte à 200 % sans débordement horizontal sur les parcours testés ; aucune erreur JavaScript relevée.

Les résultats synthétiques sans noms de vérificateurs ni décisions privées sont dans [production-checks.json](production-checks.json). Les journaux de tests sont temporaires ou dans `.local/`, jamais dans les journaux réels. L’interface locale nécessite JavaScript, comme précédemment ; les fichiers structurés et les contrôles Python sont autonomes.
