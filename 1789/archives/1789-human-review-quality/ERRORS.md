# Erreurs et causes documentaires

Chaque correction est rattachée ci-dessous à un incident. Les ajouts et réductions complémentaires ne sont pas comptés comme deux erreurs. Les décisions humaines sont conservées ; l’analyse des causes est celle de Codex.

| Incident | Classe principale | Gravité retenue | Observation dans la source ou les positions |
|---|---|---|---|
| clerge-agen-rubrique | D | structural | Rubrique des demandes particulières du clergé incluse après l’article 27 ; la note humaine évoque une signature mais le texte observé est un titre. |
| clerge-agen-art6 | F | major | ART. 6. est un paragraphe distinct auparavant classé en rubrique ; article ajouté depuis les passages C, pas une fusion avec un autre article. |
| noblesse-agen-1-2 | A | major | Le début « 2" D’assurer… était absorbé dans l’article 1. |
| noblesse-agen-3-4 | C | minor | Déplacement de guillemet et retrait du préfixe OCR h avant 4° ; l’article 4 existait déjà. |
| noblesse-agen-8-1 | A | major | t° après une prose de liaison et une reprise de numérotation ; le nouvel article était inclus dans le précédent. |
| noblesse-agen-16 | F | structural | Après la citation numérotée, Nous enjoignons… et les mandats suivants sont de la prose documentaire/revendicative ; leur assimilation à du simple paratexte ne serait pas justifiée. |
| noblesse-agen-9-10 | A | major | 10d Nos députés… non reconnu ; l’ajout est suivi d’une attribution du numéro 10, sans seconde erreur de limites. |
| noblesse-agen-13-14 | A | major | 14a Nos députés… non reconnu. |
| noblesse-agen-7-8 | A | major | 8tt Les graviers… non reconnu ; la correction ultérieure du numéro porte sur les mêmes limites. |
| noblesse-agen-10-11 | A | major | il* Le roi et les États… entre 10 et 12. |
| terre-franche-11 | E | metadata | i lfl… onzième chef… : article déjà séparé dans le corpus initial ; seul le numéro passe de null à 11, positions inchangées. |
| vic-31-32 | A | major | A:rt. 32. Pour le bien du commerce… absorbé dans 31. |
| mirecourt-prose-2 | F | interpretation | De maintenir les droits… ne porte pas de marqueur 2 visible dans le TEI. Un article 2 est créé par décision humaine. Cette interprétation n’est pas une fusion numérotée démontrée par la seule transcription. |
| mirecourt-4-5 | A | major | 56 Que les lettres de change… est séparé de 4 et numéroté 5 par le lecteur. |
| mirecourt-3-4 | A | major | Le marqueur 4°\Que… existe ; le caractère entre le marqueur et le texte empêche sa reconnaissance. |

## Décompte sans double comptage

- **A — 9 fusions établies** : six dans la noblesse d’Agen, une à Vic, deux dans la noblesse de Mirecourt. Toutes sont associées à un marqueur mal reconnu ou à un caractère inattendu après le numéro.
- **B — 0 séparation incorrecte enregistrée**. Ce constat sur les décisions ne démontre pas une impossibilité de faux découpage.
- **C — 1 petit déplacement** de guillemets/préfixe OCR autour des articles 3/4 d’Agen.
- **D — 1 rubrique absorbée** après l’article 27 du clergé d’Agen.
- **E — 1 modification du seul numéro**, à Terre-Franche, sans changement des limites de l’article 11 déjà présent.
- **F — 3 cas** : l’article 6 classé en rubrique et omis ; une prose de mandat absorbée après l’article 16 ; une unité humaine numérotée 2 créée à partir de « De maintenir… », sans marqueur 2 visible dans le TEI. La dernière ne peut être présentée comme une fusion numérotée démontrée par la seule transcription.

On distingue donc **13 incidents de découpage étayés**, dont dix graves (neuf fusions et une omission), deux autres différences structurelles et un petit déplacement ; s’y ajoutent un numéro seul et un cas interprétatif. Le mandat non numéroté contient de la parole revendicative : le qualifier entièrement de paratexte serait abusif.

## Numérotation et fidélité

Les neuf fusions établies concernent la reconnaissance de marqueurs (`2"`, `t°`, `10d`, `14a`, `8tt`, `il*`, `A:rt. 32.`, `56`, `4°\Que`). Cette famille domine les erreurs graves observées, mais les erreurs de rôle et de prose documentaire subsistent.

Une reprise à 1, un numéro absent ou le saut 14° → 16° ne suffisent pas à démontrer une erreur de découpage. Le lecteur peut accepter les limites sans certifier le numéro imprimé ou les rubriques. Aucune correction OCR n’est appliquée. Les positions exactes et les événements rattachés à chaque incident sont disponibles dans `data/errors.json`, sans reproduction du journal nominatif.
