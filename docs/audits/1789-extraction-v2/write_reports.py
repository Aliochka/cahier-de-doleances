"""Rapports calculés à partir des sorties gelées; aucune modification des règles."""

from common import HERE, read, rows


def put(name, text):
    (HERE / name).write_text(text.strip() + "\n")


def pct(x):
    return f"{100 * x:.1f} %".replace(".", ",")


def main():
    m = read(HERE / "data/evaluation-metrics.json")
    g = read(HERE / "data/global-comparison.json")
    corpus = read(HERE / "data/corpus-summary.json")
    rr = rows(HERE / "data/19-diagnoses.jsonl")
    table = "| n° | Cahier | Référence initiale `[début,fin)` | V1 brute | Diagnostic sur le TEI | V2 identique à la référence ? | Réexaminer la référence ? |\n|---:|---|---|---|---|---|---|\n"
    for r in rr:
        table += f"| {r['index']} | {r['document_key']} | `{r['original_reference_span']}` | `{r['primary_v1_span']}` | {r['diagnosis']} | {'Oui' if r['v2_matches_original'] else 'Non'} | {'Oui' if r['reference_reexamination_requested'] else 'Non'} |\n"
    put(
        "REGRESSIONS.md",
        f"""# Les 19 différences : diagnostic individuel

Les 19 unités ne sont **pas 19 nouvelles régressions introduites par la V1** : leurs limites échouaient déjà dans l’extraction brute du premier pilote. La comparaison antérieure portait sur ses annotations revues, pas sur ses seules prédictions. Ces 19 références recouvrent 14 prédictions V1 erronées : les fusions affectent plusieurs références.

Recalcul sur les mêmes parents et la même référence : **250/269** limites exactes en V1, **260/269** en V2. **Aucune des 250 précédemment exactes n’est perdue**. Dix des dix-neuf écarts sont résolus; neuf restent non résolus. Les unités et identifiants anciens restent inchangés.

Les coordonnées ci-dessous sont des intervalles semi-ouverts de points de code Unicode dans `itertext()` du XML complet, **pas des octets du fichier XML**. Les XPath, textes et identifiants anciens complets sont dans [les 19 dossiers sources](data/segmentation-differences-19.jsonl). Les diagnostics sont dans [19-diagnoses.jsonl](data/19-diagnoses.jsonl).

{table}

## Pourquoi privilégier ces limites, sans sacraliser l’ancienne référence

Les rubriques « Religion. », « Administration. », « Dette nationale consolidée. » et « Visite des titres des créanciers… » précèdent de nouveaux articles : elles ne prolongent pas la demande précédente. La V2 les distingue par une règle nominale courte, avec garde contre les marqueurs d’article isolés. Cette règle est cependant imparfaite : voir la **nouvelle troncature de Grigny** dans [EVALUATION](EVALUATION.md).

Les virgules de Montigny et Ferrières et le tiret de Mirecourt se trouvent en tête du paragraphe du nouvel article. Les attribuer à celui-ci respecte mieux l’ancrage XML que les rattacher à l’article précédent. C’est une convention documentaire explicite, pas une certitude historique issue d’un fac-similé.

Ribaucourt et Montigny contiennent des marqueurs corrompus (`i lfl`, `z8`, `36`, `B®`, `Il®`). Leur contexte appuie certaines unités distinctes, mais ne justifie pas la restauration automatique d’un chiffre. Les références restent des hypothèses revues dans le TEI, sans correction silencieuse du texte.

Sept lignes appellent une relecture complémentaire : portée de la charte d’Angoumois, conventions de ponctuation, et phrase de Ferrières s’arrêtant sur « se rendre perpétuels, ». Cette dernière peut avoir une frontière physique claire tout en restant textuellement incomplète. Aucune ancienne annotation A n’est rétroactivement modifiée.

## Autres contrôles de développement

Les 48 unités des anciennes fenêtres V1 passent de **46/48 à 48/48** : `ArtIer.` (La Rochelle) et `Àri. er.` (Vernouillet) sont reconnus sans réécriture. Pecqueuse conserve **38 articles**, dont le 37e sur deux paragraphes XML. Ce sont des cas de développement/régression, jamais des preuves de généralisation.

Le détecteur de parents a néanmoins deux régressions sur les trente anciens cahiers : **Anjou clergé** devient incertain et ne regroupe plus ses trois chapitres; **Mirecourt noblesse** est abusivement classé comme pièce associée. La bonne segmentation conditionnelle sur des parents de référence ne masque pas ces échecs de découverte. Voir [development-parent-regressions.jsonl](data/development-parent-regressions.jsonl).
""",
    )
    put(
        "DISCOVERY.md",
        """# Découverte documentaire V2

## Règles et gel

Réutilisation des primitives de provenance du pilote, de `fast_blocks.py` et des conventions V1. Les nouvelles règles sont dans [rules_v2.py](rules_v2.py), le parcours dans [discover_v2.py](discover_v2.py). Leurs empreintes ont été gelées dans [rules-freeze.json](rules-freeze.json) **avant la lecture des nouveaux packs sources et la constitution de leur référence**. Aucune correction de règle après examen du lot nouveau.

Six classes : `autonomous` (cahier autonome), `part` (partie/continuation), `associated` (pièce revendicative associée), `mention`, `out_of_scope`, `uncertain`. Tous les résultats globaux gardent `automatic_not_certified`.

Les règles distinguent les titres, ouvertures, contexte éditorial et débuts internes. La normalisation accents/casse sert uniquement à reconnaître les marqueurs; le texte produit n’est jamais normalisé. Les parties contiguës sont liées au parent précédent sous des conditions explicites. Un titre interne fort peut scinder une division; une rubrique ne doit pas la scinder.

| Problème connu de développement | Traitement V2 observé | Limite |
|---|---|---|
| Cahiers absents à Béziers et Soissons | Formules d’absence élargies, exclusion | D’autres formulations restent possibles |
| Résumés sous Charles VIII/Charles IX | Période et introduction éditoriale, exclusion | Pas une datation historique complète |
| Montargis/Claye : rubriques internes | `part`, pas nouveau parent | Détection nominale encore fragile |
| Armagnac, titre `REMONTRÂCES` | Formule de début élargie, admission | Reconnaissance OCR non exhaustive |
| Dijon, titre `MANDATS` | Admission documentaire | Le sens doit rester contextualisé |
| Saint-Pierre-le-Moutier, titre dans `p` | Lecture des premiers paragraphes sans `head` | Pas de recherche de tous les débuts implicites |
| Bouvignies, doléances dans PV | `associated` si titre et contenu l’appuient | Guérande montre qu’une annonce n’est pas le corps annoncé |
| Arles, pièces professionnelles successives | Séparation de débuts internes et classe associée | Intitulé collectif très court pris pour une pièce : reste suspect |
| Plusieurs cahiers dans une division | Scission sur titre interne fort | Reconnaissance dépendante de formules explicites |

## Échecs nouveaux conservés pour une V3

- **Courtiches**, III, `div2[22]/div3[12]` : « village, corps et communauté » déclenche à tort le motif professionnel. Le cahier territorial devient `associated`. Il reste accessible dans un périmètre inclusif, mais sa classification est fausse.
- **Minimes/place Royale**, VI, `div2[52]/div3[5]` : instructions collectives de 28 articles, mais `uncertain`. Les mots de localité abîmés et l’ouverture font échouer le faisceau d’indices. Le document est manqué par les deux versions.
- **La Rochelle**, III, `div2[35]/div3[4–5]` : instruction particulière parallèle au cahier et pouvoirs. Référence associée; prédictions respectivement incertaine et hors périmètre. Pas deux cahiers à ajouter pour gonfler un rappel.
- **Grasse**, III, `div2[24]/div3[6]` : doléance particulière du théologal signée; V2 incertaine. **Dauphiné**, III, `div2[8]/div3[1]` : pouvoirs substantiels dans des procès-verbaux, également incertains.
- **Anjou clergé**, II, `div2[2]/div3[1–3]` (développement) : la formule « Demandes et doléances » n’appartient plus au motif initial V2. Le parent n’est pas admis, donc ses chapitres ne sont pas rattachés. Régression bloquante, non corrigée après gel.
- **Mirecourt noblesse** (développement) : motif professionnel trop large, même famille d’erreur que Courtiches.
- **Grasse**, III, `div2[24]/div3[3]/p[50]` (diff global exploratoire, hors validation) : « DEMANDES ET DOLÉANCES » commence une pièce distincte non souscrite par les curés, avec signatures propres. L’ancre V1 disparaît du parcours interne V2. La disparition n’est pas un nettoyage réussi.

## Limite du vocabulaire de classes

Le repli V2 `mention/not_a_cahier_start` inclut aussi des listes nominatives ne mentionnant pas de cahier. Ce nom de classe ne signifie donc pas toujours « simple mention textuelle d’un cahier ». Cette imprécision est explicitement conservée dans la V2 gelée; elle doit être corrigée en V3. Les mesures binaires d’admission n’en sont pas changées, mais la classification documentaire à six classes reste imparfaite.

Les annexes restent dans leur dossier et ne sont jamais supprimées. Brue, par exemple, garde ses pièces justificatives après `EXTRAIT` p12; cela ne certifie pas tous leurs rôles. Les doléances dans les PV, extraits, sous-documents professionnels et cahiers collectifs doivent être évalués séparément, sans forcer un statut autonome.
""",
    )
    ct = "| Périmètre | Version | VP | FP | Manqués | Précision locale | Rappel local |\n|---|---|---:|---:|---:|---:|---:|\n"
    for group, label in [
        ("candidates", "24 candidats nouveaux"),
        ("continuous_zones", "12 zones continues"),
    ]:
        for scope, scope_label in [("strict", "autonomes"), ("inclusive", "autonomes + associés")]:
            for ver in ["v1", "v2"]:
                x = m[group][scope][ver]
                ct += f"| {label}, {scope_label} | {ver.upper()} | {x['tp']} | {x['fp']} | {x['fn']} | {pct(x['precision'])} | {pct(x['recall'])} |\n"
    at = "| Version | Références | Bornes toutes deux exactes | Débuts exacts | Fins exactes | Couverture du texte revu par unités exactes |\n|---|---:|---:|---:|---:|---:|\n"
    for ver in ["v1", "v2"]:
        x = m["articles"][ver]
        at += f"| {ver.upper()} | 79 | {x['exact']} ({pct(x['exact_proportion'])}) | {x['correct_starts']} | {x['correct_ends']} | {pct(x['coverage_on_reviewed_text'])} |\n"
    put(
        "EVALUATION.md",
        f"""# Évaluation V1/V2

## Protocole effectivement suivi

1. Enregistrement de [24 candidats et 12 zones](validation-plan.json) avant finalisation des règles. Exclusion conservatrice des divisions des 30 parents du pilote, des 170 candidats sélectionnés en V1, des anciennes fenêtres négatives et de Pecqueuse.
2. Finalisation sur le développement seulement puis [gel des règles](rules-freeze.json).
3. Lecture des packs **sources seuls**, sans classements V2 nouveaux. Chaque zone comprend deux divisions feuilles consécutives complètes, soit 24 divisions sources, y compris listes nominatives et règlements sans cahier. Les 12 zones ont été lues intégralement. Pour les candidats séparés : titre, ouverture, courtes rubriques, clôture et contexte voisin, **pas collation intégrale de tous les longs corps**.
4. Création de [références déclaratives](annotate_reference.py), puis [gel des références](reference-freeze.json), avant prédictions nouvelles.
5. Comparaison aux hypothèses V1 archivées sur l’ensemble des six volumes, puis aux prédictions V2 gelées. Les seuils et règles n’ont pas été ajustés sur les erreurs nouvelles.

Un défaut de nouveauté a été découvert pendant la lecture source : Albret absent appartenait déjà aux cas négatifs du premier pilote. Il est conservé comme témoin connu et **exclu des performances nouvelles**. Une réserve déterministe supplémentaire est enregistrée dans [novelty-amendment.json](novelty-amendment.json). Aucun autre candidat nouveau éligible du même cadre ne restait au volume I : réserve prise au volume II, par empreinte et sans prédiction. Au total : **25 candidats enregistrés, dont 24 réellement nouveaux**, répartis sur les six volumes (3, 5, 4, 4, 4, 4). Les douze zones n’ont pas changé. L’enregistrement initial est conservé, pas réécrit.

La sélection par empreinte est indépendante des prédictions, mais stratifiée à partir d’indices lexicaux bruts, de la longueur et du volume : **pas un échantillon représentatif de tous les cahiers**. Les strates ont un repli quand elles sont vides; les étiquettes `strong_long` ne garantissent donc pas un long texte au volume I. Les candidats connus ne servent pas à annoncer la généralisation.

La référence est établie par Codex : séparation procédurale du développement, **pas validation humaine indépendante, ni test aveugle indépendant**. Pas de nouvelle vérification des fac-similés : les résultats portent sur la transcription XML et son organisation, pas sur l’exactitude de l’OCR par rapport à l’imprimé.

## Découverte

{ct}

Dans les 24 candidats, la référence comporte 15 cahiers autonomes, 3 pièces associées et 6 cas négatifs/parties. La V1 ne distingue pas les pièces associées : Grasse était un faux autonome. La V2 évite cet autonome abusif mais classe Courtiches comme associé, perdant un vrai autonome. Le gain de précision est donc **conditionnel à ce petit lot et accompagné d’une baisse de rappel strict**. Dans le périmètre inclusif, aucun gain net n’est démontré.

Les zones continues contiennent 13 débuts de cahiers autonomes et 2 débuts de pièces associées. Cinq zones n’ont aucun nouveau début (dont une continuation de cahier). Les deux versions trouvent 12/13 autonomes et 12/15 documents inclusifs, sans faux positif dans ces zones. Ce rappel est **exhaustif pour les débuts recensés dans ces seules zones**, jamais un rappel global des six volumes. Les instructions des Minimes et les deux pièces de La Rochelle restent manquées.

Pour les 12 autonomes retrouvés dans les zones, **12 débuts et 12 fins sont exacts dans les deux versions**; aucune fusion ou troncature parentale supplémentaire n’y est observée. Cela n’inclut pas les parents manqués et ne démontre aucun gain sur les fins. Les fins des longs candidats séparés ne sont pas certifiées et ne figurent pas dans ce dénominateur. Les sous-classes `associated/part/out_of_scope` ont des erreurs même lorsque la décision binaire d’admission est correcte.

## Articles sur les documents nouveaux

79 unités de référence ont été délimitées par lecture du XML, sur treize parents des zones continues. Les fenêtres couvrent débuts ordinaux, marqueurs corrompus, articles sur plusieurs `p`, plusieurs articles dans un `p`, changement de page, note et clôture. Elles sont choisies pour varier les structures, pas pour mesurer un taux représentatif de tous les articles.

{at}

Cette comparaison utilise les **mêmes parents de référence** pour isoler le segmenteur : c’est une mesure conditionnelle, **pas la performance de bout en bout du détecteur**. Les instructions des Minimes sont segmentées dans ce contrôle alors que le détecteur n’en admet pas le parent. Le fichier [article-boundary-comparison.jsonl](data/article-boundary-comparison.jsonl) permet de retrouver chaque décision et chaque prédiction.

La V2 gagne les articles 13 et 14 des Enfants Rouges par affectation du tiret au bon article, mais **perd l’article 2 de Grigny** : « Cela fait bien du tort pour la deuxième coupe. » est pris pour une rubrique et détaché de l’article. Bilan net : +1 unité exacte, avec une vraie régression nouvelle. Les neuf écarts de développement résiduels ne sont pas ces dix erreurs nouvelles : ce sont des périmètres distincts.

Parmi les dix références non exactes V2 : 5 débuts manquent; 7 ont au moins une prédiction débordante et 2 une prédiction tronquée. Ces catégories se recouvrent et leur somme n’est pas un nombre d’articles. Le fichier conserve les recouvrements, plutôt qu’une attribution forcée à une cause unique. Les faux débuts en dehors des fenêtres ne sont pas tous annotés : **aucune précision globale des propositions d’articles n’est annoncée**.

## Difficultés concrètes

| Cas | Structure source observée | Résultat / cause |
|---|---|---|
| Grigny, IV `div2[18]/div3[175]/p[5–6]` | Article 2 suivi de « Cela fait… » | V1 exact, V2 tronqué : règle nominale trop permissive |
| Saint-Nom, V `div2[1]/div3[68]/p[7]` | `Ar . 6.` | Marqueur non reconnu; fusion avec art5 |
| Sainte-Aulde, V `div2[1]/div3[54]/p[17]` | `Ar.t. 12.` | Marqueur non reconnu; art12 manqué |
| Minimes, VI `div2[52]/div3[5]/p[14]` | `Ant, 17.` | Marqueur OCR non reconnu |
| Avesnes régulier, II `div2[12]/div3[2]/p[4–5]` | Le paragraphe suivant réclame la pragmatique sanction, sans numéro visible | Fusion de deux propositions documentaires; la référence ne rétablit aucun chiffre manquant |
| Enfants Rouges, VI `div2[52]/div3[4]/p[36]` | Clôture OCR `Glos et arrêté` | Clôture absorbée par art40 |
| Saint-Ouen, V `div2[1]/div3[69]/p[2]` | `Arl. 1er.` | Début manqué |
| Avesnes séculier, II `div2[12]/div3[1]/p[10–13]` | Art9 interrompu par une note, son fragment `Archives de l Empire.` dans un `p` | Bornes exactes ne garantissent pas la pureté du texte de lecture |
| Saint-Prix et Saint-Nom | Notes éditoriales à l’intérieur de paragraphes ordinaires | Fidélité au TEI conservée, séparation éditoriale non certifiée |

La qualification de p5 d’Avesnes comme proposition séparée est appuyée par son contenu distinct mais sa numérotation manque. Elle reste une difficulté documentaire, pas la preuve d’un article « 5 » historiquement certifié.

## Après référence et effort observé

Les 79 références initiales ont été examinées; une réserve documentaire explicite abaisse ensuite à 78 le nombre exporté en A, sans modifier la référence gelée ni les résultats primaires : voir [reference-review-notes.jsonl](data/reference-review-notes.jsonl). La fin de l’article4 d’Avesnes régulier reste incertaine car p5 n’a pas de marqueur; on ne fabrique donc pas un article5. La sensibilité sur les 78 références sans cette réserve donne V1 68/78 et V2 69/78. Sur la référence initiale, **69/79** correspondent aux propositions V2 initiales. Les 10 autres (dont une limite ensuite réservée) ne sont pas silencieusement remplacées dans les prédictions. L’export de référence, avec 78 A et une réserve maintenue en contexte, représente les décisions revues, pas une amélioration automatique après correction. A signifie « bornes examinées dans le TEI par Codex », pas preuve historique indépendante ni transcription débarrassée de ses notes/OCR.

Journal : [review-log.jsonl](data/review-log.jsonl). 19 écarts anciens examinés individuellement; 25 candidats source dont un connu exclu; 12 zones complètes; 79 unités revues (ces périmètres se recouvrent). 0 intervention humaine indépendante; **temps humain de validation non mesuré**. Aucune durée humaine n’est déduite des temps de calcul. La génération/comparaison nouvelle a pris {m["seconds"]:.2f} s sur cet environnement; le balayage global {read(HERE / "data/v2-discovery-summary.json")["seconds"]:.2f} s. Ce sont des mesures locales de calcul, pas le coût documentaire récurrent. Les dates des gels ne sont pas des chronomètres de lecture.

Les fautes constatées après gel deviennent des pistes V3, sans réécriture de l’expérience V2. Aucun intervalle de confiance, précision globale ou projection de productivité humaine n’est justifié par ce lot.
""",
    )
    gt = "| Volume | V1 admis | V2 autonomes | V2 associés |\n|---|---:|---:|---:|\n"
    for v, x in g["by_volume"].items():
        gt += f"| {v} | {x['v1']} | {x['v2_autonomous']} | {x['v2_associated']} |\n"
    put(
        "GENERALIZATION.md",
        f"""# Balayage des six volumes et décision

**Ne pas lancer encore une extraction systématique en considérant ses parents comme fiables.** Le balayage expérimental des six volumes a été réalisé et archivé; il révèle des problèmes bloquants pour une extraction systématique de contenu retenu. Continuer un inventaire non certifié reste possible, mais n’apporte pas la garantie documentaire recherchée.

## Diff global réel

La V1 recensait 4 448 signaux, dont 1 278 hypothèses admises. La V2 classe 1 954 ancres : 1 197 autonomes, 43 associées, 174 parties, 121 hors périmètre, 55 incertaines et 364 replis `mention`. **Les deux inventaires n’ont pas le même cadre** : V2 classe toutes les divisions feuilles et certains titres internes, V1 conservait aussi de nombreuses mentions courantes. 1 954 contre 4 448 ne mesure ni précision ni rappel.

{gt}

Sur les 1 278 ancres précédemment admises : 1 166 deviennent autonomes, 13 associées, 40 parties, 31 hors périmètre, 25 incertaines, 1 repli `mention`; 2 ne sont plus proposées. Il y a 61 nouvelles ancres admises par rapport à la V1. Aucun de ces ajouts n’est automatiquement validé.

1 276 identifiants d’ancres communs sont conservés; 58 intervalles associés à une ancienne ancre changent. Six pièces admises sont rattachées à un autre dossier : **1 234 hypothèses non rattachées**, contre 1 240 admissions en comptant ces six pièces. Ce ne sont pas 1 234 cahiers certifiés.

Les [diffs complets](data/v1-v2-document-diff.jsonl), [classifications](data/v2-document-predictions.jsonl) et [anomalies](data/global-anomalies.jsonl) sont conservés. 26 alertes : 24 racines scindées et 2 admissions très courtes, dont l’intitulé collectif du dossier d’Arles. Une alerte demande un contrôle; elle n’est pas une erreur certifiée en elle-même.

## Changements suspects effectivement examinés

- **Grasse**, III, `div2[24]/div3[3]/p[50]` : « DEMANDES ET DOLÉANCES / Du clergé de Grasse et de Vence, auxquelles les curés… n’ont pas souscrit », suivi de deux demandes et de signatures. Disparition d’une pièce réellement distincte : manque de reconnaissance de cette formule.
- **Montargis**, IV, `div2[2]/div3[1]/p[54]`, « :Doléances pour te peuple. » : disparition d’une rubrique auparavant surinterprétée, cohérente avec le diagnostic de développement. La perte d’une ancre n’est donc pas toujours un document manqué.
- **Anjou clergé** : régression de classification et de rattachement des chapitres II–III. **Mirecourt noblesse** : confusion entre corps nobiliaire et corps professionnel.
- Sur les trente anciens parents, **28 intervalles V2 sont strictement identiques**. Pour Beaurecueil, les 26 caractères supplémentaires sont uniquement du blanc de mise en forme : pas une nouvelle pièce absorbée. Pour Anjou clergé, la différence est documentaire et grave. Égalité d’intervalle et bonne classe sont deux contrôles différents.

Ces contrôles globaux sont exploratoires, effectués après l’évaluation; ils ne sont pas ajoutés au dénominateur du test nouveau.

## Ce qui peut être conservé

Provenance, empreintes, intervalles Unicode et XPath; parents complets; classement séparé des pièces associées; exclusion des absences explicites et des récits hors 1789; mécanisme de référence figée; priorité aux marqueurs documentaires plutôt qu’à une segmentation sémantique. Pecqueuse confirme le traitement multi-paragraphe sans équivalence article=`p`.

## Prochaine itération prioritaire, sans la commencer ici

1. **V3 sur les cas désormais de développement** : reconnaître « Demandes et doléances »; restreindre les motifs professionnels; distinguer liste/mention/hors périmètre; préserver les continuations. Ajouter aux contrôles de parents Anjou, Mirecourt, Courtiches, Grasse et Minimes.
2. Retirer ou fortement contraindre la détection nominale des rubriques qui tronque Grigny; traiter explicitement clôtures et marqueurs OCR raisonnablement déterministes. Ne pas rétablir automatiquement les chiffres illisibles de Montigny.
3. Geler V3 puis sélectionner un nouveau lot **encore inédit**, avec zones continues et contrôle de notes/signatures. Ne pas recycler le lot V2 comme preuve de généralisation V3.
4. Faire relire une partie de la référence et des fac-similés par un lecteur indépendant, chronométrer son travail. Puis envisager un lot d’extraction plus grand **avec quarantaine**, jamais une publication automatique.

Les cahiers sans titre canonique, les dossiers composites, PV, pouvoirs, suppléments, numérotations OCR dégradées, notes en paragraphes ordinaires et changements de sections restent soumis à contrôle. Aucune estimation de milliers de documents fiables ou de journées humaines n’est fondée à ce stade.
""",
    )
    put(
        "README.md",
        f"""# Fiabilisation de l’extraction des cahiers de 1789 — V2

**Conclusion : des progrès de segmentation, mais pas encore un détecteur assez fiable pour lancer une extraction systématique expérimentale de parents retenus sans corrections bloquantes.** La V2 a été exécutée et évaluée, puis balayée sur les six volumes. Les prédictions initiales et les échecs sont conservés.

## Résultats principaux

| Contrôle | V1 | V2 | Portée |
|---|---:|---:|---|
| Unités A du premier pilote reproduites exactement | 250/269 | 260/269 | Développement; aucune perte parmi les 250 |
| Anciennes fenêtres de 48 articles | 46/48 | 48/48 | Développement |
| Pecqueuse | 38 articles | 38 articles | Régression; article37 sur deux paragraphes |
| 24 nouveaux candidats, précision des autonomes | 15/16 | 14/14 | Gain de précision local, mais un autonome perdu |
| 24 nouveaux candidats, rappel des autonomes | 15/15 | 14/15 | Courtiches mal classé comme associé |
| 12 nouvelles zones, rappel des autonomes | 12/13 | 12/13 | Aucun gain de découverte démontré |
| 79 nouvelles unités, limites exactes | 68/79 | 69/79 | Parents de référence; +2 unités, −1 régression |

Les 19 écarts anciens étaient déjà présents dans l’extracteur brut du premier pilote : **10 résolus, 9 persistants**, sans changement des anciennes annotations. Sept références méritent une relecture complémentaire. Les chiffres nouveaux proviennent d’une lecture Codex du XML; **pas d’une validation humaine indépendante** ni d’une collation complète des imprimés.

Le balayage global produit **1 197 hypothèses autonomes et 43 associées**. Leur nombre ne prouve aucune amélioration de qualité. Il montre notamment une régression sur Anjou clergé et Mirecourt noblesse, et une pièce manquée à Grasse. Les difficultés nouvelles ne sont pas corrigées après gel afin de préserver l’évaluation.

## Documents et données

- [REGRESSIONS.md](REGRESSIONS.md) : tableau des 19 écarts, diagnostics et références à réexaminer.
- [DISCOVERY.md](DISCOVERY.md) : règles, corrections connues, erreurs nouvelles, six classes et leurs limites.
- [EVALUATION.md](EVALUATION.md) : sélection, gels, référence source, mesures comparables, galerie des erreurs et effort réellement observé.
- [GENERALIZATION.md](GENERALIZATION.md) : exécution six volumes, changements suspects, contrôles et prochaine étape.
- [data/](data/) : inventaires V1/V2, nouvelles annotations, prédictions, comparaisons détaillées, journal et contrôles.

L’export local de référence contient **{corpus["parents"]} parents**, **{corpus["reviewed_A"]} unités A**, **{corpus["B_proposals"]} propositions B** et **{corpus["uncovered_C"]} plages C**. A : bornes examinées dans le TEI par Codex. B : proposition non certifiée. C : texte hors fenêtres d’articles revues, incluant potentiellement des articles non revus, titres, notes et signatures. **Les B ne forment pas une partition avec A/C** : ils sont un jeu de propositions distinct. Les textes sources complets restent dans les parents; aucune correction OCR ou modernisation.

`corpus-A.jsonl` exclut une référence documentaire ambiguë conservée dans [les réserves explicites](data/reference-review-notes.jsonl), sans modifier les 79 références initialement gelées. C’est un export des décisions sources, distinct des 69 correspondances automatiques V2 exactes. Les identifiants de voisins de cet export désignent les **voisins parmi les unités revues**, pas nécessairement les articles consécutifs du cahier. Les positions permettent de retrouver aussi les passages intermédiaires non revus. Les trente anciens parents et leurs identifiants restent référencés dans [la table de correspondance](data/legacy-document-crosswalk.jsonl), sans remplacement silencieux.

## Sources et isolation

Six XML Stanford, révision `926fd3cd986a3c3d411e93d1845fff6475cb2602`, vérifiés contre les empreintes de l’audit antérieur. L’ancien cache temporaire était absent après l’arrêt de la machine, ce qui est compatible avec un nettoyage de `/tmp` au redémarrage. **La restauration des six fichiers figés a été expressément autorisée**; ils résident désormais dans `.cache/sources/`, ignoré par Git. Aucun autre corpus téléchargé, aucune collecte Persée, aucun embedding.

Les intervalles sont des points de code Unicode dans le texte XML décodé, semi-ouverts `[début,fin)`, avec XPath et lignes XML, pages et liens Stanford. Ce ne sont pas des offsets d’octets XML. Les erreurs OCR, blancs et ponctuation sont préservés. Les notes XML sont traçables séparément; les notes dans des paragraphes ordinaires peuvent encore contaminer une unité aux bornes exactes.

Aucune modification applicative, PostgreSQL, index, route ou déploiement. Les 370 fichiers des audits antérieurs suivis par empreinte restent inchangés. [checks.json](data/checks.json) contient les contrôles effectivement exécutés, y compris fidélité des textes, gels, ordre et reconstruction.

## Reproduction

Exécuter depuis la racine du dépôt avec `/usr/bin/python3` (Python 3.10.12, lxml4.8.0 installé localement). Aucun environnement applicatif ou PostgreSQL nécessaire.

```sh
/usr/bin/python3 docs/audits/1789-extraction-v2/evaluate.py
/usr/bin/python3 docs/audits/1789-extraction-v2/discover_v2.py
/usr/bin/python3 docs/audits/1789-extraction-v2/analyze_global.py
/usr/bin/python3 docs/audits/1789-extraction-v2/check_development_extra.py
/usr/bin/python3 docs/audits/1789-extraction-v2/review_notes.py
/usr/bin/python3 docs/audits/1789-extraction-v2/export_verified.py
/usr/bin/python3 docs/audits/1789-extraction-v2/checks.py
```

Ruff a été exécuté sur les scripts avec exceptions explicites de style pour `annotate_reference.py` (référence gelée) et de variable inutilisée pour `rules_v2.py` (règle gelée), afin de conserver exactement leurs empreintes. La syntaxe Python et les contrôles documentaires passent. Aucun build applicatif n’est requis pour ces fichiers d’audit.

Les mesures de temps peuvent changer; les coordonnées, textes, identifiants, jugements et comptes doivent rester identiques. Les sources vérifiées sont déjà présentes dans le cache persistant local. Après perte du cache, `restore_sources.py` permet la restauration des **six mêmes fichiers** sous réseau autorisé; aucune récupération n’est nécessaire pour lire les résultats archivés.

`review_notes.py` conserve une réserve documentaire et son analyse de sensibilité (78 références sans cette réserve), sans retoucher les résultats primaires sur 79.

Ne pas relancer les scripts de **création** des gels, plans, amendement ou références en écrasant leurs sorties. Ils gardent leurs assertions anti-écrasement. `annotate_reference.py` enregistre des décisions de lecture explicites, pas une référence fabriquée à partir des prédictions. Les scripts V1 et du pilote sont des dépendances lues, empreintes conservées; ils ne sont pas modifiés.

## Réponses aux dix questions

1. **19 différences :** dix corrigées en V2, neuf persistantes. Aucune n’était nouvelle par rapport au premier extracteur brut; sept anciennes références méritent encore une relecture.
2. **Erreurs corrigées :** absences explicites, résumés hors 1789, rubriques abusives; récupération de titres en paragraphes, Mandats et remontrances OCR de cas connus. Les PV revendicatifs sont distingués partiellement.
3. **Erreurs restantes :** formules de début non couvertes, motifs professionnels trop larges, instructions ambiguës, notes et clôtures OCR, numéros dégradés, portée des pièces associées.
4. **Précision V2 :** meilleure sur les 24 candidats autonomes de ce lot (14/14 contre 15/16), avec rappel strict inférieur; aucun gain généralisable établi.
5. **Rappel :** pas amélioré dans les zones nouvelles (12/13 autonomes pour les deux versions); régressions de classification présentes.
6. **Frontières :** 12/12 parents retrouvés exacts dans les zones pour les deux versions; pas de progrès démontré, et Anjou est une régression bloquante hors test nouveau.
7. **Articles :** progrès sur le développement et net +1 sur 79 nouveaux, **avec une nouvelle troncature à Grigny**. L’absence de perte sur 269 ne suffisait pas.
8. **Traitement systématique :** balayage non certifié effectué; ne pas lancer l’extraction systématique de parents réputés fiables avant V3.
9. **Contrôles indispensables :** dates/genre, existence du corps, titres internes, rattachements/annexes, signatures/notes, numéros OCR et conservation du texte; contrôles des zones non détectées et relecture indépendante.
10. **Prochaine étape :** V3 limitée aux défauts observés, gel puis nouvel échantillon inédit et relecture indépendante chronométrée, avant toute intégration applicative.
""",
    )


if __name__ == "__main__":
    main()
