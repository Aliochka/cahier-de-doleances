# Fusions restant à contrôler

La liste automatique n’est **pas exhaustive**. Une absence d’alerte ne certifie pas la segmentation.

| Cas | Référence et position source | Constat | Conduite recommandée |
|---|---|---|---|
| Mirecourt, noblesse | `arcpa_0000-0000_1879_num_4_1_1745`, tome IV, 12463 ; `/TEI.2/text/body/div1/div2[1]/div3[3]/p[5]` | `56 Que les lettres de change…`. Les voisins candidats sont 3 et 6 ; un `* 4°` intermédiaire n’est pas reconnu par cette extension. `56` est conservé tel quel ; aucune conversion en 5 automatique. | **Fusion potentielle** affichée dans le panneau et comme anomalie de l’article non validé. Examiner 4/5/6 dans la source. |
| Vic, clergé | `arcpa_0000-0000_1879_num_6_1_2497`, tome VI, 157031 ; `/TEI.2/text/body/div1/div2[1]/div3[4]/p[36]` | `A:rt. 32. Pour le bien du commerce…` n’est pas détecté ; fusion avec l’article précédent. Échec découvert dans la validation distincte. | Séparer manuellement au marqueur exact, vérifier les deux limites. Aucun ajustement rétroactif des règles sur ce cas. |
| Terre-Franche / Ribeaucourt | `arcpa_0000-0000_1879_num_3_1_1844`, tome III, 1763071 ; `/TEI.2/text/body/div1/div2[22]/div3[9]/p[13]` | `i lfl IJ ne reste plus pour lq onzième chef…`. Les articles 10/11 étaient séparés dans le corpus initial ; leur séparation n’est pas reproduite par V2 brut ni par l’extension. | **Conserver les deux unités A existantes**, pas de régénération globale. Préfixe OCR complexe à contrôler avant une future version. |
| Agen, noblesse, art. 3/4 | `…_1_1_1530`, tome I, autour de 5156312 | `h 4°` et guillemets : désaccord de ponctuation et de propriété du préfixe. | La correction humaine existante prévaut. Aucun nouvel examen imposé à l’utilisateur. |

## Proposition nouvelle contrôlée après gel

Clergé d’Alençon (`arcpa_0000-0000_1879_num_1_1_1539`) : `5tt Que l'on ne puisse faire aucune dépense…`, position 5417073, entre `4° Demander…` et `6° Prendre…`. La proposition sépare l’ancien `[5416825,5417473[` en `[5416825,5417047[` et `[5417073,5417473[`. La succession est confirmée dans le texte, mais ce contrôle Codex n’est ni une décision humaine, ni une nouvelle évaluation indépendante du mécanisme de sélection des propositions.

`data/suspects.json` contient le suspect produit automatiquement et ses indices. `data/comparison.jsonl.gz` conserve tous les marqueurs reconnus, les propositions, les rôles modifiés et les correspondances d’identifiants. Ces fichiers restent locaux et ignorés par Git.
