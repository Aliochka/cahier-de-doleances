# Génération 6 — séparation des revendications thématiques fusionnées

La collection active est `data/corpus/global-corpus-6-29e180f0c67f`. Cette génération a été effectivement produite sur les six volumes, en 52 secondes sur cette machine, sans relancer la découverte des cahiers ni le segmenteur des numéros. La génération 5 et les journaux humains sont conservés.

## Résultat

| Indicateur | G5 figée | G5 avec décisions récentes | G6 |
|---|---:|---:|---:|
| Notices | 1 305 | 1 305 | 1 305 |
| Textes parents | 1 267 | 1 267 | 1 267 |
| Cahiers autonomes probables | 1 224 | 1 224 | 1 224 |
| Articles | 39 673 | 39 677 | **39 772** |
| Articles validés/corrigés humainement | 600 | 605 | **605** |
| Sections | 1 844 | 1 844 | 1 844 |
| Passages C bruts, blancs compris | 43 355 | 43 359 | 43 415 |

**61 unités automatiques réparties dans 42 parents ont été séparées**, pour produire **95 nouvelles revendications non numérotées proposées**. Il s’agit de vraies séparations à l’intérieur des anciennes plages, pas de simples changements de classification. Les unités concernées étaient 48 articles, huit sections et cinq passages C. Les préfixes gardent leur type ; les 47 préfixes numérotés gardent leur numéro et marqueur d’origine. Les restes ambigus et notes sont conservés en C. Leur nombre peut donc augmenter sans aucune perte de texte.

| Tome | Nouvelles revendications | Articles après | Dont humains |
|---|---:|---:|---:|
| I | 11 | 1 088 | 254 |
| II | 23 | 8 472 | 246 |
| III | 12 | 7 181 | 11 |
| IV | 5 | 8 016 | 33 |
| V | 29 | 8 854 | 18 |
| VI | 15 | 6 161 | 43 |

Les 95 nouvelles unités ont le statut **proposition automatique B**, sans numéro inventé. Leur type technique `article` n’affirme pas que l’imprimé porte ce mot. `unit_form: unnumbered_thematic_claim` et le contexte sourcé les distinguent des articles numérotés. Aucun de ces résultats n’est une certification historique.

## Cause et réparation à Amiens

Le document est le **cahier du clergé du bailliage d’Amiens**, notice `arcpa_0000-0000_1879_num_1_1_1547`. L’ancienne unité `ap1789-global-unit-1:d582bf0823b2ba22ac70b6b4ba6d`, numérotée 2, couvrait les positions Unicode **[5640887, 5650434[** du texte Stanford canonique. Elle contenait plusieurs développements et titres successifs.

Dans `/TEI.2/text/body/div1/div2[9]/div3[9]`, les paragraphes `p[30]` à `p[32]` portent la rémunération des curés ; `p[33]` porte « Dotation des cures de l'ordre de Malte et vicariats d'icelles. » ; `p[34]` son développement ; `p[35]` commence le titre de la retraite des ecclésiastiques. Ces titres sont des paragraphes ordinaires, sans attribut typographique significatif. Le lecteur conserve leur XPath, leurs positions et leur texte exact.

Trois limites de G5 se cumulaient : la reconnaissance thématique refusait un titre inclus dans un article déjà constitué ; « on demande qu’el- le… » n’était pas reconnu par les formulations retenues ; certains titres courts repliés sur plusieurs lignes étaient ignorés. L’analyse s’effectue maintenant aussi **à l’intérieur des articles et sections automatiques**, avec normalisation des espaces uniquement pour la recherche d’indices. Le texte exporté n’est jamais normalisé.

Après correction :

- l’article 2 conserve son numéro et son développement salarial, positions **[5640887, 5643975[** ;
- la dotation des cures devient une proposition non numérotée, **[5643975, 5644604[**, titre et développement réunis, jusqu’au titre suivant ;
- d’autres rubriques suffisamment étayées sont séparées dans cette même ancienne unité ; les développements insuffisamment établis restent en C et dans le parent intégral. Le titre « Retraite… » n’est pas automatiquement déclaré une nouvelle revendication sur sa seule apparence.

Les huit décisions récentes d’Amiens, et toutes les décisions de Beauvais, sont rejouées sans remplacement. L’unité salariale ci-dessus n’avait pas de décision humaine. Une autre unité automatique du même cahier pouvait donc être réparée sans toucher les unités humaines du document.

## Règle générale retenue

`extraction/fusion.py`, version figée `thematic-fusion-2`, complète les outils existants. Une séparation exige simultanément : titre court dans un élément XML isolé ; motif de titres voisins concordants ; développement substantiel ; demande explicite ; vocabulaire du titre présent dans le développement et nouveau par rapport aux paragraphes précédents ; fermeture du développement précédent ; limite droite matérielle ; absence de numérotation interne ou d’indice de continuation au-delà de l’unité.

Un sous-titre argumentatif (« Motifs », « Causes », « Conséquences »), une certification, une citation, une liste de participants, une phrase ordinaire, un développement interrompu et une sous-numérotation possible provoquent un refus ou une incertitude. Les demandes successives dans un même développement ne sont pas découpées. Les portées partagées entre documents restent protégées.

Le contrôle porte sur les **plages de tous les événements humains, avant et après**, pas seulement le dernier statut. Les unités validées, corrigées, laissées incertaines, leurs restes nécessaires au rejeu, et les anciennes références A restent protégées. Les suggestions qui les concernent sont séparées de l’état retenu. Une consultation n’ajoute jamais de décision.

## Incertitudes conservées

La recherche structurelle examine **1 393 unités** ayant au moins une ressemblance de titre intérieur ; **378** contiennent plusieurs emplacements candidats. Ces nombres ne représentent pas des fusions confirmées. Sur 5 107 emplacements analysés, 95 sont retenus et **5 012 sont conservés sans application**. Beaucoup sont de simples paragraphes courts ou des sous-titres, sans demande autonome démontrée.

Parmi ces refus, **182** réunissent au moins une demande explicite et un indice lexical de changement thématique, mais échouent à d’autres contrôles ; trois sont protégés par un historique humain. Ils ne sont pas annoncés comme 182 erreurs certaines. Le dossier peut les montrer dans un panneau de comparaison, sans imposer une file de milliers de validations. Les refus peuvent se trouver dans une unité ayant par ailleurs reçu une autre séparation sûre.

## Contrôles et régressions

Une première règle a été rejetée : sur 11 fenêtres contrôlées, quatre propositions étaient inadéquates (considérants interrompus avant un arrêté, phrase au futur, ordinal OCR `36d`, nom dans une liste). Sa version et son plan restent conservés ; **aucune génération n’a adopté cette règle**. Ces exemples sont ensuite devenus des contrôles de développement. Les quatre séparations fautives sont absentes de G6.

La seconde règle a été figée avant examen d’un **nouveau lot de neuf séparations**, issu d’un tirage reproductible d’unités candidates, et de **six refus**, un par volume. Les parents humains, du développement, des contrôles G5 et du premier contrôle ont été exclus. La graine est `178906`. Les refus sont choisis par mécanisme et empreinte, pas comme un échantillon statistique.

Aucune séparation manifestement incorrecte n’a été observée dans les neuf nouvelles fenêtres ; les six refus sont prudents. « Observation » sur l’usure contient par exemple une demande, mais son autonomie sous ce titre générique reste incertaine. Il n’y avait plus de candidat positif inédit admissible au tome I et un seul au tome III : les neuf fenêtres couvrent donc les tomes II à VI, les contre-exemples couvrent les six. **Ce sont des contrôles exploratoires Codex, avec propositions visibles, pas une validation humaine indépendante ni une mesure de précision globale.** Les règles n’ont pas été modifiées après ce second contrôle.

Les 86 tests Python passent. Les contrôles complets vérifient :

- identité des 1 267 parents, frontières et textes ;
- conservation des 84 856 unités non remplacées et des **707 unités courantes liées à une décision humaine**, dont 605 articles validés/corrigés ;
- partition exacte de chaque parent, texte extrait identique à la source, absence de trou ou chevauchement interne ;
- correspondance explicite des 61 anciennes unités avec leurs remplaçantes, numéros conservés ;
- sources, journaux, inventaire, zones sources non attribuées et deux chevauchements documentaires inchangés ;
- zéro groupe de duplication de plages d’articles ;
- conservation des anciennes fenêtres et exemples de l’interface.

Les essais navigateur vérifient l’accès au nouveau lot, le surlignage, Amiens, les filtres, la reprise, l’affichage mobile, la conservation des corrections humaines de Beauvais et l’absence d’erreur JavaScript. Un essai distinct de validation/annulation vérifie les badges et leur persistance **dans des copies temporaires des journaux uniquement**. Aucune décision humaine réelle n’a été créée ou modifiée par ces tests.

## Petit contrôle à ouvrir

Après arrêt et redémarrage du serveur avec `python3 1789/review.py`, ouvrir :

**http://127.0.0.1:1789/?fusion_review=1**

Le panneau **« Nouveau contrôle ciblé — séparations de revendications »** contient le cas d’Amiens, les neuf nouvelles séparations du lot hors développement, puis les six refus consultables. Le titre ciblé est surligné dans son unité. Le badge d’avancement repose sur les décisions explicites. Inutile de reprendre les douze exemples précédents. Le panneau du cahier permet également de comparer l’ancienne unité complète avec les nouvelles propositions.

## Reproduction et fichiers

Les fichiers de G6 incluent `fusion-candidates.jsonl.gz`, `fusion-changes.jsonl.gz`, `unit-crosswalk.jsonl.gz`, les unités A/B/C, `units.jsonl.gz`, le registre des contextes, le bilan et les empreintes. Les journaux utilisés sont figés sous `.private/` de la génération, exclus de Git. Les originaux append-only sont inchangés. Les sources Stanford restent à la révision `926fd3cd986a3c3d411e93d1845fff6475cb2602`.

```sh
# Vérifications seules, sans extraction ni écriture dans les journaux :
python3 1789/extraction/production.py --verify-only 1789/data/corpus/global-corpus-6-29e180f0c67f
python3 1789/extraction/check_fusion.py 1789/data/corpus/global-corpus-6-29e180f0c67f
PYTHONPATH=1789/extraction python3 -m unittest discover -s 1789/tools/document-review -p 'test_*.py'

# Reproduction de cette transformation, depuis G5 et les journaux choisis :
python3 1789/extraction/fusion_production.py --no-activate
```

`--decisions-directory CHEMIN` permet de rejouer un instantané de journaux. Les chemins et leurs empreintes font partie des entrées : un autre emplacement donne un autre identifiant de génération, même à décisions identiques. Une sortie existante n’est jamais écrasée. `fusion_plan.py` n’a pas besoin d’être relancé : les deux plans figés et leurs empreintes sont conservés. Le constructeur est celui de cette transition G5 → G6, pas une commande permettant de remplacer les décisions ultérieures d’une G6 déjà vérifiée.

[Bilan structuré des contrôles](fusion-corrections-checks.json). Les gros résultats, textes et journaux restent locaux. Il reste des revendications possibles non séparées : la règle privilégie une abstention traçable à une nouvelle découpe artificielle.
