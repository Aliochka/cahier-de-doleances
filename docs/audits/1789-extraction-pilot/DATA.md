# Données, provenance et reproduction

## Dépendances et isolation

Python 3.10+ et `lxml` suffisent pour les scripts. `lxml` 4.8.0 était déjà disponible dans l’environnement ; aucune dépendance du projet n’a été ajoutée. Les traitements n’importent aucun module applicatif et n’utilisent ni SQL, ni service de recherche, ni modèle d’embeddings.

Depuis la racine du dépôt :

```sh
python docs/audits/1789-extraction-pilot/fetch_sources.py /tmp/cahier-1789-extraction-pilot/sources
python docs/audits/1789-extraction-pilot/extract.py /tmp/cahier-1789-extraction-pilot/sources
python docs/audits/1789-extraction-pilot/verify.py /tmp/cahier-1789-extraction-pilot/sources
python docs/audits/1789-extraction-pilot/derive.py
python docs/audits/1789-extraction-pilot/render_reports.py
```

Pour refaire le contrôle de reproductibilité (deux extractions et vérifications, puis régénération des rapports pour leur dernière durée mesurée) :

```sh
python docs/audits/1789-extraction-pilot/check_reproducibility.py /tmp/cahier-1789-extraction-pilot/sources
python docs/audits/1789-extraction-pilot/render_reports.py
```

Le premier script réutilise les fichiers présents si leurs SHA-256 concordent. Il télécharge sinon les seuls six XML Stanford figés. Une empreinte différente provoque un échec. Ne pas exécuter ces scripts avec l’option Python `-O`, qui désactiverait les assertions de contrôle.

Les cinq images de comparaison sont facultatives pour l’extraction :

```sh
python docs/audits/1789-extraction-pilot/fetch_scans.py /tmp/cahier-1789-extraction-pilot/scans
```

Leurs URL et empreintes sont archivées dans `data/scan-checks.json`. Le script ne réalise aucune nouvelle analyse visuelle ; les observations consignées décrivent la revue effectuée pendant cette mission. Les images et XML sources ne sont pas copiés dans les répertoires applicatifs.

## Séparation des responsabilités

| Niveau | Fichiers | Nature |
|---|---|---|
| Sources brutes | cache `/tmp/.../sources`, empreintes `data/provenance.json` | Six fichiers figés, aucune correction |
| Décisions de revue | `decisions.json`, `negative-cases.json`, `review-log.json` | Choix déclaratifs inspectables ; auteur Codex, pas validation humaine |
| Règles | `common.py`, `extract.py` | Texte XML, classification, segmentation déterministe |
| Résultats automatiques bruts | `data/automatic-predictions.jsonl` | Avant rôles documentaires et remplacement par référence A |
| Référence vérifiée | fenêtres `decisions.json`, positions `data/reference.json` | Annotations explicites, pas reprise des sorties de l’algorithme |
| Corpus après revue | `documents.jsonl`, `units.jsonl`, `retained-unsegmented.jsonl` | A, B et C distincts |
| Contrôles | `verify.py`, `data/checks.json`, `data/negative-results.json` | Invariants matériels et cas négatifs |
| Évaluation | `derive.py`, `data/evaluation.json`, `data/summary.json` | Mesures et suivi des modifications |
| Rapports calculés | `render_reports.py`, `REGISTER.md`, `EVALUATION.md` | Présentation des résultats, aucune extraction nouvelle |

Les champs contenant `manual` désignent des décisions déclaratives saisies dans les fichiers, par opposition aux prédictions calculées. Ils ne signifient pas qu’un validateur humain a réalisé ce travail.

## Convention de texte et positions

Le parseur est configuré sans DTD distante, sans réseau XML, sans résolution d’entités externes, sans mode de récupération. Pour chaque volume, son texte décodé est construit dans l’ordre XML, équivalent à `''.join(root.itertext())`. Les textes des nœuds et leurs queues sont comptés une seule fois. Les `pb` sans texte produisent une position mais aucun caractère ajouté.

Toutes les plages sont **semi-ouvertes `[start, end)` en points de code Unicode**, dans ce texte décodé du volume. Ce ne sont ni des offsets d’octets XML ni des positions UTF-16 JavaScript. Les règles XML de décodage s’appliquent ; la fidélité binaire se vérifie séparément par le SHA-256 du fichier source.

- Le texte parent est exactement `source_text[source_text_start:source_text_end]`.
- Une unité a une enveloppe `start/end` et une liste ordonnée `text_spans`. Son texte est exactement la concaténation des tranches de cette liste, sans séparateur inventé.
- Les notes éditoriales, en-têtes courants reconnus et signatures séparées sont exclus du texte de l’unité par des plages explicites ; ils restent dans le parent et ses annotations.
- Les blancs avant le premier caractère et après le dernier caractère d’une unité sont hors de son intervalle. Les blancs internes, césures, retours à la ligne, caractères, coquilles et ponctuations sont conservés.
- `parent_start` et `parent_end` permettent de retrouver l’enveloppe dans `full_text`. Pour masquer une note dans une vue de lecture, utiliser les `text_spans` relatifs au même début parent.
- Les XPath renvoient aux fichiers Stanford figés, pas à une arborescence applicative. Un fragment XML de contrôle peut comporter une racine technique et une sérialisation différente des blancs extérieurs ; le texte canonique de contexte est le champ `full_text` vérifié contre la source.

Les textes ne subissent ni `split/join` de normalisation, ni correction OCR, ni modernisation, ni normalisation Unicode. La fonction `compact()` ne sert qu’à reconnaître des conventions et à afficher des résumés d’inspection ; elle ne fournit jamais le texte stocké d’un parent ou d’une unité.

## Schéma des principaux fichiers

**`documents.jsonl`** : une ligne par cahier/dossier parent. Elle comprend `id`, `key`, `corpus_id`, les titres exacts et le libellé de sélection, `full_text`, son empreinte, ses positions globales, les divisions, sections, blocs et annotations, les pages, les liens, les métadonnées avec provenance, les dates explicitement balisées, la bibliographie exacte du TEI, les incertitudes, les identifiants des unités et les plages non segmentées. `legacy_document_id` est une correspondance technique, pas un identifiant historique.

**`units.jsonl`** : une ligne par candidat article ou unité numérotée. Champs essentiels : `id`, `document_id`, `corpus_id`, `status`, `validation`, `order`, `section_id`, `label_exact`, `historical_number`, `text`, `text_spans`, `start/end`, `parent_start/parent_end`, `xml_blocks`, `pages`, `separated_annotations`, `previous_unit_id`, `next_unit_id`, `anchor`, les métadonnées, le fichier et les empreintes source/méthode. Le type distingue également les unités de pièce jointe et de supplément.

`historical_number` est le jeton littéral lisible dans un marqueur reconnu, pas un identifiant historique normalisé. Ainsi `1er` reste `1er`. Pour `z8`, `36` ou `i lfl`, il est nul même si le contexte suggère le numéro attendu. `label_exact` et le texte conservent les caractères source. Les reprises de numérotation sont distinguées par le parent, la section et l’ordre technique.

**`retained-unsegmented.jsonl`** : plages C conservées, sans revendication autonome certifiée. Les paragraphes sont des localisateurs techniques ; ce fichier ne transforme pas chacun d’eux en unité historique. Il ne remplace pas le texte intégral. Des préambules, mandats et observations peuvent aussi y figurer.

**`register.json`** : registre des 30 cahiers sans duplication du texte intégral. Les frontières, sections, métadonnées, sources, validation et raisons de sélection y sont réunies. `end_at` est explicité dans `decisions.json` pour Beaurecueil ; son offset corrigé figure dans les résultats.

**`reference.json`** : fenêtres de lecture et plages de référence. La seule fenêtre B n’est pas utilisée comme vérité de segmentation. Les A sont des décisions de frontières XML contrôlées, pas une collation intégrale de l’OCR sur images.

**`proposal-review.json`** suit chaque proposition brute : inchangée A, inchangée B, frontière modifiée ou exclusion comme article autonome. **`boundary-errors.json`** conserve les textes et plages des propositions incorrectes et des unités de référence manquées dans les fenêtres évaluées. **`legacy-crosswalk.json`** relie les 28 passages précédents aux nouvelles étendues, sans écraser leurs anciens identifiants.

## Identifiants et navigation

Les identifiants `ap1789-pilot-d1:...` associent révision, empreinte du fichier, divisions et plage parent. Les identifiants `ap1789-pilot-u1:...` ajoutent les positions d’unité à cette identité parent. Ils sont reproductibles pour cette version et ces frontières ; une modification du périmètre produit un autre identifiant. Ce sont des identifiants techniques expérimentaux, distincts des références bibliographiques, numéros d’article et identifiants Persée.

Le champ `method_version` et les empreintes du code et de `decisions.json` rendent les résultats traçables. Le corpus complet n’est pas un produit applicatif : aucune migration ou route n’est définie.

Les ancres, positions relatives et voisins permettent de préparer un résultat de recherche, retrouver le passage dans le parent et lire ses voisins. Ne pas considérer un voisin B comme validé : le jeu de positions est complet pour les candidats produits, pas pour toutes les revendications historiques possibles. Voir `data/navigation-examples.json` pour trois objets complets.

## Métadonnées et pagination

Le libellé de présentation est construit pour le registre ; les titres TEI exacts restent séparés. L’ordre, le territoire ou la localité ne sont attribués que lorsqu’ils ont été lus explicitement dans le titre ou le contexte documentaire, avec provenance. Un champ nul signifie parfois « non extrait de manière fiable », pas « information absente de toute archive ».

Les dates structurées et leur texte sont conservés indépendamment de la date de présentation choisie. Les dates de collation et de certification ne doivent pas être assimilées à la date de rédaction. Les dates manuscrites déduites ou les lieux modernes ne sont pas inventés.

Les pages correspondent aux `pb/@id` et `pb/@n`. La première page est le dernier `pb` précédant le début du passage, puis tous les `pb` à l’intérieur de sa plage. Un `@n` vide reste vide ; le numéro d’image n’est pas traité comme page imprimée. L’URL du service d’image utilise le gabarit Stanford vérifié dans les audits ; seules les cinq images du journal ont été téléchargées dans cette mission. Les références des autres pages ne valent pas vérification visuelle ou test HTTP individuel.

## Reproductibilité et vérifications

`data/reproducibility.json` compare deux exécutions du même code sur les sources figées : corpus JSONL, parents texte/XML, référence et registre. Les durées et horodatages sont volontairement hors comparaison binaire ; les métriques hors durée sont comparées séparément. Les scripts de téléchargement n’interviennent pas dans le calcul des unités.

`verify.py` vérifie les SHA-256, l’équivalence au texte XML, la reconstruction des parents et unités, les références XML, les plages sans chevauchement, le parent correct, l’ordre, les voisins, les notes exclues et la correspondance exacte de chaque A avec la référence. Il détecte les sept corruptions artificiellement injectées et contrôle les six exclusions documentaires.

Les contrôles réussis de fidélité ne prouvent pas que les 490 unités B ont de bonnes frontières documentaires. C’est précisément le rôle d’une validation complémentaire.
