# Diagnostic des corrections réelles

## Journal examiné

Instantané privé de 155 événements (395 689 octets), empreinte dans `data/journal-snapshots.json` :

| Cahier | Notice Persée | Événements | Corrections | Ajouts | Validations | Incertitudes |
|---|---|---:|---:|---:|---:|---:|
| Clergé d’Agen | `arcpa_0000-0000_1879_num_1_1_1529` | 76 | 1 | 1 | 72 | 2 |
| Noblesse d’Agen | `arcpa_0000-0000_1879_num_1_1_1530` | 79 | 10 | 6 | 63 | 0 |

Les 18 opérations de correction/ajout produisent 16 plages distinctes : deux opérations suivantes ne modifient que le numéro d’un article ajouté. Le journal original n’est ni réécrit ni tronqué. Les remarques libres ne sont pas utilisées comme preuve de la cause : une remarque évoque une signature là où le texte montre une rubrique.

## Cas examinés dans la transcription

Positions Unicode globales, intervalles demi-ouverts dans le tome I décodé, et non offsets en octets du XML. Les XPath et correspondances complètes sont dans les résultats locaux.

| Cas | Ancienne plage automatique | Intervention humaine / texte observé | Diagnostic et résultat |
|---|---|---|---|
| Clergé, art. 27 | `[5138392,5138679[` | Fin retenue 5138532 ; suit « demandes et doléances qui intéressent le clergé… » | Rubrique absorbée, pas deux articles fusionnés. Nouvelle fin 5138532. |
| Clergé, art. 6 | absent | `ART. 6.` puis texte dans le paragraphe suivant ; plage humaine `[5140840,5141305[` | Le marqueur seul avait le rôle `section_heading`. Rôle restauré en corps ; proposition `[5140865,5141304[` (blancs périphériques exclus). |
| Noblesse, art. 1/2 | `[5155243,5155961[` | `« 2" D'assurer le retour…`, début 5155532 | Suffixe OCR `"`, entre 1 et 3. Séparation retrouvée. |
| Noblesse, art. 3/4 | `[5155962,5156339[` | Plage humaine `[5155960,5156312[` ; suit `h 4° Que l'intention…` | Attribution du guillemet initial et du `h` OCR avant 4 ; l’ancien segmenteur possédait déjà un article 4. Pas un article supplémentaire retrouvé. L’extension ne reproduit pas cette correction. |
| Noblesse, art. 8, prose et nouveau 1 | `[5157492,5158687[` | 8 finit à 5157753 ; « Et, attendu… », « Nous chargeons… », « Que lesdits États… » ; puis `« t° Qu'à l'avenir…` à 5158416 | Prose de liaison séparée ; `t°` reconnu comme hypothèse de reprise à 1, jamais réécrit ni transformé automatiquement en numéro historique 1. |
| Noblesse, art. 16 | `[5164403,5168583[` | Fin humaine 5164836 ; « Nous enjoignons… », « Nous défendons… », « Notre volonté… » ensuite | Prose de mandat absorbée après la fin d’une citation. Nouvelle fin reproduite ; aucune revendication artificiellement numérotée. |
| Noblesse, art. 9/10 | `[5186122,5187045[` | `10d Nos députés…` à 5186582 | `d` à la place du signe ordinal, entre 9 et 11. Séparation retrouvée. |
| Noblesse, art. 13/14 | `[5188408,5188860[` | `14a Nos députés…` à 5188633 | `a` ordinal dégradé, entre 13 et 15. Séparation retrouvée. |
| Noblesse, art. 7/8 | `[5196149,5198172[` | `8tt Les graviers…` à 5197361 | Marqueur après 7 et avant une rubrique/clôture. Séparation retrouvée. |
| Noblesse, art. 10/11 | `[5204670,5205653[` | `il* Le roi et les États…` à 5205317 | Indice numérique technique 11, corroboré par 10/12 ; aucune substitution dans le texte ou invention de numéro historique. |

Ces corrections démontrent des marqueurs OCR et une erreur de rôle. Elles ne démontrent pas, à elles seules, une fusion due à l’absence d’espace après le numéro. Cette variante est testée séparément sur des exemples synthétiques (`11Nous`, `llQue`, `Art. 2Que`).

## Extension des règles existantes

`segmentation.py` appelle le segmenteur V2 inchangé, puis ajoute des propositions prudentes :

1. Réexaminer les paragraphes classés en rubriques lorsqu’ils ne contiennent qu’un marqueur explicite d’article.
2. Rechercher les marqueurs après ponctuation initiale ou une limite de phrase, en excluant les notes.
3. Pour les ordinaux dégradés et chiffres OCR, exiger des voisins numériques concordants, ou un voisin et une frontière de section ; ne pas transformer l’indice calculé en numéro historique.
4. Considérer séparément les marqueurs collés à leur texte ; vérifier le début de proposition qui suit.
5. Garder comme suspects les marqueurs plausibles insuffisamment étayés.
6. Éviter les montants, dates, références juridiques et listes internes dans un article explicitement numéroté `Art.`.
7. Traiter de façon ciblée les rubriques et reprises de prose effectivement observées à Agen. Ces deux dernières règles sont moins généralisées que la reconnaissance de numéros : aucune efficacité globale n’est revendiquée.

Les nombres présents au milieu d’une phrase ne suffisent pas à déclencher une séparation. Une reprise à 1 ne provoque aucune renumérotation. Les propositions gardent le libellé exact, les positions et les indices observés.
