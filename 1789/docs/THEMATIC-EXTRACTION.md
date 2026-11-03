# Génération 5 — rubriques et revendications non numérotées

La génération livrée est `data/corpus/global-corpus-5-7b829ada54d6`. Les six volumes ont été réellement régénérés, à parents inchangés. La génération 4, les sources Stanford figées et tous les journaux humains sont conservés.

## Résultat de production

La génération 4 figée contenait 39 243 articles. Vos nouvelles corrections portent son état rejoué à **39 269 articles avant cette extraction**. La génération 5 ajoute **404 propositions thématiques non numérotées**, pour un total de **39 673 articles**. Ces 404 propositions ne reçoivent aucune validation humaine automatique.

| Indicateur | G4 figée | G4 avec décisions récentes, avant transformation | G5 |
|---|---:|---:|---:|
| Notices | 1 305 | 1 305 | 1 305 |
| Textes parents | 1 267 | 1 267 | 1 267 |
| Cahiers autonomes probables | 1 224 | 1 224 | 1 224 |
| Articles | 39 243 | 39 269 | **39 673** |
| Articles validés/corrigés humainement | 333 | **600** | **600** |
| Unités de type section | 1 143 | 1 159 | 1 844 |
| Passages techniques C bruts | 42 370 | 42 329 | 43 355 |
| Unités thématiques non numérotées identifiables par les nouvelles règles | non distinguées | 6 unités déjà constituées | **410** |
| Titres thématiques retenus par la reconnaissance | non distingués | non exposés dans G4 | **1 388** |
| Rubriques associées à plusieurs articles | non distinguées | non exposées dans G4 | **957** |
| Liens article → rubrique proposés et sourcés | anciennes attributions heuristiques non comparables | non exposés sous cette forme | **8 362** |
| C d’origine requalifiés, identifiants distincts | — | — | **1 027** |
| Hypothèses thématiques insuffisamment établies | — | — | **1 234** |

Les diagnostics thématiques « avant » utilisent les mêmes règles sur les unités antérieures : ils ne représentent pas des annotations produites anciennement par G4. Les 410 unités reconnues après transformation comprennent les six unités déjà constituées et les 404 nouvelles propositions. **Un numéro absent ne prouve pas à lui seul qu’une unité est une revendication non numérotée** : les autres articles sans numéro reconnu peuvent encore relever d’un OCR dégradé ou d’une structure incertaine.

Sur les 404 créations d’articles, **147 reprennent exactement les plages d’une unité antérieure** et constituent un changement de classification ; **257 délimitent ou réunissent un titre et son développement** à partir des unités techniques ou sections disponibles. Les **933 unités de titre de section** créées restent distinctes des articles. Au total, 1 027 C et 248 anciennes sections automatiques sont concernés. La variation du nombre de C ou de sections traduit aussi leur fragmentation et la conservation des restes : elle ne mesure aucune perte de texte.

| Tome | Articles G5 | Dont humains | Sections | C bruts |
|---|---:|---:|---:|---:|
| I | 1 073 | 249 | 45 | 1 116 |
| II | 8 449 | 246 | 264 | 9 046 |
| III | 7 169 | 11 | 443 | 7 902 |
| IV | 8 011 | 33 | 330 | 8 910 |
| V | 8 825 | 18 | 496 | 9 638 |
| VI | 6 146 | 43 | 266 | 6 743 |

## Référence humaine de Beauvais

Le cahier concerné est le **tiers-état du bailliage de Beauvais**, notice `arcpa_0000-0000_1879_num_2_1_1639`. Le journal contient 195 événements pour ce parent au moment de l’analyse ; ce nombre n’est pas un nombre d’articles. Les décisions montrent notamment :

- des sections seules, comme « Religion. Clergé. » ;
- des sections avec introduction, dont « Commerce », « Juridiction consulaire » et « Agriculture » ;
- des suites d’articles numérotés, corrigées ou validées ;
- des articles sans numéro, dont « Jurandes et maîtrises », « De la gabelle », « Du tabac » et « Francs-fiefs ».

Ces choix humains restent inchangés, y compris lorsqu’une section humaine comprend déjà son introduction ou qu’une interprétation automatique pourrait proposer un autre type. Aucun travail n’est demandé à refaire.

### XML observé

Dans le tome II, division `/TEI.2/text/body/div1/div2[20]/div3[3]` :

- `p[235]` porte « Jurandes et maîtrises. », sans attribut typographique ; `p[236]`, `p[237]` et `p[238]` forment son développement ; `p[239]` commence « Agriculture. » ;
- `p[189]` porte « Commerce. », également dans un simple paragraphe, suivi de l’introduction puis d’articles ;
- les titres sont donc des paragraphes distincts, pas nécessairement des `head` et jamais des balises sémantiques de « revendication ».

Le lecteur conserve les éléments, leur ordre, les espaces, XPath, positions Unicode et pages. Les retours à la ligne internes à un paragraphe peuvent correspondre aux lignes de l’édition ou à la mise en forme XML : ils ne sont pas utilisés comme un découpage sémantique. Les formes ne sont pas uniformes dans les six volumes.

## Règles appliquées

L’extension `extraction/thematic.py` complète les unités existantes. Elle ne relance ni la découverte des documents ni la reconnaissance des numéros.

Un titre candidat doit être un élément XML isolé et court, compatible avec une étiquette thématique. Dates, marqueurs d’article, titres documentaires, formules de vote, signatures et fragments manifestement phrastiques sont écartés. Pour les paragraphes ordinaires, une succession d’au moins trois titres comparables dans la même division est demandée. Le titre suivant, les divisions, titres structurels et clôtures bornent le développement.

**Titre + développement autonome.** En l’absence d’articles numérotés dans la portée, un développement suffisamment substantiel, une demande explicite hors notes et une fin repérable permettent de proposer une seule unité `article`, de numéro `null`, comprenant le titre et le développement. Plusieurs demandes dans ce développement ne déclenchent aucun découpage supplémentaire. `unit_form` permet de distinguer cette proposition d’un article explicitement numéroté. Le modèle technique « article » n’affirme pas que l’imprimé porte ce mot.

**Rubrique + articles, avec ou sans introduction.** Au moins deux articles déjà présents permettent de proposer une section thématique et leurs relations. Le titre peut devenir une unité de section ; l’introduction reste conservée dans les C et ses plages sont identifiées. Une introduction déjà groupée dans une section humaine est conservée telle quelle. Les articles numérotés ne sont ni redécoupés ni renumérotés.

**Paratexte documentaire.** Un titre de cahier n’est pas transformé en revendication. Les notes sont exclues des nouvelles plages d’article et restent présentes dans le parent et ses unités techniques. Une demande ne peut être inférée de la seule présence d’une formule dans une note XML.

**Abstention.** Une ligne courte n’est jamais une preuve suffisante. Sont notamment laissés incertains les fins non marquées, titres qui semblent inclus dans un article numéroté, rubriques minuscules ambiguës, listes de phrases courtes, développements traversant une autre rubrique, numérotations possiblement manquées et sous-documents de localités. Tous les parents ayant déjà des événements humains d’articles sont protégés intégralement contre les transformations automatiques ; seules des métadonnées de contexte distinctes peuvent y être proposées.

## Contexte et compatibilité

Les champs existants `parent.sections`, `section_id`, les unités `article/section/technical_passage` et les identifiants sources sont réutilisés. Le `section_id` original d’un article, notamment humain, n’est pas écrasé. Une couche additive fournit :

- `thematic_context` : titre exact, XPath, portée, rôle proposé et provenance ;
- `effective_section_id` : relation thématique proposée lorsqu’elle est disponible, avec conservation de l’attribution antérieure ;
- `introduction_spans` dans le registre des rubriques : positions de l’introduction ;
- `unit_form: unnumbered_thematic_claim` pour les propositions correspondantes.

Le contexte reste proposé : il ne constitue pas une validation humaine de la relation ni une reconstitution complète de tous les niveaux de titres. Les anciennes rubriques heuristiques, parfois erronées, restent traçables ; elles ne sont pas certifiées rétroactivement. Les données sont exploitables sans changement PostgreSQL ni modèle applicatif.

## Portée des contrôles et limites

Douze fenêtres limitées, couvrant les deux formes dans chacun des six volumes, ont été examinées dans le TEI :

| Tome | Exemple de titre + développement | Exemple de rubrique + articles |
|---|---|---|
| I | Clergé d’Amiens : « Aides et gabelles » | Noblesse d’Agen : améliorations particulières |
| II | Tiers-état de Bordeaux : « Constitution » | Clergé d’Armagnac : législation et jurisprudence |
| III | Ville de Vienne : « Des lois et des tribunaux » | Noblesse de Thionville : « Administration » |
| IV | Tiers-état de Nemours : « Des vingtièmes » | Argenteuil : « Dépense » |
| V | Tiers-état de Senlis : « Les cadastres » | Clergé de Paris : « Subsides » |
| VI | Tiers-état de Saint-Flour : « Constitution nationale » | Noblesse de Troyes : « États généraux » |

Les références exactes sont dans [le bilan structuré](thematic-extraction-checks.json). Il s’agit de contrôles documentaires exploratoires par Codex, dont certains cas déjà connus, **pas d’une validation humaine indépendante ni d’une mesure de précision extrapolable**.

Le traitement conserve **8 303 ressemblances typographiques candidates** : 1 388 sont suffisamment étayées pour des propositions, 1 234 ressemblent à l’une des deux structures mais restent incertaines, et 5 681 autres n’ont pas de rôle établi. Ces dernières ne sont pas annoncées comme autant de vraies rubriques ni mises dans une file obligatoire de vérification. Les raisons se recoupent : absence de développement, portée non close, titre dans un article, nouvelle rubrique possible, signature, numérotation à vérifier, etc.

Les deux chevauchements documentaires déjà connus restent inchangés. Les 14 hypothèses touchant leurs plages communes sont conservées sans nouvelle segmentation automatique. Cela évite de créer une nouvelle attribution d’article sur une plage partagée dont le statut documentaire reste distinct de cette mission. Aucun groupe de doublons d’articles par plages sources identiques n’est ajouté.

## Intégrité et vérification locale

Les contrôles vérifient :

- les 1 305 notices, 1 267 parents et leurs textes, métadonnées et frontières inchangés ;
- la conservation exacte de chaque caractère dans une partition sans lacune ni chevauchement interne ;
- les **39 269 articles préexistants, dont 38 628 numérotés, strictement identiques** après rejeu des décisions ;
- les **653 unités validées/corrigées humainement, dont 600 articles**, et l’état entier des parents ayant un historique humain, y compris incertitudes et restes techniques ;
- les références sources, identifiants, correspondances, notes et journaux ;
- le maintien exact du tirage indépendant de 24 fenêtres, sans nouvelle validation ;
- les listes d’identifiants des unités des parents rangées dans l’ordre du texte source (14 anciennes listes par statut ont été remises en ordre, sans changer les unités) ;
- les fonctions de l’interface et les blancs techniques masqués comme auparavant.

Les **74 tests Python** et les essais navigateur passent. Le test navigateur des structures thématiques vérifie les filtres, titres, articles sans numéro, liens de section, conservation du cas humain de Beauvais et affichage mobile, sans POST ni décision humaine créée. Les tests écrivant des décisions utilisent uniquement des journaux synthétiques ou des copies temporaires.

## Utiliser et reproduire

Relancer l’outil avant de poursuivre les corrections :

```sh
python3 1789/review.py
```

Dans **Articles**, les filtres « Revendications thématiques non numérotées » et « Rubriques et articles rattachés » donnent accès aux nouveaux résultats. Le panneau du dernier contrôle contient **12 exemples thématiques supplémentaires** ; le lot précédent et son avancement sont conservés. Aucun examen systématique des milliers de ressemblances non retenues n’est demandé.

La génération contient `parents.jsonl.gz`, `units-A/B/C.jsonl.gz`, l’état rejoué `units.jsonl.gz`, ainsi que :

- `thematic-regions.jsonl.gz` : titres, portées, introductions, indices et incertitudes ;
- `thematic-context.jsonl.gz` : relations proposées des unités actuelles ;
- `thematic-changes.jsonl.gz` : types, plages et identifiants avant/après, avec distinction des changements de classification seuls ;
- `unit-crosswalk.jsonl.gz` : correspondances des bases automatiques ; les identifiants humains restent conservés par le journal ;
- `inputs.json`, `complete.json`, `.private/` : empreintes et instantanés privés pour la reproduction.

```sh
python3 1789/extraction/production.py --verify-only 1789/data/corpus/global-corpus-5-7b829ada54d6
python3 1789/extraction/check_thematic.py 1789/data/corpus/global-corpus-5-7b829ada54d6

# Reproduction de cette extraction, à partir de ses décisions figées, sans activation
python3 1789/extraction/thematic_production.py --no-activate \
  --decisions-directory 1789/data/corpus/global-corpus-5-7b829ada54d6/.private
```

Le producteur refuse d’écraser une génération existante. Une incohérence de version ou un changement d’entrée pendant la production provoque un arrêt explicite. La génération 4 reste nécessaire comme base documentaire et historique de rejeu ; les générations et journaux privés restent hors Git et doivent être sauvegardés.

**Recommandation :** conserver cette génération comme corpus de travail, examiner quelques-uns des douze exemples thématiques dans l’interface, puis stabiliser les corrections. Les cas insuffisamment établis restent dans leur texte parent et les passages techniques ; il n’est pas nécessaire de rouvrir les frontières ni de relancer un cycle général d’optimisation pour utiliser les deux formes documentaires.
