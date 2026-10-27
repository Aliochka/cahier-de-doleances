# Les 19 différences : diagnostic individuel

Les 19 unités ne sont **pas 19 nouvelles régressions introduites par la V1** : leurs limites échouaient déjà dans l’extraction brute du premier pilote. La comparaison antérieure portait sur ses annotations revues, pas sur ses seules prédictions. Ces 19 références recouvrent 14 prédictions V1 erronées : les fusions affectent plusieurs références.

Recalcul sur les mêmes parents et la même référence : **250/269** limites exactes en V1, **260/269** en V2. **Aucune des 250 précédemment exactes n’est perdue**. Dix des dix-neuf écarts sont résolus; neuf restent non résolus. Les unités et identifiants anciens restent inchangés.

Les coordonnées ci-dessous sont des intervalles semi-ouverts de points de code Unicode dans `itertext()` du XML complet, **pas des octets du fichier XML**. Les XPath, textes et identifiants anciens complets sont dans [les 19 dossiers sources](data/segmentation-differences-19.jsonl). Les diagnostics sont dans [19-diagnoses.jsonl](data/19-diagnoses.jsonl).

| n° | Cahier | Référence initiale `[début,fin)` | V1 brute | Diagnostic sur le TEI | V2 identique à la référence ? | Réexaminer la référence ? |
|---:|---|---|---|---|---|---|
| 1 | alencon-clerge | `[5413730, 5413889]` | `[5413730, 5413926]` | Religion. est un intitulé suivi de nouveaux ordinaux; fin après p9 préférable, rubrique p10 séparée. | Oui | Non |
| 2 | angoumois-noblesse | `[19196, 21901]` | `[19196, 21925]` | Administration. ouvre le groupe suivant; conserver la charte p6–19 dans l’article4 sans absorber p20. Le statut hiérarchique de la charte mérite une relecture, pas un découpage sémantique. | Oui | Oui |
| 3 | ribaucourt | `[1762743, 1763046]` | `[1762743, 1763808]` | Le dixième chef s’arrête àp12; p13 annonce explicitement le onzième, et p14 est un mandat. Ancienne limite mieux étayée. | Non | Non |
| 4 | ribaucourt | `[1763071, 1763588]` | `[1762743, 1763808]` | i lfl n’autorise pas à restaurer un chiffre, mais «onzième chef» et le paragraphe autonome étayent la séparation de p13; mandat p14 hors article. | Non | Non |
| 5 | montigny-ostrevent | `[2030891, 2032644]` | `[2030891, 2033536]` | La V1 absorbe z8 et36 dans le premier article; les paragraphes et repères distincts soutiennent les limites anciennes, sans corriger les chiffres. | Non | Non |
| 6 | montigny-ostrevent | `[2032670, 2033062]` | `[2030891, 2033536]` | z8 ouvre un nouveau paragraphe de doléances; conserver cette étiquette littérale. La fusion avec1° puis36 est moins fidèle à la structure. | Non | Non |
| 7 | montigny-ostrevent | `[2033088, 2033536]` | `[2030891, 2033536]` | 36 ouvre p3; la continuation au début de p4 précède4®. L’ancienne étendue respecte cette continuation sans inventer un numéro. | Non | Non |
| 8 | montigny-ostrevent | `[2033537, 2034106]` | `[2033537, 2034133]` | La virgule initiale du p suivant est absorbée par4® en V1. La convention de propriété du paragraphe favorise l’ancienne fin; la ponctuation historique doit être distinguée. | Oui | Oui |
| 9 | montigny-ostrevent | `[2034132, 2034386]` | `[2034133, 2034386]` | Le p commence par,5®; garder la virgule avec le repère conserve la tranche source. C’est une convention explicite de frontière, pas une correction OCR. | Oui | Oui |
| 10 | montigny-ostrevent | `[2034639, 2034931]` | `[2034639, 2035218]` | La V1 fusionne7® avec B®; les p7 etp8 et leurs amorces distinctes favorisent les anciennes unités. Aucun remplacement de B par8. | Non | Non |
| 11 | montigny-ostrevent | `[2034957, 2035218]` | `[2034639, 2035218]` | B® est conservé littéralement; la frontière de p8 est mieux soutenue que la fusion avec7®. | Non | Non |
| 12 | montigny-ostrevent | `[2035482, 2035819]` | `[2035482, 2036084]` | 10® et Il® sont deux amorces dans deux paragraphes; l’ancienne fin de10® évite d’absorber les collecteurs. | Non | Non |
| 13 | montigny-ostrevent | `[2035845, 2036084]` | `[2035482, 2036084]` | Il® reste une étiquette non restaurée; p10 forme une unité documentaire plus fidèle que sa fusion avec10®. | Non | Non |
| 14 | mirecourt-noblesse | `[10263, 10372]` | `[10263, 10399]` | Le tiret initial du paragraphe suivant est annexé à10° en V1. La convention XML donne l’ancienne fin. | Oui | Oui |
| 15 | mirecourt-noblesse | `[10398, 10841]` | `[10399, 10841]` | -11° doit conserver son préfixe source dans la convention retenue; ne pas le laisser à10°. | Oui | Oui |
| 16 | ferrieres | `[5030860, 5030997]` | `[5030860, 5031024]` | La virgule de p17 est rattachée à13 par V1; préférer l’ancienne fin de p16 selon la propriété du paragraphe. | Oui | Oui |
| 17 | ferrieres | `[5031023, 5031335]` | `[5031025, 5031335]` | Préférer le début de p17 avec sa virgule; la phrase14 se termine incomplètement avant15 dans le TEI. Réexaminer sa complétude et sa portée sur image avant une certitude historique. | Oui | Oui |
| 18 | toul-noblesse | `[44192, 44423]` | `[44192, 44477]` | Dette nationale consolidée. introduit l’article2, pas la fin de1; garder p10–11 puis rubrique séparée. | Oui | Non |
| 19 | toul-noblesse | `[44503, 44643]` | `[44503, 44712]` | Visite des titres des créanciers de l’Etat. introduit le groupe suivant; l’ancienne fin de p13 est mieux étayée. | Oui | Non |


## Pourquoi privilégier ces limites, sans sacraliser l’ancienne référence

Les rubriques « Religion. », « Administration. », « Dette nationale consolidée. » et « Visite des titres des créanciers… » précèdent de nouveaux articles : elles ne prolongent pas la demande précédente. La V2 les distingue par une règle nominale courte, avec garde contre les marqueurs d’article isolés. Cette règle est cependant imparfaite : voir la **nouvelle troncature de Grigny** dans [EVALUATION](EVALUATION.md).

Les virgules de Montigny et Ferrières et le tiret de Mirecourt se trouvent en tête du paragraphe du nouvel article. Les attribuer à celui-ci respecte mieux l’ancrage XML que les rattacher à l’article précédent. C’est une convention documentaire explicite, pas une certitude historique issue d’un fac-similé.

Ribaucourt et Montigny contiennent des marqueurs corrompus (`i lfl`, `z8`, `36`, `B®`, `Il®`). Leur contexte appuie certaines unités distinctes, mais ne justifie pas la restauration automatique d’un chiffre. Les références restent des hypothèses revues dans le TEI, sans correction silencieuse du texte.

Sept lignes appellent une relecture complémentaire : portée de la charte d’Angoumois, conventions de ponctuation, et phrase de Ferrières s’arrêtant sur « se rendre perpétuels, ». Cette dernière peut avoir une frontière physique claire tout en restant textuellement incomplète. Aucune ancienne annotation A n’est rétroactivement modifiée.

## Autres contrôles de développement

Les 48 unités des anciennes fenêtres V1 passent de **46/48 à 48/48** : `ArtIer.` (La Rochelle) et `Àri. er.` (Vernouillet) sont reconnus sans réécriture. Pecqueuse conserve **38 articles**, dont le 37e sur deux paragraphes XML. Ce sont des cas de développement/régression, jamais des preuves de généralisation.

Le détecteur de parents a néanmoins deux régressions sur les trente anciens cahiers : **Anjou clergé** devient incertain et ne regroupe plus ses trois chapitres; **Mirecourt noblesse** est abusivement classé comme pièce associée. La bonne segmentation conditionnelle sur des parents de référence ne masque pas ces échecs de découverte. Voir [development-parent-regressions.jsonl](data/development-parent-regressions.jsonl).
