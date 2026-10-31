# Frontières documentaires — corrections de production

> Bilan de la génération 2 conservé. La [finalisation documentaire](DOCUMENTARY-FINALIZATION.md) décrit la génération 3 et le lot de 12 cahiers prêt au contrôle humain.

Une nouvelle génération complète a été **exécutée** sur les six volumes : `data/corpus/global-corpus-2-45273d688b59/`. La génération de référence `global-corpus-1-95b58b690be5/` est conservée. Le registre, les sources et les journaux n’ont pas été modifiés.

**26 documents ont effectivement changé de plage** : 14 fins arrêtées avant un autre cahier identifié et 12 alignements repris à partir d’une ouverture explicite. Ces derniers comprennent **7 notices auparavant sans texte**, avec leur nature propre conservée. Aucun document précédemment extrait n’a disparu.

## Avant / après

| Indicateur | Avant | Après |
|---|---:|---:|
| Notices traitées | 1 305 | 1 305 |
| Textes parents extraits | 1 237 | 1 244 |
| Cahiers autonomes probables extraits | 1 201 | 1 202 |
| Frontières humaines préservées | 29 | 29 |
| Frontières automatiques sans alerte documentaire détectée | 805 | 932 |
| Frontières automatiques suspectes | 402 | 282 |
| Périmètres incertains | 1 | 1 |
| Notices sans texte | 68 | 61 |
| Dont annonces de cahiers absents | 4 | 4 |
| Sans plage exploitable  hors annonces d’absence | 64 | 57 |
| Paires de chevauchements documentaires | 46 | 16 |
| Groupes de plages sources identiques | 377 | 73 |
| Articles après reprise des décisions | 38 186 | 38 553 |
| Articles humains préservés | 333 | 333 |

Les catégories « sans alerte » et « rapprochement fort » restent des **propositions automatiques**, sans certification des frontières. Les quatre annonces de cahiers absents sont conservées sans tentative de fabriquer leur texte. Les 57 autres notices sans texte comprennent **23 cahiers probables et 34 listes, procès-verbaux ou pièces associées**.

## Corrections déterministes appliquées

### Divisions XML contenant plusieurs cahiers

Une division feuille est parfois utilisée jusqu’à sa fin pour chacune des notices qu’elle contient. Cela duplique les textes suivants. La règle arrête le parent à une **ouverture explicite d’un autre cahier**, identifiée séparément par son nom, son ordre éventuel, sa page et sa position dans le catalogue. Elle exige des indices concordants : **aucune coupe ne repose sur la pagination seule**.

La règle ne sépare pas automatiquement une annexe d’un parent, ne saute pas une notice intermédiaire non résolue et conserve les signatures/notes précédant l’ouverture suivante. Les 14 corrections de fin résolvent 26 anciennes paires de chevauchement, impliquant 23 documents (certaines paires se recoupent).

Exemples : les cahiers nobles d’Albret et de Nérac finissaient tous deux après le cahier du tiers de Tartas ; ils s’arrêtent désormais aux ouvertures respectives de Nérac et du tiers. Le cahier commun d’Amont n’absorbe plus Gray. Les pièces successives du groupe de Barcelonnette sont mieux isolées, sans imposer une coupe lorsque le titre intermédiaire reste douteux.

### Alignements erronés sur une page partagée

La nouvelle vérification recherche une **seule ouverture compatible avec les noms distinctifs, l’ordre lorsqu’il est explicite, le genre documentaire et la page**. Elle compare toutes les ouvertures admissibles, conserve les alternatives ambiguës et refuse les approximations OCR. Les séparations typographiques (`Saint- Victoret`, `Er-, mont`) sont reconnues pour comparer les noms ; le texte original reste inchangé.

Douze alignements ont été repris. Quatre anciennes paires impliquant huit documents sont résolues par cette famille. Ermont ne pointe plus vers Épinay ; Saint-Victoret ne reçoit plus le cahier de Saint-Zacharie ; Silans ne reçoit plus Saunes. Aubagne est également réaligné sur son propre titre. Les anciens noms, positions et hypothèses restent disponibles dans la génération antérieure et dans les résolutions.

Sept notices sont récupérées :

- Cahier du tiers-état de la sénéchaussée de Brest — `proces_verbal`.
- Cahier de la paroisse de Massugas (Sénéchaussée de Castelmoron d'Albret) — `proces_verbal`.
- Délibération de la ville de Pontivy (Sénéchaussée de Ploërmel) — `document_associe`.
- Déclaration de la noblesse de Bretagne (Sénéchaussée de Saint-Brieuc) — `document_associe`.
- Liste des comparants de la noblesse et du tiers-état du bailliage de Senlis — `liste`.
- Liste des comparants des trois ordres de la sénéchaussée de Villeneuve-de-Berg — `liste`.
- Cahier de la communauté d'Allauch (Sénéchaussée d'Aix) — `cahier_autonome_probable`.

Brest et Massugas restent classés comme procès-verbaux selon les références antérieures ; leurs textes comportent un cahier, mais ils ne deviennent pas artificiellement des cahiers autonomes. Les listes et délibérations gardent également leur catégorie. Le nombre de cahiers autonomes extraits augmente donc de **1**, pas de 7.

### Alertes expliquées, sans prétendre certifier les textes

- **101 alertes de page de fin** : la dernière lettre non blanche de la plage est située sur la page annoncée. Parmi les anciennes alertes, 62 venaient de blancs après un changement de page, 20 étaient déjà contredites par le périmètre effectivement retenu et 19 sont résolues après les corrections actuelles. Seul ce test numérique précis est levé : les autres contradictions restent visibles.
- **12 signalements d’ancienne frontière incorrecte** concernaient encore la proposition originale alors qu’une référence examinée dans la source, ou une décision humaine, était déjà appliquée. Leurs preuves et leur origine sont conservées. Le cas humain incertain de Digne garde ses alertes.
- **44 ambiguïtés d’identité** sont levées par une ouverture unique et des noms/ordres/pages concordants. Les rapprochements simplement probables sans ces preuves restent prioritaires pour confirmation.
- **11 alertes d’ancre partagée** sont levées seulement lorsque les positions finales sont effectivement distinctes et le nom de l’ouverture concorde. Les véritables chevauchements sont recalculés ensuite, jamais désactivés.

Ces nombres sont des résolutions d’alertes, avec recoupements entre documents ; **ce ne sont pas des mesures de précision**. Les changements de confiance sont traçables séparément des changements de plages et ne créent aucune validation humaine.

## Problèmes non résolus

Les **16 paires restantes** sont conservées intégralement :

| Famille restante | Paires | Documents impliqués | Décision |
|---|---:|---:|---|
| Imbrication, succession ou colonnes encore ambiguës | 9 | 17 | Vérifier les ouvertures, clôtures et pièces intercalées ; pas de coupe arbitraire |
| Document associé ou niveau de description différent | 2 | 4 | Examiner la relation, sans supposer une erreur ni fusionner |
| Même plage pour deux identités différentes | 5 | 10 | Départager la mauvaise attribution et une éventuelle pièce commune |

Les documents peuvent intervenir dans plusieurs paires. Les deux cas associés concernent notamment les corps d’Arles et les listes du clergé du Poitou : leur recouvrement n’est pas déclaré bénin sans contrôle. Les 5 cas de plage identique concernent Lessart/Létang-la-Ville, les deux Ormoy, les pièces du Pin, Villecresne/Ville-du-Bois et Tholonet/Tretz.

Les **377 anciens groupes de plages identiques ont tous été rapprochés par positions sources**, indépendamment des nouveaux identifiants d’articles : 304 ne sont plus dupliqués et 73 subsistent. Aucun nouveau groupe de plages identiques et aucune nouvelle paire de chevauchement n’apparaissent. Aucun texte ou document n’a été supprimé pour obtenir cette baisse.

Certaines limites connues comme douteuses restent protégées lorsqu’elles proviennent d’un examen antérieur ou d’une décision humaine. Les 16 dossiers ayant des alternatives/conflits conservent leurs preuves. Un cas concerne une ouverture alternative à Châtellerault : **la frontière humaine est inchangée**, avec signalement, sans appliquer cette proposition.

Le rapprochement doit aussi rester sensible au genre : une ouverture « Pouvoirs » de Dijon avait l’identité géographique et l’ordre attendus, mais ne constituait pas le cahier complet. Elle est écartée par les garde-fous de genre. De même, un procès-verbal de noblesse d’Avesnes ne remplace pas une liste des trois ordres. Ces contrôles constituent des tests de régression, pas une validation indépendante du détecteur.

## Vérification humaine ciblée

La file **documentaire**, séparée des anomalies d’articles, contient :

- **144 priorités hautes** : identités non établies, chevauchements, texte intercalé ou contradictions documentaires importantes.
- **183 priorités moyennes** : rapprochements seulement probables, pièces non localisées, ouvertures ou fins plausibles à confirmer.
- **946 priorités basses** : contrôles par échantillonnage et irrégularités sans conséquence démontrée. Ce n’est pas une consigne de lecture systématique de ces 946 dossiers.
- **32 dossiers sans contrôle demandé** : frontières humaines sans nouvelle divergence et annonces d’absence. La frontière humaine avec une alternative reste en priorité haute.

Cela concentre le parcours sur **327 dossiers ciblés**, à commencer par les 144 hauts, plutôt que de parcourir indistinctement les 402 anciens suspects. Ce total inclut des notices sans texte ; les catégories ne sont donc pas les seules frontières suspectes. Les 29 frontières humaines sont conservées. Une nouvelle validation humaine fait autorité sur ces propositions ; le bilan chiffré reste un instantané de génération.

Redémarrer le serveur existant :

```sh
python3 1789/review.py
```

Ouvrir directement [les priorités hautes](http://127.0.0.1:1789/?review_priority=high) ou [moyennes](http://127.0.0.1:1789/?review_priority=medium). Le menu **Contrôle documentaire** filtre les trois niveaux ; « Lot initial de 30 » reste facultatif. Pour un dossier, `/?document=<identifiant du registre>` donne un accès direct sans enregistrer de décision.

Exemples à reprendre : [Albret](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_1_1_1536), [Arles](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1572), [Lessart/Létang-la-Ville](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_2238), [Châtellerault](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_2_1_1692). Pour contrôler une correction appliquée : [Ermont](http://127.0.0.1:1789/?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_4_1_2168).

L’interface affiche la plage corrigée, la priorité et l’explication, et conserve les propositions initiales, les alternatives et les preuves dans les détails. Une ouverture de dossier ne valide rien. Le journal humain reste append-only. Les fichiers `boundary-resolutions.jsonl.gz` et `documentary-review.jsonl.gz` de la génération permettent d’exploiter la file sans manipuler les XML.

## Données, intégrité et reproduction

Le reste des fichiers conserve le format décrit dans [PRODUCTION.md](PRODUCTION.md). La nouvelle génération contient **38 553 articles, 1 222 sections et 41 681 passages techniques**. L’évolution du nombre d’articles résulte des parents réparés/récupérés, **sans modification du segmenteur**. Les 333 articles humains gardent exactement leurs identifiants, textes, plages, numéros et décisions.

Les sources et leurs compléments hors parents sont conservés. L’intégralité du texte décodé de chaque volume reste couverte par l’union des parents et son complément explicite. La diminution du texte cumulé entre parents vient des attributions multiples corrigées, pas d’une suppression du texte source. Les métadonnées des 1 305 notices sont identiques ; les 1 237 anciens parents sont tous encore présents.

```sh
# Nouvelle génération, uniquement si les entrées ont changé ; aucune ancienne version écrasée.
python3 1789/extraction/production.py
# Vérification seule de la génération livrée.
python3 1789/extraction/production.py --verify-only 1789/data/corpus/global-corpus-2-45273d688b59
# Refaire le bilan, sans extraction ni modification des sources/journaux.
python3 1789/extraction/boundary_report.py --before 1789/data/corpus/global-corpus-1-95b58b690be5 --after 1789/data/corpus/global-corpus-2-45273d688b59 --output 1789/data/corpus-comparisons/boundaries-1
```

`current.json` sélectionne la génération active ; la version antérieure reste intacte et son chemin est conservé comme `previous_directory`. Pour revenir en arrière, sélectionner cette ancienne génération dans `current.json` puis redémarrer le serveur, sans toucher aux journaux. Si de nouvelles décisions ont été enregistrées entre-temps, leurs compatibilités sont toujours contrôlées et elles ne sont pas effacées.

Les sources, corpus, comparaisons détaillées et journaux privés restent ignorés par Git. Le petit bilan versionné ne contient ni texte intégral ni journal nominatif. Les anciennes archives restent inchangées. Aucun accès à PostgreSQL, application publique, embedding, index, OCR ou LLM n’a été utilisé.

## Contrôles exécutés

- **47 tests Python réussis**, dont huit tests des corrections : noms coupés typographiquement, faux amis OCR non acceptés, noms sur page partagée, fins avant le cahier suivant, ouverture d’Allauch, refus de confondre une annexe avec un cahier et maintien des décisions humaines/Digne.
- Vérification intégrale de la nouvelle génération : sommes des sorties, textes exacts, offsets, couverture des parents et complément des sources, unicité, métadonnées et rejeu des décisions.
- Comparaison des générations : les 1 305 notices et tous les anciens parents sont conservés ; les **29 frontières humaines et 333 articles humains** sont identiques ; les **deux journaux sont inchangés octet pour octet**. Les 20 entrées de production sont encore conformes à leurs empreintes.
- Aucun nouveau chevauchement ni nouveau groupe de plages identiques. Les 377 anciens groupes ont une disposition explicite dans la comparaison locale.
- Navigateur Chromium : filtres de priorité, accès direct à Ermont, plage XML corrigée visible, consultation sans écriture, clavier, largeurs 320/375/768/1280 et texte à 200 %, sans débordement sur les parcours testés.
- Parcours global sur journaux copiés/temporaires : validation d’un parent, sortie de sa file prioritaire, reconstruction, validation d’un article et rechargement. Aucune validation synthétique dans les journaux réels ; aucune erreur JavaScript relevée. Ruff, syntaxe JavaScript et `git diff --check` conformes.

Le bilan structuré et les résultats synthétiques sont dans [boundary-checks.json](boundary-checks.json). Les dispositions détaillées des 46 paires et 377 groupes sont locales sous `data/corpus-comparisons/boundaries-1/`, sans recopier de journaux privés dans Git. Les contrôles sont des vérifications de source et d’intégrité réalisées par Codex, pas une nouvelle validation humaine indépendante de tous les documents.
