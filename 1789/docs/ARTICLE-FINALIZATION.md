# Extraction des articles : génération 4

La génération active est `data/corpus/global-corpus-4-b643646266f1`. Les six volumes ont été réellement traités. Les générations antérieures et les journaux humains sont conservés. Cette étape ne produit ni embeddings ni index.

## Résultat avant / après

| Indicateur | Génération 3 | Génération 4 |
|---|---:|---:|
| Notices conservées | 1 305 | 1 305 |
| Textes parents | 1 267 | 1 267 |
| Cahiers autonomes probables extraits | 1 224 | 1 224 |
| Frontières validées humainement | 29 | 45 |
| Articles | 39 072 | 39 243 |
| Articles validés/corrigés humainement | 333 | 333 |
| Articles automatiquement proposés | 38 739 | 38 910 |
| Articles avec alertes classiques de segmentation | 4 723 | 4 703 |
| Unités fusionnées séparées par la nouvelle règle | — | 66 |
| Gain net d’articles par ces séparations | — | 68 |
| Articles récupérés depuis C par la nouvelle règle | — | 1 |
| Sections proposées | 1 231 | 1 143 |
| Passages techniques C conservés | 42 262 | 42 370 |
| Chevauchements documentaires connus | 2 | 2 |
| Groupes d’articles ayant des plages sources identiques | 0 | 0 |

Les 171 articles supplémentaires se décomposent en **102 à Digne**, **68 issus de séparations** et **1 récupéré depuis C**. Digne n’avait auparavant aucun article : son texte était conservé dans 94 sections en attente de décision documentaire. Votre confirmation permet d’y appliquer l’extracteur existant : 102 articles, 6 sections et 110 passages C. Les variations de sections et de C ne mesurent donc pas une perte ou un gain de texte.

Les articles et les alertes sont des propositions, sauf statut humain explicite. La baisse des alertes ne constitue pas une mesure de précision. Aucun taux de fiabilité global n’est annoncé.

| Tome | Articles | Dont humains | Sections | C | Articles avec alertes classiques |
|---|---:|---:|---:|---:|---:|
| I | 1 057 | 143 | 23 | 1 127 | 159 |
| II | 8 321 | 85 | 129 | 8 852 | 1 476 |
| III | 7 060 | 11 | 323 | 7 698 | 1 139 |
| IV | 7 961 | 33 | 187 | 8 704 | 657 |
| V | 8 718 | 18 | 336 | 9 384 | 514 |
| VI | 6 126 | 43 | 145 | 6 605 | 758 |

## Dernières décisions documentaires appliquées

Le journal contient les confirmations des **12 cahiers tirés au sort** et des **trois dossiers de finalisation** (cinq notices, dont une déjà validée). Cela porte à 45 le nombre de parents validés. Les journaux contiennent 56 événements documentaires et 346 événements d’articles ; ces événements ne sont pas des nombres de documents ou d’articles distincts.

Les différences de plages portent essentiellement sur des blancs aux limites des blocs. La seule suppression de texte substantiel concerne Clermont-Ferrand : la formule éditoriale finale « FIN DU TOME DEUXIEME » sort du cahier. Elle reste dans l’inventaire du texte source hors parents. Digne est libéré de son ancien état d’attente. Aucun algorithme de découverte ou de correction des frontières n’a été relancé.

Les deux chevauchements connus restent enregistrés séparément des confirmations humaines. Une confirmation ne les fait pas disparaître. Les dix parents ayant des décisions humaines d’articles sont protégés intégralement contre les nouvelles séparations automatiques. Les **333 articles humains** et les **217 articles A hérités** conservent leurs textes et leurs plages.

## Corrections appliquées

Une extension additive du segmenteur reconnaît des marqueurs littéraux tels que `A:rt.`, `Ârt.`, `Arl.`, `Ari.`, un chiffre collé au texte ou une séquence OCR telle que `l0`. Elle ne réécrit aucun caractère.

Une séparation automatique exige un faisceau d’indices : formule introduisant une demande, marqueur effectivement présent, numéros voisins déjà reconnus encadrant une séquence complète, même division XML et absence de rubrique ou clôture intermédiaire. Un numéro sans préfixe exige aussi des voisins de même style. Une alternative autorise une suite d’au moins trois articles explicitement préfixés dans C. Un saut de numéro seul ne provoque jamais de découpage. Les dates, sommes, références d’articles et sous-listes sont couvertes par des tests négatifs.

Les 66 unités modifiées étaient B, jamais humaines ou A. Elles donnent 134 unités proposées ; une séparation peut révéler plusieurs articles. Le seul article récupéré depuis C est celui de Peynier, tome VI, notice `2621` : `Àrt. 36. La Suppression des péages et pulvé-rages.` Ses voisins 35 et 37 et son paragraphe XML étayent sa récupération. Ces résultats restent proposés, sans validation humaine ajoutée. Un indice numérique interprété (`l0` → indice 10) reste séparé du numéro historique : aucune étiquette « 10 » n’est fabriquée lorsque la source porte des lettres.

Dix-sept fenêtres, réparties entre les six volumes et distinctes des dix cahiers de développement humain, ont été sélectionnées par ordre de hachage avant leur lecture. Les 19 nouveaux débuts concernés ont été examinés dans les paragraphes XML et leur voisinage ; aucune fausse séparation n’y a été observée. Les continuations sur plusieurs paragraphes sont conservées. Ce contrôle Codex porte sur les nouvelles coupures, pas sur une référence exhaustive des fins, et ne constitue ni une validation humaine indépendante ni une estimation globale. Les fonctions de découpage sont restées gelées après cette sélection ; leurs empreintes AST sont conservées dans `extraction/article-rule-checks.json`. La qualification de C a été rendue plus prudente séparément.

## Ce que signifient les anomalies restantes

Les mécanismes suivants peuvent se cumuler sur une même unité :

| Mécanisme | Nombre | Interprétation |
|---|---:|---|
| Numéro répété | 2 669 | Reprise de section ou erreur possible ; pas une erreur démontrée |
| Séquence irrégulière | 1 794 | Saut ou reprise conservé ; aucune renumérotation |
| Étiquette OCR incertaine | 632 | Lire le marqueur dans son contexte |
| Article de plus de 12 000 caractères | 50 | Longueur inhabituelle, pas nécessairement une fusion |
| Marqueur intérieur restant dans un article | 393 | Fusion possible, indices insuffisants pour corriger automatiquement |
| Section contenant une formule de demande | 829 | Le texte est conservé en section, pas perdu ni transformé en article |

Les 393 fusions possibles peuvent recouper les 4 703 articles signalés par les contrôles classiques. **Il ne s’agit pas de 393 erreurs confirmées.** Les reprises de numérotation et les anciennes rubriques déduites automatiquement restent à interpréter avec prudence.

Sur les **42 370 C**, la qualification automatique distingue :

| Qualification proposée | Nombre |
|---|---:|
| Paratexte, dont blancs et ponctuation | 37 600 |
| Formule revendicative dans de la prose conservée | 1 373 |
| Marqueur numérique pouvant annoncer un article manqué | 204 |
| Nature indéterminée | 3 193 |

Cette qualification ne change pas le type C. Une formule de demande peut appartenir à un préambule ; elle ne prouve pas l’autonomie d’une revendication. Un nombre peut appartenir à une date ou une rubrique. Les notes explicitement balisées, titres XML, blancs et clôtures sans indice de demande sont distingués ; un rôle heuristique de « rubrique » ne suffit pas à écarter un texte. Aucun C n’est supprimé. Les **597 signalements de coupure possibles** (393 articles et 204 C) constituent un inventaire machine, pas une file obligatoire de 597 décisions humaines.

## Dernier contrôle limité dans l’interface

Relancer le serveur s’il était déjà ouvert :

```sh
python3 1789/review.py
```

Ouvrir **http://127.0.0.1:1789/?article_sample=1**. Dans le mode Articles, le panneau « Dernier contrôle des articles » donne accès à :

- **24 fenêtres indépendantes**, deux articles sans alerte et deux C non vides par volume ;
- **13 exemples ciblés**, dont six séparations, l’article récupéré depuis C et quelques passages à qualifier.

Le tirage utilise `random.Random(178939072)` sur des identifiants triés. Il exclut les parents du pilote initial, ceux ayant des décisions humaines d’articles et ceux du contrôle des nouvelles règles. Les articles retenus n’ont ni alerte ni mécanisme signalé ; les C sont seulement soumis à un seuil de lisibilité de 80 caractères. Les listes d’éligibilité sont identifiées par leurs effectifs et empreintes. Ce petit plan stratifié n’est pas représentatif des 1 305 notices. Aucune appréciation documentaire ni validation n’a été portée sur ces 24 fenêtres : les essais du navigateur vérifient uniquement leur accès technique.

Les filtres permettent de retrouver les corrections, les fusions possibles et les qualifications de C. Une correction automatique a un fond distinct du vert des décisions humaines. Le panneau de comparaison montre l’ancienne unité entière, les marqueurs et les nouvelles unités. Les outils existants de contexte, correction, classement et validation groupée restent disponibles. Une consultation ne crée aucune décision.

Commencer par ce petit lot, plutôt que parcourir systématiquement tous les signalements. Si le contrôle révèle une erreur silencieuse grave ou une famille récurrente de faux découpages, la documenter avant de stabiliser la collection. Les passages incertains restent à arbitrer progressivement. Le gros de l’extraction est produit ; la qualité finale reste à confirmer par ce contrôle humain limité.

## Données, intégrité et reproduction

La génération contient notamment :

- `inventory.jsonl.gz`, `parents.jsonl.gz`, `units.jsonl.gz` : inventaire complet, textes intégraux et état incluant les décisions humaines ;
- `units-A/B/C.jsonl.gz` : bases reproductibles, avant superposition du journal ;
- `article-changes.jsonl.gz`, `unit-crosswalk.jsonl.gz` : séparations et correspondances des anciennes bases automatiques vers les nouvelles ; les identifiants des articles créés humainement restent inchangés dans l’état final ;
- `unit-quality.jsonl.gz`, `article-marker-candidates.jsonl.gz` : qualifications et indices, sans certification ;
- `article-workbench.json` : échantillon figé, exemples, graine et exclusions ;
- `parent-human-updates.jsonl.gz`, `document-overlaps.jsonl.gz`, `unassigned-source.jsonl.gz` : modifications parentales explicitement enregistrées, chevauchements conservés et texte source hors parents ;
- `inputs.json`, `complete.json`, `summary.json`, `.private/` : versions, empreintes, bilan et copies privées des journaux pour la reproduction.

**Tous les caractères de chaque parent sont couverts exactement une fois par ses unités**, y compris les blancs et notes. Les plages sont des positions Unicode dans la représentation textuelle TEI Stanford conservée, avec XPath, blocs et pagination. Les articles en plusieurs plages ne fusionnent pas silencieusement les notes avec le texte principal. L’ordre des unités permet la navigation ; il ne certifie pas une succession historique lorsque la segmentation est proposée.

Les contrôles vérifient les 1 305 notices, l’unicité des identifiants, les rattachements, la fidélité aux sources, les limites et la partition exacte des parents, les références humaines et l’intégrité des fichiers. Aucun parent n’a disparu. Le texte hors parents reste inventorié. Les fichiers de sources, registre et journaux ont gardé leurs empreintes. Les métadonnées et la liste documentaire héritées restent disponibles.

```sh
# Vérification de la génération livrée, sans réextraction
python3 1789/extraction/article_production.py --verify-only 1789/data/corpus/global-corpus-4-b643646266f1
python3 1789/extraction/check_article_finalization.py 1789/data/corpus/global-corpus-4-b643646266f1

# Nouvelle génération après décisions supplémentaires, sans relancer les frontières
python3 1789/extraction/article_production.py
```

Le producteur utilise les parents figés de génération 3 et les décisions documentaires explicites. Pour rejouer les articles humains, il conserve les bases de la génération active ; `--history-baseline CHEMIN` permet de figer cette dépendance. Une incompatibilité entre ancien article humain et nouveau parent bloque ce dossier explicitement au lieu de transférer la validation. `--no-activate` construit sans changer la génération active. Une génération existante n’est jamais écrasée ; utiliser `--verify-only` pour la contrôler. Les durées ne rendent pas les fichiers de bilan identiques octet par octet, mais les données et identifiants sont déterminés par les entrées et versions conservées.

Les **57 tests Python** passent, ainsi que les essais navigateur de la collection, des filtres, des comparaisons, des liens directs et de la navigation clavier, aux largeurs 320, 375, 768 et 1 280 pixels et avec texte à 200 %. Les tests écrivant des décisions utilisent exclusivement des copies temporaires des journaux. Le parcours du nouveau lot ne produit aucun POST. L’ancien test documentaire utilise désormais son instantané historique, plutôt que de supposer que Digne est encore incertain dans le journal réel.

Les corpus, copies de journaux et fichiers de travail restent ignorés par Git. Seuls le code, les instructions, les références limitées du contrôle des règles et le [bilan agrégé](article-finalization-checks.json) sont versionnables. Les décisions humaines n’ont pas été modifiées et doivent continuer à être sauvegardées avec les données locales. Aucun changement applicatif, PostgreSQL, OCR ou calcul de modèle n’a été effectué.
