# Reproductibilité et conventions

Ce dossier est autonome vis-à-vis de l'application : aucun import du moteur ou du frontend, aucune connexion PostgreSQL, aucune inférence. Les anciens audits sont lus mais jamais exécutés en mode écriture. Seules leurs primitives de source sont chargées, et les règles du segmenteur ont été reprises dans un nouveau fichier.

## Sources, versions et isolement

Les six XML restent dans `/tmp/cahier-1789-extraction-pilot/sources/`. `common.sources()` reprend le chargeur du pilote et vérifie les six SHA-256 contre le premier inventaire. La révision est `926fd3cd986a3c3d411e93d1845fff6475cb2602`. Les sources ne sont pas dupliquées dans le dépôt. Si le cache disparaît, récupérer uniquement ces six fichiers à cette révision, aux URL/empreintes de l'inventaire antérieur, avant de relancer.

Python 3.11.17 et lxml 6.0.2 ont été utilisés. lxml est installé uniquement dans `/tmp/cahier-1789-extraction-200-tools`, avec cache uv séparé ; aucune dépendance applicative n'est ajoutée :

```sh
uv pip install --target /tmp/cahier-1789-extraction-200-tools --cache-dir /tmp/cahier-1789-extraction-200-uv-cache lxml==6.0.2
```

Le parsing conserve les textes sans normalisation ; les accès réseau XML, DTD externes et résolution d'entités sont désactivés. Les versions et empreintes finales sont archivées avec les résultats. Aucun scan, PDF ou XML intégral Persée n'est ajouté ici. Les réserves de republication des audits précédents restent applicables ; une étude locale n'est pas une publication sur le site.

## Séparation des étapes

| Étape | Outil / état |
|---|---|
| Inventaire de tout I–VI | `discover.py` → `data/candidates.jsonl`, `inventory-summary.json` |
| Développement et régression | `regression.py`, `development_segmentation.py`, `pilot_segment.py` |
| Tirage après inventaire | `select.py` → sélection, strates et fenêtres négatives |
| Gel des règles | `freeze.json` : classification, segmentation, primitives et tirage |
| Dossiers source sans sorties d'articles | `review_pack.py`, fichiers temporaires dans `/tmp/cahier-1789-extraction-200/` |
| Décisions de référence | `annotate_reference.py` → `reference-documents.jsonl`, `reference-negative.json` |
| Gel de la référence | `reference-freeze.json`, avant les prédictions nouvelles |
| Contrôles complémentaires | `additional-parent-decisions.json`, cinq rejets chronologiques postérieurs, hors scores de validation |
| Extraction brute puis corrections | `extract.py` ; cache équivalent dans `fast_blocks.py` |
| Mesures avant correction | `evaluate.py` ; ne compare pas seulement les unités retenues comme correctes |
| Contrôles | `verify.py`, erreurs injectées, vérification des deux gels et de tous les anciens fichiers |

`select.py` et `annotate_reference.py` refusent de remplacer un gel déjà existant. Ne pas les relancer pour masquer un changement de méthode ou de référence. Pour une nouvelle itération, créer une version distincte avec un nouveau lot de validation.

## Reproduire les résultats livrés

Depuis la racine, avec les anciens audits et les six XML inchangés :

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/audits/1789-extraction-200/extract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/audits/1789-extraction-200/evaluate.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/audits/1789-extraction-200/regression.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/audits/1789-extraction-200/development_segmentation.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/audits/1789-extraction-200/check_reproducibility.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/audits/1789-extraction-200/verify.py
```

Ces commandes réécrivent seulement les résultats du présent audit. Elles ne refont pas une annotation humaine : elles réappliquent les décisions explicites conservées. Les dossiers temporaires de lecture ne sont pas indispensables au recalcul, puisque les références et leurs positions sont livrées. Sauvegarder les mesures initiales avant une nouvelle mesure de durée.

L'optimisation `fast_blocks.py` remplace la matérialisation répétée de tous les frères précédents par un test du premier paragraphe et met en cache les nœuds/ranges. Les résultats de blocs sont comparés à ceux de la fonction gelée sur les douze candidats de validation. Les motifs de classification, rôles et segmentation gelés restent inchangés. Deux tentatives lentes ont été interrompues avant cette optimisation ; leur durée totale n'a pas été mesurée et n'est pas transformée en temps humain.

## Fichiers de corpus

- `documents.jsonl.gz` : 200 parents/fiches, `full_text` exact, source, divisions, blocs, sections, notes et incertitudes. **Exclure `record_status=quarantined_false_parent` de tout usage comme cahier de 1789**. `automatic_unverified` n'est pas une certification des 153 nouveaux parents correspondants.
- `units-A.jsonl` : 317 unités aux limites examinées, avec `validation_origin` distinguant les 269 anciennes et 48 nouvelles.
- `units-B.jsonl.gz` : 5 872 propositions, sans validation individuelle implicite.
- `retained-C.jsonl.gz` : 812 plages de texte conservé, avec rôle et provenance ; pas 812 revendications ou articles.
- `automatic-parents.jsonl.gz` et `automatic-units.jsonl` : hypothèses et 5 445 propositions d'articles nouvelles **avant** correction. Les parents longs erronés et les textes des faux cahiers y restent inspectables.
- `register.json` : métadonnées des 200 fiches sans le texte intégral ; joindre `candidate_id` à `selection.jsonl` pour les raisons et strates du tirage.
- `crosswalk.json` : identités des 30 anciens parents et 759 anciennes unités, puis correspondances entre hypothèses automatiques et résultat revu. Les nouveaux identifiants après correction d'Arles sont explicites ; une liste de correspondances peut être vide pour une proposition exclue et conservée en C.

Les classifications d'inventaire sont des codes explicites : `incidental_mention` n'est pas un début ; `continuation` est une pièce à rattacher ; `published_extract`, `notice_missing`, `attached_or_other_document` ou les états incertains ne sont pas admis comme cahiers complets. Les signaux et les extraits source expliquent la décision automatique. Les corrections revues sont dans des fichiers distincts et ne modifient pas cet inventaire gelé.

## Texte, positions et identifiants

Les intervalles sont semi-ouverts `[start,end)`, en **points de code Unicode du texte XML décodé**, selon le parcours du pilote. Ce ne sont pas des offsets d'octets dans le fichier XML sérialisé. Le SHA-256 du fichier, la révision Git, les XPath et lignes source des blocs permettent de retrouver les balises originales. Le texte parent est exactement une tranche de ce texte source, sans remplacement Unicode, réduction des blancs ou correction OCR.

Chaque A/B possède son parent, son ordre, l'étiquette originale, un numéro seulement lorsqu'il est littéralement lisible, ses positions globales et relatives au parent, les `xml_blocks`, pages, source et version, `section_id`, ancre et voisins. `text_spans` retire les notes XML du texte de l'article sans les perdre : elles restent dans le parent et les plages C. Une section automatique et une signature « hypothèse » ne sont pas une interprétation documentaire certifiée.

Les IDs hérités restent inchangés. Les nouveaux IDs dérivent de la source figée, des divisions et intervalles ; un changement de statut seul ne change pas l'identité. Une correction de frontière parent peut changer les IDs de ses unités, d'où la table de correspondance. La navigation utilise `previous_unit_id` et `next_unit_id` ; le statut de chaque voisin doit être respecté.

## Mesures et vérifications

Les valeurs de `evaluation.json` séparent découverte, fenêtres d'articles de vrais parents, propositions de faux parents et contrôles de non-détection. Aucune précision après substitution de la référence n'est utilisée comme preuve de généralisation. Les mesures de développement sont dans un autre fichier.

`verify.py` contrôle textes, offsets, parent, XPath, ordre et voisins, plages C, conservation du texte non blanc, unicité des IDs, anciens identifiants et gels. Il rejette six fautes injectées : réécriture, mauvais parent, sortie de parent, décalage relatif, plage source invalide et empreinte incorrecte.

```sh
.venv/bin/ruff check docs/audits/1789-extraction-200 --ignore F401
.venv/bin/ruff format --check docs/audits/1789-extraction-200
```

L'exception F401 conserve deux imports inutilisés dans les scripts déjà gelés de tirage/annotation ; elle ne masque pas une erreur documentaire. Aucun build frontend ou test écrivant en base n'est lancé pour cette étude sans modification applicative.

Les SHA-256 des livrables, versions, résultats des contrôles et liens locaux sont archivés en fin de mission. Les temps d'exécution et horodatages sont exclus de la comparaison de reproductibilité binaire ; les textes, identifiants et décisions doivent rester identiques. Les temps du journal sont ceux du workflow Codex, **jamais une durée de validation humaine estimée**.
