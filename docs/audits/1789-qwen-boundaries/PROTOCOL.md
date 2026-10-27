# Protocole expérimental

## Données, fenêtres et intégrité

Réutilisation en lecture du registre 1 305 notices, du détecteur V2 et des helpers de provenance du pilote. Stanford : six XML locaux, révision `926fd3cd986a3c3d411e93d1845fff6475cb2602`, empreintes vérifiées. Aucun nouveau corpus Persée, texte ni métadonnée collecté.

Les fenêtres sont établies **par les pages initiale et finale Persée**, avec six blocs complets autour de ces pages, sans utiliser la fin A pour choisir le contexte. Le milieu absent est déclaré avec ses positions et le nombre de blocs omis. Ce sont des fenêtres de frontière, pas des documents intégraux. Chaque bloc conserve texte exact, ID global stable, XPath, positions Unicode, tag, page et provenance de cette page ; les changements `pb` sont transmis. Aucun paragraphe trop long n’est coupé silencieusement. Le modèle refuse un contexte dépassant 24 576 tokens ; aucun dépassement dans la campagne. Les XML entiers sont parsés localement pour les positions, jamais chargés dans le contexte du modèle.

`vN-bXXXXXX` désigne un bloc `head`, `p` ou `note`, ou un marqueur `pb`. Les ID incluent des balises de titre et des paragraphes, pas uniquement des articles. Le texte transmis est le flux exact reconstruit par `Source`, sans correction OCR ni normalisation ; les offsets sont des points de code Unicode dans `itertext`, pas des octets XML. Un saut de page n’est jamais une borne autorisée. Les relations parent–passage/index applicatif restent inchangées.

B reçoit titre, notice, voisins connus et blocs ; **pas la proposition A, ses XPath, scores ou annotations**. C reçoit exactement les mêmes données, plus la proposition A et la visibilité de ses extrémités. Le gabarit est celui du tokenizer Qwen, `enable_thinking=False`. L’égalité des deux contextes hors proposition A est contrôlée automatiquement.

## Développement et gel

24 cas : les 15 erreurs du registre, six contrôles conformes, Chaumont Vexin fausse absence, Artois colonnes intercalées et Eguilles/mémoire Goullin. Ces cas ne sont pas une validation indépendante.

Premiers essais non contraints sur deux cas, soit quatre réponses : trois sorties échouent au contrat d’identifiants. Elles sont conservées dans `pilot-v1-*`, avec le texte du prompt initial. Les instructions sont précisées puis le décodage contraint déjà installé est utilisé. Quatre réponses de ce second essai sont examinées ; la recette finale est conservée pour tout le lot. Aucun nouveau réglage après les lectures de validation. Le prompt n’a pas été optimisé exhaustivement sur les 24 cas : cela limite la conclusion à la recette testée.

`data/freeze.json` enregistre les octets des instructions, adaptateur, runner, préparation, sources de fenêtres et sélection. Une variable locale de lecture a été renommée avant toute lecture des nouvelles références ; ce nettoyage et le gel initial sont archivés. Les instructions, paramètres et sélection n’ont pas changé. Les fichiers de référence ont ensuite été ajoutés au gel **avant toute inférence de validation**.

## Validation nouvelle

36 notices, six par tome, tirage par empreinte déterministe avec alternance de strates simples/complexes fondées sur les statuts existants. Cadre éligible 986 notices. Exclusion des 72 anciens contrôles, 100 notices du registre, sources/feuilles antérieurement examinées, zones continues et références documentaires des pilotes. L’emplacement réel des 36 débuts de référence a également été contrôlé contre ces exclusions : 36 feuilles nouvelles. Aucun candidat difficile remplacé.

La strate « complexe » est un indicateur technique (priorité, ambiguïté ou titre probable), pas un décompte de dossiers réellement composites. Plusieurs cas sont voisins, notamment en tome I : ce n’est pas un échantillon aléatoire représentatif des 1 305 notices, ni 36 observations historiquement indépendantes.

Codex a examiné ouvertures, clôtures et transitions dans les sources, avec les outils `reference_view.py` et inspections ponctuelles. Le milieu omis n’est pas collationné, les fac-similés ne sont pas revérifiés. Les sorties de validation Qwen n’existaient pas encore à la fixation des références. Les anciennes études restent connues ; **ce n’est ni une validation humaine indépendante ni un test aveugle intégral**.

## Politique documentaire et score

La cible est le dossier de la notice : titre propre, corps, signatures, certifications, pièces préliminaires ou annexes explicitement liées et incluses dans son périmètre. Les documents possédant une notice voisine restent séparés. Un en-tête territorial commun ne détermine pas le début du seul cahier. Les notes gardent leur nature éditoriale ; les indications comme « suivent plusieurs signatures » restent conservées dans le dossier.

Une paire est exacte si les deux ID de premier/dernier bloc correspondent à la référence ; fin **inclusive**. L’espace seul autour d’une `div` est neutralisé par projection sur les blocs non vides. Aucun ajustement a posteriori d’un ID voisin n’est accepté. Les erreurs d’un seul titre ou d’une certification comptent aussi ; les exemples distinguent leur gravité des fusions de plusieurs textes.

Sur développement, 21 références de paire exacte ; Castelnaudary a une extrémité nécessaire dans le milieu omis, Riez a une portée/début non certifiée dans ce contexte, Artois mélange des colonnes. Ces trois cas sont conservés pour l’abstention, pas transformés en succès ou erreurs d’exactitude inventées. Deux des 15 anciennes erreurs appartiennent à ces cas non tranchables ; les six contrôles conformes ne sont pas réévalués comme nouvelles preuves.

Les sorties sont vérifiées : JSON sans doublon de clés, IDs présents, absence de `pb` comme borne, ordre source, schéma et abstention cohérente. La grammaire impose les IDs visibles, pas leur sens. Les invalides sont conservées et ne reçoivent pas une frontière de substitution. Le score n’utilise jamais `uncertain` comme preuve de justesse.

## Reproduction

Les grands fichiers sont livrés en gzip sans perte ; `materialize.py` les restaure dans ce dossier après vérification des empreintes. Les poids et sources locales restent à leur emplacement existant, ignorés par Git.

```sh
/usr/bin/python3 docs/audits/1789-qwen-boundaries/materialize.py
/usr/bin/python3 docs/audits/1789-qwen-boundaries/evaluate.py
/usr/bin/python3 docs/audits/1789-qwen-boundaries/test_contract.py
/usr/bin/python3 docs/audits/1789-qwen-boundaries/checks.py
```

Pour réexécuter l’inférence, uniquement GPU libre et dans le même environnement autorisé :

```sh
.venv/bin/python docs/audits/1789-qwen-boundaries/preflight.py
.venv/bin/python docs/audits/1789-qwen-boundaries/run_local.py development
.venv/bin/python docs/audits/1789-qwen-boundaries/run_local.py validation
```

Le runner utilise `bootstrap.py` et les packages judges existants. Il reprend par empreintes entrée/recette et n’écrase pas les sorties ; une sortie invalide n’est pas silencieusement remplacée. Ne pas le relancer pour simplement lire les résultats. Les deux commandes de préparation de référence sont destinées au protocole initial ; `build_references.py` refuse de reconstruire une référence de validation après génération de sorties. Les fenêtres et références fournies permettent de revoir l’expérience sans nouvelle inférence.
