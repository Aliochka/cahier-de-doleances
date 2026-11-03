# Collection documentaire de référence 1 et passages techniques

**Mise à jour :** les deux exceptions décrites ci-dessous sont résolues dans la génération `reference-documents-2-7cbcaea79991`, désormais active : **1 224 cahiers substantiels et 11 391 passages**. Voir [la récupération des deux textes et le bilan final](TWO-EMPTY-RECOVERY.md). Le présent document conserve le bilan initial de référence 1 ; son constructeur ne doit pas remplacer la collection corrigée.


La structure principale est désormais **Corpus 1789 → Document/cahier → Passage technique de recherche**. Les articles et rubriques historiques sont des annotations secondaires conservées intégralement ; ils ne déterminent aucune frontière du nouveau découpage.

La collection réellement produite est `data/documents/reference-documents-1-b8b8b20c2f76`, sélectionnée par `data/documents/current.json`. G6 reste inchangée dans `data/corpus/global-corpus-6-29e180f0c67f`, avec son propre pointeur historique, ses textes, ses annotations et tous les journaux. Aucun ancien résultat n’est supprimé.

## Bilan de production

| Indicateur | Résultat |
|---|---:|
| Notices conservées | 1 305 |
| Documents parents conservés | 1 267 |
| Cahiers autonomes probables conservés | 1 224 |
| Cahiers avec texte substantiel | **1 222** |
| Autres documents avec texte extrait | 43 |
| Notices sans texte extrait | 38 |
| Passages techniques, tous documents | **11 358** |
| Dont passages dans les cahiers probables | **10 717** |
| Tokens par passage : moyenne / médiane | **591,1 / 599** |
| Minimum / 95e percentile / maximum | 55 / 696 / 800 |
| Passages entre 400 et 800 tokens | 11 020 |
| Passages de moins de 400 tokens | 338, tous en fin de document |
| Passages dépassant 800 tokens | **0** |
| Paragraphes XML de plus de 800 tokens | 56, références conservées |
| Couverture du texte substantiel | **100 %** |
| Caractères sources conservés dans les parents | 30 656 665 |
| Caractères couverts par les passages, hors répétitions | 30 656 615 |
| Blancs seuls non transformés en passages | 50 caractères, dans deux parents conservés |
| Frontières humaines / automatiques sans alerte / suspectes | 45 / 969 / 253 |
| Articles humains conservés comme annotations secondaires | **605** |
| Erreurs d’intégrité après vérification | **0** |

Les 1 224 cahiers restent des cahiers **probables**, sans certification collective de leurs frontières. Les 253 statuts documentaires suspects restent explicites. Les deux chevauchements documentaires hérités restent identifiés dans G6 ; ils ne sont pas confondus avec les chevauchements mécaniques des passages.

### Documents de nature différente

| Catégorie | Notices | Documents extraits conservés |
|---|---:|---:|
| Cahier autonome probable | 1 224 | 1 224, dont deux plages uniquement blanches |
| Document associé | 21 | 19 |
| Procès-verbal | 8 | 6 |
| Liste | 46 | 16 |
| Extrait | 2 | 2 |
| Annonce d’absence | 4 | 0, absence conservée comme telle |

Les 43 autres documents avec texte reçoivent aussi des passages techniques, en gardant leur catégorie. Ils ne deviennent pas des cahiers. Les 38 notices sans texte restent dans l’inventaire et les métadonnées, sans passage inventé.

### Par volume

| Tome | Documents conservés | Cahiers probables | Passages, tous types | Moyenne tokens |
|---|---:|---:|---:|---:|
| 1 | 24 | 24 | 349 | 597.7 |
| 2 | 181 | 174 | 2255 | 595.2 |
| 3 | 220 | 204 | 2508 | 590.0 |
| 4 | 346 | 346 | 2254 | 588.5 |
| 5 | 294 | 288 | 2183 | 587.4 |
| 6 | 202 | 188 | 1809 | 593.9 |

## Exceptions révélées par l’intégrité

Deux parents hérités de G6 contiennent chacun seulement `\n` suivi de 24 espaces :

- `arcpa_0000-0000_1879_num_5_1_2837` — clergé de la province du Quercy, métadonnées p. 483–484 ;
- `arcpa_0000-0000_1879_num_5_1_2877` — tiers-état du bailliage de Saint-Pierre-le-Moutier, métadonnées p. 635–643.

Leur titre ne permet pas d’inventer leur texte. Leurs plages, textes exacts et statuts initiaux restent conservés ; `content_flags: ["source_slice_whitespace_only"]` signale cette anomalie de contenu. **Aucun passage de recherche n’en est tiré.** Leur éventuelle récupération nécessiterait une décision documentaire distincte : cette mission ne modifie aucune frontière. Ils restent accessibles dans la vue de lecture et l’inventaire. Le contrôle initial a précisément refusé de considérer ces deux plages comme une couverture substantielle ; la collection achevée les distingue explicitement.

Ces exceptions et les incertitudes héritées limitent l’exhaustivité historique, mais n’empêchent pas la livraison et la vérification de la collection exploitable. Elles ne justifient pas une nouvelle campagne de correction des articles.

## Découpage mécanique

Le fichier `extraction/technical-passages-config.json` fixe une cible de **600 tokens**, une plage préférée de **400 à 800**, un maximum strict de **800** et un chevauchement visé de **60**, plafonné à **80**.

Le comptage utilise exclusivement le tokenizer BGE-M3 local, dépôt `BAAI/bge-m3`, révision `5617a9f61b028005a4858fdac845db406aefb181`, bibliothèque `tokenizers 0.21.4`. Son SHA-256 correspond au manifeste local du snapshot. Ni les poids, ni PyTorch, ni le GPU ne sont chargés. La fenêtre locale documentée est de 8 192 tokens ; deux tokens spéciaux sont réservés. Le comptage des passages exclut ces tokens spéciaux et toute métadonnée.

Priorité aux fins de paragraphes XML proches de la cible, puis aux fins de phrases si les paragraphes sont trop longs. Une phrase exceptionnellement longue peut être coupée à une frontière de mot ; le repli sur une position Unicode est prévu mais n’a pas été nécessaire ici. Les abréviations et l’OCR peuvent rendre une fin de phrase imparfaite : la coupure reste technique, jamais une interprétation de revendication.

Résultats : 9 922 fins de paragraphes XML, 139 fins de phrases, 32 frontières de mots dans de longues phrases et 1 265 fins de documents. Les 338 extraits courts sont les documents courts ou les dernières portions ; ils ne sont pas artificiellement complétés.

Les 10 093 chevauchements non nuls répètent en moyenne **58,1 tokens**, entre 20 et 80. Leur plage et leur taille sont enregistrées ; ils représentent 2 886 105 caractères répétés dans les extraits, sans duplication de documents. Aucun article, numéro, rubrique ou décision humaine sur les unités historiques n’est utilisé pour calculer les coupures.

## Fichiers et modèle

```text
1789/data/documents/
├── current.json
└── reference-documents-1-b8b8b20c2f76/
    ├── documents.jsonl.gz       # 1 267 documents intégraux et leurs plages XML
    ├── metadata.jsonl.gz        # 1 305 métadonnées, titres, ordres et labels de lieu
    ├── inventory.jsonl.gz       # toutes les notices, y compris sans texte
    ├── passages.jsonl.gz        # 11 358 extraits techniques exacts
    ├── long-paragraphs.jsonl.gz # 56 paragraphes exceptionnels avec XPath
    ├── visual-sample.json       # douze exemples de lecture, non validés automatiquement
    ├── inputs.json             # empreintes des sources, G6, scripts et journaux
    ├── manifest.json           # configuration, tokenizer, empreintes des fichiers
    ├── summary.json            # bilan et intégrité
    └── .private/               # instantanés privés des deux journaux, jamais dans Git
```

L’identifiant de document est celui du registre ; `extent_id` et le SHA-256 fixent la version du texte. Les positions sont des intervalles **[début, fin[ en caractères Unicode**, pas des octets de sérialisation XML. Chaque document conserve son texte intégral, son type, ses références Stanford/Persée, blocs XML, notes, anomalies et état de validation. Les métadonnées originales restent accessibles séparément.

Les ordres sont extraits uniquement des mentions explicites du titre Persée. Plusieurs ordres peuvent être conservés ; une absence reste « non établi ». Les labels territoriaux sont repris littéralement des métadonnées, sans géocodage ni assimilation automatique à une commune actuelle. Les champs lexicaux séparés conservent titre, labels de lieu, contexte territorial et ordres. Ils permettront plus tard des recherches comme « Agen agriculture », sans ajouter « Agen » à chaque texte vectoriel.

Chaque passage contient son identifiant, document/étendue parent, texte exact, SHA-256, positions relatives et sources, XPath/blocs intersectés, pagination, voisins, chevauchement explicite et version des règles. L’identifiant dépend du parent, de l’étendue, des positions et des règles/tokenizer, **pas du seul rang**. `ordinal` sert seulement à la navigation. Une même préparation, avec les mêmes entrées, reproduit les mêmes identifiants.

**Pour les futurs embeddings, le contenu est uniquement `passage.text`.** Aucun titre, lieu ni ordre n’est ajouté. La mention éventuelle d’un titre dans le texte source lui-même reste naturellement conservée. Notes, signatures, introductions et prose sont préservées ; tous les passages techniques ne sont donc pas des revendications.

`historical_segmentation` renvoie à G6 comme annotation secondaire. Les 39 772 articles, rubriques, corrections, 605 articles humains et 697 événements d’articles restent intacts dans cette génération et les journaux privés. Les empreintes des deux journaux sont identiques entre G6, les originaux actuels et l’instantané de cette collection. Aucune validation n’est transférée artificiellement aux nouveaux passages.

## Lecture et vérification visuelle limitée

```sh
python3 1789/review.py
```

Puis ouvrir **http://127.0.0.1:1789/passages**. Redémarrer le serveur s’il était déjà lancé. Cette vue réutilise le serveur local existant et reste **en lecture seule**, sans décision ni écriture dans un journal. Elle permet de choisir le document, puis un passage, et de consulter le texte intégral avec le passage surligné et positionné dans le panneau de contexte. Les liens précédent/suivant et le permalien conservent l’emplacement exact. Les notices sans texte restent visibles dans l’ancien inventaire documentaire.

Douze liens de lecture sont prêts : deux cahiers substantiels tirés par volume, puis un passage par cahier, graine `178903`, population triée par identifiant. Il ne s’agit pas d’une nouvelle campagne de validation de revendications. Vérifier seulement la lisibilité des frontières techniques et du contexte ; aucune validation humaine n’est créée.

## Reproduction et contrôles

```sh
# Nouvelle collection immuable à partir des parents G6 conservés :
python3 1789/extraction/prepare_documents.py

# Contrôle seul, sans découpage ni écriture dans les décisions :
python3 1789/extraction/prepare_documents.py --verify-only 1789/data/documents/reference-documents-1-b8b8b20c2f76

# Tests locaux, fixtures synthétiques :
PYTHONPATH=1789/extraction python3 -m unittest discover -s 1789/tools/document-review -p 'test_*.py'
```

Les mêmes entrées ne peuvent pas écraser la génération existante : une tentative de reconstruction à l’identique est refusée. Utiliser le contrôle seul pour vérifier l’état déjà produit. Les fichiers `inputs.json`, la configuration et le manifeste permettent d’identifier toutes les entrées. De nouvelles décisions parentales incompatibles bloquent l’activation plutôt que déplacer silencieusement une frontière. Les scripts historiques d’articles ne doivent plus être relancés pour cette chaîne.

Les **92 tests Python** passent, dont six contrôles dédiés aux paragraphes, phrases longues, Unicode, blancs, ponctuation, tailles et indépendance des numéros historiques. Les tests navigateur vérifient les douze liens des six volumes, le texte exact, le contexte intégral, le surlignage visible, la navigation, les documents blancs et l’affichage mobile, sans POST. Les anciennes fonctions historiques restent opérationnelles. Le comptage des tokens et les empreintes ont été revérifiés après lecture des fichiers produits ; zéro passage vide, dépassement de taille, identifiant dupliqué ou trou substantiel.

La collection est **stabilisée techniquement**. Les incertitudes documentaires et exceptions restent des données, sans être présentées comme résolues. L’intégration multicorpus constitue une prochaine mission distincte : aucune base, recherche, indexation ou génération d’embeddings n’a été entreprise ici.

[Bilan structuré et résultats des contrôles](reference-collection-checks.json).
