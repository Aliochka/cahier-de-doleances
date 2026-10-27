# Couverture et désaccords

| Tome | Notices Persée griev | Hypothèses V2 admises | V2 admis sans ancre équivalente |
| --- | --- | --- | --- |
| 1 | 24 | 20 | 1 |
| 2 | 181 | 183 | 23 |
| 3 | 223 | 196 | 14 |
| 4 | 347 | 352 | 18 |
| 5 | 298 | 298 | 19 |
| 6 | 232 | 191 | 17 |

Les 1 954 prédictions V2 ne sont pas 1 954 cahiers : seules 1 240 sont admises comme autonomes/associées par ce détecteur ; les autres sont parties, mentions, incertitudes ou hors corpus. Le registre Persée ne reprend que le type `griev` : ses omissions apparentes peuvent correspondre à une notice d’un autre type. **Ni les 1 305 entrées ni les 1 240 admissions ne sont un décompte vérifié des cahiers de 1789.**

1 229 notices possèdent une ancre primaire retrouvée dans les prédictions V2 (y compris des V2 non admises), 76 n’en ont pas. Cette comparaison n’est pas une précision d’identité. Parmi les 1 229, 27 présentent une plage différente et 66 un désaccord de catégorie au sens de la comparaison technique. 24 notices partagent une ancre primaire avec une autre notice ; 185 commencent sur une page également initiale d’une autre notice. Les pages partagées restent distinctes ; aucun voisin n’est attribué sur ce seul critère.

Les 92 hypothèses V2 admises sans ancre équivalente sont dans `stanford-complement.jsonl`, sans fusion automatique. Le champ `contained_by_proposals` signale seulement une inclusion spatiale dans un dossier proposé. Des hypothèses sans notice peuvent être de vraies pièces manquantes, des doublons, des subdivisions ou de faux positifs ; elles ne deviennent pas 92 nouveaux cahiers. Les 55 V2 `uncertain` sont conservées dans un autre fichier et restent consultables dans la comparaison générale.

## Cas concrets

- **Marolles / Marolles-en-Hurepoix**, IV680 : notices2264 et2265 distinctes, faux rapprochement de la première vers le second cahier. La première correspond à `div3[230]`, le second à `div3[231]`. Une page commune et un bon score ne suffisent pas.
- **Uzent / Vicdessos**, IV285 : Uzent est intégré au bloc `div2[16]/div3[3]/p[129]` ; le résultat automatique désigne le cahier de Vicdessos suivant. Autre faux rapprochement malgré proximité de pages.
- **Riez / Digne**, III339–346 : le résultat vise des demandes particulières du chapitre de Riez dans Digne, puis s’arrête avant le cahier de la chambre ecclésiastique de Riez. Le nom du lieu ne suffit pas à l’identité d’ordre/dossier.
- **Chaumont Vexin**, II730–732 : la noblesse est présente dans la même division que l’annonce d’absence du clergé. Un filtre d’absence mal circonscrit peut supprimer un vrai document.
- **Pouvoirs Saintonge**, V `div2[24]/div3[2]`, et **mémoire Goullin**, VI `div2[17]/div3[28]` : références source repérées dans les zones continues mais non admises automatiquement. Goullin est explicitement annoncé comme pièce jointe par l’article 25 d’Eguilles. À rattacher comme pièce associée, sans fabriquer un deuxième cahier.
- **Avallon/Aunay** et **Artois clergé/noblesse** : anomalies de composition du texte Stanford ; les notices ne réparent pas les colonnes ou les continuations mal placées.

Aucun document n’est déclaré définitivement absent de Stanford sur un échec de l’appariement ; même les 32 abstentions initiales ne sont pas des lacunes prouvées. Les métadonnées apportent un inventaire stable et une distinction entre notices ; la fiabilité des plages doit être construite séparément.
