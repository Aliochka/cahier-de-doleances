# Découverte documentaire V2

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
